"""Real six-path execution sentinel for Goal 034.

The local exporter is the only command that touches the Phase 1 foundation.
The runner consumes one deidentified numeric bundle and emits aggregate
execution evidence only.  It deliberately does not implement the later full
production queue or ecological evaluation.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

import numpy as np

from .contracts import ARCHITECTURES, METHODS, SPECIES, ArchitectureSpec


class ContractError(ValueError):
    """Raised when the frozen Goal034 contract or an authority drifts."""


class BundleError(ValueError):
    """Raised when a private numeric bundle violates its contract."""


class RunError(ValueError):
    """Raised when a six-path run or receipt is invalid."""


ENDPOINTS = (
    "fraction25/ladder00",
    "fraction50/ladder00",
    "fraction100/full",
)
ENDPOINT_SLUGS = {
    "fraction25/ladder00": "fraction25",
    "fraction50/ladder00": "fraction50",
    "fraction100/full": "fraction100",
}
TARGET = "sarcophilus_harrisii"
HELD_FOLD = "fold01"
STOPPING_FOLD = "fold02"
BASE_SEED = 31031
ARCHITECTURE = ArchitectureSpec("resmlp13", 3, 128, 64, "constant", 0.0, 0.001)
AUTHORITY_KEYS = {
    "goal027_protocol",
    "goal028_config",
    "goal028_decision",
    "goal031_config",
    "goal031_decision",
    "goal033_config",
    "goal033_decision",
    "goal033_winner",
    "goal029_config",
    "goal026_feature_contract",
    "goal026_fit_parameters",
}
SOURCE_KEYS = {
    "real_six_path",
    "real_six_path_data",
    "contracts",
    "models",
    "real_data",
    "target_subsets",
    "modeling_contract",
    "goal029_production",
    "uv_lock",
}
RUNTIME_POLICY = {
    "python_major_minor": "3.12",
    "numpy": "2.2.6",
    "scipy": "1.16.3",
    "scikit_learn": "1.9.0",
    "threadpoolctl": "3.6.0",
    "torch_base": "2.7.1",
    "torch_threads": 1,
}
_HEX64 = re.compile(r"[0-9a-f]{64}")
_PRIVATE_TEXT = re.compile(
    r"(?:^|[^a-z])(row.?id|grid.?cell|cell.?id|latitude|longitude|tas_cam|/Users/|\\Users\\|raw.?camera)(?:[^a-z]|$)",
    re.IGNORECASE,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition: bool, message: str, error: type[ValueError] = ContractError) -> None:
    if not condition:
        raise error(message)


def _safe_authority(root: Path, binding: Mapping[str, Any]) -> Path:
    _require(set(binding) == {"path", "sha256"}, "authority binding schema")
    raw = binding.get("path")
    digest = binding.get("sha256")
    _require(isinstance(raw, str) and raw and not Path(raw).is_absolute() and ".." not in Path(raw).parts, "authority path invalid")
    _require(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None, "authority digest invalid")
    path = (root / raw).resolve()
    _require(root.resolve() == path or root.resolve() in path.parents, "authority path escape")
    _require(path.is_file() and _sha_bytes(path.read_bytes()) == digest, f"authority digest mismatch: {raw}")
    return path


@dataclass(frozen=True)
class SentinelConfig:
    source: Path
    root: Path
    raw: Mapping[str, Any]
    authority_digests: Mapping[str, str]
    source_digests: Mapping[str, str]
    source_fingerprint: str
    config_digest: str
    architecture: ArchitectureSpec = ARCHITECTURE
    max_epochs: int = 300
    patience: int = 30
    test_only: bool = False


def load_config(path: str | Path, *, root: str | Path | None = None) -> SentinelConfig:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid config: {exc}") from exc
    expected_top = {
        "schema_version", "goal_id", "authorities", "execution_sources", "runtime",
        "sentinel", "methods", "architecture", "auxiliary", "training",
        "execution", "privacy", "evidence",
    }
    _require(isinstance(raw, dict) and set(raw) == expected_top, "config section drift")
    _require(raw["schema_version"] == "1.0" and raw["goal_id"] == "goal034-dsdm-real-six-path-sentinel", "config identity drift")
    project_root = Path(root).resolve() if root is not None else source.resolve().parents[1]
    authorities = raw["authorities"]
    _require(isinstance(authorities, dict) and set(authorities) == AUTHORITY_KEYS, "authority set drift")
    authority_paths = {name: _safe_authority(project_root, binding) for name, binding in authorities.items()}
    sources = raw["execution_sources"]
    _require(isinstance(sources, dict) and set(sources) == SOURCE_KEYS, "execution source set drift")
    source_paths = {name: _safe_authority(project_root, binding) for name, binding in sources.items()}
    _require(len(set(source_paths.values())) == len(source_paths), "execution source path duplicate")
    source_digests = {name: str(value["sha256"]) for name, value in sources.items()}
    source_records = [
        {"name": name, "path": str(sources[name]["path"]), "sha256": source_digests[name]}
        for name in sorted(sources)
    ]
    source_fingerprint = _sha_bytes(_canonical(source_records))
    _require(raw["runtime"] == RUNTIME_POLICY, "shared runtime policy drift")
    winner = json.loads(authority_paths["goal033_winner"].read_text(encoding="utf-8"))
    _require(winner.get("final_winner") == "resmlp13", "Goal033 winner drift")
    _require(winner.get("outer_attempted") == winner.get("outer_opened") == 0, "Goal033 outer boundary drift")

    sentinel = raw["sentinel"]
    _require(set(sentinel) == {
        "target", "held_fold", "stopping_fold", "discovery_folds",
        "eligible_auxiliary_folds", "base_seed", "endpoints", "target_endpoint_counts",
    }, "sentinel schema drift")
    _require(sentinel["target"] == TARGET and sentinel["held_fold"] == HELD_FOLD and sentinel["stopping_fold"] == STOPPING_FOLD, "sentinel case drift")
    _require(sentinel["discovery_folds"] == ["fold00", "fold03", "fold04"], "discovery fold drift")
    _require(sentinel["eligible_auxiliary_folds"] == ["fold00", "fold02", "fold03", "fold04"], "auxiliary fold drift")
    _require(sentinel["base_seed"] == BASE_SEED and tuple(sentinel["endpoints"]) == ENDPOINTS, "sentinel endpoint/seed drift")
    expected_counts = {
        "fraction25/ladder00": {"rows": 670, "presence": 648, "absence": 22},
        "fraction50/ladder00": {"rows": 1340, "presence": 1295, "absence": 45},
        "fraction100/full": {"rows": 2679, "presence": 2589, "absence": 90},
    }
    _require(sentinel["target_endpoint_counts"] == expected_counts, "target endpoint count drift")
    _require(tuple(raw["methods"]) == METHODS, "method drift")
    arch = raw["architecture"]
    _require(tuple(arch.get(key) for key in ("id", "blocks", "width", "bottleneck", "shape", "dropout", "weight_decay")) == tuple(ARCHITECTURE.__dict__.values()), "architecture drift")
    _require(tuple(ARCHITECTURE.__dict__.values()) in ARCHITECTURES, "architecture registry drift")
    auxiliary = raw["auxiliary"]
    _require(auxiliary == {
        "species_count": 7,
        "response_sources": ["presence", "survey_supported_absence"],
        "exclude_target": True,
        "exclude_pseudoabsence": True,
        "neural_weighting": "mean_of_seven_within_species_means",
        "q_linear_weighting": "exact_equal_species_contribution",
        "reuse_scope": "target_fold_seed",
    }, "auxiliary contract drift")
    training = raw["training"]
    _require(training == {
        "predictor_count": 77, "q_predictor_count": 78, "dtype": "float32",
        "deterministic_algorithms": True, "torch_threads": 1, "batch_size": 128,
        "optimizer": "AdamW", "learning_rate": 0.001, "max_epochs": 300,
        "patience": 30, "min_delta": 0.0,
        "target_loss": "unweighted_BCEWithLogitsLoss", "class_weighting": False,
        "resampling": False,
        "q_linear": {"penalty": "elasticnet", "solver": "saga", "C": 1.0,
                     "l1_ratio": 0.5, "max_iter": 5000, "tol": 0.00001},
    }, "training contract drift")
    _require(raw["execution"] == {
        "auxiliary_logical_artifacts": 3, "target_logical_artifacts": 18,
        "logical_artifacts": 21, "physical_fits": 41,
        "later_full_target_logical_artifacts": 8400,
        "later_full_auxiliary_logical_artifacts": 440,
        "later_full_lifecycle_logical_artifacts": 8840,
        "full_lifecycle_authorized": False, "outer_assessment_authorized": False,
    }, "execution contract drift")
    privacy = raw["privacy"]
    _require(privacy == {
        "float_arrays_only": True, "species_indices_only": True,
        "row_identifiers": False, "coordinates": False, "raw_camera_records": False,
        "absolute_paths": False, "inner_assessment_labels_private": True,
        "outer_attempted": 0, "outer_opened": 0,
    }, "privacy contract drift")
    _require(raw["evidence"].get("real_run_authorized") is True and raw["evidence"].get("full_run_authorized") is False and raw["evidence"].get("ecological_metrics") is False, "evidence boundary drift")
    digests = {name: str(value["sha256"]) for name, value in authorities.items()}
    return SentinelConfig(
        source.resolve(), project_root, raw, digests, source_digests,
        source_fingerprint, _sha_bytes(_canonical(raw)),
    )


def test_config(
    config: SentinelConfig,
    architecture: ArchitectureSpec,
    *,
    max_epochs: int,
    patience: int,
) -> SentinelConfig:
    """Return a direct-Python CI contract; CLI commands reject this object."""
    _require(1 <= max_epochs <= 3 and 1 <= patience <= max_epochs, "test epoch budget invalid")
    _require(architecture.id.startswith("test_") and architecture.width <= 16, "test architecture invalid")
    return replace(config, architecture=architecture, max_epochs=max_epochs, patience=patience, test_only=True)


test_config.__test__ = False


def build_plan(config: SentinelConfig) -> dict[str, int]:
    _require(len(config.raw["methods"]) == 6 and len(config.raw["sentinel"]["endpoints"]) == 3, "planner contract drift")
    return {
        "auxiliary_logical_artifacts": 3,
        "target_logical_artifacts": 18,
        "logical_artifacts": 21,
        "neural_discovery_fits": 20,
        "neural_replay_fits": 20,
        "q_linear_fits": 1,
        "physical_fits": 41,
        "full_target_logical_artifacts": 8400,
        "full_auxiliary_logical_artifacts": 440,
        "full_lifecycle_logical_artifacts": 8840,
        "fits_executed": 0,
    }


def _array_names() -> tuple[str, ...]:
    target = []
    for slug in ENDPOINT_SLUGS.values():
        for role in ("discovery", "stopping", "replay"):
            target.extend((f"target_{slug}_x_{role}", f"target_{slug}_y_{role}"))
    target.extend(("target_x_assessment", "target_y_assessment"))
    auxiliary = []
    for role in ("discovery", "stopping", "replay"):
        auxiliary.extend((f"aux_x_{role}", f"aux_y_{role}", f"aux_species_{role}"))
    return tuple(target + auxiliary)


ARRAY_NAMES = _array_names()


@dataclass(frozen=True)
class SixPathBundle:
    arrays: Mapping[str, np.ndarray]
    metadata: Mapping[str, Any]
    digest: str


def _privacy_check(value: Any, *, error: type[ValueError] = BundleError) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    if _PRIVATE_TEXT.search(text):
        raise error("portable privacy violation")


def _array_digest(value: np.ndarray) -> str:
    return _sha_bytes(np.asarray(value).tobytes(order="C"))


def _bundle_digest(metadata: Mapping[str, Any], arrays: Mapping[str, np.ndarray]) -> str:
    body = dict(metadata)
    body.pop("bundle_digest", None)
    digest = hashlib.sha256(_canonical(body))
    for name in ARRAY_NAMES:
        digest.update(name.encode("ascii"))
        digest.update(np.asarray(arrays[name]).tobytes(order="C"))
    return digest.hexdigest()


def _binary_pair(x: Any, y: Any, role: str, width: int = 77) -> tuple[np.ndarray, np.ndarray]:
    xv = np.asarray(x)
    yv = np.asarray(y)
    _require(xv.dtype == np.float32 and xv.ndim == 2 and xv.shape[1] == width, f"{role} predictors invalid", BundleError)
    _require(yv.dtype == np.float32 and yv.shape == (len(xv),), f"{role} response invalid", BundleError)
    _require(len(xv) > 0 and np.isfinite(xv).all() and np.isfinite(yv).all() and np.isin(yv, (0.0, 1.0)).all(), f"{role} values invalid", BundleError)
    return np.ascontiguousarray(xv), np.ascontiguousarray(yv)


def _validate_arrays(config: SentinelConfig, arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    _require(set(arrays) == set(ARRAY_NAMES), "bundle array inventory drift", BundleError)
    normalized: dict[str, np.ndarray] = {}
    endpoint_counts: dict[str, dict[str, int]] = {}
    for endpoint, slug in ENDPOINT_SLUGS.items():
        for role in ("discovery", "stopping", "replay"):
            x, y = _binary_pair(arrays[f"target_{slug}_x_{role}"], arrays[f"target_{slug}_y_{role}"], f"target {endpoint} {role}")
            _require(len(np.unique(y)) == 2, f"target {endpoint} {role} lacks both classes", BundleError)
            normalized[f"target_{slug}_x_{role}"] = x
            normalized[f"target_{slug}_y_{role}"] = y
        replay_y = normalized[f"target_{slug}_y_replay"]
        endpoint_counts[endpoint] = {"rows": len(replay_y), "presence": int(replay_y.sum()), "absence": int(len(replay_y) - replay_y.sum())}
    assess_x, assess_y = _binary_pair(arrays["target_x_assessment"], arrays["target_y_assessment"], "target assessment")
    _require(len(np.unique(assess_y)) == 2, "target assessment lacks both classes", BundleError)
    normalized["target_x_assessment"], normalized["target_y_assessment"] = assess_x, assess_y

    def rows_are_nested(short_x: np.ndarray, short_y: np.ndarray, long_x: np.ndarray, long_y: np.ndarray) -> bool:
        short_rows = Counter(x.tobytes() + y.tobytes() for x, y in zip(short_x, short_y))
        long_rows = Counter(x.tobytes() + y.tobytes() for x, y in zip(long_x, long_y))
        return all(count <= long_rows[row] for row, count in short_rows.items())

    for short, long in (("fraction25", "fraction50"), ("fraction50", "fraction100")):
        for role in ("discovery", "stopping", "replay"):
            _require(
                rows_are_nested(
                    normalized[f"target_{short}_x_{role}"],
                    normalized[f"target_{short}_y_{role}"],
                    normalized[f"target_{long}_x_{role}"],
                    normalized[f"target_{long}_y_{role}"],
                ),
                "target subsets not nested",
                BundleError,
            )
    if not config.test_only:
        _require(endpoint_counts == config.raw["sentinel"]["target_endpoint_counts"], "real target endpoint counts drift", BundleError)

    species_counts: dict[str, list[int]] = {}
    species_weights: dict[str, list[float]] = {}
    for role in ("discovery", "stopping", "replay"):
        x, y = _binary_pair(arrays[f"aux_x_{role}"], arrays[f"aux_y_{role}"], f"auxiliary {role}")
        species = np.asarray(arrays[f"aux_species_{role}"])
        _require(species.dtype == np.int32 and species.shape == (len(x),), f"auxiliary {role} species indices invalid", BundleError)
        _require(set(species.tolist()) == set(range(7)), f"auxiliary {role} species set invalid", BundleError)
        counts = np.bincount(species, minlength=7).astype(int)
        weights = len(species) / (7.0 * counts[species])
        totals = [float(weights[species == index].sum()) for index in range(7)]
        _require(max(totals) - min(totals) <= 1e-12, f"auxiliary {role} species weighting invalid", BundleError)
        normalized[f"aux_x_{role}"], normalized[f"aux_y_{role}"] = x, y
        normalized[f"aux_species_{role}"] = np.ascontiguousarray(species)
        species_counts[role] = counts.tolist()
        species_weights[role] = totals
    return {
        "normalized": normalized,
        "endpoint_counts": endpoint_counts,
        "species_counts": species_counts,
        "species_weights": species_weights,
    }


_AUDIT_KEYS = {
    "target_excluded", "pseudoabsence_rows", "held_fold_rows", "unknown_rows",
    "eligible_folds", "discovery_folds", "stopping_fold", "species_weighting",
    "q_linear_weighting", "outer_attempted", "outer_opened", "source_binding_digest",
    "subset_membership_digests", "subset_nesting_verified",
}


def build_bundle(
    config: SentinelConfig,
    arrays: Mapping[str, np.ndarray],
    audit: Mapping[str, Any],
) -> SixPathBundle:
    _privacy_check(audit)
    _require(set(audit) == _AUDIT_KEYS, "bundle audit schema drift", BundleError)
    _require(audit["target_excluded"] is True, "auxiliary target leakage", BundleError)
    _require(audit["pseudoabsence_rows"] == 0, "auxiliary pseudoabsence leakage", BundleError)
    _require(audit["held_fold_rows"] == 0, "auxiliary held-fold leakage", BundleError)
    _require(audit["unknown_rows"] == 0, "auxiliary unknown leakage", BundleError)
    _require(audit["eligible_folds"] == ["fold00", "fold02", "fold03", "fold04"], "auxiliary eligible fold drift", BundleError)
    _require(audit["discovery_folds"] == ["fold00", "fold03", "fold04"] and audit["stopping_fold"] == "fold02", "auxiliary role fold drift", BundleError)
    _require(audit["species_weighting"] == "mean_of_seven_within_species_means", "auxiliary loss weighting drift", BundleError)
    _require(audit["q_linear_weighting"] == "exact_equal_species_contribution", "q weighting drift", BundleError)
    _require(audit["outer_attempted"] == audit["outer_opened"] == 0, "outer access detected", BundleError)
    _require(isinstance(audit["source_binding_digest"], str) and _HEX64.fullmatch(audit["source_binding_digest"]) is not None, "source binding digest invalid", BundleError)
    _require(
        isinstance(audit["subset_membership_digests"], dict)
        and set(audit["subset_membership_digests"]) == set(ENDPOINTS)
        and all(isinstance(value, str) and _HEX64.fullmatch(value) is not None for value in audit["subset_membership_digests"].values()),
        "subset membership digest invalid",
        BundleError,
    )
    _require(audit["subset_nesting_verified"] is True, "subset nesting not verified", BundleError)
    checked = _validate_arrays(config, arrays)
    normalized = checked["normalized"]
    metadata: dict[str, Any] = {
        "schema_version": "goal034-six-path-bundle-v1",
        "goal_id": "goal034-dsdm-real-six-path-sentinel",
        "config_digest": config.config_digest,
        "authority_digests": dict(sorted(config.authority_digests.items())),
        "source_digests": dict(sorted(config.source_digests.items())),
        "source_fingerprint": config.source_fingerprint,
        "target": TARGET,
        "held_fold": HELD_FOLD,
        "stopping_fold": STOPPING_FOLD,
        "base_seed": BASE_SEED,
        "architecture": "resmlp13",
        "endpoints": list(ENDPOINTS),
        "methods": list(METHODS),
        "predictor_count": 77,
        "q_predictor_count": 78,
        "auxiliary_species_count": 7,
        "target_endpoint_counts": checked["endpoint_counts"],
        "auxiliary_species_counts": checked["species_counts"],
        "auxiliary_species_total_weights": checked["species_weights"],
        "array_shapes": {name: list(normalized[name].shape) for name in ARRAY_NAMES},
        "array_dtypes": {name: str(normalized[name].dtype) for name in ARRAY_NAMES},
        "array_digests": {name: _array_digest(normalized[name]) for name in ARRAY_NAMES},
        "audit": deepcopy(dict(audit)),
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    _privacy_check(metadata)
    digest = _bundle_digest(metadata, normalized)
    metadata["bundle_digest"] = digest
    return SixPathBundle(normalized, metadata, digest)


def validate_bundle(bundle: SixPathBundle, config: SentinelConfig) -> None:
    _privacy_check(bundle.metadata)
    _require(bundle.metadata.get("schema_version") == "goal034-six-path-bundle-v1", "bundle schema drift", BundleError)
    _require(bundle.metadata.get("config_digest") == config.config_digest, "bundle config binding mismatch", BundleError)
    _require(bundle.metadata.get("authority_digests") == dict(sorted(config.authority_digests.items())), "bundle authority binding mismatch", BundleError)
    _require(bundle.metadata.get("source_digests") == dict(sorted(config.source_digests.items())), "bundle source binding mismatch", BundleError)
    _require(bundle.metadata.get("source_fingerprint") == config.source_fingerprint, "bundle source fingerprint mismatch", BundleError)
    rebuilt = build_bundle(config, bundle.arrays, bundle.metadata.get("audit", {}))
    _require(bundle.digest == bundle.metadata.get("bundle_digest") == rebuilt.digest, "bundle digest mismatch", BundleError)
    _require(bundle.metadata == rebuilt.metadata, "bundle metadata drift", BundleError)


def save_bundle(bundle: SixPathBundle, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{bundle.digest}.npz"
    payload = {name: bundle.arrays[name] for name in ARRAY_NAMES}
    payload["metadata_json"] = np.frombuffer(_canonical(bundle.metadata), dtype=np.uint8)
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".goal034-", suffix=".npz", delete=False) as handle:
        temp = Path(handle.name)
    try:
        np.savez_compressed(temp, **payload)
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)
    return output


def load_bundle(path: str | Path, config: SentinelConfig) -> SixPathBundle:
    source = Path(path)
    try:
        with np.load(source, allow_pickle=False) as payload:
            _require(set(payload.files) == set(ARRAY_NAMES) | {"metadata_json"}, "bundle file inventory drift", BundleError)
            arrays = {name: np.asarray(payload[name]).copy() for name in ARRAY_NAMES}
            metadata = json.loads(bytes(payload["metadata_json"].tolist()).decode("utf-8"))
    except BundleError:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise BundleError("invalid bundle file") from exc
    digest = metadata.get("bundle_digest")
    _require(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None, "bundle digest invalid", BundleError)
    bundle = SixPathBundle(arrays, metadata, digest)
    validate_bundle(bundle, config)
    return bundle


def export_from_foundation(
    config: SentinelConfig,
    *,
    root: str | Path,
    output: str | Path,
) -> tuple[Path, SixPathBundle]:
    """Build one private bundle from the sealed outer-training foundation."""
    _require(not config.test_only, "test config cannot export real data", BundleError)
    project_root = Path(root).resolve()
    _require(project_root == config.root, "export root/config mismatch", BundleError)
    from .real_data import CaseSpec, _encode, records_from_foundation
    from dsdm_phase1.goal029_production import ingest_production_foundation
    from dsdm_phase1.target_subsets import build_ladders

    authorities = config.raw["authorities"]
    foundation_binding = {
        "bindings": {
            name: deepcopy(authorities[name])
            for name in ("goal029_config", "goal026_feature_contract", "goal026_fit_parameters")
        },
        "training": {"base_seed": BASE_SEED},
    }
    case = CaseSpec("goal034", TARGET, HELD_FOLD, "resmlp13", BASE_SEED)
    records, source_audit = records_from_foundation(project_root, foundation_binding, case)
    _require(source_audit.get("outer_attempted") == source_audit.get("outer_opened") == 0, "outer access during export", BundleError)
    goal029_path = project_root / authorities["goal029_config"]["path"]
    goal029_config = json.loads(goal029_path.read_text(encoding="utf-8"))
    broker, _, vault = ingest_production_foundation(project_root, goal029_config)
    _require(vault.attempted_open_count == vault.open_count == 0, "outer access during subset binding", BundleError)

    record_by_key = {(str(row["species"]), str(row["cell"])): row for row in records}
    training, assessment = broker.inner(TARGET, HELD_FOLD)
    ladders = build_ladders(training)
    arrays: dict[str, np.ndarray] = {}
    membership_digests: dict[str, str] = {}
    discovery_folds = set(config.raw["sentinel"]["discovery_folds"])
    for endpoint, slug in ENDPOINT_SLUGS.items():
        fraction, ladder = endpoint.split("/")
        lookup_ladder = "ladder00" if fraction == "fraction100" else ladder
        authoritative = ladders[(fraction, lookup_ladder)]
        keys = authoritative.keys
        membership_digests[endpoint] = authoritative.subset_digest
        role_keys = {
            "discovery": [key for key in keys if broker._fold_by_key[key] in discovery_folds],
            "stopping": [key for key in keys if broker._fold_by_key[key] == STOPPING_FOLD],
            "replay": list(keys),
        }
        for role, selected in role_keys.items():
            _require(bool(selected), f"empty target export role: {endpoint}/{role}", BundleError)
            rows = [record_by_key[(key.species_id, key.grid_cell_id)] for key in selected]
            arrays[f"target_{slug}_x_{role}"] = np.stack([_encode(row) for row in rows]).astype(np.float32)
            arrays[f"target_{slug}_y_{role}"] = np.asarray([row["y"] for row in rows], dtype=np.float32)

    assessment_rows = [record_by_key[(key.species_id, key.grid_cell_id)] for key in assessment.keys]
    arrays["target_x_assessment"] = np.stack([_encode(row) for row in assessment_rows]).astype(np.float32)
    arrays["target_y_assessment"] = np.asarray([row["y"] for row in assessment_rows], dtype=np.float32)
    aux_names = tuple(name for name in SPECIES if name != TARGET)
    species_index = {name: index for index, name in enumerate(aux_names)}
    eligible_folds = set(config.raw["sentinel"]["eligible_auxiliary_folds"])
    auxiliary = [
        row for row in records
        if row["species"] in species_index
        and row["fold"] in eligible_folds
        and row["source"] in {"presence", "survey_supported_absence"}
    ]
    role_folds = {
        "discovery": discovery_folds,
        "stopping": {STOPPING_FOLD},
        "replay": eligible_folds,
    }
    for role, folds in role_folds.items():
        rows = [row for row in auxiliary if row["fold"] in folds]
        arrays[f"aux_x_{role}"] = np.stack([_encode(row) for row in rows]).astype(np.float32)
        arrays[f"aux_y_{role}"] = np.asarray([row["y"] for row in rows], dtype=np.float32)
        arrays[f"aux_species_{role}"] = np.asarray([species_index[str(row["species"])] for row in rows], dtype=np.int32)
    audit = {
        "target_excluded": all(row["species"] != TARGET for row in auxiliary),
        "pseudoabsence_rows": sum(row["source"] == "pseudoabsence" for row in auxiliary),
        "held_fold_rows": sum(row["fold"] == HELD_FOLD for row in auxiliary),
        "unknown_rows": 0,
        "eligible_folds": list(config.raw["sentinel"]["eligible_auxiliary_folds"]),
        "discovery_folds": list(config.raw["sentinel"]["discovery_folds"]),
        "stopping_fold": STOPPING_FOLD,
        "species_weighting": "mean_of_seven_within_species_means",
        "q_linear_weighting": "exact_equal_species_contribution",
        "outer_attempted": int(source_audit["outer_attempted"]),
        "outer_opened": int(source_audit["outer_opened"]),
        "source_binding_digest": str(source_audit["source_binding_digest"]),
        "subset_membership_digests": membership_digests,
        "subset_nesting_verified": (
            set(ladders[("fraction25", "ladder00")].keys)
            <= set(ladders[("fraction50", "ladder00")].keys)
            <= set(ladders[("fraction100", "ladder00")].keys)
        ),
    }
    bundle = build_bundle(config, arrays, audit)
    path = save_bundle(bundle, output)
    return path, bundle
