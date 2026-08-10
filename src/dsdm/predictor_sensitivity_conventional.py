"""Frozen conventional-model helpers for Goal 039.

The module deliberately reuses the Goal 029 runner.  Predictor reduction is
implemented as a view over ``FeatureProvider`` that neutralises excluded
continuous columns while preserving the complete encoded feature schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from dsdm_phase1 import model_adapters as _model_adapters
from dsdm_phase1.goal029_production import (
    ENDPOINTS,
    FOLDS,
    SEEDS_BY_FAMILY,
    SPECIES,
    ProductionLeaf,
    classify_leaf_warnings,
    load_leaf_checkpoint,
    write_leaf_checkpoint,
)
from dsdm_phase1.inner_cv import CandidateOOF, SelectionStratum, run_candidate_oof
from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, build_adapter
from dsdm_phase1.modeling_contract import FeatureBatch, FeatureProvider, TaskKey, derive_seed
from dsdm_phase1.target_subsets import build_ladders

from .inner_evaluation import binary_metrics, select_threshold


FAMILIES = (
    "elastic_net",
    "random_forest",
    "hist_gradient_boosting",
    "shallow_ann",
)
ALL_CONTROL_FAMILIES = ("intercept", *FAMILIES)
SCREEN_ENDPOINTS = (
    ("fraction25", "ladder00"),
    ("fraction50", "ladder00"),
    ("fraction100", "full"),
)
CONFIRMATION_NEW_ENDPOINTS = (
    ("fraction25", "ladder01"),
    ("fraction25", "ladder02"),
    ("fraction50", "ladder01"),
    ("fraction50", "ladder02"),
)
CONFIRMATION_ANALYSIS_ENDPOINTS = (*CONFIRMATION_NEW_ENDPOINTS, ("fraction100", "full"))
PRODUCER_COMMIT = "f85e45922e182858fd351fdaf4f1b36b33fb4f2f"
EXPECTED_PRIVATE_CORE_MANIFEST = "836384b71fa03797e3fe92052aed2255b737d59a347aaa8614830a28d0851ab6"
_HEX = frozenset("0123456789abcdef")
_CONTROL_COLUMNS = (
    "species_id",
    "fraction_id",
    "ladder_id",
    "model_family",
    "candidate_id",
    "seed_label",
    "fold_id",
    "row_index",
    "row_token",
    "y_true",
    "score",
)
_CONTROL_SCHEMA = pa.schema(
    [
        ("species_id", pa.string()),
        ("fraction_id", pa.string()),
        ("ladder_id", pa.string()),
        ("model_family", pa.string()),
        ("candidate_id", pa.string()),
        ("seed_label", pa.string()),
        ("fold_id", pa.string()),
        ("row_index", pa.int32()),
        ("row_token", pa.string()),
        ("y_true", pa.int8()),
        ("score", pa.float64()),
    ]
)


class ConventionalSensitivityError(ValueError):
    """Raised when a frozen conventional control or reduced replay drifts."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConventionalSensitivityError(message)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def conventional_runtime_probe() -> dict[str, Any]:
    """Fail before execution unless all four frozen family adapters are callable."""
    dependencies = {
        "elastic_net": ("LogisticRegression",),
        "random_forest": ("RandomForestClassifier",),
        "hist_gradient_boosting": ("HistGradientBoostingClassifier",),
        "shallow_ann": ("_TorchShallow",),
    }
    availability: dict[str, dict[str, bool]] = {}
    for family, symbols in dependencies.items():
        availability[family] = {
            symbol: callable(getattr(_model_adapters, symbol, None))
            for symbol in symbols
        }
        adapter = build_adapter(family)
        availability[family]["adapter_fit"] = callable(getattr(adapter, "fit", None))
    _require(
        all(all(values.values()) for values in availability.values()),
        "conventional_runtime_dependency_unavailable",
    )
    return {
        "schema_version": "goal039-conventional-runtime-probe-v1",
        "families": list(FAMILIES),
        "availability": availability,
        "pygam_required": False,
    }


CONVENTIONAL_RUNTIME = conventional_runtime_probe()


def _endpoint_name(endpoint: tuple[str, str]) -> str:
    return f"{endpoint[0]}/{endpoint[1]}"


@dataclass(frozen=True, order=True)
class ConventionalLeaf:
    species_id: str
    fraction_id: str
    ladder_id: str
    model_family: str
    candidate_id: str
    seed_label: str

    @property
    def endpoint(self) -> str:
        return _endpoint_name((self.fraction_id, self.ladder_id))

    def task(self, fold: str) -> TaskKey:
        return TaskKey(
            self.species_id,
            f"cv_{fold}",
            self.fraction_id,
            self.ladder_id,
            self.model_family,
            self.candidate_id,
            self.seed_label,
        )


