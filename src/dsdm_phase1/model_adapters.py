"""Goal028 deterministic model adapters and feature-bound serialization.

The adapters deliberately expose a small protocol shared by conventional
scikit-learn/pyGAM estimators and native PyTorch models.  They are target-only:
the caller supplies already materialised :class:`FeatureBatch` objects and no
adapter accepts assessment data during fitting.
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import copy
import hashlib
import importlib.metadata
import json
import pickle
import random
import re
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np

from .modeling_contract import FeatureBatch, ModelingContractError, canonical_json

try:  # imports are kept local-friendly for contract-only environments
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from pygam import LogisticGAM, l, s, te
except Exception:  # pragma: no cover - dependency contract catches this
    HistGradientBoostingClassifier = RandomForestClassifier = LogisticRegression = None
    ConvergenceWarning = RuntimeWarning
    LogisticGAM = l = s = te = None

import torch
from torch import nn


class ModelAdapterError(ModelingContractError):
    """Raised for invalid candidates, fitting failures, or unsafe replay."""


@dataclass(frozen=True)
class FitReport:
    converged: bool
    iterations: int
    best_epoch: int | None
    stopping_fold: str | None
    neural_stop_status: str | None
    warnings: tuple[str, ...]
    runtime_seconds: float
    peak_rss_bytes: int
    initial_state_digest: str | None = None


class FittedAdapter(Protocol):
    def predict_scores(self, batch: FeatureBatch) -> np.ndarray: ...
    def serialize(self, path: Path) -> Mapping[str, Any]: ...


class ModelAdapter(Protocol):
    family: str

    def fit(
        self,
        train: FeatureBatch,
        stopping: FeatureBatch | None,
        candidate: Mapping[str, Any],
        seed: int,
        exact_epochs: int | None = None,
    ) -> tuple[FittedAdapter, FitReport]: ...


FAMILIES = {
    "intercept",
    "elastic_net",
    "gam",
    "random_forest",
    "hist_gradient_boosting",
    "shallow_ann",
    "residual_mlp",
}


def _canonical_registry() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {"null00": {"family": "intercept", "id": "null00", "positive_fraction": "empirical_inner_training_clipped_1e-7"}}
    for i, (c, l1) in enumerate(((.01, 0), (.03, 0), (.1, 0), (.03, .5), (.1, .5), (.3, .5), (.03, 1), (.1, 1), (.3, 1), (1, .5))): out[f"enet{i:02d}"] = {"family":"elastic_net","id":f"enet{i:02d}","C":c,"l1_ratio":l1,"solver":"saga","max_iter":5000,"tol":1e-6}
    for i, (n, lam) in enumerate(((6,.1),(6,1),(8,1),(8,10),(12,10))): out[f"gam{i:02d}"] = {"family":"gam","id":f"gam{i:02d}","n_splines":n,"lam":lam,"max_iter":500,"tol":1e-5}
    rf = (("sqrt",1,None),("sqrt",3,None),("sqrt",10,None),(.33,3,None),(.33,10,None),(.67,3,20),(.67,10,20))
    for i, (mf, leaf, depth) in enumerate(rf): out[f"rf{i:02d}"] = {"family":"random_forest","id":f"rf{i:02d}","n_estimators":500,"bootstrap":True,"max_features":mf,"min_samples_leaf":leaf,"max_depth":depth}
    hgb = ((.03,15,20,0),(.03,31,20,1),(.05,15,20,1),(.05,31,20,1),(.05,31,50,1),(.1,15,20,10),(.1,31,50,10))
    for i, (lr, leaf, minimum, l2) in enumerate(hgb): out[f"hgb{i:02d}"] = {"family":"hist_gradient_boosting","id":f"hgb{i:02d}","max_iter":300,"early_stopping":False,"learning_rate":lr,"max_leaf_nodes":leaf,"min_samples_leaf":minimum,"l2_regularization":l2}
    ann = ((32,0,0,1e-3),(32,.1,1e-5,1e-3),(64,.1,1e-5,1e-3),(64,.2,1e-4,1e-3),(128,.2,1e-4,5e-4),(128,.3,1e-3,5e-4))
    for i, (w, d, wd, lr) in enumerate(ann): out[f"ann{i:02d}"] = {"family":"shallow_ann","id":f"ann{i:02d}","width":w,"dropout":d,"weight_decay":wd,"lr":lr,"max_epochs":300,"patience":30}
    res = ((2,64,32,.1,1e-5,1e-3),(3,128,32,.2,1e-4,5e-4),(4,128,64,.3,1e-3,5e-4))
    for i, (blocks,w,b,d,wd,lr) in enumerate(res): out[f"resmlp{i:02d}"] = {"family":"residual_mlp","id":f"resmlp{i:02d}","blocks":blocks,"width":w,"bottleneck":b,"dropout":d,"weight_decay":wd,"lr":lr,"activation":"GELU","norm":"LayerNorm","max_epochs":300,"patience":30}
    return out


# Goal029 prospectively adds a conservative pyGAM recovery panel. The original
# gam00-gam04 payloads remain unchanged for Goal028 replay; only Goal029's
# independently content-bound config authorizes these additional identifiers.
GOAL029_GAM_CANDIDATES = {
    f"gamr{index:02d}": {
        "family": "gam",
        "id": f"gamr{index:02d}",
        "n_splines": n_splines,
        "lam": lam,
        "max_iter": 500,
        "tol": 1e-5,
    }
    for index, (n_splines, lam) in enumerate(
        ((4, 10), (4, 100), (4, 1000), (6, 10), (6, 100), (6, 1000))
    )
}
_BASE_CANONICAL_CANDIDATES = _canonical_registry()
_GOAL029_AUTHORITY = contextvars.ContextVar(
    "dsdm_goal029_candidate_authority", default=False
)


class _CanonicalCandidateRegistry(Mapping[str, Mapping[str, Any]]):
    def _active(self) -> Mapping[str, Mapping[str, Any]]:
        if _GOAL029_AUTHORITY.get():
            return {**_BASE_CANONICAL_CANDIDATES, **GOAL029_GAM_CANDIDATES}
        return _BASE_CANONICAL_CANDIDATES

    def __getitem__(self, key: str) -> Mapping[str, Any]:
        return self._active()[key]

    def __iter__(self):
        return iter(self._active())

    def __len__(self) -> int:
        return len(self._active())


CANONICAL_CANDIDATES = _CanonicalCandidateRegistry()


@contextlib.contextmanager
def goal029_candidate_authority(
    candidate_payloads: Mapping[str, Mapping[str, Any]],
):
    """Explicitly authorize the exact Goal029-only GAM registry in this context."""
    if dict(candidate_payloads) != GOAL029_GAM_CANDIDATES:
        raise ModelAdapterError("goal029_candidate_authority_mismatch")
    token = _GOAL029_AUTHORITY.set(True)
    try:
        yield
    finally:
        _GOAL029_AUTHORITY.reset(token)


def _candidate_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, Mapping) or type(candidate.get("id")) is not str or not candidate["id"]:
        raise ModelAdapterError("candidate_invalid")
    return {str(k): candidate[k] for k in candidate}


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _runtime_versions() -> dict[str, str]:
    names = {"python": sys.version.split()[0], "numpy": "numpy", "scipy": "scipy", "sklearn": "scikit-learn", "pygam": "pygam", "torch": "torch"}
    out: dict[str, str] = {}
    for key, package in names.items():
        if key == "python": out[key] = package
        else:
            try: out[key] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError: out[key] = "unknown"
    return out


def _initial_state_digest(model: nn.Module) -> str:
    named = []
    for name, tensor in model.state_dict().items():
        arr = tensor.detach().cpu().contiguous().numpy()
        named.append({"name": name, "shape": list(arr.shape), "dtype": str(arr.dtype), "sha256": hashlib.sha256(arr.tobytes()).hexdigest()})
    return _digest(named)


def validate_candidate(family: str, candidate: Mapping[str, Any]) -> None:
    """Reject missing, extra, or drifted candidate fields before construction."""
    if family not in FAMILIES:
        raise ModelAdapterError("unknown_model_family")
    c = _candidate_payload(candidate)
    canonical = CANONICAL_CANDIDATES.get(c.get("id"))
    if canonical is None or canonical != c or canonical.get("family") != family:
        raise ModelAdapterError("candidate_registry_mismatch")
    if c.get("family") != family:
        raise ModelAdapterError("candidate_family_mismatch")
    expected: dict[str, set[str]] = {
        "intercept": {"family", "id", "positive_fraction"},
        "elastic_net": {"family", "id", "C", "l1_ratio", "solver", "max_iter", "tol"},
        "gam": {"family", "id", "n_splines", "lam", "max_iter", "tol"},
        "random_forest": {"family", "id", "n_estimators", "bootstrap", "max_features", "min_samples_leaf", "max_depth"},
        "hist_gradient_boosting": {"family", "id", "max_iter", "early_stopping", "learning_rate", "max_leaf_nodes", "min_samples_leaf", "l2_regularization"},
        "shallow_ann": {"family", "id", "width", "dropout", "weight_decay", "lr", "max_epochs", "patience"},
        "residual_mlp": {"family", "id", "blocks", "width", "bottleneck", "dropout", "weight_decay", "lr", "activation", "norm", "max_epochs", "patience"},
    }[family]
    if set(c) != expected:
        raise ModelAdapterError("candidate_fields_mismatch")
    # Exact type/range checks prevent bool-as-number and silent defaults.
    for key, value in c.items():
        if key in {"family", "id", "solver", "positive_fraction", "activation", "norm"}:
            continue
        if key in {"bootstrap", "early_stopping"}:
            if type(value) is not bool:
                raise ModelAdapterError("candidate_numeric_invalid")
            continue
        if key == "max_features" and (value == "sqrt" or (isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value))):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            if key not in {"max_depth", "max_features"} or value is not None:
                raise ModelAdapterError("candidate_numeric_invalid")
    if family == "intercept" and c["positive_fraction"] != "empirical_inner_training_clipped_1e-7":
        raise ModelAdapterError("candidate_value_drift")
    if family == "elastic_net" and (c["solver"] != "saga" or c["max_iter"] != 5000 or c["tol"] != 1e-6 or not (0 <= c["l1_ratio"] <= 1) or c["C"] <= 0):
        raise ModelAdapterError("candidate_value_drift")
    if family == "gam" and (c["max_iter"] != 500 or c["tol"] != 1e-5):
        raise ModelAdapterError("candidate_value_drift")
    if family == "gam" and (c["n_splines"] < 2 or c["lam"] <= 0):
        raise ModelAdapterError("candidate_value_drift")
    if family == "random_forest" and (c["n_estimators"] != 500 or c["bootstrap"] is not True):
        raise ModelAdapterError("candidate_value_drift")
    if family == "hist_gradient_boosting" and (c["max_iter"] != 300 or c["early_stopping"] is not False):
        raise ModelAdapterError("candidate_value_drift")
    if family in {"shallow_ann", "residual_mlp"} and (c["max_epochs"] != 300 or c["patience"] != 30):
        raise ModelAdapterError("candidate_value_drift")


def _validate_batch(batch: FeatureBatch) -> None:
    if not isinstance(batch, FeatureBatch) or batch.x.ndim != 2 or len(batch.keys) != len(batch.y):
        raise ModelAdapterError("feature_batch_invalid")
    if not np.isin(batch.y, [0.0, 1.0]).all() or len(set(batch.y.tolist())) < 2:
        raise ModelAdapterError("single_class_training")


def _validate_seed(seed: int) -> None:
    if type(seed) is not int or seed < 0 or seed > 2**32 - 1:
        raise ModelAdapterError("seed_invalid")


def _schema_meta(batch: FeatureBatch) -> dict[str, Any]:
    return {
        "feature_names": tuple(batch.feature_names),
        "feature_kinds": tuple(batch.feature_kinds),
        "continuous_count": int(batch.continuous_count),
        "feature_schema_digest": batch.feature_schema_digest,
        "transform_id": batch.transform_id,
        "transform_digest": batch.transform_digest,
        "encoder_digest": batch.encoder_digest,
    }


def _check_schema(batch: FeatureBatch, schema: Mapping[str, Any]) -> None:
    for key in ("feature_names", "feature_kinds"):
        if tuple(getattr(batch, key)) != tuple(schema[key]):
            raise ModelAdapterError("feature_schema_order_mismatch")
    if int(batch.continuous_count) != int(schema["continuous_count"]) or batch.feature_schema_digest != schema["feature_schema_digest"]:
        raise ModelAdapterError("feature_schema_digest_mismatch")
    for key in ("transform_id", "transform_digest", "encoder_digest"):
        if getattr(batch, key) != schema[key]:
            raise ModelAdapterError(f"{key}_mismatch")


def _report(start: float, **kwargs: Any) -> FitReport:
    return FitReport(runtime_seconds=time.perf_counter() - start, peak_rss_bytes=0, **kwargs)


def _gam_safe_diagnostics(
    model: Any,
    caught: list[Any] | tuple[Any, ...],
    tol: float,
    *,
    prediction_finiteness: str = "not_applicable",
    prediction_range_status: str = "not_applicable",
) -> dict[str, Any]:
    logs = getattr(model, "logs_", {})
    diffs = list(logs.get("diffs", ())) if hasattr(logs, "get") else []
    finite_diffs = bool(diffs) and np.isfinite(
        np.asarray(diffs, dtype=np.float64)
    ).all()
    if not diffs:
        final_difference_class = "missing"
    elif not finite_diffs:
        final_difference_class = "nonfinite"
    elif float(diffs[-1]) < float(tol):
        final_difference_class = "lt_tol"
    else:
        final_difference_class = "ge_tol"
    messages = [str(item.message).lower() for item in caught]
    if any(
        any(token in message for token in ("overflow", "divide", "invalid"))
        for message in messages
    ):
        warning_category = "numerical"
    elif any(
        any(token in message for token in ("converg", "iteration", "maximum"))
        for message in messages
    ):
        warning_category = "convergence"
    elif messages:
        warning_category = "informational"
    else:
        warning_category = "none"
    coefficients = getattr(model, "coef_", None)
    coefficient_finiteness = (
        "missing"
        if coefficients is None
        else (
            "finite"
            if np.isfinite(np.asarray(coefficients)).all()
            else "nonfinite"
        )
    )
    return {
        "iteration_count": len(diffs) if diffs else None,
        "final_difference_class": final_difference_class,
        "warning_category": warning_category,
        "coefficient_finiteness": coefficient_finiteness,
        "prediction_finiteness": prediction_finiteness,
        "prediction_range_status": prediction_range_status,
    }


def _attach_gam_safe_diagnostics(
    error: ModelAdapterError, diagnostics: Mapping[str, Any]
) -> ModelAdapterError:
    error.safe_diagnostics = dict(diagnostics)
    return error


class _FittedBase:
    def __init__(self, family: str, model: Any, schema: Mapping[str, Any], candidate: Mapping[str, Any], seed: int, payload: Mapping[str, Any] | None = None):
        self.family, self.model, self.schema = family, model, dict(schema)
        self.candidate = dict(candidate)
        self.seed = seed
        self.candidate_digest = _digest(self.candidate)
        self.payload = dict(payload or {})

    def _check(self, batch: FeatureBatch) -> None:
        _check_schema(batch, self.schema)

    def predict_scores(self, batch: FeatureBatch) -> np.ndarray:
        self._check(batch)
        try: scores = self._predict(batch.x)
        except ModelAdapterError: raise
        except Exception as exc: raise ModelAdapterError(f"{self.family}_predict_failed") from exc
        scores = np.asarray(scores, dtype=np.float64).reshape(-1)
        if len(scores) != len(batch.keys) or not np.isfinite(scores).all() or np.any(scores < 0) or np.any(scores > 1):
            raise ModelAdapterError("nonfinite_or_invalid_scores")
        return scores

    def _predict(self, x: np.ndarray) -> np.ndarray:
        if hasattr(self.model, "predict_proba"):
            out = np.asarray(self.model.predict_proba(x))
            return out[:, 1] if out.ndim == 2 else out.reshape(-1)
        if hasattr(self.model, "predict_mu"):
            return np.asarray(self.model.predict_mu(x)).reshape(-1)
        if hasattr(self.model, "predict"):
            out = self.model.predict(x)
            out = np.asarray(out).reshape(-1)
            return out
        raise ModelAdapterError("model_predict_unavailable")

    def _envelope(self, payload_bytes: bytes) -> dict[str, Any]:
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        identity = {
            "version": 1,
            "family": self.family,
            "candidate": self.candidate,
            "candidate_digest": self.candidate_digest,
            "fit_seed": self.seed,
            "schema": self.schema,
            "transform_digest": self.schema["transform_digest"],
            "encoder_digest": self.schema["encoder_digest"],
            "feature_schema_digest": self.schema["feature_schema_digest"],
            "runtime_versions": _runtime_versions(),
        }
        identity["identity_digest"] = _digest(identity)
        return {
            "version": 1,
            "family": self.family,
            "candidate": self.candidate,
            "candidate_digest": self.candidate_digest,
            "fit_seed": self.seed,
            "schema": self.schema,
            "transform_digest": self.schema["transform_digest"],
            "encoder_digest": self.schema["encoder_digest"],
            "feature_schema_digest": self.schema["feature_schema_digest"],
            "runtime_versions": identity["runtime_versions"],
            "identity": identity,
            "identity_digest": identity["identity_digest"],
            "payload_digest": payload_digest,
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
        }

    def serialize(self, path: Path) -> Mapping[str, Any]:
        identity = self._envelope(b"")["identity"]
        payload = pickle.dumps({"identity": identity, "model": self.model, "payload": self.payload}, protocol=5)
        envelope = self._envelope(payload)
        raw = (canonical_json(envelope) + "\n").encode("utf-8")
        Path(path).write_bytes(raw)
        envelope["whole_file_sha256"] = hashlib.sha256(raw).hexdigest()
        return envelope


class _ConventionalAdapter:
    def __init__(self, family: str):
        self.family = family

    def fit(self, train: FeatureBatch, stopping: FeatureBatch | None, candidate: Mapping[str, Any], seed: int, exact_epochs: int | None = None):
        if stopping is not None or exact_epochs is not None:
            raise ModelAdapterError("conventional_stopping_forbidden")
        validate_candidate(self.family, candidate); _validate_batch(train); _validate_seed(seed)
        start = time.perf_counter(); warnings_out: list[str] = []
        y = train.y.astype(np.float64); x = train.x.astype(np.float64)
        np.random.seed(seed)
        if self.family == "intercept":
            p = float(np.clip(np.mean(y), 1e-7, 1 - 1e-7)); model = _InterceptModel(p)
            iterations = 1
        elif self.family == "elastic_net":
            model = LogisticRegression(C=candidate["C"], l1_ratio=candidate["l1_ratio"], penalty="elasticnet", solver="saga", max_iter=5000, tol=1e-6, random_state=seed, fit_intercept=True, class_weight=None, n_jobs=1)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try: model.fit(x, y)
                except ModelAdapterError: raise
                except Exception as exc: raise ModelAdapterError("elastic_net_fit_failed") from exc
            if any(issubclass(w.category, ConvergenceWarning) for w in caught) or getattr(model, "n_iter_", [0])[0] >= 5000:
                raise ModelAdapterError("elastic_net_nonconverged")
            iterations = int(np.max(model.n_iter_))
        elif self.family == "gam":
            n_cont = train.continuous_count
            terms = None
            for index in range(n_cont):
                term = s(index, n_splines=candidate["n_splines"], spline_order=3, lam=candidate["lam"])
                terms = term if terms is None else terms + term
            for index in range(n_cont, x.shape[1]):
                term = l(index, lam=candidate["lam"])
                terms = term if terms is None else terms + term
            model = LogisticGAM(terms, max_iter=500, tol=1e-5, verbose=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    model.fit(x, y)
                except ModelAdapterError: raise
                except Exception as exc:
                    error = _attach_gam_safe_diagnostics(
                        ModelAdapterError("gam_fit_failed"),
                        _gam_safe_diagnostics(model, caught, candidate["tol"]),
                    )
                    raise error from exc
            warnings_out.extend(str(w.message) for w in caught)
            logs = getattr(model, "logs_", {})
            diffs = list(logs.get("diffs", [])) if hasattr(logs, "get") else []
            convergence_warning = any(
                (
                    issubclass(w.category, (RuntimeWarning, UserWarning))
                    and any(word in str(w.message).lower() for word in ("converg", "iteration", "maximum"))
                )
                or (
                    issubclass(w.category, RuntimeWarning)
                    and any(word in str(w.message).lower() for word in ("overflow", "divide", "invalid"))
                )
                for w in caught
            )
            exhausted = (
                bool(diffs)
                and (
                    len(diffs) > int(candidate["max_iter"])
                    or (len(diffs) == int(candidate["max_iter"]) and float(diffs[-1]) >= float(candidate["tol"]))
                )
            )
            if convergence_warning or exhausted or not diffs or not np.isfinite(np.asarray(diffs, dtype=np.float64)).all() or float(diffs[-1]) >= float(candidate["tol"]) or not np.isfinite(np.asarray(model.coef_)).all():
                raise _attach_gam_safe_diagnostics(
                    ModelAdapterError("gam_nonconverged"),
                    _gam_safe_diagnostics(model, caught, candidate["tol"]),
                )
            iterations = len(diffs)
        elif self.family == "random_forest":
            model = RandomForestClassifier(n_estimators=500, criterion="gini", bootstrap=True, max_features=candidate["max_features"], min_samples_leaf=candidate["min_samples_leaf"], max_depth=candidate["max_depth"], min_samples_split=2, random_state=seed, n_jobs=1, class_weight=None)
            try: model.fit(x, y)
            except ModelAdapterError: raise
            except Exception as exc: raise ModelAdapterError("random_forest_fit_failed") from exc
            iterations = 500
        else:
            model = HistGradientBoostingClassifier(loss="log_loss", max_iter=300, early_stopping=False, learning_rate=candidate["learning_rate"], max_leaf_nodes=candidate["max_leaf_nodes"], min_samples_leaf=candidate["min_samples_leaf"], l2_regularization=candidate["l2_regularization"], class_weight=None, random_state=seed)
            try: model.fit(x, y)
            except ModelAdapterError: raise
            except Exception as exc: raise ModelAdapterError("hist_gradient_boosting_fit_failed") from exc
            iterations = 300
        fitted = _FittedBase(self.family, model, _schema_meta(train), candidate, seed)
        try:
            fitted.predict_scores(train)
        except ModelAdapterError as exc:
            if self.family == "gam" and not hasattr(exc, "safe_diagnostics"):
                status = (
                    "failed_validation"
                    if str(exc) == "nonfinite_or_invalid_scores"
                    else "not_evaluated"
                )
                _attach_gam_safe_diagnostics(
                    exc,
                    _gam_safe_diagnostics(
                        model,
                        caught,
                        candidate["tol"],
                        prediction_finiteness=status,
                        prediction_range_status=status,
                    ),
                )
            raise
        except Exception as exc: raise ModelAdapterError(f"{self.family}_predict_failed") from exc
        return fitted, _report(start, converged=True, iterations=iterations, best_epoch=None, stopping_fold=None, neural_stop_status=None, warnings=tuple(warnings_out))


class _InterceptModel:
    def __init__(self, p: float): self.p = p
    def predict_proba(self, x: np.ndarray) -> np.ndarray: return np.column_stack([np.full(len(x), 1 - self.p), np.full(len(x), self.p)])


class _TorchShallow(nn.Module):
    def __init__(self, n_in: int, width: int, dropout: float):
        super().__init__(); self.net = nn.Sequential(nn.Linear(n_in, width), nn.GELU(), nn.Dropout(dropout), nn.Linear(width, 1))
    def forward(self, x): return self.net(x).reshape(-1)


class _ResidualBlock(nn.Module):
    def __init__(self, width: int, bottleneck: int, dropout: float):
        super().__init__(); self.norm = nn.LayerNorm(width); self.down = nn.Linear(width, bottleneck); self.act = nn.GELU(); self.drop = nn.Dropout(dropout); self.up = nn.Linear(bottleneck, width)
    def forward(self, h): return h + self.up(self.drop(self.act(self.down(self.norm(h)))))


class _TorchResidual(nn.Module):
    def __init__(self, n_in: int, blocks: int, width: int, bottleneck: int, dropout: float):
        super().__init__(); self.input_projection = nn.Linear(n_in, width); self.activation = nn.GELU(); self.blocks = nn.ModuleList([_ResidualBlock(width, bottleneck, dropout) for _ in range(blocks)]); self.head_norm = nn.LayerNorm(width); self.head = nn.Linear(width, 1)
    def forward(self, x):
        h = self.activation(self.input_projection(x))
        for block in self.blocks: h = block(h)
        return self.head(self.head_norm(h)).reshape(-1)


def _init_torch(module: nn.Module) -> None:
    for layer in module.modules():
        if isinstance(layer, nn.Linear): nn.init.xavier_uniform_(layer.weight, gain=1.0); nn.init.zeros_(layer.bias)
        elif isinstance(layer, nn.LayerNorm): nn.init.ones_(layer.weight); nn.init.zeros_(layer.bias)


class _FittedTorch(_FittedBase):
    def _predict(self, x):
        self.model.eval()
        with torch.no_grad():
            logits = self.model(torch.as_tensor(np.array(x, copy=True), dtype=torch.float32)).detach().cpu().numpy()
        return 1.0 / (1.0 + np.exp(-logits))

    def serialize(self, path: Path) -> Mapping[str, Any]:
        identity = self._envelope(b"")["identity"]
        payload = pickle.dumps({"identity": identity, "state": self.model.state_dict(), "architecture": self.payload}, protocol=5)
        envelope = self._envelope(payload); raw = (canonical_json(envelope) + "\n").encode(); Path(path).write_bytes(raw); envelope["whole_file_sha256"] = hashlib.sha256(raw).hexdigest(); return envelope


class _NeuralAdapter:
    def __init__(self, family: str): self.family = family

    def _model(self, n: int, c: Mapping[str, Any]) -> nn.Module:
        if self.family == "shallow_ann": return _TorchShallow(n, int(c["width"]), float(c["dropout"]))
        return _TorchResidual(n, int(c["blocks"]), int(c["width"]), int(c["bottleneck"]), float(c["dropout"]))

    def fit(self, train: FeatureBatch, stopping: FeatureBatch | None, candidate: Mapping[str, Any], seed: int, exact_epochs: int | None = None):
        validate_candidate(self.family, candidate); _validate_batch(train); _validate_seed(seed)
        if exact_epochs is not None and type(exact_epochs) is not int: raise ModelAdapterError("exact_epoch_invalid")
        if exact_epochs is None and stopping is None: raise ModelAdapterError("neural_stopping_required")
        if exact_epochs is not None and stopping is not None: raise ModelAdapterError("neural_exact_stopping_conflict")
        if stopping is not None and (not np.isin(stopping.y, [0.0, 1.0]).all() or len(set(stopping.y.tolist())) < 2):
            raise ModelAdapterError("single_class_stopping")
        if stopping is not None:
            _check_schema(stopping, _schema_meta(train))
        torch.manual_seed(seed); np.random.seed(seed); random.seed(seed); torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
        start = time.perf_counter(); model = self._model(train.x.shape[1], candidate); _init_torch(model); initial_digest = _initial_state_digest(model); model.train()
        try:
            opt = torch.optim.AdamW(model.parameters(), lr=float(candidate["lr"]), weight_decay=float(candidate["weight_decay"]), betas=(0.9, 0.999), eps=1e-8, amsgrad=False, foreach=False, fused=False)
        except Exception as exc: raise ModelAdapterError("neural_optimizer_failure") from exc
        order = np.asarray(sorted(range(len(train.keys)), key=lambda i: train.keys[i]), dtype=int)
        loss_fn = nn.BCEWithLogitsLoss(); x = torch.as_tensor(np.array(train.x[order], copy=True), dtype=torch.float32); y = torch.as_tensor(np.array(train.y[order], copy=True), dtype=torch.float32)
        generator = torch.Generator(device="cpu"); generator.manual_seed(int(seed)); batch_size = min(128, len(train.keys)); max_epochs = int(candidate["max_epochs"])
        best_state = None; best_loss = float("inf"); best_epoch = None; patience_count = 0; status = None
        stopping_x = stopping_y = None
        if stopping is not None:
            stop_order = np.asarray(sorted(range(len(stopping.keys)), key=lambda i: stopping.keys[i]), dtype=int)
            stopping_x = torch.as_tensor(np.array(stopping.x[stop_order], copy=True), dtype=torch.float32); stopping_y = torch.as_tensor(np.array(stopping.y[stop_order], copy=True), dtype=torch.float32)
        epochs = int(exact_epochs) if exact_epochs is not None else max_epochs
        if epochs < 1 or epochs > max_epochs: raise ModelAdapterError("exact_epoch_invalid")
        completed_epochs = 0
        for epoch in range(1, epochs + 1):
            completed_epochs = epoch
            model.train(); perm = torch.randperm(len(x), generator=generator)
            for begin in range(0, len(x), batch_size):
                idx = perm[begin: begin + batch_size]; opt.zero_grad(set_to_none=True); logits = model(x[idx]); loss = loss_fn(logits, y[idx])
                if not torch.isfinite(loss): raise ModelAdapterError("neural_nonfinite_loss")
                loss.backward()
                for p in model.parameters():
                    if p.grad is None or not torch.isfinite(p.grad).all(): raise ModelAdapterError("neural_nonfinite_gradient")
                try:
                    opt.step()
                except Exception as exc:
                    raise ModelAdapterError("neural_optimizer_failure") from exc
                if any(not torch.isfinite(p).all() for p in model.parameters()): raise ModelAdapterError("neural_nonfinite_parameter")
            if stopping is not None:
                model.eval()
                with torch.no_grad(): stop_loss = loss_fn(model(stopping_x), stopping_y)
                if not torch.isfinite(stop_loss): raise ModelAdapterError("neural_nonfinite_stopping_loss")
                value = float(stop_loss)
                if value < best_loss:
                    best_loss = value; best_epoch = epoch; best_state = copy.deepcopy(model.state_dict()); patience_count = 0
                else: patience_count += 1
                if patience_count >= int(candidate["patience"]): status = "patience_stop"; break
        if stopping is not None:
            if best_state is None or best_epoch is None: raise ModelAdapterError("neural_no_valid_checkpoint")
            model.load_state_dict(best_state)
            if status is None and epochs == max_epochs: status = "max_epochs_reached"
        else:
            best_epoch = int(exact_epochs)
        fitted = _FittedTorch(self.family, model.eval(), _schema_meta(train), candidate, seed, {k: candidate[k] for k in candidate if k not in {"family", "id"}})
        try: fitted.predict_scores(train)
        except ModelAdapterError: raise
        except Exception as exc: raise ModelAdapterError("neural_predict_failed") from exc
        return fitted, _report(start, converged=True, iterations=completed_epochs, best_epoch=best_epoch, stopping_fold=None, neural_stop_status=status, warnings=(("max_epochs_reached",) if status == "max_epochs_reached" else ()), initial_state_digest=initial_digest)


class _Adapter:
    def __init__(self, family: str): self.family = family
    def fit(self, *args, **kwargs):
        if self.family in {"shallow_ann", "residual_mlp"}: return _NeuralAdapter(self.family).fit(*args, **kwargs)
        return _ConventionalAdapter(self.family).fit(*args, **kwargs)


def build_adapter(family: str) -> ModelAdapter:
    if family not in FAMILIES: raise ModelAdapterError("unknown_model_family")
    return _Adapter(family)


def load_fitted_model(path: Path, expected_sha256: str) -> FittedAdapter:
    raw = Path(path).read_bytes()
    if type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None: raise ModelAdapterError("external_digest_invalid")
    if hashlib.sha256(raw).hexdigest() != expected_sha256: raise ModelAdapterError("whole_file_digest_mismatch")
    try: envelope = json.loads(raw.decode("utf-8"))
    except Exception as exc: raise ModelAdapterError("serialization_invalid") from exc
    if not isinstance(envelope, Mapping) or envelope.get("version") != 1: raise ModelAdapterError("serialization_version_invalid")
    try: encoded = envelope["payload"]
    except KeyError as exc: raise ModelAdapterError("payload_missing") from exc
    if type(encoded) is not str or not encoded: raise ModelAdapterError("payload_base64_invalid")
    try: payload = base64.b64decode(encoded.encode("ascii"), validate=True)
    except Exception as exc: raise ModelAdapterError("payload_base64_invalid") from exc
    if base64.b64encode(payload).decode("ascii") != encoded: raise ModelAdapterError("payload_base64_noncanonical")
    if hashlib.sha256(payload).hexdigest() != envelope.get("payload_digest"): raise ModelAdapterError("payload_digest_mismatch")
    family = envelope.get("family"); schema = envelope.get("schema"); candidate = envelope.get("candidate")
    identity = envelope.get("identity")
    identity_for_digest = dict(identity) if isinstance(identity, Mapping) else None
    if identity_for_digest is None: raise ModelAdapterError("identity_digest_mismatch")
    embedded_identity_digest = identity_for_digest.pop("identity_digest", None)
    if envelope.get("identity_digest") != embedded_identity_digest or envelope.get("identity_digest") != _digest(identity_for_digest): raise ModelAdapterError("identity_digest_mismatch")
    if identity.get("family") != family or identity.get("candidate") != candidate or identity.get("schema") != schema or identity.get("fit_seed") != envelope.get("fit_seed") or identity.get("runtime_versions") != envelope.get("runtime_versions"): raise ModelAdapterError("identity_envelope_mismatch")
    if envelope.get("candidate_digest") != _digest(candidate) or identity.get("candidate_digest") != envelope.get("candidate_digest"): raise ModelAdapterError("candidate_digest_mismatch")
    if type(envelope.get("fit_seed")) is not int: raise ModelAdapterError("fit_seed_invalid")
    if not isinstance(schema, Mapping) or schema.get("feature_schema_digest") != envelope.get("feature_schema_digest") or schema.get("transform_digest") != envelope.get("transform_digest") or schema.get("encoder_digest") != envelope.get("encoder_digest"):
        raise ModelAdapterError("serialization_schema_identity_mismatch")
    expected_schema_digest = _digest({"feature_names": tuple(schema.get("feature_names", ())), "feature_kinds": tuple(schema.get("feature_kinds", ())), "continuous_count": schema.get("continuous_count")})
    if expected_schema_digest != schema.get("feature_schema_digest") or len(schema.get("feature_names", ())) != len(schema.get("feature_kinds", ())):
        raise ModelAdapterError("serialization_feature_schema_invalid")
    if family not in FAMILIES or not isinstance(candidate, Mapping):
        raise ModelAdapterError("serialization_identity_invalid")
    validate_candidate(family, candidate)
    try: obj = pickle.loads(payload)
    except Exception as exc: raise ModelAdapterError("payload_unpickle_failed") from exc
    if not isinstance(obj, Mapping) or not isinstance(obj.get("identity"), Mapping) or canonical_json(obj.get("identity")) != canonical_json(identity): raise ModelAdapterError("payload_identity_mismatch")
    if family in {"shallow_ann", "residual_mlp"}:
        architecture = obj.get("architecture", {})
        expected_arch = {k: candidate[k] for k in candidate if k not in {"family", "id"}}
        if architecture != expected_arch: raise ModelAdapterError("neural_architecture_mismatch")
        adapter = _NeuralAdapter(family); model = adapter._model(len(schema["feature_names"]), candidate); _init_torch(model)
        try: model.load_state_dict(obj["state"])
        except Exception as exc: raise ModelAdapterError("neural_state_invalid") from exc
        if any(not torch.isfinite(p).all() for p in model.parameters()): raise ModelAdapterError("neural_nonfinite_parameter")
        return _FittedTorch(family, model.eval(), schema, candidate, int(envelope["fit_seed"]), architecture)
    model = obj.get("model")
    if family == "intercept" and not isinstance(model, _InterceptModel): raise ModelAdapterError("model_type_mismatch")
    if family == "elastic_net" and not isinstance(model, LogisticRegression): raise ModelAdapterError("model_type_mismatch")
    if family == "gam" and not isinstance(model, LogisticGAM): raise ModelAdapterError("model_type_mismatch")
    if family == "random_forest" and not isinstance(model, RandomForestClassifier): raise ModelAdapterError("model_type_mismatch")
    if family == "hist_gradient_boosting" and not isinstance(model, HistGradientBoostingClassifier): raise ModelAdapterError("model_type_mismatch")
    return _FittedBase(family, model, schema, candidate, int(envelope["fit_seed"]), obj.get("payload", {}))


# Public named constructors are useful to tests and callers that prefer an
# explicit family while retaining the common ``build_adapter`` entry point.
InterceptAdapter = type("InterceptAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "intercept")})
ElasticNetAdapter = type("ElasticNetAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "elastic_net")})
GAMAdapter = type("GAMAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "gam")})
RandomForestAdapter = type("RandomForestAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "random_forest")})
HistGradientBoostingAdapter = type("HistGradientBoostingAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "hist_gradient_boosting")})
ShallowANNAdapter = type("ShallowANNAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "shallow_ann")})
ResidualMLPAdapter = type("ResidualMLPAdapter", (_Adapter,), {"__init__": lambda self: _Adapter.__init__(self, "residual_mlp")})