@dataclass(frozen=True)
class ControlFold:
    fold_id: str
    row_tokens: tuple[str, ...]
    y_true: np.ndarray
    scores: np.ndarray


@dataclass(frozen=True)
class ControlLeaf:
    leaf: ConventionalLeaf
    folds: tuple[ControlFold, ...]
    row_identity_digest: str
    prediction_digest: str


@dataclass(frozen=True)
class ConventionalControlCatalog:
    parquet_path: Path
    manifest_path: Path
    manifest: Mapping[str, Any]
    selections: Mapping[tuple[str, str, str, str], str]
    leaf_keys: frozenset[tuple[str, str, str, str, str, str]]

    @property
    def manifest_digest(self) -> str:
        return str(self.manifest["manifest_digest"])

    def selected_candidate(
        self, species: str, fraction: str, ladder: str, family: str
    ) -> str:
        try:
            return str(self.selections[(species, fraction, ladder, family)])
        except KeyError as exc:
            raise ConventionalSensitivityError("selected_candidate_missing") from exc


def load_full28_controls(
    parquet_path: str | Path,
    manifest_path: str | Path,
    *,
    expected_manifest_digest: str | None = None,
    expected_parquet_sha256: str | None = None,
    expected_producer_commit: str = PRODUCER_COMMIT,
    expected_private_core_manifest: str = EXPECTED_PRIVATE_CORE_MANIFEST,
) -> ConventionalControlCatalog:
    """Validate the immutable Goal 036 full-28 OOF export without scoring it."""
    parquet_path = Path(parquet_path)
    manifest_path = Path(manifest_path)
    _require(
        parquet_path.is_file()
        and manifest_path.is_file()
        and not parquet_path.is_symlink()
        and not manifest_path.is_symlink(),
        "full28_control_missing",
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConventionalSensitivityError("full28_manifest_invalid") from exc
    _require(isinstance(manifest, dict), "full28_manifest_invalid")
    body = dict(manifest)
    claimed = body.pop("manifest_digest", None)
    _require(_is_digest(claimed) and claimed == digest_value(body), "full28_manifest_digest_mismatch")
    if expected_manifest_digest is not None:
        _require(claimed == expected_manifest_digest, "full28_manifest_authority_mismatch")
    actual_parquet_sha = sha256_file(parquet_path)
    if expected_parquet_sha256 is not None:
        _require(actual_parquet_sha == expected_parquet_sha256, "full28_parquet_authority_mismatch")
    _require(
        manifest.get("schema_version") == "goal036-conventional-oof-export-v1"
        and manifest.get("producer_commit") == expected_producer_commit
        and manifest.get("private_core_manifest_sha256") == expected_private_core_manifest
        and manifest.get("family_strata") == 280
        and manifest.get("selected_checkpoints") == 952
        and manifest.get("outer_attempted") == manifest.get("outer_opened") == 0
        and manifest.get("species") == list(SPECIES)
        and manifest.get("endpoints") == [_endpoint_name(endpoint) for endpoint in ENDPOINTS]
        and manifest.get("families") == list(ALL_CONTROL_FAMILIES)
        and manifest.get("seed_count_by_family")
        == {family: len(SEEDS_BY_FAMILY[family]) for family in ALL_CONTROL_FAMILIES}
        and manifest.get("parquet_sha256") == actual_parquet_sha
        and manifest.get("parquet_bytes") == parquet_path.stat().st_size,
        "full28_manifest_contract_drift",
    )
    parquet = pq.ParquetFile(parquet_path)
    _require(
        parquet.schema_arrow == _CONTROL_SCHEMA
        and parquet.metadata.num_rows == manifest.get("rows"),
        "full28_parquet_schema_or_count_drift",
    )

    identity_columns = _CONTROL_COLUMNS[:6]
    leaf_keys: set[tuple[str, str, str, str, str, str]] = set()
    rows_seen = 0
    for batch in parquet.iter_batches(batch_size=131072, columns=list(identity_columns)):
        payload = batch.to_pydict()
        rows_seen += batch.num_rows
        for values in zip(*(payload[name] for name in identity_columns), strict=True):
            species, fraction, ladder, family, candidate, seed = values
            _require(
                species in SPECIES
                and (fraction, ladder) in ENDPOINTS
                and family in ALL_CONTROL_FAMILIES
                and seed in SEEDS_BY_FAMILY[family],
                "full28_leaf_identity_invalid",
            )
            canonical_candidate = CANONICAL_CANDIDATES.get(candidate)
            _require(
                canonical_candidate is not None
                and canonical_candidate.get("family") == family,
                "full28_candidate_not_canonical",
            )
            leaf_keys.add((species, fraction, ladder, family, candidate, seed))
    _require(rows_seen == manifest["rows"] and len(leaf_keys) == 952, "full28_leaf_inventory_drift")

    selection_sets: dict[tuple[str, str, str, str], set[str]] = {}
    seed_sets: dict[tuple[str, str, str, str, str], set[str]] = {}
    for species, fraction, ladder, family, candidate, seed in leaf_keys:
        selection_sets.setdefault((species, fraction, ladder, family), set()).add(candidate)
        seed_sets.setdefault((species, fraction, ladder, family, candidate), set()).add(seed)
    expected_strata = {
        (species, fraction, ladder, family)
        for species in SPECIES
        for fraction, ladder in ENDPOINTS
        for family in ALL_CONTROL_FAMILIES
    }
    _require(set(selection_sets) == expected_strata, "full28_selection_strata_drift")
    _require(all(len(values) == 1 for values in selection_sets.values()), "full28_selected_candidate_ambiguous")
    for key, candidates in selection_sets.items():
        candidate = next(iter(candidates))
        _require(seed_sets[(*key, candidate)] == set(SEEDS_BY_FAMILY[key[3]]), "full28_seed_inventory_drift")
    selections = {
        key: next(iter(candidates))
        for key, candidates in selection_sets.items()
        if key[3] in FAMILIES
    }
    conventional_keys = frozenset(key for key in leaf_keys if key[3] in FAMILIES)
    _require(len(selections) == 224 and len(conventional_keys) == 896, "full28_conventional_inventory_drift")
    return ConventionalControlCatalog(
        parquet_path.resolve(),
        manifest_path.resolve(),
        manifest,
        selections,
        conventional_keys,
    )


def _leaf_tuple(leaf: ConventionalLeaf) -> tuple[str, str, str, str, str, str]:
    return (
        leaf.species_id,
        leaf.fraction_id,
        leaf.ladder_id,
        leaf.model_family,
        leaf.candidate_id,
        leaf.seed_label,
    )


def validate_selected_leaf(catalog: ConventionalControlCatalog, leaf: ConventionalLeaf) -> None:
    _require(
        isinstance(leaf, ConventionalLeaf)
        and leaf.species_id in SPECIES
        and (leaf.fraction_id, leaf.ladder_id) in ENDPOINTS
        and leaf.model_family in FAMILIES
        and leaf.seed_label in SEEDS_BY_FAMILY[leaf.model_family]
        and catalog.selected_candidate(
            leaf.species_id, leaf.fraction_id, leaf.ladder_id, leaf.model_family
        )
        == leaf.candidate_id
        and _leaf_tuple(leaf) in catalog.leaf_keys,
        "selected_leaf_authority_mismatch",
    )


def load_control_leaf(
    catalog: ConventionalControlCatalog, leaf: ConventionalLeaf
) -> ControlLeaf:
    """Load one private selected-model seed leaf and validate row identity."""
    validate_selected_leaf(catalog, leaf)
    filters = [
        ("species_id", "=", leaf.species_id),
        ("fraction_id", "=", leaf.fraction_id),
        ("ladder_id", "=", leaf.ladder_id),
        ("model_family", "=", leaf.model_family),
        ("candidate_id", "=", leaf.candidate_id),
        ("seed_label", "=", leaf.seed_label),
    ]
    table = pq.read_table(catalog.parquet_path, filters=filters)
    _require(table.column_names == list(_CONTROL_COLUMNS) and table.num_rows > 0, "full28_control_leaf_missing")
    payload = table.to_pydict()
    for name, expected in zip(_CONTROL_COLUMNS[:6], _leaf_tuple(leaf), strict=True):
        _require(set(payload[name]) == {expected}, "full28_control_leaf_identity_drift")
    folds: list[ControlFold] = []
    identity_payload: list[dict[str, Any]] = []
    prediction_payload: list[dict[str, Any]] = []
    fold_values = np.asarray(payload["fold_id"], dtype=object)
    for fold in FOLDS:
        indices = np.flatnonzero(fold_values == fold)
        _require(indices.size > 0, "full28_control_fold_missing")
        order = indices[np.argsort(np.asarray(payload["row_index"])[indices], kind="stable")]
        row_indices = np.asarray(payload["row_index"], dtype=np.int64)[order]
        tokens = tuple(str(payload["row_token"][index]) for index in order)
        y = np.asarray([payload["y_true"][index] for index in order], dtype=np.int8)
        scores = np.asarray([payload["score"][index] for index in order], dtype=np.float64)
        _require(
            np.array_equal(row_indices, np.arange(len(order)))
            and len(set(tokens)) == len(tokens)
            and np.isin(y, (0, 1)).all()
            and set(y.tolist()) == {0, 1}
            and np.isfinite(scores).all()
            and np.all((scores >= 0.0) & (scores <= 1.0)),
            "full28_control_fold_invalid",
        )
        y.flags.writeable = False
        scores.flags.writeable = False
        folds.append(ControlFold(fold, tokens, y, scores))
        identity_payload.append({"fold": fold, "tokens": tokens, "y": y.tolist()})
        prediction_payload.append(
            {"fold": fold, "score_sha256": hashlib.sha256(scores.tobytes()).hexdigest()}
        )
    _require(set(fold_values.tolist()) == set(FOLDS), "full28_control_fold_scope_drift")
    return ControlLeaf(
        leaf,
        tuple(folds),
        digest_value(identity_payload),
        digest_value(prediction_payload),
    )


class ZeroedContinuousProvider:
    """Fold-aware 77-column view that zeros excluded continuous predictors."""

    def __init__(
        self,
        provider: FeatureProvider,
        excluded_by_fold: Mapping[str, Sequence[str | int]],
    ):
        _require(isinstance(provider, FeatureProvider), "feature_provider_invalid")
        _require(set(excluded_by_fold) == set(FOLDS), "mask_fold_scope_mismatch")
        normalized: dict[str, tuple[str | int, ...]] = {}
        for fold in FOLDS:
            values = tuple(excluded_by_fold[fold])
            _require(
                len(values) > 0
                and all(
                    (isinstance(value, str) and bool(value))
                    or (type(value) is int and value >= 0)
                    for value in values
                ),
                "excluded_predictor_reference_invalid",
            )
            normalized[fold] = values
        self.provider = provider
        self.excluded_by_fold = normalized

    def fit_encoder(self, train: Any, family: str, transform_id: str) -> Mapping[str, Any]:
        self._fold(transform_id)
        return self.provider.fit_encoder(train, family, transform_id)

    @staticmethod
    def _fold(transform_id: str) -> str:
        _require(
            isinstance(transform_id, str)
            and transform_id.startswith("cv_")
            and transform_id[3:] in FOLDS,
            "reduced_transform_not_inner_fold",
        )
        return transform_id[3:]

    def excluded_indices(self, batch: FeatureBatch) -> tuple[int, ...]:
        fold = self._fold(batch.transform_id)
        indices: set[int] = set()
        for reference in self.excluded_by_fold[fold]:
            if type(reference) is int:
                index = reference
            else:
                _require(reference in batch.feature_names, "excluded_predictor_name_missing")
                index = batch.feature_names.index(reference)
            _require(0 <= index < batch.continuous_count, "excluded_predictor_not_continuous")
            indices.add(index)
        _require(bool(indices), "excluded_predictor_set_empty")
        return tuple(sorted(indices))

    def materialize(
        self, rows: Any, transform_id: str, encoder_state: Mapping[str, Any]
    ) -> FeatureBatch:
        batch = self.provider.materialize(rows, transform_id, encoder_state)
        indices = self.excluded_indices(batch)
        matrix = np.array(batch.x, copy=True)
        matrix[:, indices] = 0.0
        return replace(batch, x=matrix)


def build_conventional_plan(
    catalog: ConventionalControlCatalog, stage: str
) -> tuple[ConventionalLeaf, ...]:
    if stage == "screen":
        endpoints = SCREEN_ENDPOINTS
    elif stage == "confirmation":
        endpoints = CONFIRMATION_NEW_ENDPOINTS
    else:
        raise ConventionalSensitivityError("unknown_conventional_stage")
    leaves = tuple(
        ConventionalLeaf(
            species,
            fraction,
            ladder,
            family,
            catalog.selected_candidate(species, fraction, ladder, family),
            seed,
        )
        for species in SPECIES
        for fraction, ladder in endpoints
        for family in FAMILIES
        for seed in SEEDS_BY_FAMILY[family]
    )
    expected = 384 if stage == "screen" else 512
    _require(len(leaves) == expected and all(_leaf_tuple(leaf) in catalog.leaf_keys for leaf in leaves), "conventional_plan_drift")
    return leaves


def build_conventional_analysis_plan(
    catalog: ConventionalControlCatalog, stage: str
) -> tuple[ConventionalLeaf, ...]:
    """Return the exact leaves contributing to a stage's descriptive analysis."""
    leaves = build_conventional_plan(catalog, stage)
    if stage == "screen":
        return leaves
    reused = tuple(
        leaf
        for leaf in build_conventional_plan(catalog, "screen")
        if (leaf.fraction_id, leaf.ladder_id) == ("fraction100", "full")
    )
    combined = (*leaves, *reused)
    _require(
        len(reused) == 128
        and len(combined) == 640
        and len(set(combined)) == len(combined)
        and {leaf.endpoint for leaf in combined}
        == {_endpoint_name(endpoint) for endpoint in CONFIRMATION_ANALYSIS_ENDPOINTS},
        "conventional_confirmation_analysis_plan_drift",
    )
    return combined


def stage_counts(stage: str) -> dict[str, int]:
    endpoints = len(SCREEN_ENDPOINTS) if stage == "screen" else len(CONFIRMATION_NEW_ENDPOINTS) if stage == "confirmation" else 0
    if not endpoints:
        raise ConventionalSensitivityError("unknown_conventional_stage")
    species_endpoints = len(SPECIES) * endpoints
    leaves = species_endpoints * sum(len(SEEDS_BY_FAMILY[family]) for family in FAMILIES)
    fold_units = leaves * len(FOLDS)
    physical_fits = species_endpoints * (
        sum(len(SEEDS_BY_FAMILY[family]) * len(FOLDS) for family in FAMILIES if family != "shallow_ann")
        + len(SEEDS_BY_FAMILY["shallow_ann"]) * len(FOLDS) * 2
    )
    return {
        "endpoints": endpoints,
        "leaves": leaves,
        "fold_units": fold_units,
        "physical_fits": physical_fits,
    }


def _endpoints_by_fold(leaf: ConventionalLeaf, broker: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for fold in FOLDS:
        training, _ = broker.inner(leaf.species_id, fold)
        lookup = "ladder00" if leaf.fraction_id == "fraction100" else leaf.ladder_id
        endpoint = build_ladders(training)[(leaf.fraction_id, lookup)]
        _require(
            endpoint.fraction_id == leaf.fraction_id
            and endpoint.ladder_id == leaf.ladder_id,
            "endpoint_identity_mismatch",
        )
        result[fold] = endpoint
    return result


def run_selected_leaf(
    catalog: ConventionalControlCatalog,
    leaf: ConventionalLeaf,
    broker: Any,
    provider: FeatureProvider | ZeroedContinuousProvider,
    *,
    goal029_config: Mapping[str, Any] | None = None,
) -> CandidateOOF:
    """Replay one frozen selected candidate/seed through Goal 029's OOF path."""
    validate_selected_leaf(catalog, leaf)
    candidate = CANONICAL_CANDIDATES.get(leaf.candidate_id)
    _require(candidate is not None and candidate.get("family") == leaf.model_family, "selected_candidate_not_canonical")
    result = run_candidate_oof(
        SelectionStratum(
            leaf.species_id,
            leaf.fraction_id,
            leaf.ladder_id,
            leaf.model_family,
            (leaf.seed_label,),
        ),
        FOLDS,
        _endpoints_by_fold(leaf, broker),
        candidate,
        broker,
        provider,
        build_adapter(leaf.model_family),
    )
    if goal029_config is not None:
        classify_leaf_warnings(ProductionLeaf(**asdict(leaf)), result, goal029_config)
    return result


def _row_token(key: Any) -> str:
    return json.dumps([key.species_id, key.grid_cell_id], separators=(",", ":"))


def result_prediction_digest(result: CandidateOOF) -> str:
    payload = []
    for fold in result.folds:
        payload.append(
            {
                "fold": fold.fold_id,
                "row_identity": digest_value(
                    [
                        (_row_token(key), int(value))
                        for key, value in zip(fold.keys, fold.y_true, strict=True)
                    ]
                ),
                "seed_scores": {
                    seed: hashlib.sha256(
                        np.asarray(fold.scores_by_seed[seed], dtype=np.float64).tobytes()
                    ).hexdigest()
                    for seed in result.stratum.ordered_selection_seeds
                },
            }
        )
    return digest_value(
        {
            "stratum": asdict(result.stratum),
            "candidate_id": result.candidate_id,
            "folds": payload,
            "best_epochs": {
                seed: record.best_epochs_by_fold
                for seed, record in result.neural_epochs_by_seed.items()
            },
        }
    )


def result_row_identity_digest(result: CandidateOOF) -> str:
    return digest_value(
        [
            {
                "fold": fold.fold_id,
                "tokens": tuple(_row_token(key) for key in fold.keys),
                "y": np.asarray(fold.y_true, dtype=np.int8).tolist(),
            }
            for fold in result.folds
        ]
    )


def compare_result_to_control(
    result: CandidateOOF, control: ControlLeaf, *, atol: float = 0.0
) -> dict[str, Any]:
    leaf = control.leaf
    _require(
        result.candidate_id == leaf.candidate_id
        and result.stratum
        == SelectionStratum(
            leaf.species_id,
            leaf.fraction_id,
            leaf.ladder_id,
            leaf.model_family,
            (leaf.seed_label,),
        )
        and len(result.folds) == len(FOLDS),
        "full28_replay_identity_mismatch",
    )
    maximum = 0.0
    rows = 0
    for observed, expected in zip(result.folds, control.folds, strict=True):
        tokens = tuple(_row_token(key) for key in observed.keys)
        scores = np.asarray(observed.scores_by_seed[leaf.seed_label], dtype=np.float64)
        _require(
            observed.fold_id == expected.fold_id
            and tokens == expected.row_tokens
            and np.array_equal(observed.y_true.astype(np.int8), expected.y_true)
            and scores.shape == expected.scores.shape,
            "full28_replay_row_identity_mismatch",
        )
        difference = float(np.max(np.abs(scores - expected.scores)))
        _require(np.isfinite(difference) and difference <= atol, "full28_replay_prediction_mismatch")
        maximum = max(maximum, difference)
        rows += len(scores)
    receipt = {
        "schema_version": "goal039-conventional-full28-replay-v1",
        "leaf": asdict(leaf),
        "rows": rows,
        "maximum_abs_difference": maximum,
        "tolerance": float(atol),
        "control_row_identity_digest": control.row_identity_digest,
        "control_prediction_digest": control.prediction_digest,
        "replay_prediction_digest": result_prediction_digest(result),
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def validate_full28_canary_receipts(receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    _require(
        len(receipts) == len(FAMILIES)
        and {receipt.get("leaf", {}).get("model_family") for receipt in receipts}
        == set(FAMILIES),
        "full28_canary_family_scope_drift",
    )
    for receipt in receipts:
        body = dict(receipt)
        claimed = body.pop("receipt_digest", None)
        _require(
            claimed == digest_value(body)
            and receipt.get("maximum_abs_difference") <= receipt.get("tolerance")
            and receipt.get("outer_attempted") == receipt.get("outer_opened") == 0,
            "full28_canary_receipt_invalid",
        )
    output = {
        "families": list(FAMILIES),
        "replays": len(receipts),
        "maximum_abs_difference": max(float(row["maximum_abs_difference"]) for row in receipts),
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    output["receipt_digest"] = digest_value(output)
    return output


def compare_reduced_repeats(first: CandidateOOF, second: CandidateOOF) -> dict[str, Any]:
    first_digest = result_prediction_digest(first)
    second_digest = result_prediction_digest(second)
    first_rows = result_row_identity_digest(first)
    second_rows = result_row_identity_digest(second)
    _require(
        first_digest == second_digest and first_rows == second_rows,
        "reduced_repeat_not_deterministic",
    )
    receipt = {
        "schema_version": "goal039-conventional-reduced-repeat-v1",
        "candidate_id": first.candidate_id,
        "prediction_digest": first_digest,
        "row_identity_digest": first_rows,
        "exact": True,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    return receipt


def reduced_leaf_identity(
    leaf: ConventionalLeaf,
    *,
    stage: str,
    config_digest: str,
    source_fingerprint: str,
    control_manifest_digest: str,
    mask_digest_by_fold: Mapping[str, str],
) -> dict[str, Any]:
    _require(stage in {"screen", "confirmation"}, "reduced_leaf_stage_invalid")
    _require(
        all(_is_digest(value) for value in (config_digest, source_fingerprint, control_manifest_digest))
        and set(mask_digest_by_fold) == set(FOLDS)
        and all(_is_digest(value) for value in mask_digest_by_fold.values()),
        "reduced_leaf_authority_invalid",
    )
    payload = {
        "schema_version": "goal039-conventional-reduced-leaf-v1",
        "stage": stage,
        "leaf_task": asdict(leaf),
        "fit_seed_by_fold": {
            fold: derive_seed(leaf.task(fold), "fit") for fold in FOLDS
        },
        "config_digest": config_digest,
        "source_fingerprint": source_fingerprint,
        "control_manifest_digest": control_manifest_digest,
        "mask_digest_by_fold": {fold: mask_digest_by_fold[fold] for fold in FOLDS},
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    payload["identity_digest"] = digest_value(payload)
    return payload


def _validate_reduced_identity(identity: Mapping[str, Any]) -> ConventionalLeaf:
    body = dict(identity)
    claimed = body.pop("identity_digest", None)
    _require(
        _is_digest(claimed)
        and claimed == digest_value(body)
        and identity.get("schema_version") == "goal039-conventional-reduced-leaf-v1"
        and identity.get("stage") in {"screen", "confirmation"}
        and identity.get("outer_attempted") == identity.get("outer_opened") == 0,
        "reduced_leaf_identity_invalid",
    )
    try:
        leaf = ConventionalLeaf(**identity["leaf_task"])
    except (KeyError, TypeError) as exc:
        raise ConventionalSensitivityError("reduced_leaf_task_invalid") from exc
    _require(
        identity.get("fit_seed_by_fold")
        == {fold: derive_seed(leaf.task(fold), "fit") for fold in FOLDS}
        and set(identity.get("mask_digest_by_fold", {})) == set(FOLDS),
        "reduced_leaf_seed_or_mask_drift",
    )
    return leaf


def write_reduced_leaf(
    private_leaf_root: str | Path,
    identity: Mapping[str, Any],
    result: CandidateOOF,
) -> tuple[Path, bool]:
    leaf = _validate_reduced_identity(identity)
    _require(
        result.candidate_id == leaf.candidate_id
        and result.stratum.ordered_selection_seeds == (leaf.seed_label,),
        "reduced_leaf_result_mismatch",
    )
    return write_leaf_checkpoint(Path(private_leaf_root), identity, result)


def load_reduced_leaf(
    private_leaf_root: str | Path, identity: Mapping[str, Any]
) -> CandidateOOF:
    _validate_reduced_identity(identity)
    return load_leaf_checkpoint(
        Path(private_leaf_root) / str(identity["identity_digest"]), identity
    )


def inventory_status(
    private_leaf_root: str | Path,
    identities: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    root = Path(private_leaf_root)
    digests: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []
    complete: list[str] = []
    for identity in identities:
        _validate_reduced_identity(identity)
        digest = str(identity["identity_digest"])
        _require(digest not in digests, "duplicate_reduced_leaf_identity")
        digests.append(digest)
        path = root / digest
        if not path.exists() and not path.is_symlink():
            missing.append(digest)
            continue
        try:
            load_reduced_leaf(root, identity)
        except Exception:
            invalid.append(digest)
        else:
            complete.append(digest)
    return {
        "planned": len(identities),
        "complete": len(complete),
        "missing": len(missing),
        "invalid": len(invalid),
        "complete_inventory_digest": digest_value(sorted(complete)),
        "missing_identity_digests": sorted(missing),
        "invalid_identity_digests": sorted(invalid),
        "outer_attempted": 0,
        "outer_opened": 0,
    }


def _variant_metrics(
    labels_by_fold: Sequence[np.ndarray], scores_by_fold: Sequence[np.ndarray]
) -> dict[str, float]:
    _require(
        len(labels_by_fold) == len(scores_by_fold) == len(FOLDS),
        "conventional_fold_metric_inventory_drift",
    )
    threshold, _, _ = select_threshold(
        np.concatenate(labels_by_fold), np.concatenate(scores_by_fold)
    )
    fold_metrics = [
        binary_metrics(y, scores, threshold)
        for y, scores in zip(labels_by_fold, scores_by_fold, strict=True)
    ]
    _require(
        all(
            row["roc_auc"] is not None
            and row["tss"] is not None
            and row["mcc"] is not None
            for row in fold_metrics
        ),
        "conventional_metric_invalid",
    )
    return {
        metric: float(np.mean([row[metric] for row in fold_metrics]))
        for metric in ("roc_auc", "tss", "mcc")
    }


def aggregate_family_effects(
    catalog: ConventionalControlCatalog,
    reduced_results: Mapping[ConventionalLeaf, CandidateOOF],
    *,
    endpoints: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """Return aggregate-only reduced-minus-full effects for conventional context."""
    endpoint_tuple = tuple(endpoints)
    _require(
        len(endpoint_tuple) > 0
        and len(set(endpoint_tuple)) == len(endpoint_tuple)
        and set(endpoint_tuple) <= set(ENDPOINTS),
        "conventional_aggregate_endpoint_scope_invalid",
    )
    expected_leaves = tuple(
        ConventionalLeaf(
            species,
            fraction,
            ladder,
            family,
            catalog.selected_candidate(species, fraction, ladder, family),
            seed,
        )
        for species in SPECIES
        for fraction, ladder in endpoint_tuple
        for family in FAMILIES
        for seed in SEEDS_BY_FAMILY[family]
    )
    _require(set(reduced_results) == set(expected_leaves), "conventional_aggregate_leaf_inventory_drift")
    rows: list[dict[str, Any]] = []
    for species in SPECIES:
        for fraction, ladder in endpoint_tuple:
            for family in FAMILIES:
                candidate = catalog.selected_candidate(species, fraction, ladder, family)
                seeds = SEEDS_BY_FAMILY[family]
                reduced_by_seed = {
                    seed: reduced_results[
                        ConventionalLeaf(species, fraction, ladder, family, candidate, seed)
                    ]
                    for seed in seeds
                }
                control_by_seed = {
                    seed: load_control_leaf(
                        catalog,
                        ConventionalLeaf(species, fraction, ladder, family, candidate, seed),
                    )
                    for seed in seeds
                }
                all_y: list[np.ndarray] = []
                reduced_scores: list[np.ndarray] = []
                full_scores: list[np.ndarray] = []
                for fold_index, fold in enumerate(FOLDS):
                    reference = reduced_by_seed[seeds[0]].folds[fold_index]
                    tokens = tuple(_row_token(key) for key in reference.keys)
                    y = reference.y_true.astype(np.int8)
                    reduced_stack = []
                    full_stack = []
                    for seed in seeds:
                        reduced = reduced_by_seed[seed].folds[fold_index]
                        control = control_by_seed[seed].folds[fold_index]
                        _require(
                            reduced.fold_id == control.fold_id == fold
                            and tuple(_row_token(key) for key in reduced.keys) == tokens == control.row_tokens
                            and np.array_equal(reduced.y_true.astype(np.int8), y)
                            and np.array_equal(control.y_true, y),
                            "conventional_reduced_full_row_mismatch",
                        )
                        reduced_stack.append(np.asarray(reduced.scores_by_seed[seed], dtype=np.float64))
                        full_stack.append(control.scores)
                    all_y.append(y)
                    reduced_scores.append(np.mean(np.vstack(reduced_stack), axis=0))
                    full_scores.append(np.mean(np.vstack(full_stack), axis=0))
                reduced_metric = _variant_metrics(all_y, reduced_scores)
                full_metric = _variant_metrics(all_y, full_scores)
                rows.append(
                    {
                        "species": species,
                        "endpoint": _endpoint_name((fraction, ladder)),
                        "family": family,
                        "candidate": candidate,
                        "seed_count": len(seeds),
                        "full": full_metric,
                        "reduced": reduced_metric,
                        "delta": {
                            metric: reduced_metric[metric] - full_metric[metric]
                            for metric in ("roc_auc", "tss", "mcc")
                        },
                    }
                )
    summaries = []
    for endpoint in map(_endpoint_name, endpoint_tuple):
        for family in FAMILIES:
            selected = [row for row in rows if row["endpoint"] == endpoint and row["family"] == family]
            _require(len(selected) == len(SPECIES), "conventional_family_summary_drift")
            summaries.append(
                {
                    "endpoint": endpoint,
                    "family": family,
                    "species": len(selected),
                    "mean_delta": {
                        metric: float(np.mean([row["delta"][metric] for row in selected]))
                        for metric in ("roc_auc", "tss", "mcc")
                    },
                    "positive_species": {
                        metric: int(sum(row["delta"][metric] > 0 for row in selected))
                        for metric in ("roc_auc", "tss", "mcc")
                    },
                }
            )
    output = {
        "schema_version": "goal039-conventional-family-effects-v1",
        "endpoints": [_endpoint_name(endpoint) for endpoint in endpoint_tuple],
        "families": list(FAMILIES),
        "aggregation": "common_seed_mean_then_pooled_threshold_then_equal_fold_mean",
        "strata": len(rows),
        "leaf_count": len(expected_leaves),
        "species_family_effects": rows,
        "family_endpoint_summaries": summaries,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    output["receipt_digest"] = digest_value(output)
    return output
