"""Sealed conventional-baseline production for Goal029.

The module deliberately separates private leaf execution from deterministic
reduction and publication. Real outer rows never enter this API.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import math
import multiprocessing
import os
import platform
import re
import resource
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score

from .inner_cv import (
    CandidateOOF,
    FoldEpochs,
    FoldOOF,
    InnerCVError,
    NeuralFoldReceipt,
    SelectionStratum,
    _rowset_for_keys,
    _tss,
    refit_outer_training,
    run_candidate_oof,
    select_candidate,
    select_threshold,
)
from .model_adapters import (
    CANONICAL_CANDIDATES,
    FitReport,
    ModelAdapterError,
    build_adapter,
    load_fitted_model,
)
from .modeling_contract import (
    FeatureBatch,
    FeatureProvider,
    LazyFeatureSubstrate,
    ModelingContractError,
    OuterVault,
    RowKey,
    RowSet,
    SplitBroker,
    TaskKey,
    TransformingFeatureSubstrate,
    _normalize_response_pa,
    _read_bound_json,
    _read_private_records,
    canonical_json,
    derive_seed,
    ingest_synthetic_foundation,
    load_run_config,
    sha256_file,
    task_id,
)
from .target_subsets import SubsetEndpoint, build_ladders


class Goal029Error(ModelingContractError):
    """Raised when the frozen Goal029 production contract is violated."""


SPECIES = (
    "thylogale_billardierii",
    "notamacropus_rufogriseus",
    "trichosurus_vulpecula",
    "pseudocheirus_peregrinus",
    "vombatus_ursinus",
    "sarcophilus_harrisii",
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
)
ENDPOINTS = (
    ("fraction25", "ladder00"),
    ("fraction25", "ladder01"),
    ("fraction25", "ladder02"),
    ("fraction50", "ladder00"),
    ("fraction50", "ladder01"),
    ("fraction50", "ladder02"),
    ("fraction100", "full"),
)
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
FAMILIES = (
    "intercept",
    "elastic_net",
    "gam",
    "random_forest",
    "hist_gradient_boosting",
    "shallow_ann",
)
CANDIDATE_IDS = {
    "intercept": ("null00",),
    "elastic_net": tuple(f"enet{i:02d}" for i in range(10)),
    "gam": tuple(f"gam{i:02d}" for i in range(5)),
    "random_forest": tuple(f"rf{i:02d}" for i in range(7)),
    "hist_gradient_boosting": tuple(f"hgb{i:02d}" for i in range(7)),
    "shallow_ann": tuple(f"ann{i:02d}" for i in range(6)),
}
SEEDS_BY_FAMILY = {
    "intercept": ("seed00",),
    "elastic_net": tuple(f"seed{i:02d}" for i in range(5)),
    "gam": ("seed00",),
    "random_forest": tuple(f"seed{i:02d}" for i in range(5)),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": tuple(f"seed{i:02d}" for i in range(5)),
}
ANCHORS = {
    "elastic_net": "enet00",
    "gam": "gam01",
    "random_forest": "rf02",
    "hist_gradient_boosting": "hgb04",
    "shallow_ann": "ann01",
}
FAMILY_STRATA_COUNT = len(SPECIES) * len(ENDPOINTS) * len(FAMILIES)
CANDIDATE_STRATA_COUNT = len(SPECIES) * len(ENDPOINTS) * sum(
    len(CANDIDATE_IDS[family]) for family in FAMILIES
)
LEAF_COUNT = len(SPECIES) * len(ENDPOINTS) * sum(
    len(CANDIDATE_IDS[family]) * len(SEEDS_BY_FAMILY[family])
    for family in FAMILIES
)
SELECTED_REFIT_MAXIMUM = len(SPECIES) * len(ENDPOINTS) * sum(
    len(SEEDS_BY_FAMILY[family]) for family in FAMILIES
)

_HEX64 = re.compile(r"[0-9a-f]{64}")
_FORBIDDEN_TRACKED_KEYS = {
    "grid_cell_id",
    "coordinates",
    "row_payloads",
    "private_paths",
    "site_ids",
    "camera_ids",
    "observation_timing",
    "roc_auc",
    "tss",
    "threshold",
    "oof_score",
}
_CANONICAL_CONFIG_DIGEST = (
    "b9c61ea67eac4c7bc5be10c59d789674bf3621d18a65463962838982ae0cce66"
)


@dataclass(frozen=True, order=True)
class ProductionLeaf:
    species_id: str
    fraction_id: str
    ladder_id: str
    model_family: str
    candidate_id: str
    seed_label: str

    def task(self, transform_id: str = "all_cv") -> TaskKey:
        return TaskKey(
            self.species_id,
            transform_id,
            self.fraction_id,
            self.ladder_id,
            self.model_family,
            self.candidate_id,
            self.seed_label,
        )

    @property
    def leaf_id(self) -> str:
        return task_id(self.task())

    @property
    def family_stratum(self) -> tuple[str, str, str, str]:
        return (
            self.species_id,
            self.fraction_id,
            self.ladder_id,
            self.model_family,
        )

    @property
    def candidate_stratum(self) -> tuple[str, str, str, str, str]:
        return (*self.family_stratum, self.candidate_id)


@dataclass(frozen=True)
class ExecutionContext:
    source_tree_digest: str
    config_digest: str
    uv_lock_digest: str
    runtime_fingerprint: str
    host_id: str
    upstream_binding_digest: str


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal029Error("json_read_failed") from exc
    if not isinstance(value, Mapping):
        raise Goal029Error("json_mapping_required")
    return value


def _safe_bound_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise Goal029Error("binding_path_invalid")
    target = (Path(root) / path).resolve()
    if Path(root).resolve() not in target.parents:
        raise Goal029Error("binding_path_escape")
    return target


def production_plan(config: Mapping[str, Any] | None = None) -> tuple[ProductionLeaf, ...]:
    plan = tuple(
        ProductionLeaf(species, fraction, ladder, family, candidate, seed)
        for species in SPECIES
        for fraction, ladder in ENDPOINTS
        for family in FAMILIES
        for candidate in CANDIDATE_IDS[family]
        for seed in SEEDS_BY_FAMILY[family]
    )
    if len(plan) != LEAF_COUNT or len(set(plan)) != LEAF_COUNT:
        raise Goal029Error("production_plan_internal_mismatch")
    if config is not None:
        declared = config["models"]["planned_counts"]
        expected = {
            "species_endpoint_strata": len(SPECIES) * len(ENDPOINTS),
            "family_strata": FAMILY_STRATA_COUNT,
            "candidate_strata": CANDIDATE_STRATA_COUNT,
            "candidate_seed_leaves": LEAF_COUNT,
            "oof_producing_fold_units": LEAF_COUNT * len(FOLDS),
            "actual_inner_estimator_fits": (
                (LEAF_COUNT - len(SPECIES) * len(ENDPOINTS) * 6 * 5)
                * len(FOLDS)
                + len(SPECIES) * len(ENDPOINTS) * 6 * 5 * len(FOLDS) * 2
            ),
            "selected_refits_maximum": SELECTED_REFIT_MAXIMUM,
        }
        if declared != expected:
            raise Goal029Error("declared_plan_counts_mismatch")
    return plan


def calibration_plan(config: Mapping[str, Any]) -> tuple[ProductionLeaf, ...]:
    try:
        leaves = tuple(ProductionLeaf(*values) for values in config["calibration"]["leaves"])
    except (KeyError, TypeError) as exc:
        raise Goal029Error("calibration_plan_invalid") from exc
    if len(leaves) != 30 or len(set(leaves)) != 30:
        raise Goal029Error("calibration_count_or_duplicate")
    full = set(production_plan())
    if not set(leaves) <= full:
        raise Goal029Error("calibration_not_production_subset")
    if set(leaf.species_id for leaf in leaves) != set(SPECIES):
        raise Goal029Error("calibration_species_coverage")
    if set((leaf.fraction_id, leaf.ladder_id) for leaf in leaves) != set(ENDPOINTS):
        raise Goal029Error("calibration_endpoint_coverage")
    if set(leaf.model_family for leaf in leaves) != set(FAMILIES):
        raise Goal029Error("calibration_family_coverage")
    if set(leaf.seed_label for leaf in leaves) != {
        f"seed{i:02d}" for i in range(5)
    }:
        raise Goal029Error("calibration_seed_coverage")
    expected_extremes = {
        "elastic_net": {"enet00", "enet09"},
        "gam": {"gam00", "gam04"},
        "random_forest": {"rf00", "rf06"},
        "hist_gradient_boosting": {"hgb00", "hgb06"},
        "shallow_ann": {"ann00", "ann05"},
    }
    for family, candidate_ids in expected_extremes.items():
        if not candidate_ids <= {
            leaf.candidate_id for leaf in leaves if leaf.model_family == family
        }:
            raise Goal029Error(f"calibration_extreme_coverage:{family}")
    return leaves


def load_goal029_config(root: Path, path: Path | None = None) -> Mapping[str, Any]:
    root = Path(root).resolve()
    path = path or root / "config/conventional_baseline_production.json"
    if not Path(path).is_absolute():
        path = root / path
    config = _read_json(Path(path))
    if _sha(config) != _CANONICAL_CONFIG_DIGEST:
        raise Goal029Error("config_frozen_digest_mismatch")
    expected_sections = [
        "identity",
        "bindings",
        "scope",
        "partitions",
        "models",
        "failure_policy",
        "execution",
        "checkpoints",
        "hardening",
        "calibration",
        "validation",
        "artifacts",
        "non_goals",
    ]
    if list(config) != expected_sections:
        raise Goal029Error("config_sections_mismatch")
    identity = config["identity"]
    if identity != {
        "schema_version": "1.0",
        "goal_id": "goal029-conventional-baseline-production-2026-07-30",
        "protocol_version": "0.1",
        "master_seed": "dsdm-goal028-v1",
        "created_at": "2026-07-30",
    }:
        raise Goal029Error("config_identity_mismatch")
    if tuple(config["scope"]["species"]) != SPECIES:
        raise Goal029Error("species_scope_mismatch")
    if config["scope"]["excluded_species"] != ["macropus_giganteus"]:
        raise Goal029Error("excluded_species_mismatch")
    if (
        config["scope"]["complete_response_rows"] != 12711
        or config["scope"]["outer_training_rows"] != 11039
        or config["scope"]["predictor_count"] != 28
        or config["scope"]["row_weight"] != 1
        or any(
            config["scope"][key] is not False
            for key in (
                "balancing",
                "resampling",
                "imputation",
                "response_driven_feature_selection",
            )
        )
        or config["scope"]["real_outer_attempted_open_limit"] != 0
        or config["scope"]["real_outer_open_limit"] != 0
    ):
        raise Goal029Error("scope_contract_mismatch")
    if tuple(config["partitions"]["folds"]) != FOLDS:
        raise Goal029Error("fold_contract_mismatch")
    if tuple(config["partitions"]["endpoints"]) != tuple(
        f"{fraction}/{ladder}" for fraction, ladder in ENDPOINTS
    ):
        raise Goal029Error("endpoint_contract_mismatch")
    if tuple(config["models"]["families"]) != FAMILIES:
        raise Goal029Error("family_contract_mismatch")
    if {
        family: tuple(values)
        for family, values in config["models"]["candidate_ids"].items()
    } != CANDIDATE_IDS:
        raise Goal029Error("candidate_registry_mismatch")
    if {
        family: tuple(values)
        for family, values in config["models"]["seed_labels_by_family"].items()
    } != SEEDS_BY_FAMILY:
        raise Goal029Error("seed_registry_mismatch")
    if config["failure_policy"]["anchors"] != ANCHORS:
        raise Goal029Error("anchor_policy_mismatch")
    if config["failure_policy"]["mandatory_null"] != "null00":
        raise Goal029Error("mandatory_null_mismatch")
    if config["failure_policy"]["minimum_complete_valid_candidates_by_family"] != {
        family: (1 if family == "intercept" else 2) for family in FAMILIES
    }:
        raise Goal029Error("family_quorum_policy_mismatch")
    if config["execution"]["worker_ladder"] != [1, 2, 4]:
        raise Goal029Error("worker_ladder_mismatch")
    if config["execution"]["minimum_free_memory_bytes"] != 6 * 1024**3:
        raise Goal029Error("memory_headroom_mismatch")
    if config["validation"]["source_to_result_audit"]["minimum_fraction"] != 0.05:
        raise Goal029Error("audit_fraction_mismatch")
    for family, ids in CANDIDATE_IDS.items():
        for candidate_id in ids:
            candidate = CANONICAL_CANDIDATES.get(candidate_id)
            if candidate is None or candidate.get("family") != family:
                raise Goal029Error(f"candidate_authority_mismatch:{candidate_id}")
    bindings = config["bindings"]
    for role, record in bindings.items():
        if not isinstance(record, Mapping):
            raise Goal029Error(f"binding_invalid:{role}")
        target = _safe_bound_path(root, str(record.get("path", "")))
        expected = record.get("sha256")
        if (
            target.is_symlink()
            or not target.is_file()
            or not isinstance(expected, str)
            or _HEX64.fullmatch(expected) is None
            or sha256_file(target) != expected
        ):
            raise Goal029Error(f"binding_digest_mismatch:{role}")
    # This revalidates all private upstream authority digests without opening
    # private products.
    load_run_config(root, root / config["bindings"]["goal028_config"]["path"])
    production_plan(config)
    calibration_plan(config)
    return config


def source_tree_digest(root: Path, config: Mapping[str, Any]) -> str:
    files: list[dict[str, str]] = []
    source_glob = config["execution"].get("runtime_source_glob")
    if source_glob != "src/dsdm_phase1/*.py":
        raise Goal029Error("runtime_source_glob_mismatch")
    source_paths = sorted(Path(root).glob(source_glob))
    if not source_paths or not any(path.name == "__init__.py" for path in source_paths):
        raise Goal029Error("runtime_source_closure_incomplete")
    for path in source_paths:
        if path.is_symlink() or not path.is_file():
            raise Goal029Error("runtime_source_missing")
        files.append(
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
            }
        )
    for raw in config["execution"]["runtime_critical_paths"]:
        path = _safe_bound_path(Path(root), raw)
        if path.is_symlink() or not path.is_file():
            raise Goal029Error("runtime_source_missing")
        files.append({"path": raw, "sha256": sha256_file(path)})
    if len({record["path"] for record in files}) != len(files):
        raise Goal029Error("runtime_source_duplicate")
    return _sha(files)


def runtime_fingerprint() -> str:
    packages = {}
    for name in ("numpy", "scipy", "scikit-learn", "pygam", "pyarrow", "torch"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise Goal029Error(f"runtime_package_missing:{name}") from exc
    return _sha(
        {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "packages": packages,
        }
    )


def execution_context(root: Path, config: Mapping[str, Any]) -> ExecutionContext:
    bindings = [
        {
            "role": role,
            "path": record["path"],
            "sha256": record["sha256"],
        }
        for role, record in sorted(config["bindings"].items())
    ]
    return ExecutionContext(
        source_tree_digest(root, config),
        _sha(config),
        sha256_file(Path(root) / "uv.lock"),
        runtime_fingerprint(),
        socket.gethostname(),
        _sha(bindings),
    )


def audit_salt(
    plan: Sequence[ProductionLeaf], context: ExecutionContext
) -> str:
    return _sha(
        {
            "canonical_plan": [asdict(leaf) for leaf in plan],
            "execution_source_tree_digest": context.source_tree_digest,
            "config_digest": context.config_digest,
            "upstream_binding_digest": context.upstream_binding_digest,
        }
    )


def _audit_leaf_hash(salt: str, leaf: ProductionLeaf) -> str:
    fields = (
        salt,
        leaf.species_id,
        leaf.fraction_id,
        leaf.ladder_id,
        leaf.model_family,
        leaf.candidate_id,
        leaf.seed_label,
    )
    return hashlib.sha256("\x1f".join(fields).encode("utf-8")).hexdigest()


def audit_plan(
    plan: Sequence[ProductionLeaf], salt: str
) -> tuple[ProductionLeaf, ...]:
    if _HEX64.fullmatch(salt) is None:
        raise Goal029Error("audit_salt_invalid")
    canonical = tuple(plan)
    if len(canonical) != len(set(canonical)):
        raise Goal029Error("audit_plan_duplicate")
    selected: set[ProductionLeaf] = set()
    groups: dict[tuple[str, str, str, str], list[ProductionLeaf]] = {}
    for leaf in canonical:
        groups.setdefault(leaf.family_stratum, []).append(leaf)
    for group in groups.values():
        selected.add(
            min(group, key=lambda leaf: _audit_leaf_hash(salt, leaf))
        )
    for candidate_id in sorted({leaf.candidate_id for leaf in canonical}):
        if not any(leaf.candidate_id == candidate_id for leaf in selected):
            options = [leaf for leaf in canonical if leaf.candidate_id == candidate_id]
            selected.add(
                min(options, key=lambda leaf: _audit_leaf_hash(salt, leaf))
            )
    for seed_label in sorted({leaf.seed_label for leaf in canonical}):
        if not any(leaf.seed_label == seed_label for leaf in selected):
            options = [leaf for leaf in canonical if leaf.seed_label == seed_label]
            selected.add(
                min(options, key=lambda leaf: _audit_leaf_hash(salt, leaf))
            )
    target = math.ceil(0.05 * len(canonical))
    for leaf in sorted(
        (leaf for leaf in canonical if leaf not in selected),
        key=lambda item: _audit_leaf_hash(salt, item),
    ):
        if len(selected) >= target:
            break
        selected.add(leaf)
    ordered = tuple(leaf for leaf in canonical if leaf in selected)
    if (
        len(ordered) < target
        or {leaf.family_stratum for leaf in ordered} != set(groups)
        or {leaf.candidate_id for leaf in ordered}
        != {leaf.candidate_id for leaf in canonical}
        or {leaf.seed_label for leaf in ordered}
        != {leaf.seed_label for leaf in canonical}
    ):
        raise Goal029Error("audit_coverage_mismatch")
    return ordered


def _row_token(key: RowKey) -> str:
    return canonical_json([key.species_id, key.grid_cell_id])


def _parse_row_token(value: str) -> RowKey:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise Goal029Error("row_token_invalid") from exc
    if (
        not isinstance(parsed, list)
        or len(parsed) != 2
        or any(type(item) is not str or not item for item in parsed)
    ):
        raise Goal029Error("row_token_invalid")
    return RowKey(parsed[0], parsed[1])


def _endpoint(
    rows: RowSet, fraction_id: str, ladder_id: str
) -> SubsetEndpoint:
    lookup = "ladder00" if fraction_id == "fraction100" else ladder_id
    endpoint = build_ladders(rows)[(fraction_id, lookup)]
    if endpoint.fraction_id != fraction_id or endpoint.ladder_id != ladder_id:
        raise Goal029Error("endpoint_identity_mismatch")
    return endpoint


def _membership_record(
    leaf: ProductionLeaf,
    split_id: str,
    endpoint: SubsetEndpoint,
) -> Mapping[str, Any]:
    tokens = [_row_token(key) for key in endpoint.keys]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "species_id": leaf.species_id,
        "fraction_id": leaf.fraction_id,
        "ladder_id": leaf.ladder_id,
        "split_id": split_id,
        "subset_digest": endpoint.subset_digest,
        "count": len(tokens),
        "membership_digest": _sha(tokens),
        "row_tokens": tokens,
    }
    payload["record_digest"] = _sha(payload)
    return payload


def membership_records(
    leaf: ProductionLeaf, broker: SplitBroker
) -> Mapping[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for fold in FOLDS:
        training, _ = broker.inner(leaf.species_id, fold)
        endpoint = _endpoint(training, leaf.fraction_id, leaf.ladder_id)
        split_id = f"cv_{fold}"
        records[split_id] = _membership_record(leaf, split_id, endpoint)
    outer = broker.outer_training(leaf.species_id)
    endpoint = _endpoint(outer, leaf.fraction_id, leaf.ladder_id)
    records["outer"] = _membership_record(leaf, "outer", endpoint)
    _validate_membership_records(records, leaf)
    return records


def _validate_membership_records(
    records: Mapping[str, Mapping[str, Any]], leaf: ProductionLeaf
) -> None:
    expected_splits = {*(f"cv_{fold}" for fold in FOLDS), "outer"}
    if set(records) != expected_splits:
        raise Goal029Error("membership_split_set_mismatch")
    for split_id, record in records.items():
        body = dict(record)
        claimed = body.pop("record_digest", None)
        if claimed != _sha(body):
            raise Goal029Error("membership_record_digest_mismatch")
        tokens = record.get("row_tokens")
        if (
            record.get("schema_version") != "1.0"
            or record.get("species_id") != leaf.species_id
            or record.get("fraction_id") != leaf.fraction_id
            or record.get("ladder_id") != leaf.ladder_id
            or record.get("split_id") != split_id
            or not isinstance(tokens, list)
            or len(tokens) != record.get("count")
            or len(set(tokens)) != len(tokens)
            or _sha(tokens) != record.get("membership_digest")
        ):
            raise Goal029Error("membership_rows_invalid")
        for token in tokens:
            _parse_row_token(token)


def encoder_digests(
    leaf: ProductionLeaf,
    broker: SplitBroker,
    provider: FeatureProvider,
    memberships: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, str]:
    _validate_membership_records(memberships, leaf)
    output: dict[str, str] = {}
    for fold in FOLDS:
        training, _ = broker.inner(leaf.species_id, fold)
        endpoint = _endpoint(training, leaf.fraction_id, leaf.ladder_id)
        rows = _rowset_for_keys(training, endpoint.keys)
        encoder = provider.fit_encoder(rows, leaf.model_family, f"cv_{fold}")
        output[f"cv_{fold}"] = str(encoder["encoder_digest"])
    outer = broker.outer_training(leaf.species_id)
    endpoint = _endpoint(outer, leaf.fraction_id, leaf.ladder_id)
    rows = _rowset_for_keys(outer, endpoint.keys)
    encoder = provider.fit_encoder(rows, leaf.model_family, "outer")
    output["outer"] = str(encoder["encoder_digest"])
    if any(_HEX64.fullmatch(value) is None for value in output.values()):
        raise Goal029Error("encoder_digest_invalid")
    return output


def leaf_identity(
    leaf: ProductionLeaf,
    context: ExecutionContext,
    memberships: Mapping[str, Mapping[str, Any]],
    encoders: Mapping[str, str],
) -> Mapping[str, Any]:
    _validate_membership_records(memberships, leaf)
    expected_splits = {*(f"cv_{fold}" for fold in FOLDS), "outer"}
    if set(encoders) != expected_splits:
        raise Goal029Error("encoder_identity_incomplete")
    payload = {
        "schema_version": "1.0",
        "execution_source_tree_digest": context.source_tree_digest,
        "config_digest": context.config_digest,
        "uv_lock_digest": context.uv_lock_digest,
        "runtime_fingerprint": context.runtime_fingerprint,
        "host_id": context.host_id,
        "upstream_binding_digest": context.upstream_binding_digest,
        "leaf_task": asdict(leaf),
        "split_membership_digests": {
            split: memberships[split]["record_digest"]
            for split in sorted(expected_splits)
        },
        "fold_encoder_digests": {
            split: encoders[split] for split in sorted(expected_splits)
        },
    }
    payload["identity_digest"] = _sha(payload)
    return payload


def classify_leaf_warnings(
    leaf: ProductionLeaf, result: CandidateOOF, config: Mapping[str, Any]
) -> tuple[str, ...]:
    if result.candidate_id != leaf.candidate_id:
        raise Goal029Error("warning_result_candidate_mismatch")
    messages: list[str] = []
    for reports in result.fit_reports_by_seed.values():
        for report in reports:
            if not report.converged:
                raise Goal029Error("nonconverged_report")
            if report.neural_stop_status not in {
                None,
                "patience_stop",
                "max_epochs_reached",
            }:
                raise Goal029Error("unknown_neural_stop_status")
            messages.extend(report.warnings)
    allowed_substrings = tuple(
        config["failure_policy"]["allowed_informational_warning_substrings"]
    )
    allowed_soft = set(config["failure_policy"]["allowed_soft_warning_codes"])
    accepted: list[str] = []
    for message in messages:
        if message in allowed_soft or any(
            substring in message for substring in allowed_substrings
        ):
            accepted.append(message)
        else:
            raise Goal029Error(f"unclassified_warning:{message}")
    return tuple(accepted)


def run_leaf(
    leaf: ProductionLeaf,
    broker: SplitBroker,
    provider: FeatureProvider,
    config: Mapping[str, Any],
) -> CandidateOOF:
    if leaf not in set(production_plan()):
        raise Goal029Error("leaf_not_in_frozen_plan")
    endpoints = {
        fold: _endpoint(
            broker.inner(leaf.species_id, fold)[0],
            leaf.fraction_id,
            leaf.ladder_id,
        )
        for fold in FOLDS
    }
    result = run_candidate_oof(
        SelectionStratum(
            leaf.species_id,
            leaf.fraction_id,
            leaf.ladder_id,
            leaf.model_family,
            (leaf.seed_label,),
        ),
        FOLDS,
        endpoints,
        CANONICAL_CANDIDATES[leaf.candidate_id],
        broker,
        provider,
        build_adapter(leaf.model_family),
    )
    classify_leaf_warnings(leaf, result, config)
    return result


def ingest_production_foundation(
    root: Path, config: Mapping[str, Any]
) -> tuple[SplitBroker, FeatureProvider, OuterVault]:
    """Build the eight-species outer-training view from frozen Goal028 inputs."""
    root = Path(root)
    foundation = load_run_config(
        root, root / config["bindings"]["goal028_config"]["path"]
    )
    bindings = foundation["bindings"]
    response_records = _read_private_records(
        root, bindings["goal025_response_partitioned"]
    )
    normalized: list[Mapping[str, Any]] = []
    observed_species: set[str] = set()
    for raw in response_records:
        if not isinstance(raw, Mapping):
            raise Goal029Error("response_record_invalid")
        species_id = raw.get("species_id")
        if type(species_id) is not str or not species_id:
            raise Goal029Error("response_species_invalid")
        row = dict(raw)
        row["pa"] = _normalize_response_pa(raw.get("pa"))
        normalized.append(row)
        observed_species.add(species_id)
    if (
        len(normalized) != config["scope"]["complete_response_rows"]
        or observed_species != set(SPECIES)
    ):
        raise Goal029Error("complete_response_scope_mismatch")

    map_records = _read_private_records(root, bindings["goal024_map"])
    fit_parameters = _read_bound_json(root, bindings["goal026_fit_parameters"])
    feature_contract = _read_bound_json(root, bindings["goal026_feature_contract"])
    continuous = tuple(feature_contract.get("continuous_predictors", ()))
    categorical = tuple(feature_contract.get("categorical_predictors", ()))
    if len(continuous) != 25 or len(categorical) != 3:
        raise Goal029Error("feature_contract_schema_drift")
    feature_by_cell: dict[str, Mapping[str, Any]] = {}
    for record in map_records:
        cell = record.get("grid_cell_id")
        if type(cell) is not str or not cell or cell in feature_by_cell:
            raise Goal029Error("feature_key_invalid_or_duplicate")
        if record.get("predictor_complete") not in (True, "true", "True", 1, "1"):
            raise Goal029Error("incomplete_predictor_row")
        try:
            feature_by_cell[cell] = {
                name: float(record[name]) if name in continuous else str(record[name])
                for name in continuous + categorical
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise Goal029Error("feature_value_invalid") from exc

    outer_records: list[Mapping[str, Any]] = []
    held_records: list[Mapping[str, Any]] = []
    fold_by_key: dict[RowKey, str] = {}
    all_keys: set[RowKey] = set()
    for row in normalized:
        species_id = row.get("species_id")
        grid_cell_id = row.get("grid_cell_id")
        if (
            type(species_id) is not str
            or not species_id
            or type(grid_cell_id) is not str
            or not grid_cell_id
        ):
            raise Goal029Error("row_key_invalid")
        key = RowKey(species_id, grid_cell_id)
        if key in all_keys:
            raise Goal029Error("duplicate_species_cell")
        all_keys.add(key)
        role = row.get("outer_role")
        fold = row.get("cv_fold")
        if (
            role not in {"outer_train", "test"}
            or (
                role == "outer_train"
                and (type(fold) is not str or fold not in FOLDS)
            )
            or (role == "test" and fold not in ("", None))
        ):
            raise Goal029Error("partition_or_fold_invalid")
        if role == "outer_train":
            outer_records.append(row)
            fold_by_key[key] = fold
        else:
            held_records.append(row)
    if (
        len(outer_records) != config["scope"]["outer_training_rows"]
        or {row["species_id"] for row in outer_records} != set(SPECIES)
    ):
        raise Goal029Error("outer_training_scope_mismatch")
    outer = RowSet.from_records(outer_records)
    raw_values: dict[RowKey, Mapping[str, Any]] = {}
    for key in outer.keys:
        values = feature_by_cell.get(key.grid_cell_id)
        if values is None:
            raise Goal029Error("outer_feature_join_incomplete")
        raw_values[key] = values
    substrate = TransformingFeatureSubstrate(
        raw_values, fit_parameters, continuous, categorical
    )
    broker = SplitBroker(outer, fold_by_key)
    provider = FeatureProvider(substrate, frozenset(outer.keys))
    vault = OuterVault(
        RowSet.from_records(held_records) if held_records else None,
        synthetic=False,
    )
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("real_outer_access_detected")
    return broker, provider, vault


def class_support_scan(broker: SplitBroker) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    for species_id in SPECIES:
        for fraction_id, ladder_id in ENDPOINTS:
            fold_records = []
            for fold in FOLDS:
                training, assessment = broker.inner(species_id, fold)
                endpoint = _endpoint(training, fraction_id, ladder_id)
                endpoint_rows = _rowset_for_keys(training, endpoint.keys)
                train_classes = sorted(set(int(value) for value in endpoint_rows.pa))
                assessment_classes = sorted(
                    set(int(value) for value in assessment.pa)
                )
                if train_classes != [0, 1] or assessment_classes != [0, 1]:
                    raise Goal029Error("class_support_scan_failed")
                fold_records.append(
                    {
                        "fold_id": fold,
                        "endpoint_zero_count": int(np.sum(endpoint_rows.pa == 0)),
                        "endpoint_one_count": int(np.sum(endpoint_rows.pa == 1)),
                        "assessment_zero_count": int(np.sum(assessment.pa == 0)),
                        "assessment_one_count": int(np.sum(assessment.pa == 1)),
                    }
                )
            outer = broker.outer_training(species_id)
            outer_endpoint = _endpoint(outer, fraction_id, ladder_id)
            outer_rows = _rowset_for_keys(outer, outer_endpoint.keys)
            if sorted(set(int(value) for value in outer_rows.pa)) != [0, 1]:
                raise Goal029Error("class_support_outer_refit_failed")
            records.append(
                {
                    "species_id": species_id,
                    "fraction_id": fraction_id,
                    "ladder_id": ladder_id,
                    "folds": fold_records,
                    "outer_endpoint_zero_count": int(np.sum(outer_rows.pa == 0)),
                    "outer_endpoint_one_count": int(np.sum(outer_rows.pa == 1)),
                    "status": "pass",
                }
            )
    if len(records) != 56:
        raise Goal029Error("class_support_scan_count")
    return tuple(records)


def fragility_stress_plan() -> tuple[ProductionLeaf, ...]:
    return tuple(
        ProductionLeaf(
            species_id,
            fraction_id,
            ladder_id,
            "gam",
            candidate_id,
            "seed00",
        )
        for species_id in SPECIES
        for fraction_id, ladder_id in (
            ("fraction25", "ladder00"),
            ("fraction100", "full"),
        )
        for candidate_id in ("gam02", "gam03")
    )


def _available_memory_bytes() -> int:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        if page_size > 0 and available_pages > 0:
            return page_size * available_pages
    except (OSError, ValueError, KeyError):
        pass
    output = subprocess.check_output(["vm_stat"], text=True)
    match = re.search(r"page size of (\\d+) bytes", output)
    if match is None:
        raise Goal029Error("memory_telemetry_unavailable")
    page_size = int(match.group(1))
    pages = 0
    for label in ("Pages free", "Pages inactive", "Pages speculative"):
        found = re.search(rf"^{re.escape(label)}:\\s+(\\d+)\\.", output, re.MULTILINE)
        if found:
            pages += int(found.group(1))
    if pages <= 0:
        raise Goal029Error("memory_telemetry_unavailable")
    return page_size * pages


def _swap_used_bytes() -> int:
    output = subprocess.check_output(
        ["sysctl", "-n", "vm.swapusage"], text=True
    ).strip()
    match = re.search(r"used = ([0-9.]+)([MGT])", output)
    if match is None:
        raise Goal029Error("swap_telemetry_unavailable")
    multiplier = {"M": 1024**2, "G": 1024**3, "T": 1024**4}[match.group(2)]
    return int(float(match.group(1)) * multiplier)


def _peak_rss_bytes_current_process() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


_CALIBRATION_ROOT: Path | None = None
_CALIBRATION_CONFIG: Mapping[str, Any] | None = None
_CALIBRATION_BROKER: SplitBroker | None = None
_CALIBRATION_PROVIDER: FeatureProvider | None = None
_CALIBRATION_VAULT: OuterVault | None = None


def _calibration_worker_init(root_value: str) -> None:
    global _CALIBRATION_ROOT, _CALIBRATION_CONFIG
    global _CALIBRATION_BROKER, _CALIBRATION_PROVIDER, _CALIBRATION_VAULT
    _CALIBRATION_ROOT = Path(root_value)
    _CALIBRATION_CONFIG = load_goal029_config(_CALIBRATION_ROOT)
    (
        _CALIBRATION_BROKER,
        _CALIBRATION_PROVIDER,
        _CALIBRATION_VAULT,
    ) = ingest_production_foundation(_CALIBRATION_ROOT, _CALIBRATION_CONFIG)


def _canonical_failure_code(exc: BaseException) -> str:
    text = str(exc)
    if re.fullmatch(r"[a-z0-9_:-]+", text):
        return text
    return "unclassified_execution_failure"


def _calibration_worker_leaf(leaf_value: Mapping[str, Any]) -> Mapping[str, Any]:
    if (
        _CALIBRATION_CONFIG is None
        or _CALIBRATION_BROKER is None
        or _CALIBRATION_PROVIDER is None
        or _CALIBRATION_VAULT is None
    ):
        raise Goal029Error("calibration_worker_uninitialised")
    leaf = ProductionLeaf(**leaf_value)
    try:
        result = run_leaf(
            leaf,
            _CALIBRATION_BROKER,
            _CALIBRATION_PROVIDER,
            _CALIBRATION_CONFIG,
        )
        semantic_digest = _semantic_result_digest(
            _result_metadata(result), _oof_table(result)
        )
        status = "complete"
        failure_code = ""
    except ModelAdapterError as exc:
        semantic_digest = ""
        status = "invalid_candidate"
        failure_code = _canonical_failure_code(exc)
    if (
        _CALIBRATION_VAULT.attempted_open_count != 0
        or _CALIBRATION_VAULT.open_count != 0
    ):
        raise Goal029Error("calibration_outer_access")
    return {
        "leaf": asdict(leaf),
        "status": status,
        "semantic_result_digest": semantic_digest,
        "failure_code": failure_code,
        "peak_rss_bytes": _peak_rss_bytes_current_process(),
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }


def run_calibration_trial(
    root: Path,
    config: Mapping[str, Any],
    leaves: Sequence[ProductionLeaf],
    workers: int,
    destination: Path,
) -> Mapping[str, Any]:
    if workers not in (1, 2, 4):
        raise Goal029Error("calibration_worker_count_invalid")
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise Goal029Error("calibration_destination_not_fresh")
    destination.mkdir(parents=True)
    free_before = _available_memory_bytes()
    swap_before = _swap_used_bytes()
    if free_before < int(config["execution"]["minimum_free_memory_bytes"]):
        raise Goal029Error("calibration_memory_headroom_failed")
    started = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_calibration_worker_init,
        initargs=(str(Path(root).resolve()),),
    ) as executor:
        results = list(
            executor.map(
                _calibration_worker_leaf,
                [asdict(leaf) for leaf in leaves],
                chunksize=1,
            )
        )
    wall_seconds = time.perf_counter() - started
    free_after = _available_memory_bytes()
    swap_after = _swap_used_bytes()
    leaf_order = {leaf: index for index, leaf in enumerate(leaves)}
    results.sort(
        key=lambda record: leaf_order[ProductionLeaf(**record["leaf"])]
    )
    receipt: dict[str, Any] = {
        "schema_version": "goal029_calibration_receipt_v1",
        "workers": workers,
        "actual_host": socket.gethostname(),
        "fresh_processes": True,
        "checkpoint_reuse": False,
        "fresh_destination": True,
        "leaf_count": len(results),
        "results": results,
        "semantic_digest": _sha(
            [
                {
                    "leaf": record["leaf"],
                    "status": record["status"],
                    "semantic_result_digest": record["semantic_result_digest"],
                    "failure_code": record["failure_code"],
                }
                for record in results
            ]
        ),
        "telemetry": {
            "wall_seconds": wall_seconds,
            "peak_rss_bytes": max(record["peak_rss_bytes"] for record in results),
            "free_memory_before_bytes": free_before,
            "free_memory_after_bytes": free_after,
            "swap_before_bytes": swap_before,
            "swap_after_bytes": swap_after,
        },
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    receipt["receipt_digest"] = _sha(receipt)
    _write_canonical_json(destination / "receipt.json", receipt)
    return receipt


def _write_atomic_json_file(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise Goal029Error("atomic_json_destination_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_canonical_json(temporary, value)
        _fsync_file(temporary)
        os.rename(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _validate_tracked_calibration(value: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "goal_id",
        "status",
        "trial_workers",
        "selected_workers",
        "leaf_count_per_trial",
        "class_support_strata_count",
        "fragility_stress_leaf_count",
        "fragility_invalid_candidate_count",
        "semantic_digest",
        "private_receipt_digest",
        "actual_host_digest",
        "real_outer_attempted_open_count",
        "real_outer_open_count",
    }
    if (
        set(value) != expected
        or value["schema_version"] != "goal029_calibration_index_v1"
        or value["status"] != "pass"
        or value["trial_workers"] != [1, 2, 4]
        or value["selected_workers"] not in (1, 2, 4)
        or value["class_support_strata_count"] != 56
        or value["fragility_stress_leaf_count"] != 32
        or value["real_outer_attempted_open_count"] != 0
        or value["real_outer_open_count"] != 0
        or any(
            _HEX64.fullmatch(str(value[key])) is None
            for key in (
                "semantic_digest",
                "private_receipt_digest",
                "actual_host_digest",
            )
        )
    ):
        raise Goal029Error("tracked_calibration_schema_mismatch")
    _privacy_walk(value)


def _validate_calibration_trial_receipt(
    value: Mapping[str, Any],
    *,
    workers: int,
    expected_leaves: Sequence[ProductionLeaf],
    expected_host: str,
) -> None:
    expected_keys = {
        "schema_version",
        "workers",
        "actual_host",
        "fresh_processes",
        "checkpoint_reuse",
        "fresh_destination",
        "leaf_count",
        "results",
        "semantic_digest",
        "telemetry",
        "real_outer_attempted_open_count",
        "real_outer_open_count",
        "receipt_digest",
    }
    body = dict(value)
    claimed = body.pop("receipt_digest", None)
    results = value.get("results")
    telemetry = value.get("telemetry")
    if (
        set(value) != expected_keys
        or claimed != _sha(body)
        or value.get("schema_version") != "goal029_calibration_receipt_v1"
        or value.get("workers") != workers
        or value.get("actual_host") != expected_host
        or value.get("fresh_processes") is not True
        or value.get("checkpoint_reuse") is not False
        or value.get("fresh_destination") is not True
        or value.get("leaf_count") != len(expected_leaves)
        or not isinstance(results, list)
        or len(results) != len(expected_leaves)
        or not isinstance(telemetry, Mapping)
        or set(telemetry)
        != {
            "wall_seconds",
            "peak_rss_bytes",
            "free_memory_before_bytes",
            "free_memory_after_bytes",
            "swap_before_bytes",
            "swap_after_bytes",
        }
        or value.get("real_outer_attempted_open_count") != 0
        or value.get("real_outer_open_count") != 0
    ):
        raise Goal029Error("calibration_trial_receipt_invalid")
    observed_leaves = []
    semantic_rows = []
    for record in results:
        if (
            not isinstance(record, Mapping)
            or set(record)
            != {
                "leaf",
                "status",
                "semantic_result_digest",
                "failure_code",
                "peak_rss_bytes",
                "real_outer_attempted_open_count",
                "real_outer_open_count",
            }
        ):
            raise Goal029Error("calibration_trial_result_schema")
        leaf = ProductionLeaf(**record["leaf"])
        observed_leaves.append(leaf)
        status = record["status"]
        digest = record["semantic_result_digest"]
        failure_code = record["failure_code"]
        if (
            status not in {"complete", "invalid_candidate"}
            or (
                status == "complete"
                and (
                    _HEX64.fullmatch(str(digest)) is None or failure_code != ""
                )
            )
            or (
                status == "invalid_candidate"
                and (
                    digest != ""
                    or not isinstance(failure_code, str)
                    or re.fullmatch(r"[a-z0-9_:-]+", failure_code) is None
                )
            )
            or type(record["peak_rss_bytes"]) is not int
            or record["peak_rss_bytes"] < 0
            or record["real_outer_attempted_open_count"] != 0
            or record["real_outer_open_count"] != 0
        ):
            raise Goal029Error("calibration_trial_result_invalid")
        semantic_rows.append(
            {
                "leaf": record["leaf"],
                "status": status,
                "semantic_result_digest": digest,
                "failure_code": failure_code,
            }
        )
    if tuple(observed_leaves) != tuple(expected_leaves):
        raise Goal029Error("calibration_trial_leaf_order_mismatch")
    if value["semantic_digest"] != _sha(semantic_rows):
        raise Goal029Error("calibration_trial_semantic_mismatch")
    if any(
        type(number) not in {int, float}
        or isinstance(number, bool)
        or not math.isfinite(float(number))
        or float(number) < 0
        for number in telemetry.values()
    ):
        raise Goal029Error("calibration_trial_telemetry_invalid")


def run_calibration(root: Path) -> Mapping[str, Any]:
    root = Path(root).resolve()
    config = load_goal029_config(root)
    context = execution_context(root, config)
    broker, _, vault = ingest_production_foundation(root, config)
    support = class_support_scan(broker)
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("calibration_outer_access")
    base_plan = production_plan()
    order = {leaf: index for index, leaf in enumerate(base_plan)}
    leaves = tuple(
        sorted(
            set(calibration_plan(config)) | set(fragility_stress_plan()),
            key=order.__getitem__,
        )
    )
    calibration_id = _sha(
        {
            "execution_context": asdict(context),
            "leaves": [asdict(leaf) for leaf in leaves],
            "workers": [1, 2, 4],
        }
    )
    private_root = (
        root
        / "data/processed/modeling/goal029-conventional-baseline-calibration"
        / calibration_id
    )
    tracked_root = _safe_bound_path(
        root, config["calibration"]["receipt_destination"]
    )
    if (
        private_root.exists()
        or private_root.is_symlink()
        or tracked_root.exists()
        or tracked_root.is_symlink()
    ):
        raise Goal029Error("calibration_canonical_destination_exists")
    private_root.mkdir(parents=True)
    try:
        trials = [
            run_calibration_trial(
                root,
                config,
                leaves,
                workers,
                private_root / f"workers{workers}",
            )
            for workers in (1, 2, 4)
        ]
        semantic = {trial["semantic_digest"] for trial in trials}
        hosts = {trial["actual_host"] for trial in trials}
        if len(semantic) != 1 or hosts != {socket.gethostname()}:
            raise Goal029Error("calibration_semantic_or_host_mismatch")
        minimum_free = int(config["execution"]["minimum_free_memory_bytes"])
        acceptable = [
            trial
            for trial in trials
            if trial["telemetry"]["swap_after_bytes"]
            <= trial["telemetry"]["swap_before_bytes"]
            and trial["telemetry"]["free_memory_after_bytes"] >= minimum_free
        ]
        if not acceptable:
            raise Goal029Error("calibration_no_acceptable_worker_trial")
        selected_workers = max(trial["workers"] for trial in acceptable)
        stress_set = set(fragility_stress_plan())
        representative = trials[0]["results"]
        stress_invalid = sum(
            record["status"] == "invalid_candidate"
            for record in representative
            if ProductionLeaf(**record["leaf"]) in stress_set
        )
        private_receipt: dict[str, Any] = {
            "schema_version": "goal029_calibration_master_v1",
            "calibration_id": calibration_id,
            "actual_host": socket.gethostname(),
            "execution_context": asdict(context),
            "class_support_scan": list(support),
            "class_support_scan_digest": _sha(support),
            "trial_receipts": [
                {
                    "workers": trial["workers"],
                    "relative_path": f"workers{trial['workers']}/receipt.json",
                    "receipt_digest": trial["receipt_digest"],
                }
                for trial in trials
            ],
            "selected_workers": selected_workers,
            "semantic_digest": trials[0]["semantic_digest"],
            "fragility_invalid_candidate_count": stress_invalid,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        private_receipt["receipt_digest"] = _sha(private_receipt)
        _write_canonical_json(private_root / "receipt.json", private_receipt)
        tracked = {
            "schema_version": "goal029_calibration_index_v1",
            "goal_id": config["identity"]["goal_id"],
            "status": "pass",
            "trial_workers": [1, 2, 4],
            "selected_workers": selected_workers,
            "leaf_count_per_trial": len(leaves),
            "class_support_strata_count": 56,
            "fragility_stress_leaf_count": 32,
            "fragility_invalid_candidate_count": stress_invalid,
            "semantic_digest": trials[0]["semantic_digest"],
            "private_receipt_digest": private_receipt["receipt_digest"],
            "actual_host_digest": _sha(socket.gethostname()),
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        _validate_tracked_calibration(tracked)
        _write_atomic_json_file(tracked_root / "receipt.json", tracked)
    except Exception:
        shutil.rmtree(private_root, ignore_errors=True)
        if tracked_root.is_dir() and not tracked_root.is_symlink():
            shutil.rmtree(tracked_root)
        raise
    return {
        "status": "pass",
        "selected_workers": selected_workers,
        "leaf_count_per_trial": len(leaves),
        "class_support_strata_count": 56,
        "fragility_invalid_candidate_count": stress_invalid,
        "semantic_digest": trials[0]["semantic_digest"],
        "private_receipt_digest": private_receipt["receipt_digest"],
        "tracked_receipt_digest": sha256_file(tracked_root / "receipt.json"),
        "outer_attempted_open_count": 0,
        "outer_open_count": 0,
    }


def load_calibration_authority(
    root: Path, config: Mapping[str, Any], context: ExecutionContext
) -> Mapping[str, Any]:
    tracked_path = (
        _safe_bound_path(root, config["calibration"]["receipt_destination"])
        / "receipt.json"
    )
    tracked = _read_json(tracked_path)
    _validate_tracked_calibration(tracked)
    candidates = sorted(
        (
            Path(root)
            / "data/processed/modeling/goal029-conventional-baseline-calibration"
        ).glob("*/receipt.json")
    )
    matches = [
        path
        for path in candidates
        if _read_json(path).get("receipt_digest")
        == tracked["private_receipt_digest"]
    ]
    if len(matches) != 1:
        raise Goal029Error("calibration_private_authority_missing_or_ambiguous")
    private = _read_json(matches[0])
    body = dict(private)
    claimed = body.pop("receipt_digest", None)
    expected_leaves = tuple(
        leaf
        for leaf in production_plan()
        if leaf in set(calibration_plan(config)) | set(fragility_stress_plan())
    )
    expected_private_keys = {
        "schema_version",
        "calibration_id",
        "actual_host",
        "execution_context",
        "class_support_scan",
        "class_support_scan_digest",
        "trial_receipts",
        "selected_workers",
        "semantic_digest",
        "fragility_invalid_candidate_count",
        "real_outer_attempted_open_count",
        "real_outer_open_count",
        "receipt_digest",
    }
    if (
        set(private) != expected_private_keys
        or
        claimed != _sha(body)
        or private.get("schema_version") != "goal029_calibration_master_v1"
        or private.get("actual_host") != socket.gethostname()
        or tracked.get("actual_host_digest") != _sha(socket.gethostname())
        or tracked.get("goal_id") != config["identity"]["goal_id"]
        or private.get("execution_context") != asdict(context)
        or private.get("selected_workers") != tracked.get("selected_workers")
        or private.get("semantic_digest") != tracked.get("semantic_digest")
        or private.get("real_outer_attempted_open_count") != 0
        or private.get("real_outer_open_count") != 0
    ):
        raise Goal029Error("calibration_authority_mismatch")
    expected_calibration_id = _sha(
        {
            "execution_context": asdict(context),
            "leaves": [asdict(leaf) for leaf in expected_leaves],
            "workers": [1, 2, 4],
        }
    )
    support = private.get("class_support_scan")
    if (
        private.get("calibration_id") != expected_calibration_id
        or not isinstance(support, list)
        or len(support) != 56
        or private.get("class_support_scan_digest") != _sha(support)
        or tracked.get("leaf_count_per_trial") != len(expected_leaves)
        or tracked.get("fragility_invalid_candidate_count")
        != private.get("fragility_invalid_candidate_count")
    ):
        raise Goal029Error("calibration_authority_scope_mismatch")
    trial_records = private.get("trial_receipts")
    if (
        not isinstance(trial_records, list)
        or [record.get("workers") for record in trial_records] != [1, 2, 4]
    ):
        raise Goal029Error("calibration_trial_index_invalid")
    trials = []
    private_root = matches[0].parent
    for index, record in enumerate(trial_records):
        workers = (1, 2, 4)[index]
        if (
            set(record) != {"workers", "relative_path", "receipt_digest"}
            or record["relative_path"] != f"workers{workers}/receipt.json"
        ):
            raise Goal029Error("calibration_trial_index_invalid")
        path = private_root / record["relative_path"]
        if path.is_symlink() or not path.is_file():
            raise Goal029Error("calibration_trial_receipt_missing")
        trial = _read_json(path)
        _validate_calibration_trial_receipt(
            trial,
            workers=workers,
            expected_leaves=expected_leaves,
            expected_host=socket.gethostname(),
        )
        if trial["receipt_digest"] != record["receipt_digest"]:
            raise Goal029Error("calibration_trial_digest_mismatch")
        trials.append(trial)
    if len({trial["semantic_digest"] for trial in trials}) != 1:
        raise Goal029Error("calibration_trial_semantic_disagreement")
    minimum_free = int(config["execution"]["minimum_free_memory_bytes"])
    acceptable = [
        trial
        for trial in trials
        if trial["telemetry"]["swap_after_bytes"]
        <= trial["telemetry"]["swap_before_bytes"]
        and trial["telemetry"]["free_memory_after_bytes"] >= minimum_free
    ]
    selected_workers = max(
        (trial["workers"] for trial in acceptable), default=None
    )
    if (
        selected_workers is None
        or selected_workers != private["selected_workers"]
        or selected_workers != tracked["selected_workers"]
        or trials[0]["semantic_digest"] != private["semantic_digest"]
    ):
        raise Goal029Error("calibration_worker_selection_mismatch")
    return {
        "tracked": tracked,
        "private": private,
        "trials": trials,
        "private_receipt_path": str(matches[0]),
    }


def _write_or_validate_content_json(
    directory: Path, value: Mapping[str, Any], digest_key: str
) -> Path:
    digest = value.get(digest_key)
    if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
        raise Goal029Error("content_json_digest_invalid")
    path = Path(directory) / f"{digest}.json"
    if path.exists() or path.is_symlink():
        if path.is_symlink() or canonical_json(_read_json(path)) != canonical_json(value):
            raise Goal029Error("content_json_collision")
        return path
    _write_atomic_json_file(path, value)
    return path


def _replace_atomic_json_file(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    if path.is_symlink():
        raise Goal029Error("atomic_json_symlink_forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_canonical_json(temporary, value)
        _fsync_file(temporary)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _candidate_stratum_payload(leaf: ProductionLeaf) -> Mapping[str, str]:
    return {
        "species_id": leaf.species_id,
        "fraction_id": leaf.fraction_id,
        "ladder_id": leaf.ladder_id,
        "model_family": leaf.model_family,
        "candidate_id": leaf.candidate_id,
    }


def _candidate_stratum_key(value: Mapping[str, Any] | ProductionLeaf) -> str:
    payload = (
        _candidate_stratum_payload(value)
        if isinstance(value, ProductionLeaf)
        else {
            key: value[key]
            for key in (
                "species_id",
                "fraction_id",
                "ladder_id",
                "model_family",
                "candidate_id",
            )
        }
    )
    return canonical_json([payload[key] for key in payload])


def prepare_production_provenance(
    private_stage: Path,
    plan: Sequence[ProductionLeaf],
    broker: SplitBroker,
    provider: FeatureProvider,
    context: ExecutionContext,
) -> Mapping[str, Any]:
    private_stage = Path(private_stage)
    membership_directory = private_stage / "memberships"
    encoder_directory = private_stage / "encoders"
    checkpoint_directory = private_stage / "checkpoints"
    failure_directory = private_stage / "failures"
    selected_directory = private_stage / "selected"
    for directory in (
        membership_directory,
        encoder_directory,
        checkpoint_directory,
        failure_directory,
        selected_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    membership_by_endpoint: dict[
        tuple[str, str, str], Mapping[str, Mapping[str, Any]]
    ] = {}
    membership_index: dict[str, Any] = {}
    for species_id in SPECIES:
        for fraction_id, ladder_id in ENDPOINTS:
            reference = ProductionLeaf(
                species_id,
                fraction_id,
                ladder_id,
                "intercept",
                "null00",
                "seed00",
            )
            records = membership_records(reference, broker)
            membership_by_endpoint[(species_id, fraction_id, ladder_id)] = records
            for split_id, record in sorted(records.items()):
                path = _write_or_validate_content_json(
                    membership_directory, record, "record_digest"
                )
                key = canonical_json(
                    [species_id, fraction_id, ladder_id, split_id]
                )
                membership_index[key] = {
                    "record_digest": record["record_digest"],
                    "relative_path": str(path.relative_to(private_stage)),
                }
    if len(membership_index) != 56 * 6:
        raise Goal029Error("production_membership_index_count")

    encoder_by_stratum: dict[
        tuple[str, str, str, str], Mapping[str, str]
    ] = {}
    encoder_index: dict[str, Any] = {}
    for species_id in SPECIES:
        for fraction_id, ladder_id in ENDPOINTS:
            memberships = membership_by_endpoint[
                (species_id, fraction_id, ladder_id)
            ]
            for family in FAMILIES:
                reference = ProductionLeaf(
                    species_id,
                    fraction_id,
                    ladder_id,
                    family,
                    CANDIDATE_IDS[family][0],
                    SEEDS_BY_FAMILY[family][0],
                )
                digests = encoder_digests(
                    reference, broker, provider, memberships
                )
                encoder_by_stratum[reference.family_stratum] = digests
                record: dict[str, Any] = {
                    "schema_version": "1.0",
                    "species_id": species_id,
                    "fraction_id": fraction_id,
                    "ladder_id": ladder_id,
                    "model_family": family,
                    "split_membership_digests": {
                        split: memberships[split]["record_digest"]
                        for split in sorted(memberships)
                    },
                    "encoder_digests": {
                        split: digests[split] for split in sorted(digests)
                    },
                }
                record["record_digest"] = _sha(record)
                path = _write_or_validate_content_json(
                    encoder_directory, record, "record_digest"
                )
                encoder_index[
                    canonical_json(
                        [species_id, fraction_id, ladder_id, family]
                    )
                ] = {
                    "record_digest": record["record_digest"],
                    "relative_path": str(path.relative_to(private_stage)),
                }
    if len(encoder_index) != FAMILY_STRATA_COUNT:
        raise Goal029Error("production_encoder_index_count")

    leaf_records = []
    for leaf in plan:
        memberships = membership_by_endpoint[
            (leaf.species_id, leaf.fraction_id, leaf.ladder_id)
        ]
        encoders = encoder_by_stratum[leaf.family_stratum]
        identity = leaf_identity(leaf, context, memberships, encoders)
        leaf_records.append({"leaf": asdict(leaf), "identity": identity})
    plan_record: dict[str, Any] = {
        "schema_version": "1.0",
        "execution_context": asdict(context),
        "canonical_plan_digest": _sha([asdict(leaf) for leaf in plan]),
        "membership_index": membership_index,
        "encoder_index": encoder_index,
        "leaf_records": leaf_records,
    }
    plan_record["record_digest"] = _sha(plan_record)
    plan_path = private_stage / "plan.json"
    if plan_path.exists():
        if canonical_json(_read_json(plan_path)) != canonical_json(plan_record):
            raise Goal029Error("production_plan_resume_mismatch")
    else:
        _write_atomic_json_file(plan_path, plan_record)
    return plan_record


def _production_worker_candidate(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    if (
        _CALIBRATION_CONFIG is None
        or _CALIBRATION_BROKER is None
        or _CALIBRATION_PROVIDER is None
        or _CALIBRATION_VAULT is None
    ):
        raise Goal029Error("production_worker_uninitialised")
    checkpoint_root = Path(value["checkpoint_root"])
    leaves = [ProductionLeaf(**record["leaf"]) for record in value["leaves"]]
    identities = [record["identity"] for record in value["leaves"]]
    if (
        not leaves
        or len(leaves) != len(identities)
        or any(leaf.candidate_stratum != leaves[0].candidate_stratum for leaf in leaves)
        or tuple(leaf.seed_label for leaf in leaves)
        != SEEDS_BY_FAMILY[leaves[0].model_family]
    ):
        raise Goal029Error("production_worker_candidate_group_invalid")
    results = []
    try:
        for leaf, identity in zip(leaves, identities):
            destination = checkpoint_root / identity["identity_digest"]
            if destination.exists() or destination.is_symlink():
                if destination.is_symlink() or not destination.is_dir():
                    raise Goal029Error("production_checkpoint_path_invalid")
                result = load_leaf_checkpoint(destination, identity)
                reused = True
            else:
                result = run_leaf(
                    leaf,
                    _CALIBRATION_BROKER,
                    _CALIBRATION_PROVIDER,
                    _CALIBRATION_CONFIG,
                )
                destination, reused = write_leaf_checkpoint(
                    checkpoint_root, identity, result
                )
            results.append(
                {
                    "leaf": asdict(leaf),
                    "identity_digest": identity["identity_digest"],
                    "checkpoint": str(destination),
                    "semantic_result_digest": _read_json(
                        destination / "checkpoint_manifest.json"
                    )["semantic_result_digest"],
                    "reused": reused,
                }
            )
    except ModelAdapterError as exc:
        return {
            "candidate_stratum": _candidate_stratum_payload(leaves[0]),
            "status": "invalid_candidate",
            "failure_code": _canonical_failure_code(exc),
            "failure_leaf": asdict(leaf),
            "leaves": [],
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
    if (
        _CALIBRATION_VAULT.attempted_open_count != 0
        or _CALIBRATION_VAULT.open_count != 0
    ):
        raise Goal029Error("production_worker_outer_access")
    return {
        "candidate_stratum": _candidate_stratum_payload(leaves[0]),
        "status": "complete",
        "failure_code": "",
        "failure_leaf": None,
        "leaves": results,
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }


def _validate_refit_warnings(
    family: str, report: FitReport, config: Mapping[str, Any]
) -> tuple[str, ...]:
    if not report.converged:
        raise Goal029Error("selected_refit_nonconverged")
    if report.neural_stop_status not in {None, "max_epochs_reached"}:
        # Exact-epoch selected refits have no stopping status.
        raise Goal029Error("selected_refit_stop_status_invalid")
    allowed_substrings = tuple(
        config["failure_policy"]["allowed_informational_warning_substrings"]
    )
    allowed_soft = set(config["failure_policy"]["allowed_soft_warning_codes"])
    accepted = []
    for warning in report.warnings:
        if warning in allowed_soft or any(
            substring in warning for substring in allowed_substrings
        ):
            accepted.append(warning)
        else:
            raise Goal029Error(f"unclassified_refit_warning:{warning}")
    if family != "shallow_ann" and report.neural_stop_status is not None:
        raise Goal029Error("conventional_refit_neural_status")
    return tuple(accepted)


def refit_selected_candidate(
    selected: CandidateOOF,
    broker: SplitBroker,
    provider: FeatureProvider,
    vault: OuterVault,
    config: Mapping[str, Any],
    selected_directory: Path,
    context: ExecutionContext,
) -> tuple[Mapping[str, Any], ...]:
    family = selected.stratum.model_family
    required_seeds = SEEDS_BY_FAMILY.get(family)
    if required_seeds is None or selected.stratum.ordered_selection_seeds != required_seeds:
        raise Goal029Error("selected_refit_seed_contract")
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("real_outer_access_detected")
    selected_directory = Path(selected_directory)
    selected_directory.mkdir(parents=True, exist_ok=True)
    outer = broker.outer_training(selected.stratum.species_id)
    endpoint = _endpoint(
        outer, selected.stratum.fraction_id, selected.stratum.ladder_id
    )
    endpoint_rows = _rowset_for_keys(outer, endpoint.keys)
    receipts: list[Mapping[str, Any]] = []
    for seed_label in required_seeds:
        task = TaskKey(
            selected.stratum.species_id,
            "outer",
            selected.stratum.fraction_id,
            selected.stratum.ladder_id,
            family,
            selected.candidate_id,
            seed_label,
        )
        fold_epochs = (
            selected.neural_epochs_by_seed.get(seed_label)
            if family == "shallow_ann"
            else None
        )
        fitted, report = refit_outer_training(
            task,
            endpoint,
            CANONICAL_CANDIDATES[selected.candidate_id],
            broker,
            provider,
            build_adapter(family),
            fold_epochs,
        )
        warnings = _validate_refit_warnings(family, report, config)
        encoder = provider.fit_encoder(endpoint_rows, family, "outer")
        training_batch = provider.materialize(endpoint_rows, "outer", encoder)
        challenge = build_challenge_batch(
            training_batch, int(config["hardening"]["challenge_rows_maximum"])
        )
        challenge_record = challenge_payload(challenge)
        temporary = selected_directory / f".tmp-{task_id(task)}-{uuid.uuid4().hex}"
        temporary.mkdir()
        model_path = temporary / "model.model"
        envelope = fitted.serialize(model_path)
        _fsync_file(model_path)
        model_digest = sha256_file(model_path)
        scores = fitted.predict_scores(challenge)
        if not np.isfinite(scores).all():
            raise Goal029Error("challenge_prediction_nonfinite")
        loaded = load_fitted_model(model_path, model_digest)
        replay = loaded.predict_scores(challenge)
        tolerance = 1e-6 if family == "shallow_ann" else 1e-12
        if not np.allclose(scores, replay, rtol=0.0, atol=tolerance):
            raise Goal029Error("challenge_prediction_replay_mismatch")
        challenge_path = temporary / "challenge.json"
        _write_canonical_json(challenge_path, challenge_record)
        _fsync_file(challenge_path)
        bundle_identity = {
            "schema_version": "1.0",
            "selected_task": asdict(task),
            "model_sha256": model_digest,
            "challenge_digest": challenge_record["challenge_digest"],
            "canonical_prediction_bytes_sha256": canonical_prediction_bytes_sha256(
                scores
            ),
            "feature_schema_digest": challenge.feature_schema_digest,
            "transform_digest": challenge.transform_digest,
            "encoder_digest": challenge.encoder_digest,
            "execution_context_digest": _sha(asdict(context)),
            "model_envelope_identity_digest": envelope["identity_digest"],
            "model_runtime_versions_digest": _sha(
                envelope["runtime_versions"]
            ),
            "model_candidate_digest": envelope["candidate_digest"],
            "fit_seed_uint32": derive_seed(task, "fit"),
        }
        bundle_digest = _sha(bundle_identity)
        destination = selected_directory / bundle_digest
        receipt = {
            **bundle_identity,
            "selected_bundle_digest": bundle_digest,
            "bundle_path": str(destination.relative_to(selected_directory.parent)),
            "warnings": list(warnings),
            "iterations": report.iterations,
            "outer_attempted_open_count": 0,
            "outer_open_count": 0,
        }
        _write_canonical_json(temporary / "receipt.json", receipt)
        _fsync_file(temporary / "receipt.json")
        _fsync_directory(temporary)
        if destination.exists() or destination.is_symlink():
            shutil.rmtree(temporary, ignore_errors=True)
            existing = _read_json(destination / "receipt.json")
            if canonical_json(existing) != canonical_json(receipt):
                raise Goal029Error("selected_bundle_content_collision")
        else:
            os.rename(temporary, destination)
            _fsync_directory(selected_directory)
        validate_selected_refit_receipt(
            receipt,
            selected_directory.parent,
            expected_task=task,
            broker=broker,
            provider=provider,
            config=config,
            context=context,
        )
        receipts.append(receipt)
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("real_outer_access_detected")
    return tuple(receipts)


def validate_selected_refit_receipt(
    receipt: Mapping[str, Any],
    private_root: Path,
    *,
    expected_task: TaskKey,
    broker: SplitBroker,
    provider: FeatureProvider,
    config: Mapping[str, Any],
    context: ExecutionContext,
) -> None:
    expected_receipt_keys = {
        "schema_version",
        "selected_task",
        "model_sha256",
        "challenge_digest",
        "canonical_prediction_bytes_sha256",
        "feature_schema_digest",
        "transform_digest",
        "encoder_digest",
        "execution_context_digest",
        "model_envelope_identity_digest",
        "model_runtime_versions_digest",
        "model_candidate_digest",
        "fit_seed_uint32",
        "selected_bundle_digest",
        "bundle_path",
        "warnings",
        "iterations",
        "outer_attempted_open_count",
        "outer_open_count",
    }
    if set(receipt) != expected_receipt_keys:
        raise Goal029Error("selected_refit_receipt_schema")
    task = TaskKey(**receipt["selected_task"])
    if task != expected_task:
        raise Goal029Error("selected_refit_task_authority_mismatch")
    expected_relative = (
        Path("selected") / receipt["selected_bundle_digest"]
    )
    if Path(receipt["bundle_path"]) != expected_relative:
        raise Goal029Error("selected_bundle_path_invalid")
    bundle = _relative_artifact_path(
        private_root, receipt["bundle_path"], directory=True
    )
    _validate_exact_file_inventory(
        bundle,
        {"model.model", "challenge.json", "receipt.json"},
        "selected_bundle_file_inventory",
    )
    model_path = bundle / "model.model"
    challenge_path = bundle / "challenge.json"
    receipt_path = bundle / "receipt.json"
    identity = {
        key: receipt[key]
        for key in (
            "schema_version",
            "selected_task",
            "model_sha256",
            "challenge_digest",
            "canonical_prediction_bytes_sha256",
            "feature_schema_digest",
            "transform_digest",
            "encoder_digest",
            "execution_context_digest",
            "model_envelope_identity_digest",
            "model_runtime_versions_digest",
            "model_candidate_digest",
            "fit_seed_uint32",
        )
    }
    if (
        task.transform_id != "outer"
        or task.model_family not in FAMILIES
        or task.candidate_id not in CANDIDATE_IDS[task.model_family]
        or task.seed_label not in SEEDS_BY_FAMILY[task.model_family]
        or receipt["execution_context_digest"] != _sha(asdict(context))
        or receipt["fit_seed_uint32"] != derive_seed(task, "fit")
        or bundle.name != receipt["selected_bundle_digest"]
        or receipt["selected_bundle_digest"] != _sha(identity)
        or bundle.is_symlink()
        or not bundle.is_dir()
        or model_path.is_symlink()
        or challenge_path.is_symlink()
        or receipt_path.is_symlink()
        or not model_path.is_file()
        or not challenge_path.is_file()
        or not receipt_path.is_file()
        or canonical_json(_read_json(receipt_path)) != canonical_json(receipt)
        or sha256_file(model_path) != receipt["model_sha256"]
        or receipt["outer_attempted_open_count"] != 0
        or receipt["outer_open_count"] != 0
    ):
        raise Goal029Error("selected_refit_receipt_invalid")
    challenge_record = _read_json(challenge_path)
    challenge = challenge_from_payload(challenge_record)
    outer = broker.outer_training(task.species_id)
    endpoint = _endpoint(outer, task.fraction_id, task.ladder_id)
    endpoint_rows = _rowset_for_keys(outer, endpoint.keys)
    encoder = provider.fit_encoder(
        endpoint_rows, task.model_family, "outer"
    )
    training_batch = provider.materialize(
        endpoint_rows, "outer", encoder
    )
    expected_challenge = build_challenge_batch(
        training_batch, int(config["hardening"]["challenge_rows_maximum"])
    )
    expected_challenge_record = challenge_payload(expected_challenge)
    if (
        canonical_json(challenge_record)
        != canonical_json(expected_challenge_record)
        or challenge_record["challenge_digest"] != receipt["challenge_digest"]
        or challenge.feature_schema_digest != receipt["feature_schema_digest"]
        or challenge.transform_digest != receipt["transform_digest"]
        or challenge.encoder_digest != receipt["encoder_digest"]
    ):
        raise Goal029Error("selected_challenge_provenance_mismatch")
    model = load_fitted_model(model_path, receipt["model_sha256"])
    envelope = _read_json(model_path)
    expected_candidate = CANONICAL_CANDIDATES[task.candidate_id]
    expected_runtime_versions = {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(package)
            for name, package in (
                ("numpy", "numpy"),
                ("scipy", "scipy"),
                ("sklearn", "scikit-learn"),
                ("pygam", "pygam"),
                ("torch", "torch"),
            )
        },
    }
    expected_schema = {
        "feature_names": list(expected_challenge.feature_names),
        "feature_kinds": list(expected_challenge.feature_kinds),
        "continuous_count": expected_challenge.continuous_count,
        "feature_schema_digest": expected_challenge.feature_schema_digest,
        "transform_id": expected_challenge.transform_id,
        "transform_digest": expected_challenge.transform_digest,
        "encoder_digest": expected_challenge.encoder_digest,
    }
    if (
        envelope.get("family") != task.model_family
        or envelope.get("candidate") != expected_candidate
        or envelope.get("fit_seed") != derive_seed(task, "fit")
        or envelope.get("runtime_versions") != expected_runtime_versions
        or envelope.get("schema") != expected_schema
        or envelope.get("identity_digest")
        != receipt["model_envelope_identity_digest"]
        or _sha(envelope.get("runtime_versions"))
        != receipt["model_runtime_versions_digest"]
        or envelope.get("candidate_digest")
        != receipt["model_candidate_digest"]
        or getattr(model, "family", None) != task.model_family
        or getattr(model, "candidate", None) != expected_candidate
        or getattr(model, "seed", None) != derive_seed(task, "fit")
        or canonical_json(getattr(model, "schema", None))
        != canonical_json(expected_schema)
    ):
        raise Goal029Error("selected_model_semantic_identity_mismatch")
    scores = model.predict_scores(challenge)
    if (
        canonical_prediction_bytes_sha256(scores)
        != receipt["canonical_prediction_bytes_sha256"]
    ):
        raise Goal029Error("selected_challenge_prediction_mismatch")


def _fit_report_payload(report: FitReport) -> Mapping[str, Any]:
    return {
        "converged": report.converged,
        "iterations": report.iterations,
        "best_epoch": report.best_epoch,
        "stopping_fold": report.stopping_fold,
        "neural_stop_status": report.neural_stop_status,
        "warnings": list(report.warnings),
        "runtime_seconds": report.runtime_seconds,
        "peak_rss_bytes": report.peak_rss_bytes,
        "initial_state_digest": report.initial_state_digest,
    }


def _fit_report_from_payload(value: Mapping[str, Any]) -> FitReport:
    return FitReport(
        bool(value["converged"]),
        int(value["iterations"]),
        None if value["best_epoch"] is None else int(value["best_epoch"]),
        value["stopping_fold"],
        value["neural_stop_status"],
        tuple(value["warnings"]),
        float(value["runtime_seconds"]),
        int(value["peak_rss_bytes"]),
        value["initial_state_digest"],
    )


def _receipt_payload(receipt: NeuralFoldReceipt) -> Mapping[str, Any]:
    return {
        "task": asdict(receipt.task),
        "stopping_fold": receipt.stopping_fold,
        "best_epoch": receipt.best_epoch,
        "discovery_report": _fit_report_payload(receipt.discovery_report),
        "replay_report": _fit_report_payload(receipt.replay_report),
        "discovery_initial_state_digest": receipt.discovery_initial_state_digest,
        "replay_initial_state_digest": receipt.replay_initial_state_digest,
    }


def _receipt_from_payload(value: Mapping[str, Any]) -> NeuralFoldReceipt:
    return NeuralFoldReceipt(
        TaskKey(**value["task"]),
        str(value["stopping_fold"]),
        int(value["best_epoch"]),
        _fit_report_from_payload(value["discovery_report"]),
        _fit_report_from_payload(value["replay_report"]),
        str(value["discovery_initial_state_digest"]),
        str(value["replay_initial_state_digest"]),
    )


def _result_metadata(result: CandidateOOF) -> Mapping[str, Any]:
    metadata: dict[str, Any] = {
        "schema_version": "1.0",
        "stratum": asdict(result.stratum),
        "candidate_id": result.candidate_id,
        "threshold": result.threshold,
        "mean_fold_roc_auc": result.mean_fold_roc_auc,
        "mean_fold_tss_at_oof_threshold": result.mean_fold_tss_at_oof_threshold,
        "fold_metrics": [
            {
                "fold_id": fold.fold_id,
                "roc_auc": fold.roc_auc,
                "tss_at_oof_threshold": fold.tss_at_oof_threshold,
            }
            for fold in result.folds
        ],
        "neural_epochs_by_seed": {
            seed: {
                "stratum": asdict(record.stratum),
                "candidate_id": record.candidate_id,
                "seed_label": record.seed_label,
                "best_epochs_by_fold": list(record.best_epochs_by_fold),
                "receipts": [_receipt_payload(receipt) for receipt in record.receipts],
            }
            for seed, record in result.neural_epochs_by_seed.items()
        },
        "fit_reports_by_seed": {
            seed: [_fit_report_payload(report) for report in reports]
            for seed, reports in result.fit_reports_by_seed.items()
        },
    }
    return metadata


def _oof_table(result: CandidateOOF) -> pa.Table:
    rows = {
        "fold_id": [],
        "row_index": [],
        "row_token": [],
        "y_true": [],
        "seed_label": [],
        "score": [],
    }
    for fold in result.folds:
        for seed_label in result.stratum.ordered_selection_seeds:
            for index, (key, value, score) in enumerate(
                zip(fold.keys, fold.y_true, fold.scores_by_seed[seed_label])
            ):
                rows["fold_id"].append(fold.fold_id)
                rows["row_index"].append(index)
                rows["row_token"].append(_row_token(key))
                rows["y_true"].append(int(value))
                rows["seed_label"].append(seed_label)
                rows["score"].append(float(score))
    return pa.table(
        {
            "fold_id": pa.array(rows["fold_id"], type=pa.string()),
            "row_index": pa.array(rows["row_index"], type=pa.int32()),
            "row_token": pa.array(rows["row_token"], type=pa.string()),
            "y_true": pa.array(rows["y_true"], type=pa.int8()),
            "seed_label": pa.array(rows["seed_label"], type=pa.string()),
            "score": pa.array(rows["score"], type=pa.float64()),
        }
    )


def _semantic_result_digest(metadata: Mapping[str, Any], table: pa.Table) -> str:
    stable = json.loads(canonical_json(metadata))
    for reports in stable.get("fit_reports_by_seed", {}).values():
        for report in reports:
            report.pop("runtime_seconds", None)
            report.pop("peak_rss_bytes", None)
    for record in stable.get("neural_epochs_by_seed", {}).values():
        for receipt in record.get("receipts", []):
            for name in ("discovery_report", "replay_report"):
                receipt[name].pop("runtime_seconds", None)
                receipt[name].pop("peak_rss_bytes", None)
    rows = table.to_pylist()
    return _sha({"metadata": stable, "oof": rows})


def _fsync_file(path: Path) -> None:
    with Path(path).open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_canonical_json(path: Path, value: Mapping[str, Any]) -> None:
    Path(path).write_text(canonical_json(value) + "\n", encoding="utf-8")


def write_leaf_checkpoint(
    checkpoint_root: Path,
    identity: Mapping[str, Any],
    result: CandidateOOF,
) -> tuple[Path, bool]:
    identity_digest = identity.get("identity_digest")
    body = dict(identity)
    body.pop("identity_digest", None)
    if identity_digest != _sha(body) or _HEX64.fullmatch(str(identity_digest)) is None:
        raise Goal029Error("checkpoint_identity_invalid")
    checkpoint_root = Path(checkpoint_root)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    destination = checkpoint_root / str(identity_digest)
    if destination.exists() or destination.is_symlink():
        load_leaf_checkpoint(destination, identity)
        return destination, True
    temporary = checkpoint_root / f".{identity_digest}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        metadata = _result_metadata(result)
        table = _oof_table(result)
        _write_canonical_json(temporary / "identity.json", identity)
        _write_canonical_json(temporary / "result.json", metadata)
        pq.write_table(table, temporary / "oof.parquet", compression="zstd")
        manifest = {
            "schema_version": "1.0",
            "identity_digest": identity_digest,
            "semantic_result_digest": _semantic_result_digest(metadata, table),
            "files": {
                name: {
                    "sha256": sha256_file(temporary / name),
                    "bytes": (temporary / name).stat().st_size,
                }
                for name in ("identity.json", "result.json", "oof.parquet")
            },
        }
        _write_canonical_json(temporary / "checkpoint_manifest.json", manifest)
        for name in (
            "identity.json",
            "result.json",
            "oof.parquet",
            "checkpoint_manifest.json",
        ):
            _fsync_file(temporary / name)
        _fsync_directory(temporary)
        load_leaf_checkpoint(temporary, identity)
        os.rename(temporary, destination)
        _fsync_directory(checkpoint_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination, False


def load_leaf_checkpoint(
    path: Path, expected_identity: Mapping[str, Any]
) -> CandidateOOF:
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise Goal029Error("checkpoint_not_regular_directory")
    identity = _read_json(path / "identity.json")
    if canonical_json(identity) != canonical_json(expected_identity):
        raise Goal029Error("checkpoint_identity_mismatch")
    manifest = _read_json(path / "checkpoint_manifest.json")
    if (
        manifest.get("schema_version") != "1.0"
        or manifest.get("identity_digest") != expected_identity.get("identity_digest")
        or set(manifest.get("files", {}))
        != {"identity.json", "result.json", "oof.parquet"}
    ):
        raise Goal029Error("checkpoint_manifest_invalid")
    for name, record in manifest["files"].items():
        target = path / name
        if (
            target.is_symlink()
            or not target.is_file()
            or target.stat().st_size != record.get("bytes")
            or sha256_file(target) != record.get("sha256")
        ):
            raise Goal029Error("checkpoint_file_tamper")
    metadata = _read_json(path / "result.json")
    table = pq.read_table(path / "oof.parquet")
    if manifest.get("semantic_result_digest") != _semantic_result_digest(metadata, table):
        raise Goal029Error("checkpoint_semantic_digest_mismatch")
    return _result_from_checkpoint(metadata, table)


def _result_from_checkpoint(
    metadata: Mapping[str, Any], table: pa.Table
) -> CandidateOOF:
    stratum = SelectionStratum(
        metadata["stratum"]["species_id"],
        metadata["stratum"]["fraction_id"],
        metadata["stratum"]["ladder_id"],
        metadata["stratum"]["model_family"],
        tuple(metadata["stratum"]["ordered_selection_seeds"]),
    )
    records = table.to_pylist()
    folds: list[FoldOOF] = []
    metrics = {row["fold_id"]: row for row in metadata["fold_metrics"]}
    for fold_id in FOLDS:
        fold_rows = sorted(
            [row for row in records if row["fold_id"] == fold_id],
            key=lambda row: (row["seed_label"], row["row_index"]),
        )
        by_seed: dict[str, list[Mapping[str, Any]]] = {}
        for row in fold_rows:
            by_seed.setdefault(row["seed_label"], []).append(row)
        if set(by_seed) != set(stratum.ordered_selection_seeds):
            raise Goal029Error("checkpoint_seed_rows_mismatch")
        reference = by_seed[stratum.ordered_selection_seeds[0]]
        keys = tuple(_parse_row_token(row["row_token"]) for row in reference)
        y = np.asarray([row["y_true"] for row in reference], dtype=np.int8)
        scores: dict[str, np.ndarray] = {}
        for seed in stratum.ordered_selection_seeds:
            current = by_seed[seed]
            if (
                [row["row_token"] for row in current]
                != [row["row_token"] for row in reference]
                or [row["y_true"] for row in current]
                != [row["y_true"] for row in reference]
            ):
                raise Goal029Error("checkpoint_seed_alignment_mismatch")
            scores[seed] = np.asarray([row["score"] for row in current], dtype=np.float64)
        mean = np.mean(np.vstack([scores[seed] for seed in stratum.ordered_selection_seeds]), axis=0)
        fold_metric = metrics[fold_id]
        folds.append(
            FoldOOF(
                fold_id,
                keys,
                y,
                scores,
                mean,
                float(fold_metric["roc_auc"]),
                float(fold_metric["tss_at_oof_threshold"]),
            )
        )
    epochs: dict[str, FoldEpochs] = {}
    receipts: dict[str, tuple[NeuralFoldReceipt, ...]] = {}
    for seed, record in metadata["neural_epochs_by_seed"].items():
        record_stratum = SelectionStratum(
            record["stratum"]["species_id"],
            record["stratum"]["fraction_id"],
            record["stratum"]["ladder_id"],
            record["stratum"]["model_family"],
            tuple(record["stratum"]["ordered_selection_seeds"]),
        )
        parsed_receipts = tuple(
            _receipt_from_payload(value) for value in record["receipts"]
        )
        epochs[seed] = FoldEpochs(
            record_stratum,
            record["candidate_id"],
            record["seed_label"],
            tuple(record["best_epochs_by_fold"]),
            parsed_receipts,
        )
        receipts[seed] = parsed_receipts
    fit_reports = {
        seed: tuple(_fit_report_from_payload(value) for value in values)
        for seed, values in metadata["fit_reports_by_seed"].items()
    }
    result = CandidateOOF(
        stratum,
        str(metadata["candidate_id"]),
        tuple(folds),
        float(metadata["threshold"]),
        float(metadata["mean_fold_roc_auc"]),
        float(metadata["mean_fold_tss_at_oof_threshold"]),
        epochs,
        receipts,
        fit_reports,
    )
    # Existing selection validation independently recomputes every metric.
    select_candidate([result])
    return result


def merge_seed_leaves(
    leaf_results: Mapping[str, CandidateOOF],
    family: str,
    candidate_id: str,
) -> CandidateOOF:
    required = SEEDS_BY_FAMILY[family]
    if set(leaf_results) != set(required):
        raise Goal029Error("candidate_seed_set_incomplete")
    ordered = [leaf_results[seed] for seed in required]
    reference = ordered[0]
    if any(
        result.candidate_id != candidate_id
        or result.stratum.model_family != family
        or result.stratum.ordered_selection_seeds != (seed,)
        for seed, result in zip(required, ordered)
    ):
        raise Goal029Error("candidate_leaf_identity_mismatch")
    folds: list[FoldOOF] = []
    for index, fold_id in enumerate(FOLDS):
        reference_fold = reference.folds[index]
        scores: dict[str, np.ndarray] = {}
        for seed, result in zip(required, ordered):
            fold = result.folds[index]
            if (
                fold.fold_id != fold_id
                or fold.keys != reference_fold.keys
                or not np.array_equal(fold.y_true, reference_fold.y_true)
            ):
                raise Goal029Error("candidate_seed_comparability_mismatch")
            scores[seed] = np.asarray(fold.scores_by_seed[seed], dtype=np.float64)
        mean = np.mean(np.vstack([scores[seed] for seed in required]), axis=0)
        folds.append(
            FoldOOF(
                fold_id,
                reference_fold.keys,
                reference_fold.y_true,
                scores,
                mean,
                float(roc_auc_score(reference_fold.y_true, mean)),
                None,
            )
        )
    all_y = np.concatenate([fold.y_true for fold in folds])
    all_scores = [
        np.concatenate([fold.scores_by_seed[seed] for fold in folds])
        for seed in required
    ]
    threshold = select_threshold(all_y, all_scores)
    final_folds = tuple(
        FoldOOF(
            fold.fold_id,
            fold.keys,
            fold.y_true,
            fold.scores_by_seed,
            fold.mean_score,
            fold.roc_auc,
            _tss(fold.y_true, fold.mean_score, threshold.threshold),
        )
        for fold in folds
    )
    stratum = SelectionStratum(
        reference.stratum.species_id,
        reference.stratum.fraction_id,
        reference.stratum.ladder_id,
        family,
        required,
    )
    merged = CandidateOOF(
        stratum,
        candidate_id,
        final_folds,
        threshold.threshold,
        float(np.mean([fold.roc_auc for fold in final_folds])),
        float(np.mean([fold.tss_at_oof_threshold for fold in final_folds])),
        {
            seed: record
            for result in ordered
            for seed, record in result.neural_epochs_by_seed.items()
        },
        {
            seed: records
            for result in ordered
            for seed, records in result.neural_receipts.items()
        },
        {
            seed: reports
            for result in ordered
            for seed, reports in result.fit_reports_by_seed.items()
        },
    )
    select_candidate([merged])
    return merged


def validate_family_candidates(
    family: str,
    complete: Mapping[str, CandidateOOF],
    invalid_candidate_ids: Iterable[str],
) -> CandidateOOF:
    invalid = set(invalid_candidate_ids)
    if set(complete) & invalid:
        raise Goal029Error("candidate_both_complete_and_invalid")
    expected = set(CANDIDATE_IDS[family])
    if not set(complete) | invalid <= expected:
        raise Goal029Error("unknown_candidate_state")
    if family == "intercept":
        if "null00" not in complete:
            raise Goal029Error("mandatory_null_failed")
    else:
        anchor = ANCHORS[family]
        if anchor not in complete:
            raise Goal029Error(f"mandatory_anchor_failed:{family}")
        if len(complete) < 2:
            raise Goal029Error(f"family_candidate_quorum_failed:{family}")
    return select_candidate([complete[candidate] for candidate in sorted(complete)])


def blinded_failure_receipt(
    context: ExecutionContext,
    leaf: ProductionLeaf,
    failure_code: str,
) -> Mapping[str, Any]:
    if not re.fullmatch(r"[a-z0-9_:-]+", failure_code):
        raise Goal029Error("failure_code_invalid")
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "candidate_stratum": {
            "species_id": leaf.species_id,
            "fraction_id": leaf.fraction_id,
            "ladder_id": leaf.ladder_id,
            "model_family": leaf.model_family,
            "candidate_id": leaf.candidate_id,
        },
        "status": "invalid_candidate",
        "failure_code": failure_code,
        "partial_performance_exposed": False,
        "source_tree_digest": context.source_tree_digest,
        "config_digest": context.config_digest,
        "runtime_fingerprint": context.runtime_fingerprint,
        "host_id": context.host_id,
    }
    payload["receipt_digest"] = _sha(payload)
    return payload


def build_challenge_batch(batch: FeatureBatch, maximum_rows: int = 32) -> FeatureBatch:
    if maximum_rows < 1 or batch.x.ndim != 2 or len(batch.x) < 1:
        raise Goal029Error("challenge_input_invalid")
    unique_by_bytes: dict[bytes, np.ndarray] = {}
    for row in np.asarray(batch.x, dtype=np.float64):
        canonical_bytes = np.asarray(row, dtype=">f8").tobytes(order="C")
        unique_by_bytes.setdefault(canonical_bytes, np.asarray(row, dtype=np.float64))
    ordered_bytes = sorted(unique_by_bytes)
    count = min(maximum_rows, len(ordered_bytes))
    if count < 1:
        raise Goal029Error("challenge_unique_support_empty")
    if count == 1:
        indices = [0]
    else:
        indices = [
            (index * (len(ordered_bytes) - 1)) // (count - 1)
            for index in range(count)
        ]
    matrix = np.asarray(
        [unique_by_bytes[ordered_bytes[index]] for index in indices],
        dtype=np.float64,
    )
    if not np.isfinite(matrix).all():
        raise Goal029Error("challenge_nonfinite")
    keys = tuple(RowKey("challenge", f"row{index:03d}") for index in range(count))
    # Challenge labels are structural zero placeholders and are never read by
    # prediction; no response or source-row identity is retained.
    return FeatureBatch(
        keys,
        matrix,
        np.zeros(count, dtype=np.float64),
        batch.feature_names,
        batch.feature_kinds,
        batch.continuous_count,
        batch.feature_schema_digest,
        {},
        batch.transform_id,
        batch.transform_digest,
        batch.encoder_digest,
    )


def challenge_payload(batch: FeatureBatch) -> Mapping[str, Any]:
    if any(key.species_id != "challenge" for key in batch.keys):
        raise Goal029Error("challenge_key_invalid")
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "matrix": batch.x.tolist(),
        "matrix_bytes_sha256": hashlib.sha256(
            np.asarray(batch.x, dtype=">f8").tobytes(order="C")
        ).hexdigest(),
        "feature_names": list(batch.feature_names),
        "feature_kinds": list(batch.feature_kinds),
        "continuous_count": batch.continuous_count,
        "feature_schema_digest": batch.feature_schema_digest,
        "transform_id": batch.transform_id,
        "transform_digest": batch.transform_digest,
        "encoder_digest": batch.encoder_digest,
        "contains_row_ids": False,
        "contains_response": False,
    }
    payload["challenge_digest"] = _sha(payload)
    return payload


def challenge_from_payload(value: Mapping[str, Any]) -> FeatureBatch:
    body = dict(value)
    claimed = body.pop("challenge_digest", None)
    if (
        claimed != _sha(body)
        or value.get("contains_row_ids") is not False
        or value.get("contains_response") is not False
    ):
        raise Goal029Error("challenge_payload_invalid")
    matrix = np.asarray(value["matrix"], dtype=np.float64)
    if hashlib.sha256(
        np.asarray(matrix, dtype=">f8").tobytes(order="C")
    ).hexdigest() != value.get("matrix_bytes_sha256"):
        raise Goal029Error("challenge_matrix_bytes_mismatch")
    keys = tuple(RowKey("challenge", f"row{index:03d}") for index in range(len(matrix)))
    return FeatureBatch(
        keys,
        matrix,
        np.zeros(len(matrix), dtype=np.float64),
        tuple(value["feature_names"]),
        tuple(value["feature_kinds"]),
        int(value["continuous_count"]),
        str(value["feature_schema_digest"]),
        {},
        str(value["transform_id"]),
        str(value["transform_digest"]),
        str(value["encoder_digest"]),
    )


def canonical_prediction_bytes_sha256(scores: Sequence[float]) -> str:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise Goal029Error("prediction_bytes_invalid")
    payload = len(values).to_bytes(8, "big") + np.asarray(
        values, dtype=">f8"
    ).tobytes(order="C")
    return hashlib.sha256(payload).hexdigest()


def _privacy_walk(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if (
                lowered in _FORBIDDEN_TRACKED_KEYS
                or "exception" in lowered
                or "warning" in lowered
                or "hostname" in lowered
            ):
                raise Goal029Error(f"tracked_privacy_key:{key}")
            _privacy_walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _privacy_walk(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if (
            value.startswith("/")
            or "data/processed/" in value
            or value == socket.gethostname()
            or "traceback" in lowered
            or "exception" in lowered
            or "warning" in lowered
        ):
            raise Goal029Error("tracked_value_forbidden")


def _validate_tracked_summary(value: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "goal_id",
        "mode",
        "synthetic",
        "status",
        "candidate_seed_leaf_count",
        "family_count",
        "selected_model_seed_count",
        "semantic_digest",
        "source_tree_digest",
        "source_audit_leaf_count",
        "source_audit_digest",
        "real_outer_attempted_open_count",
        "real_outer_open_count",
        "performance_values_tracked",
        "response_identifiers_tracked",
        "private_paths_tracked",
    }
    if set(value) != expected_keys:
        raise Goal029Error("tracked_summary_schema_mismatch")
    if (
        value["schema_version"] != "1.0"
        or value["mode"] not in {"synthetic", "production"}
        or value["status"] != "pass"
        or type(value["synthetic"]) is not bool
        or any(
            type(value[key]) is not int
            or isinstance(value[key], bool)
            or value[key] < 0
            for key in (
                "candidate_seed_leaf_count",
                "family_count",
                "selected_model_seed_count",
                "source_audit_leaf_count",
                "real_outer_attempted_open_count",
                "real_outer_open_count",
            )
        )
        or value["real_outer_attempted_open_count"] != 0
        or value["real_outer_open_count"] != 0
        or any(
            value[key] is not False
            for key in (
                "performance_values_tracked",
                "response_identifiers_tracked",
                "private_paths_tracked",
            )
        )
        or _HEX64.fullmatch(str(value["semantic_digest"])) is None
        or _HEX64.fullmatch(str(value["source_tree_digest"])) is None
        or _HEX64.fullmatch(str(value["source_audit_digest"])) is None
    ):
        raise Goal029Error("tracked_summary_value_mismatch")
    _privacy_walk(value)


def _tree_manifest(directory: Path, excluded: Iterable[str] = ()) -> Mapping[str, Any]:
    excluded_set = set(excluded)
    files = {}
    for path in sorted(Path(directory).rglob("*")):
        if path.is_symlink():
            raise Goal029Error("manifest_symlink_forbidden")
        if not path.is_file():
            continue
        relative = str(path.relative_to(directory))
        if relative in excluded_set:
            continue
        files[relative] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {"schema_version": "1.0", "files": files}


def _validate_tree_manifest(
    directory: Path,
    manifest: Mapping[str, Any],
    excluded: Iterable[str] = (),
) -> None:
    if (
        set(manifest) != {"schema_version", "files"}
        or manifest.get("schema_version") != "1.0"
        or not isinstance(manifest.get("files"), Mapping)
    ):
        raise Goal029Error("tree_manifest_schema")
    excluded_set = set(excluded)
    actual_files = set()
    for target in Path(directory).rglob("*"):
        if target.is_symlink():
            raise Goal029Error("manifest_symlink_forbidden")
        if target.is_file():
            relative = str(target.relative_to(directory))
            if relative not in excluded_set:
                actual_files.add(relative)
    if actual_files != set(manifest["files"]):
        raise Goal029Error("tree_manifest_file_set_mismatch")
    for relative, record in manifest.get("files", {}).items():
        target = Path(directory) / relative
        if (
            not isinstance(record, Mapping)
            or set(record) != {"sha256", "bytes"}
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or target.is_symlink()
            or not target.is_file()
            or type(record.get("bytes")) is not int
            or record["bytes"] < 0
            or _HEX64.fullmatch(str(record.get("sha256"))) is None
            or target.stat().st_size != record.get("bytes")
            or sha256_file(target) != record.get("sha256")
        ):
            raise Goal029Error("tree_manifest_mismatch")


def _validate_exact_file_inventory(
    directory: Path,
    expected_files: Iterable[str],
    error_code: str,
) -> None:
    root = Path(directory)
    expected = set(expected_files)
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise Goal029Error(f"{error_code}:symlink")
        if path.is_file():
            actual.add(str(path.relative_to(root)))
    if actual != expected:
        raise Goal029Error(error_code)


def publish_transaction_pair(
    stage_private: Path,
    stage_evidence: Path,
    private_destination: Path,
    evidence_destination: Path,
    transaction_id: str,
) -> None:
    if _HEX64.fullmatch(transaction_id) is None:
        raise Goal029Error("transaction_id_invalid")
    stage_private = Path(stage_private)
    stage_evidence = Path(stage_evidence)
    private_destination = Path(private_destination)
    evidence_destination = Path(evidence_destination)
    if (
        stage_private.is_symlink()
        or stage_evidence.is_symlink()
        or not stage_private.is_dir()
        or not stage_evidence.is_dir()
    ):
        raise Goal029Error("transaction_stage_invalid")
    for destination in (private_destination, evidence_destination):
        if destination.exists() or destination.is_symlink():
            raise Goal029Error("transaction_destination_exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
    private_core = _tree_manifest(stage_private, {"core_manifest.json"})
    evidence_core = _tree_manifest(
        stage_evidence,
        {"core_manifest.json", "PAIR.json", "FINALIZED.json"},
    )
    _write_canonical_json(stage_private / "core_manifest.json", private_core)
    _write_canonical_json(stage_evidence / "core_manifest.json", evidence_core)
    private_core_digest = sha256_file(stage_private / "core_manifest.json")
    evidence_core_digest = sha256_file(stage_evidence / "core_manifest.json")
    pair_descriptor = {
        "schema_version": "1.0",
        "transaction_id": transaction_id,
        "private_core_manifest_sha256": private_core_digest,
        "tracked_core_manifest_sha256": evidence_core_digest,
    }
    _write_canonical_json(stage_evidence / "PAIR.json", pair_descriptor)
    _validate_tree_manifest(
        stage_private, private_core, {"core_manifest.json"}
    )
    _validate_tree_manifest(
        stage_evidence,
        evidence_core,
        {"core_manifest.json", "PAIR.json", "FINALIZED.json"},
    )
    for directory in (stage_private, stage_evidence):
        for path in directory.rglob("*"):
            if path.is_file():
                _fsync_file(path)
        _fsync_directory(directory)
    published: list[Path] = []
    try:
        os.rename(stage_private, private_destination)
        published.append(private_destination)
        os.rename(stage_evidence, evidence_destination)
        published.append(evidence_destination)
        marker = {
            "schema_version": "1.0",
            "transaction_id": transaction_id,
            "pair_descriptor_sha256": sha256_file(
                evidence_destination / "PAIR.json"
            ),
            "publication_state": "finalized",
        }
        temporary_marker = evidence_destination / f".FINALIZED.{uuid.uuid4().hex}.tmp"
        _write_canonical_json(temporary_marker, marker)
        _fsync_file(temporary_marker)
        os.rename(temporary_marker, evidence_destination / "FINALIZED.json")
        _fsync_directory(evidence_destination)
        validate_transaction_pair(private_destination, evidence_destination)
    except Exception as exc:
        restoration_errors = []
        evidence_location = (
            evidence_destination
            if evidence_destination.is_dir()
            else stage_evidence
        )
        if evidence_location.is_dir() and not evidence_location.is_symlink():
            for marker in evidence_location.glob(".FINALIZED.*.tmp"):
                try:
                    marker.unlink()
                except OSError as marker_exc:
                    restoration_errors.append(marker_exc)
            final_marker = evidence_location / "FINALIZED.json"
            if final_marker.is_file() and not final_marker.is_symlink():
                try:
                    final_marker.unlink()
                except OSError as marker_exc:
                    restoration_errors.append(marker_exc)
        for stage, destination in reversed(
            (
                (stage_private, private_destination),
                (stage_evidence, evidence_destination),
            )
        ):
            if destination.exists() or destination.is_symlink():
                if (
                    stage.exists()
                    or stage.is_symlink()
                    or destination.is_symlink()
                    or not destination.is_dir()
                ):
                    restoration_errors.append(
                        Goal029Error("transaction_restore_path_conflict")
                    )
                    continue
                try:
                    os.rename(destination, stage)
                    _fsync_directory(stage.parent)
                except OSError as restore_exc:
                    restoration_errors.append(restore_exc)
        if restoration_errors:
            raise Goal029Error(
                "transaction_publication_restore_incomplete"
            ) from exc
        raise Goal029Error("transaction_publication_rollback") from exc


def validate_transaction_pair(
    private_directory: Path, evidence_directory: Path
) -> Mapping[str, Any]:
    private_directory = Path(private_directory)
    evidence_directory = Path(evidence_directory)
    for directory in (private_directory, evidence_directory):
        if directory.is_symlink() or not directory.is_dir():
            raise Goal029Error("transaction_pair_missing")
    marker_path = evidence_directory / "FINALIZED.json"
    if marker_path.is_symlink() or not marker_path.is_file():
        raise Goal029Error("transaction_unmarked")
    marker = _read_json(marker_path)
    private_core = _read_json(private_directory / "core_manifest.json")
    evidence_core = _read_json(evidence_directory / "core_manifest.json")
    pair_descriptor = _read_json(evidence_directory / "PAIR.json")
    transaction_id = marker.get("transaction_id")
    if (
        set(marker)
        != {
            "schema_version",
            "transaction_id",
            "pair_descriptor_sha256",
            "publication_state",
        }
        or set(pair_descriptor)
        != {
            "schema_version",
            "transaction_id",
            "private_core_manifest_sha256",
            "tracked_core_manifest_sha256",
        }
        or marker.get("schema_version") != "1.0"
        or pair_descriptor.get("schema_version") != "1.0"
        or marker.get("publication_state") != "finalized"
        or _HEX64.fullmatch(str(transaction_id)) is None
        or pair_descriptor.get("transaction_id") != transaction_id
    ):
        raise Goal029Error("transaction_identity_mismatch")
    private_core_digest = sha256_file(private_directory / "core_manifest.json")
    evidence_core_digest = sha256_file(evidence_directory / "core_manifest.json")
    if (
        pair_descriptor.get("private_core_manifest_sha256")
        != private_core_digest
        or pair_descriptor.get("tracked_core_manifest_sha256")
        != evidence_core_digest
        or marker.get("pair_descriptor_sha256")
        != sha256_file(evidence_directory / "PAIR.json")
    ):
        raise Goal029Error("transaction_manifest_mismatch")
    _validate_tree_manifest(
        private_directory, private_core, {"core_manifest.json"}
    )
    _validate_tree_manifest(
        evidence_directory,
        evidence_core,
        {"core_manifest.json", "PAIR.json", "FINALIZED.json"},
    )
    return {
        "status": "pass",
        "transaction_id": transaction_id,
        "outer_attempted_open_count": 0,
        "outer_open_count": 0,
    }


def _production_candidate_groups(
    plan_record: Mapping[str, Any],
) -> tuple[tuple[str, tuple[Mapping[str, Any], ...]], ...]:
    records = plan_record.get("leaf_records")
    if not isinstance(records, list) or len(records) != LEAF_COUNT:
        raise Goal029Error("production_plan_leaf_records_invalid")
    expected_plan = production_plan()
    observed = tuple(ProductionLeaf(**record["leaf"]) for record in records)
    if observed != expected_plan:
        raise Goal029Error("production_plan_leaf_order_mismatch")
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    order: list[str] = []
    for record, leaf in zip(records, observed):
        key = _candidate_stratum_key(leaf)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(record)
    if len(grouped) != CANDIDATE_STRATA_COUNT:
        raise Goal029Error("production_candidate_group_count")
    result = []
    for key in order:
        current = tuple(grouped[key])
        leaves = tuple(ProductionLeaf(**record["leaf"]) for record in current)
        if (
            any(leaf.candidate_stratum != leaves[0].candidate_stratum for leaf in leaves)
            or tuple(leaf.seed_label for leaf in leaves)
            != SEEDS_BY_FAMILY[leaves[0].model_family]
        ):
            raise Goal029Error("production_candidate_seed_group_invalid")
        result.append((key, current))
    return tuple(result)


def _relative_artifact_path(root: Path, raw: str, *, directory: bool) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise Goal029Error("production_artifact_path_invalid")
    target = Path(root) / relative
    resolved_root = Path(root).resolve()
    resolved_target = target.resolve()
    if (
        resolved_root not in resolved_target.parents
        or
        target.is_symlink()
        or (directory and not target.is_dir())
        or (not directory and not target.is_file())
    ):
        raise Goal029Error("production_artifact_missing")
    return target


def _load_candidate_states(
    private_stage: Path,
    plan_record: Mapping[str, Any],
    *,
    require_complete: bool,
) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    path = Path(private_stage) / "candidate_states.json"
    if not path.exists():
        if require_complete:
            raise Goal029Error("production_candidate_states_missing")
        empty = {
            "schema_version": "1.0",
            "plan_record_digest": plan_record["record_digest"],
            "candidate_records": [],
        }
        return empty, {}
    if path.is_symlink():
        raise Goal029Error("production_candidate_states_symlink")
    value = _read_json(path)
    records = value.get("candidate_records")
    if (
        set(value)
        != {"schema_version", "plan_record_digest", "candidate_records"}
        or value.get("schema_version") != "1.0"
        or value.get("plan_record_digest") != plan_record["record_digest"]
        or not isinstance(records, list)
    ):
        raise Goal029Error("production_candidate_states_schema")
    expected_groups = dict(_production_candidate_groups(plan_record))
    state_by_key: dict[str, Mapping[str, Any]] = {}
    for state in records:
        if not isinstance(state, Mapping):
            raise Goal029Error("production_candidate_state_invalid")
        key = _candidate_stratum_key(state["candidate_stratum"])
        if key in state_by_key or key not in expected_groups:
            raise Goal029Error("production_candidate_state_key_invalid")
        expected_records = expected_groups[key]
        expected_leaves = tuple(
            ProductionLeaf(**record["leaf"]) for record in expected_records
        )
        if state.get("status") == "complete":
            if set(state) != {
                "candidate_stratum",
                "status",
                "failure_code",
                "failure_leaf",
                "leaves",
            }:
                raise Goal029Error("production_complete_state_schema")
            leaves = state.get("leaves")
            if (
                state.get("failure_code") != ""
                or state.get("failure_leaf") is not None
                or not isinstance(leaves, list)
                or tuple(ProductionLeaf(**record["leaf"]) for record in leaves)
                != expected_leaves
            ):
                raise Goal029Error("production_complete_state_invalid")
            for leaf_record, expected_record in zip(leaves, expected_records):
                identity = expected_record["identity"]
                if (
                    leaf_record.get("identity_digest")
                    != identity["identity_digest"]
                    or leaf_record.get("checkpoint")
                    != f"checkpoints/{identity['identity_digest']}"
                    or _HEX64.fullmatch(
                        str(leaf_record.get("semantic_result_digest"))
                    )
                    is None
                ):
                    raise Goal029Error("production_complete_leaf_state_invalid")
                checkpoint = _relative_artifact_path(
                    private_stage, leaf_record["checkpoint"], directory=True
                )
                load_leaf_checkpoint(checkpoint, identity)
                if (
                    _read_json(checkpoint / "checkpoint_manifest.json").get(
                        "semantic_result_digest"
                    )
                    != leaf_record["semantic_result_digest"]
                ):
                    raise Goal029Error("production_complete_leaf_digest_mismatch")
        elif state.get("status") == "invalid_candidate":
            if set(state) != {
                "candidate_stratum",
                "status",
                "failure_code",
                "failure_leaf",
                "failure_receipt",
                "failure_receipt_digest",
                "cleanup_complete",
                "leaves",
            }:
                raise Goal029Error("production_invalid_state_schema")
            failure_leaf = ProductionLeaf(**state["failure_leaf"])
            if (
                failure_leaf not in expected_leaves
                or state.get("leaves") != []
                or type(state.get("cleanup_complete")) is not bool
                or re.fullmatch(
                    r"[a-z0-9_:-]+", str(state.get("failure_code"))
                )
                is None
            ):
                raise Goal029Error("production_invalid_state_invalid")
            receipt_path = _relative_artifact_path(
                private_stage, state["failure_receipt"], directory=False
            )
            receipt = _read_json(receipt_path)
            receipt_body = dict(receipt)
            claimed = receipt_body.pop("receipt_digest", None)
            if (
                claimed != _sha(receipt_body)
                or claimed != state["failure_receipt_digest"]
                or receipt.get("candidate_stratum")
                != state["candidate_stratum"]
                or receipt.get("failure_code") != state["failure_code"]
                or receipt.get("partial_performance_exposed") is not False
                or receipt.get("source_tree_digest")
                != plan_record["execution_context"]["source_tree_digest"]
                or receipt.get("config_digest")
                != plan_record["execution_context"]["config_digest"]
                or receipt.get("runtime_fingerprint")
                != plan_record["execution_context"]["runtime_fingerprint"]
                or receipt.get("host_id")
                != plan_record["execution_context"]["host_id"]
            ):
                raise Goal029Error("production_failure_receipt_invalid")
            if state["cleanup_complete"]:
                for expected_record in expected_records:
                    checkpoint = (
                        Path(private_stage)
                        / "checkpoints"
                        / expected_record["identity"]["identity_digest"]
                    )
                    if checkpoint.exists() or checkpoint.is_symlink():
                        raise Goal029Error(
                            "production_invalid_candidate_checkpoint"
                        )
        else:
            raise Goal029Error("production_candidate_status_invalid")
        state_by_key[key] = state
    if require_complete and set(state_by_key) != set(expected_groups):
        raise Goal029Error("production_candidate_state_count")
    return value, state_by_key


def _normalize_production_candidate_state(
    result: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    checkpoint_root: Path,
    private_stage: Path,
    plan_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    reference = ProductionLeaf(**records[0]["leaf"])
    if (
        result.get("candidate_stratum")
        != _candidate_stratum_payload(reference)
        or result.get("real_outer_attempted_open_count") != 0
        or result.get("real_outer_open_count") != 0
    ):
        raise Goal029Error("production_worker_result_scope")
    if result["status"] == "complete":
        normalized_leaves = []
        if len(result["leaves"]) != len(records):
            raise Goal029Error("production_worker_leaf_count")
        for leaf_result, expected in zip(result["leaves"], records):
            identity = expected["identity"]
            checkpoint = Path(leaf_result["checkpoint"])
            if checkpoint.resolve().parent != checkpoint_root.resolve():
                raise Goal029Error("production_worker_checkpoint_escape")
            normalized_leaves.append(
                {
                    "leaf": leaf_result["leaf"],
                    "identity_digest": identity["identity_digest"],
                    "checkpoint": f"checkpoints/{identity['identity_digest']}",
                    "semantic_result_digest": leaf_result[
                        "semantic_result_digest"
                    ],
                }
            )
        return {
            "candidate_stratum": result["candidate_stratum"],
            "status": "complete",
            "failure_code": "",
            "failure_leaf": None,
            "leaves": normalized_leaves,
        }
    if result["status"] != "invalid_candidate":
        raise Goal029Error("production_worker_status_invalid")
    failure_leaf = ProductionLeaf(**result["failure_leaf"])
    if failure_leaf.candidate_stratum != reference.candidate_stratum:
        raise Goal029Error("production_failure_leaf_mismatch")
    receipt = blinded_failure_receipt(
        ExecutionContext(**plan_record["execution_context"]),
        failure_leaf,
        result["failure_code"],
    )
    receipt_path = _write_or_validate_content_json(
        Path(private_stage) / "failures", receipt, "receipt_digest"
    )
    return {
        "candidate_stratum": result["candidate_stratum"],
        "status": "invalid_candidate",
        "failure_code": result["failure_code"],
        "failure_leaf": result["failure_leaf"],
        "failure_receipt": str(receipt_path.relative_to(private_stage)),
        "failure_receipt_digest": receipt["receipt_digest"],
        "cleanup_complete": False,
        "leaves": [],
    }


def _candidate_state_value(
    plan_record: Mapping[str, Any],
    groups: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    state_by_key: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_record_digest": plan_record["record_digest"],
        "candidate_records": [
            state_by_key[group_key]
            for group_key, _ in groups
            if group_key in state_by_key
        ],
    }


def _finish_invalid_candidate_cleanup(
    private_stage: Path,
    plan_record: Mapping[str, Any],
    groups: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
    state_by_key: dict[str, Mapping[str, Any]],
) -> None:
    checkpoint_root = Path(private_stage) / "checkpoints"
    group_lookup = dict(groups)
    for key, _ in groups:
        state = state_by_key.get(key)
        if (
            state is None
            or state["status"] != "invalid_candidate"
            or state["cleanup_complete"]
        ):
            continue
        for record in group_lookup[key]:
            checkpoint = checkpoint_root / record["identity"]["identity_digest"]
            if checkpoint.is_symlink():
                raise Goal029Error("production_invalid_checkpoint_symlink")
            if checkpoint.is_dir():
                shutil.rmtree(checkpoint)
                _fsync_directory(checkpoint_root)
            elif checkpoint.exists():
                raise Goal029Error(
                    "production_invalid_checkpoint_not_directory"
                )
        state_by_key[key] = {**state, "cleanup_complete": True}
        _replace_atomic_json_file(
            Path(private_stage) / "candidate_states.json",
            _candidate_state_value(plan_record, groups, state_by_key),
        )


def execute_production_candidates(
    root: Path,
    config: Mapping[str, Any],
    private_stage: Path,
    plan_record: Mapping[str, Any],
    workers: int,
) -> Mapping[str, Any]:
    if workers not in (1, 2, 4):
        raise Goal029Error("production_worker_count_invalid")
    _, state_by_key = _load_candidate_states(
        private_stage, plan_record, require_complete=False
    )
    groups = _production_candidate_groups(plan_record)
    _finish_invalid_candidate_cleanup(
        private_stage, plan_record, groups, state_by_key
    )
    pending = [(key, records) for key, records in groups if key not in state_by_key]
    if pending:
        checkpoint_root = Path(private_stage) / "checkpoints"
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_calibration_worker_init,
            initargs=(str(Path(root).resolve()),),
        ) as executor:
            for start in range(0, len(pending), workers):
                batch = pending[start : start + workers]
                results = list(
                    executor.map(
                        _production_worker_candidate,
                        [
                            {
                                "checkpoint_root": str(checkpoint_root),
                                "leaves": list(records),
                            }
                            for _, records in batch
                        ],
                        chunksize=1,
                    )
                )
                for (key, records), result in zip(batch, results):
                    state_by_key[key] = _normalize_production_candidate_state(
                        result,
                        records,
                        checkpoint_root,
                        private_stage,
                        plan_record,
                    )
                    _replace_atomic_json_file(
                        Path(private_stage) / "candidate_states.json",
                        _candidate_state_value(
                            plan_record, groups, state_by_key
                        ),
                    )
                    _finish_invalid_candidate_cleanup(
                        private_stage, plan_record, groups, state_by_key
                    )
    final, _ = _load_candidate_states(
        private_stage, plan_record, require_complete=True
    )
    return final


def _selection_record_base(
    selected: CandidateOOF,
    complete: Mapping[str, CandidateOOF],
    invalid: set[str],
) -> Mapping[str, Any]:
    family = selected.stratum.model_family
    selection_metrics = {
        candidate_id: {
            "mean_fold_roc_auc": result.mean_fold_roc_auc,
            "mean_fold_tss_at_oof_threshold": (
                result.mean_fold_tss_at_oof_threshold
            ),
            "threshold": result.threshold,
        }
        for candidate_id, result in sorted(complete.items())
    }
    return {
        "schema_version": "1.0",
        "family_stratum": {
            "species_id": selected.stratum.species_id,
            "fraction_id": selected.stratum.fraction_id,
            "ladder_id": selected.stratum.ladder_id,
            "model_family": family,
        },
        "selected_candidate_id": selected.candidate_id,
        "complete_candidate_ids": sorted(complete),
        "invalid_candidate_ids": sorted(invalid),
        "selection_metrics": selection_metrics,
        "selection_digest": _sha(selection_metrics),
    }


def reduce_and_refit_production(
    private_stage: Path,
    config: Mapping[str, Any],
    plan_record: Mapping[str, Any],
    broker: SplitBroker,
    provider: FeatureProvider,
    vault: OuterVault,
) -> Mapping[str, Any]:
    context = ExecutionContext(**plan_record["execution_context"])
    _, states = _load_candidate_states(
        private_stage, plan_record, require_complete=True
    )
    plan_lookup = {
        ProductionLeaf(**record["leaf"]): record
        for record in plan_record["leaf_records"]
    }
    state_by_stratum = {
        tuple(json.loads(key)): state for key, state in states.items()
    }
    selection_directory = Path(private_stage) / "selections"
    selection_directory.mkdir(parents=True, exist_ok=True)
    selected_directory = Path(private_stage) / "selected"
    family_records = []
    for species_id in SPECIES:
        for fraction_id, ladder_id in ENDPOINTS:
            for family in FAMILIES:
                complete: dict[str, CandidateOOF] = {}
                invalid: set[str] = set()
                for candidate_id in CANDIDATE_IDS[family]:
                    state = state_by_stratum[
                        (
                            species_id,
                            fraction_id,
                            ladder_id,
                            family,
                            candidate_id,
                        )
                    ]
                    if state["status"] == "invalid_candidate":
                        invalid.add(candidate_id)
                        continue
                    seed_results = {}
                    for seed_label in SEEDS_BY_FAMILY[family]:
                        leaf = ProductionLeaf(
                            species_id,
                            fraction_id,
                            ladder_id,
                            family,
                            candidate_id,
                            seed_label,
                        )
                        identity = plan_lookup[leaf]["identity"]
                        seed_results[seed_label] = load_leaf_checkpoint(
                            Path(private_stage)
                            / "checkpoints"
                            / identity["identity_digest"],
                            identity,
                        )
                    complete[candidate_id] = merge_seed_leaves(
                        seed_results, family, candidate_id
                    )
                selected = validate_family_candidates(family, complete, invalid)
                base = _selection_record_base(selected, complete, invalid)
                index_name = f"{_sha(base['family_stratum'])}.json"
                index_path = selection_directory / index_name
                if index_path.exists() or index_path.is_symlink():
                    if index_path.is_symlink():
                        raise Goal029Error("production_selection_symlink")
                    record = _read_json(index_path)
                    record_body = dict(record)
                    claimed = record_body.pop("record_digest", None)
                    if (
                        claimed != _sha(record_body)
                        or {
                            key: record[key]
                            for key in base
                        }
                        != base
                    ):
                        raise Goal029Error("production_selection_resume_mismatch")
                    receipts = record.get("refit_receipts")
                    if not isinstance(receipts, list):
                        raise Goal029Error("production_selection_receipts_invalid")
                    for receipt, seed_label in zip(
                        receipts, SEEDS_BY_FAMILY[family], strict=True
                    ):
                        validate_selected_refit_receipt(
                            receipt,
                            private_stage,
                            expected_task=TaskKey(
                                species_id,
                                "outer",
                                fraction_id,
                                ladder_id,
                                family,
                                selected.candidate_id,
                                seed_label,
                            ),
                            broker=broker,
                            provider=provider,
                            config=config,
                            context=context,
                        )
                else:
                    receipts = list(
                        refit_selected_candidate(
                            selected,
                            broker,
                            provider,
                            vault,
                            config,
                            selected_directory,
                            context,
                        )
                    )
                    record = {
                        **base,
                        "refit_receipts": receipts,
                    }
                    record["record_digest"] = _sha(record)
                    _write_atomic_json_file(index_path, record)
                if len(receipts) != len(SEEDS_BY_FAMILY[family]):
                    raise Goal029Error("production_selected_seed_count")
                expected_tasks = [
                    asdict(
                        TaskKey(
                            species_id,
                            "outer",
                            fraction_id,
                            ladder_id,
                            family,
                            selected.candidate_id,
                            seed_label,
                        )
                    )
                    for seed_label in SEEDS_BY_FAMILY[family]
                ]
                if [receipt["selected_task"] for receipt in receipts] != expected_tasks:
                    raise Goal029Error("production_selected_task_scope")
                family_records.append(
                    {
                        "family_stratum": base["family_stratum"],
                        "relative_path": str(index_path.relative_to(private_stage)),
                        "record_digest": record["record_digest"],
                    }
                )
    if len(family_records) != FAMILY_STRATA_COUNT:
        raise Goal029Error("production_selection_family_count")
    state_digest = sha256_file(Path(private_stage) / "candidate_states.json")
    semantic_digest = _sha(
        {
            "candidate_states_file_sha256": state_digest,
            "selection_record_digests": [
                record["record_digest"] for record in family_records
            ],
        }
    )
    value = {
        "schema_version": "1.0",
        "plan_record_digest": plan_record["record_digest"],
        "candidate_states_file_sha256": state_digest,
        "family_records": family_records,
        "selected_model_seed_count": sum(
            len(_read_json(Path(private_stage) / record["relative_path"])[
                "refit_receipts"
            ])
            for record in family_records
        ),
        "semantic_digest": semantic_digest,
    }
    _replace_atomic_json_file(Path(private_stage) / "selection.json", value)
    return value


def _validate_production_plan_artifacts(
    private_stage: Path,
    context: ExecutionContext,
) -> Mapping[str, Any]:
    plan_record = _read_json(Path(private_stage) / "plan.json")
    body = dict(plan_record)
    claimed = body.pop("record_digest", None)
    if (
        claimed != _sha(body)
        or plan_record.get("execution_context") != asdict(context)
        or plan_record.get("canonical_plan_digest")
        != _sha([asdict(leaf) for leaf in production_plan()])
        or len(plan_record.get("membership_index", {})) != 56 * 6
        or len(plan_record.get("encoder_index", {})) != FAMILY_STRATA_COUNT
    ):
        raise Goal029Error("production_plan_artifact_invalid")
    memberships: dict[
        tuple[str, str, str], dict[str, Mapping[str, Any]]
    ] = {}
    for raw_key, index in plan_record["membership_index"].items():
        species_id, fraction_id, ladder_id, split_id = json.loads(raw_key)
        record = _read_json(
            _relative_artifact_path(
                private_stage, index["relative_path"], directory=False
            )
        )
        if (
            record.get("record_digest") != index["record_digest"]
            or _sha({key: record[key] for key in record if key != "record_digest"})
            != record["record_digest"]
        ):
            raise Goal029Error("production_membership_artifact_invalid")
        memberships.setdefault(
            (species_id, fraction_id, ladder_id), {}
        )[split_id] = record
    if len(memberships) != 56:
        raise Goal029Error("production_membership_stratum_count")
    for (species_id, fraction_id, ladder_id), records in memberships.items():
        _validate_membership_records(
            records,
            ProductionLeaf(
                species_id,
                fraction_id,
                ladder_id,
                "intercept",
                "null00",
                "seed00",
            ),
        )
    encoders = {}
    for raw_key, index in plan_record["encoder_index"].items():
        key = tuple(json.loads(raw_key))
        record = _read_json(
            _relative_artifact_path(
                private_stage, index["relative_path"], directory=False
            )
        )
        body = dict(record)
        record_digest = body.pop("record_digest", None)
        if (
            record_digest != _sha(body)
            or record_digest != index["record_digest"]
        ):
            raise Goal029Error("production_encoder_artifact_invalid")
        encoders[key] = record
    for record, leaf in zip(plan_record["leaf_records"], production_plan()):
        membership = memberships[
            (leaf.species_id, leaf.fraction_id, leaf.ladder_id)
        ]
        encoder_record = encoders[leaf.family_stratum]
        expected = leaf_identity(
            leaf,
            context,
            membership,
            encoder_record["encoder_digests"],
        )
        if record["leaf"] != asdict(leaf) or record["identity"] != expected:
            raise Goal029Error("production_leaf_identity_recompute_mismatch")
    return plan_record


def _validate_production_inventory(
    private_stage: Path,
    evidence_stage: Path,
    plan_record: Mapping[str, Any],
    states: Mapping[str, Mapping[str, Any]],
    selection: Mapping[str, Any],
    family_records: Sequence[Mapping[str, Any]],
    *,
    require_source_audit: bool,
) -> None:
    expected_private = {
        "plan.json",
        "candidate_states.json",
        "selection.json",
        "run.json",
    }
    if require_source_audit:
        expected_private.add("source_audit.json")
    expected_private.update(
        index["relative_path"]
        for index in plan_record["membership_index"].values()
    )
    expected_private.update(
        index["relative_path"] for index in plan_record["encoder_index"].values()
    )
    for state in states.values():
        if state["status"] == "complete":
            for leaf in state["leaves"]:
                expected_private.update(
                    f"{leaf['checkpoint']}/{name}"
                    for name in (
                        "identity.json",
                        "result.json",
                        "oof.parquet",
                        "checkpoint_manifest.json",
                    )
                )
        else:
            expected_private.add(state["failure_receipt"])
    expected_private.update(
        index["relative_path"] for index in selection["family_records"]
    )
    for record in family_records:
        for receipt in record["refit_receipts"]:
            expected_private.update(
                f"{receipt['bundle_path']}/{name}"
                for name in ("model.model", "challenge.json", "receipt.json")
            )
    _validate_exact_file_inventory(
        private_stage,
        expected_private,
        "production_private_file_inventory",
    )
    _validate_exact_file_inventory(
        evidence_stage,
        {"summary.json"},
        "production_tracked_file_inventory",
    )


def validate_production_staged(
    private_stage: Path,
    evidence_stage: Path,
    context: ExecutionContext,
    *,
    broker: SplitBroker,
    provider: FeatureProvider,
    config: Mapping[str, Any],
    require_source_audit: bool,
) -> Mapping[str, Any]:
    plan_record = _validate_production_plan_artifacts(private_stage, context)
    _, states = _load_candidate_states(
        private_stage, plan_record, require_complete=True
    )
    selection = _read_json(Path(private_stage) / "selection.json")
    if (
        selection.get("plan_record_digest") != plan_record["record_digest"]
        or selection.get("candidate_states_file_sha256")
        != sha256_file(Path(private_stage) / "candidate_states.json")
        or len(selection.get("family_records", [])) != FAMILY_STRATA_COUNT
        or selection.get("selected_model_seed_count") > SELECTED_REFIT_MAXIMUM
        or _HEX64.fullmatch(str(selection.get("semantic_digest"))) is None
    ):
        raise Goal029Error("production_selection_index_invalid")
    family_records = []
    plan_lookup = {
        ProductionLeaf(**record["leaf"]): record
        for record in plan_record["leaf_records"]
    }
    state_by_stratum = {
        tuple(json.loads(key)): state for key, state in states.items()
    }
    expected_family_strata = [
        {
            "species_id": species_id,
            "fraction_id": fraction_id,
            "ladder_id": ladder_id,
            "model_family": family,
        }
        for species_id in SPECIES
        for fraction_id, ladder_id in ENDPOINTS
        for family in FAMILIES
    ]
    if [
        index.get("family_stratum") for index in selection["family_records"]
    ] != expected_family_strata:
        raise Goal029Error("production_selection_family_order")
    for index in selection["family_records"]:
        record = _read_json(
            _relative_artifact_path(
                private_stage, index["relative_path"], directory=False
            )
        )
        body = dict(record)
        claimed = body.pop("record_digest", None)
        if (
            claimed != _sha(body)
            or claimed != index["record_digest"]
            or record.get("family_stratum") != index["family_stratum"]
        ):
            raise Goal029Error("production_selection_record_invalid")
        family = record["family_stratum"]["model_family"]
        species_id = record["family_stratum"]["species_id"]
        fraction_id = record["family_stratum"]["fraction_id"]
        ladder_id = record["family_stratum"]["ladder_id"]
        if (
            record["selected_candidate_id"]
            not in record["complete_candidate_ids"]
            or set(record["complete_candidate_ids"])
            | set(record["invalid_candidate_ids"])
            != set(CANDIDATE_IDS[family])
            or ANCHORS.get(family, "null00")
            not in record["complete_candidate_ids"]
            or len(record["complete_candidate_ids"])
            < (1 if family == "intercept" else 2)
        ):
            raise Goal029Error("production_selection_policy_invalid")
        complete: dict[str, CandidateOOF] = {}
        invalid: set[str] = set()
        for candidate_id in CANDIDATE_IDS[family]:
            state = state_by_stratum[
                (
                    species_id,
                    fraction_id,
                    ladder_id,
                    family,
                    candidate_id,
                )
            ]
            if state["status"] == "invalid_candidate":
                invalid.add(candidate_id)
                continue
            seed_results = {}
            for seed_label in SEEDS_BY_FAMILY[family]:
                leaf = ProductionLeaf(
                    species_id,
                    fraction_id,
                    ladder_id,
                    family,
                    candidate_id,
                    seed_label,
                )
                identity = plan_lookup[leaf]["identity"]
                seed_results[seed_label] = load_leaf_checkpoint(
                    Path(private_stage)
                    / "checkpoints"
                    / identity["identity_digest"],
                    identity,
                )
            complete[candidate_id] = merge_seed_leaves(
                seed_results, family, candidate_id
            )
        selected = validate_family_candidates(family, complete, invalid)
        expected_base = _selection_record_base(selected, complete, invalid)
        if {key: record[key] for key in expected_base} != expected_base:
            raise Goal029Error("production_selection_recompute_mismatch")
        expected_tasks = [
            asdict(
                TaskKey(
                    species_id,
                    "outer",
                    fraction_id,
                    ladder_id,
                    family,
                    selected.candidate_id,
                    seed_label,
                )
            )
            for seed_label in SEEDS_BY_FAMILY[family]
        ]
        if [
            receipt["selected_task"] for receipt in record["refit_receipts"]
        ] != expected_tasks:
            raise Goal029Error("production_selected_task_scope")
        for receipt, expected_task_payload in zip(
            record["refit_receipts"], expected_tasks, strict=True
        ):
            validate_selected_refit_receipt(
                receipt,
                private_stage,
                expected_task=TaskKey(**expected_task_payload),
                broker=broker,
                provider=provider,
                config=config,
                context=context,
            )
        family_records.append(record)
    semantic_digest = _sha(
        {
            "candidate_states_file_sha256": sha256_file(
                Path(private_stage) / "candidate_states.json"
            ),
            "selection_record_digests": [
                record["record_digest"] for record in family_records
            ],
        }
    )
    if semantic_digest != selection["semantic_digest"]:
        raise Goal029Error("production_semantic_digest_mismatch")
    run = _read_json(Path(private_stage) / "run.json")
    summary = _read_json(Path(evidence_stage) / "summary.json")
    _validate_tracked_summary(summary)
    if (
        run.get("mode") != "production"
        or run.get("synthetic") is not False
        or run.get("execution_context") != asdict(context)
        or run.get("selected_workers")
        not in config["execution"]["worker_ladder"]
        or run.get("plan_record_digest") != plan_record["record_digest"]
        or run.get("semantic_digest") != semantic_digest
        or run.get("candidate_seed_leaf_count") != LEAF_COUNT
        or run.get("family_count") != FAMILY_STRATA_COUNT
        or run.get("selected_model_seed_count")
        != selection["selected_model_seed_count"]
        or run.get("real_outer_attempted_open_count") != 0
        or run.get("real_outer_open_count") != 0
        or summary.get("mode") != "production"
        or summary.get("synthetic") is not False
        or summary.get("goal_id") != config["identity"]["goal_id"]
        or summary.get("source_tree_digest") != context.source_tree_digest
        or summary.get("semantic_digest") != semantic_digest
        or summary.get("candidate_seed_leaf_count") != LEAF_COUNT
        or summary.get("family_count") != FAMILY_STRATA_COUNT
        or summary.get("selected_model_seed_count")
        != selection["selected_model_seed_count"]
        or len(states) != CANDIDATE_STRATA_COUNT
    ):
        raise Goal029Error("production_run_summary_mismatch")
    if require_source_audit:
        audit = _read_json(Path(private_stage) / "source_audit.json")
        _validate_production_source_audit(
            audit, run, context, plan_record, states, config
        )
        claimed = audit["receipt_digest"]
        if (
            run.get("source_audit_receipt_digest") != claimed
            or summary.get("source_audit_digest") != claimed
            or run.get("source_audit_leaf_count") != audit.get("leaf_count")
            or summary.get("source_audit_leaf_count") != audit.get("leaf_count")
        ):
            raise Goal029Error("production_source_audit_invalid")
    elif (
        summary.get("source_audit_leaf_count") != 0
        or summary.get("source_audit_digest") != "0" * 64
    ):
        raise Goal029Error("production_source_audit_premature")
    _validate_production_inventory(
        private_stage,
        evidence_stage,
        plan_record,
        states,
        selection,
        family_records,
        require_source_audit=require_source_audit,
    )
    return {
        "status": "pass",
        "mode": "production",
        "candidate_seed_leaf_count": LEAF_COUNT,
        "family_count": FAMILY_STRATA_COUNT,
        "selected_model_seed_count": selection["selected_model_seed_count"],
        "semantic_digest": semantic_digest,
        "source_audit_leaf_count": summary["source_audit_leaf_count"],
        "outer_attempted_open_count": 0,
        "outer_open_count": 0,
    }


def _production_source_audit_candidate(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    if (
        _CALIBRATION_CONFIG is None
        or _CALIBRATION_BROKER is None
        or _CALIBRATION_PROVIDER is None
        or _CALIBRATION_VAULT is None
    ):
        raise Goal029Error("source_audit_worker_uninitialised")
    selected = tuple(ProductionLeaf(**leaf) for leaf in value["selected_leaves"])
    complete_candidate = value["expected_status"] == "complete"
    if complete_candidate:
        results = []
        try:
            for leaf in selected:
                result = run_leaf(
                    leaf,
                    _CALIBRATION_BROKER,
                    _CALIBRATION_PROVIDER,
                    _CALIBRATION_CONFIG,
                )
                results.append(
                    {
                        "leaf": asdict(leaf),
                        "semantic_result_digest": _semantic_result_digest(
                            _result_metadata(result), _oof_table(result)
                        ),
                    }
                )
        except ModelAdapterError as exc:
            return {
                "status": "invalid_candidate",
                "failure_code": _canonical_failure_code(exc),
                "failure_leaf": asdict(leaf),
                "results": [],
            }
        output = {
            "status": "complete",
            "failure_code": "",
            "failure_leaf": None,
            "results": results,
        }
    else:
        reference = selected[0]
        output = None
        for seed_label in SEEDS_BY_FAMILY[reference.model_family]:
            leaf = ProductionLeaf(
                *reference.candidate_stratum, seed_label
            )
            try:
                run_leaf(
                    leaf,
                    _CALIBRATION_BROKER,
                    _CALIBRATION_PROVIDER,
                    _CALIBRATION_CONFIG,
                )
            except ModelAdapterError as exc:
                output = {
                    "status": "invalid_candidate",
                    "failure_code": _canonical_failure_code(exc),
                    "failure_leaf": asdict(leaf),
                    "results": [],
                }
                break
        if output is None:
            output = {
                "status": "complete",
                "failure_code": "",
                "failure_leaf": None,
                "results": [],
            }
    if (
        _CALIBRATION_VAULT.attempted_open_count != 0
        or _CALIBRATION_VAULT.open_count != 0
    ):
        raise Goal029Error("source_audit_outer_access")
    return {
        **output,
        "candidate_stratum": _candidate_stratum_payload(selected[0]),
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }


def _expected_source_audit_rows(
    leaves: Sequence[ProductionLeaf],
    states: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for leaf in leaves:
        state = states[_candidate_stratum_key(leaf)]
        if state["status"] == "complete":
            by_leaf = {
                ProductionLeaf(**record["leaf"]): record[
                    "semantic_result_digest"
                ]
                for record in state["leaves"]
            }
            rows.append(
                {
                    "leaf": asdict(leaf),
                    "status": "complete",
                    "semantic_result_digest": by_leaf[leaf],
                }
            )
        else:
            rows.append(
                {
                    "leaf": asdict(leaf),
                    "status": "invalid_candidate",
                    "failure_code": state["failure_code"],
                }
            )
    return rows


def _validate_production_source_audit(
    audit: Mapping[str, Any],
    run: Mapping[str, Any],
    context: ExecutionContext,
    plan_record: Mapping[str, Any],
    states: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        "selection_salt",
        "audit_leaf_digest",
        "leaf_count",
        "results_digest",
        "plan_record_digest",
        "candidate_states_file_sha256",
        "cache_disabled",
        "fresh_process",
        "fresh_destination",
        "workers",
        "real_outer_attempted_open_count",
        "real_outer_open_count",
        "receipt_digest",
    }
    body = dict(audit)
    claimed = body.pop("receipt_digest", None)
    plan = production_plan(config)
    salt = audit_salt(plan, context)
    leaves = audit_plan(plan, salt)
    expected_rows = _expected_source_audit_rows(leaves, states)
    minimum = int(
        config["validation"]["source_to_result_audit"]["minimum_leaf_count"]
    )
    if (
        set(audit) != expected_keys
        or claimed != _sha(body)
        or audit.get("schema_version") != "1.0"
        or audit.get("selection_salt") != salt
        or audit.get("audit_leaf_digest")
        != _sha([asdict(leaf) for leaf in leaves])
        or len(leaves) != minimum
        or audit.get("leaf_count") != len(leaves)
        or audit.get("results_digest") != _sha(expected_rows)
        or audit.get("plan_record_digest") != plan_record["record_digest"]
        or audit.get("candidate_states_file_sha256")
        != run.get("candidate_states_file_sha256")
        or audit.get("workers") != run.get("selected_workers")
        or audit.get("cache_disabled") is not True
        or audit.get("fresh_process") is not True
        or audit.get("fresh_destination") is not True
        or audit.get("real_outer_attempted_open_count") != 0
        or audit.get("real_outer_open_count") != 0
    ):
        raise Goal029Error("production_source_audit_invalid")


def run_fresh_production_source_audit(
    root: Path,
    context: ExecutionContext,
    private_stage: Path,
    plan_record: Mapping[str, Any],
    workers: int,
) -> Mapping[str, Any]:
    plan = production_plan()
    salt = audit_salt(plan, context)
    leaves = audit_plan(plan, salt)
    _, states = _load_candidate_states(
        private_stage, plan_record, require_complete=True
    )
    selected_groups: dict[str, list[ProductionLeaf]] = {}
    for leaf in leaves:
        selected_groups.setdefault(_candidate_stratum_key(leaf), []).append(leaf)
    payloads = []
    for key, selected in selected_groups.items():
        state = states[key]
        payloads.append(
            {
                "selected_leaves": [asdict(leaf) for leaf in selected],
                "expected_status": state["status"],
            }
        )
    destination = Path(
        tempfile.mkdtemp(prefix="goal029-production-source-audit-fresh-")
    )
    try:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_calibration_worker_init,
            initargs=(str(Path(root).resolve()),),
        ) as executor:
            results = list(
                executor.map(
                    _production_source_audit_candidate,
                    payloads,
                    chunksize=1,
                )
            )
        result_by_key = {
            _candidate_stratum_key(record["candidate_stratum"]): record
            for record in results
        }
        if (
            len(results) != len(selected_groups)
            or set(result_by_key) != set(selected_groups)
        ):
            raise Goal029Error("source_audit_candidate_result_set_mismatch")
        audit_rows = []
        for key, selected in selected_groups.items():
            state = states[key]
            observed = result_by_key[key]
            if (
                observed["status"] != state["status"]
                or observed["real_outer_attempted_open_count"] != 0
                or observed["real_outer_open_count"] != 0
            ):
                raise Goal029Error("source_audit_candidate_status_mismatch")
            if state["status"] == "complete":
                expected = {
                    ProductionLeaf(**record["leaf"]): record[
                        "semantic_result_digest"
                    ]
                    for record in state["leaves"]
                }
                expected_observed = [
                    {
                        "leaf": asdict(leaf),
                        "semantic_result_digest": expected[leaf],
                    }
                    for leaf in selected
                ]
                if observed["results"] != expected_observed:
                    raise Goal029Error("source_audit_result_mismatch")
                audit_rows.extend(
                    {
                        "leaf": asdict(leaf),
                        "status": "complete",
                        "semantic_result_digest": expected[leaf],
                    }
                    for leaf in selected
                )
            else:
                if (
                    observed["failure_code"] != state["failure_code"]
                    or observed["failure_leaf"] != state["failure_leaf"]
                ):
                    raise Goal029Error("source_audit_failure_mismatch")
                audit_rows.extend(
                    {
                        "leaf": asdict(leaf),
                        "status": "invalid_candidate",
                        "failure_code": state["failure_code"],
                    }
                    for leaf in selected
                )
        audit_rows = _expected_source_audit_rows(leaves, states)
        receipt = {
            "schema_version": "1.0",
            "selection_salt": salt,
            "audit_leaf_digest": _sha([asdict(leaf) for leaf in leaves]),
            "leaf_count": len(leaves),
            "results_digest": _sha(audit_rows),
            "plan_record_digest": plan_record["record_digest"],
            "candidate_states_file_sha256": sha256_file(
                Path(private_stage) / "candidate_states.json"
            ),
            "cache_disabled": True,
            "fresh_process": True,
            "fresh_destination": True,
            "workers": workers,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        receipt["receipt_digest"] = _sha(receipt)
        _write_canonical_json(destination / "source_audit.json", receipt)
        return _read_json(destination / "source_audit.json")
    finally:
        shutil.rmtree(destination, ignore_errors=True)


def validate_production_publication(
    root: Path, private_directory: Path, evidence_directory: Path
) -> Mapping[str, Any]:
    transaction = validate_transaction_pair(private_directory, evidence_directory)
    config = load_goal029_config(root)
    context = execution_context(root, config)
    broker, provider, vault = ingest_production_foundation(root, config)
    result = validate_production_staged(
        private_directory,
        evidence_directory,
        context,
        broker=broker,
        provider=provider,
        config=config,
        require_source_audit=True,
    )
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("production_validation_outer_access")
    return {**result, "transaction_id": transaction["transaction_id"]}


def run_production(root: Path) -> Mapping[str, Any]:
    root = Path(root).resolve()
    config = load_goal029_config(root)
    context = execution_context(root, config)
    calibration = load_calibration_authority(root, config, context)
    plan = production_plan(config)
    run_id = _sha(
        {
            "execution_context": asdict(context),
            "canonical_plan_digest": _sha([asdict(leaf) for leaf in plan]),
            "calibration_receipt_digest": calibration["private"][
                "receipt_digest"
            ],
        }
    )
    private_destination = _safe_bound_path(
        root, config["artifacts"]["private_destination"]
    )
    evidence_destination = _safe_bound_path(
        root, config["artifacts"]["tracked_destination"]
    )
    if (
        private_destination.exists()
        or private_destination.is_symlink()
        or evidence_destination.exists()
        or evidence_destination.is_symlink()
    ):
        raise Goal029Error("production_destination_exists")
    private_stage = (
        private_destination.parent
        / f".{private_destination.name}.stage-{run_id}"
    )
    evidence_stage = (
        evidence_destination.parent
        / f".{evidence_destination.name}.stage-{run_id}"
    )
    for stage in (private_stage, evidence_stage):
        if stage.is_symlink():
            raise Goal029Error("production_stage_symlink")
        stage.mkdir(parents=True, exist_ok=True)
    broker, provider, vault = ingest_production_foundation(root, config)
    support = class_support_scan(broker)
    if _sha(support) != calibration["private"]["class_support_scan_digest"]:
        raise Goal029Error("production_class_support_calibration_mismatch")
    plan_record = prepare_production_provenance(
        private_stage, plan, broker, provider, context
    )
    workers = int(calibration["private"]["selected_workers"])
    candidate_states = execute_production_candidates(
        root, config, private_stage, plan_record, workers
    )
    selection = reduce_and_refit_production(
        private_stage, config, plan_record, broker, provider, vault
    )
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("production_outer_access")
    run_record = {
        "schema_version": "1.0",
        "mode": "production",
        "synthetic": False,
        "run_id": run_id,
        "execution_context": asdict(context),
        "calibration_receipt_digest": calibration["private"]["receipt_digest"],
        "selected_workers": workers,
        "plan_record_digest": plan_record["record_digest"],
        "candidate_states_file_sha256": sha256_file(
            private_stage / "candidate_states.json"
        ),
        "selection_file_sha256": sha256_file(
            private_stage / "selection.json"
        ),
        "candidate_seed_leaf_count": LEAF_COUNT,
        "candidate_strata_count": len(candidate_states["candidate_records"]),
        "family_count": FAMILY_STRATA_COUNT,
        "selected_model_seed_count": selection["selected_model_seed_count"],
        "semantic_digest": selection["semantic_digest"],
        "source_audit_leaf_count": 0,
        "source_audit_receipt_digest": "0" * 64,
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    _replace_atomic_json_file(private_stage / "run.json", run_record)
    tracked_summary = {
        "schema_version": "1.0",
        "goal_id": config["identity"]["goal_id"],
        "mode": "production",
        "synthetic": False,
        "status": "pass",
        "candidate_seed_leaf_count": LEAF_COUNT,
        "family_count": FAMILY_STRATA_COUNT,
        "selected_model_seed_count": selection["selected_model_seed_count"],
        "semantic_digest": selection["semantic_digest"],
        "source_tree_digest": context.source_tree_digest,
        "source_audit_leaf_count": 0,
        "source_audit_digest": "0" * 64,
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
        "performance_values_tracked": False,
        "response_identifiers_tracked": False,
        "private_paths_tracked": False,
    }
    _validate_tracked_summary(tracked_summary)
    _replace_atomic_json_file(evidence_stage / "summary.json", tracked_summary)
    validate_production_staged(
        private_stage,
        evidence_stage,
        context,
        broker=broker,
        provider=provider,
        config=config,
        require_source_audit=False,
    )
    source_audit = run_fresh_production_source_audit(
        root, context, private_stage, plan_record, workers
    )
    _replace_atomic_json_file(
        private_stage / "source_audit.json", source_audit
    )
    run_record["source_audit_leaf_count"] = source_audit["leaf_count"]
    run_record["source_audit_receipt_digest"] = source_audit["receipt_digest"]
    _replace_atomic_json_file(private_stage / "run.json", run_record)
    tracked_summary["source_audit_leaf_count"] = source_audit["leaf_count"]
    tracked_summary["source_audit_digest"] = source_audit["receipt_digest"]
    _validate_tracked_summary(tracked_summary)
    _replace_atomic_json_file(evidence_stage / "summary.json", tracked_summary)
    validate_production_staged(
        private_stage,
        evidence_stage,
        context,
        broker=broker,
        provider=provider,
        config=config,
        require_source_audit=True,
    )
    transaction_id = _sha(
        {
            "run_id": run_id,
            "semantic_digest": selection["semantic_digest"],
            "source_audit_receipt_digest": source_audit["receipt_digest"],
        }
    )
    publish_transaction_pair(
        private_stage,
        evidence_stage,
        private_destination,
        evidence_destination,
        transaction_id,
    )
    return validate_production_publication(
        root, private_destination, evidence_destination
    )


def _synthetic_foundation() -> tuple[SplitBroker, FeatureProvider, OuterVault]:
    species_id = SPECIES[0]
    rows: list[Mapping[str, Any]] = []
    values: dict[RowKey, Any] = {}
    folds: dict[RowKey, str] = {}
    for index in range(30):
        key = RowKey(species_id, f"synthetic_{index:03d}")
        response = int(index % 3 == 0)
        rows.append(
            {
                "species_id": species_id,
                "grid_cell_id": key.grid_cell_id,
                "pa": response,
                "pa_type": "presence"
                if response
                else (
                    "survey_supported_absence" if index % 2 else "pseudoabsence"
                ),
                "microcluster": f"mc{index % 4:02d}",
            }
        )
        values[key] = {
            "continuous": [
                float(
                    np.sin((index + 1) * (column + 1) / 13.0)
                    + response * 0.2
                )
                for column in range(25)
            ],
            "categorical": {
                "soil_class": (
                    "unseen_validation"
                    if index == 4
                    else ("north" if index % 2 else "south")
                ),
                "veg_mvg": f"s{index % 2}",
                "landuse_secondary": f"q{index % 3}",
            },
        }
        folds[key] = f"fold{index % 5:02d}"
    return ingest_synthetic_foundation(rows, values, folds)


def _synthetic_plan() -> tuple[ProductionLeaf, ...]:
    candidates = {
        "intercept": ("null00",),
        "elastic_net": ("enet00", "enet01"),
        "gam": ("gam01", "gam04"),
        "random_forest": ("rf02", "rf00"),
        "hist_gradient_boosting": ("hgb04", "hgb00"),
        "shallow_ann": ("ann01", "ann00"),
    }
    return tuple(
        ProductionLeaf(
            SPECIES[0],
            "fraction100",
            "full",
            family,
            candidate,
            seed,
        )
        for family in FAMILIES
        for candidate in candidates[family]
        for seed in SEEDS_BY_FAMILY[family]
    )


def _write_memberships(
    directory: Path,
    memberships: Mapping[str, Mapping[str, Any]],
    leaf: ProductionLeaf,
) -> Mapping[str, str]:
    _validate_membership_records(memberships, leaf)
    paths: dict[str, str] = {}
    for split_id, record in sorted(memberships.items()):
        path = Path(directory) / f"{record['record_digest']}.json"
        _write_canonical_json(path, record)
        _fsync_file(path)
        paths[split_id] = str(path)
    return paths


def _synthetic_source_audit_worker(
    root_value: str,
    leaf_values: Sequence[Mapping[str, Any]],
    expected_digests: Mapping[str, str],
    salt: str,
    destination_value: str,
) -> None:
    root = Path(root_value)
    destination = Path(destination_value)
    config = load_goal029_config(root)
    context = execution_context(root, config)
    leaves = tuple(ProductionLeaf(**value) for value in leaf_values)
    if audit_salt(_synthetic_plan(), context) != salt:
        raise Goal029Error("source_audit_salt_context_mismatch")
    broker, provider, vault = _synthetic_foundation()
    results = []
    for leaf in leaves:
        result = run_leaf(leaf, broker, provider, config)
        semantic_digest = _semantic_result_digest(
            _result_metadata(result), _oof_table(result)
        )
        if expected_digests.get(leaf.leaf_id) != semantic_digest:
            raise Goal029Error("source_audit_result_mismatch")
        results.append(
            {"leaf": asdict(leaf), "semantic_result_digest": semantic_digest}
        )
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("source_audit_outer_access")
    receipt = {
        "schema_version": "1.0",
        "selection_salt": salt,
        "leaf_count": len(leaves),
        "results_digest": _sha(results),
        "cache_disabled": True,
        "fresh_process": True,
        "fresh_destination": True,
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    receipt["receipt_digest"] = _sha(receipt)
    _write_canonical_json(destination / "source_audit.json", receipt)


def run_fresh_synthetic_source_audit(
    root: Path,
    context: ExecutionContext,
    leaf_records: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    plan = _synthetic_plan()
    salt = audit_salt(plan, context)
    leaves = audit_plan(plan, salt)
    expected = {
        ProductionLeaf(**record["leaf"]).leaf_id: record["semantic_result_digest"]
        for record in leaf_records
    }
    destination = Path(tempfile.mkdtemp(prefix="goal029-source-audit-fresh-"))
    process = multiprocessing.get_context("spawn").Process(
        target=_synthetic_source_audit_worker,
        args=(
            str(Path(root).resolve()),
            [asdict(leaf) for leaf in leaves],
            expected,
            salt,
            str(destination),
        ),
    )
    try:
        process.start()
        process.join()
        if process.exitcode != 0:
            raise Goal029Error("source_audit_fresh_process_failed")
        receipt = _read_json(destination / "source_audit.json")
        body = dict(receipt)
        claimed = body.pop("receipt_digest", None)
        if (
            claimed != _sha(body)
            or receipt.get("leaf_count") != len(leaves)
            or receipt.get("selection_salt") != salt
            or receipt.get("cache_disabled") is not True
            or receipt.get("fresh_process") is not True
            or receipt.get("fresh_destination") is not True
            or receipt.get("real_outer_attempted_open_count") != 0
            or receipt.get("real_outer_open_count") != 0
        ):
            raise Goal029Error("source_audit_receipt_invalid")
        return receipt
    finally:
        shutil.rmtree(destination, ignore_errors=True)


def run_synthetic(
    root: Path, output_root: Path | None = None
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    config = load_goal029_config(root)
    context = execution_context(root, config)
    output_root = Path(output_root or root / "temp/goal029-synthetic").resolve()
    if output_root.exists() or output_root.is_symlink():
        raise Goal029Error("synthetic_output_exists")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix="goal029-synthetic-stage-", dir=output_root.parent)
    )
    stage_private = stage_root / "private"
    stage_evidence = stage_root / "evidence"
    for path in (
        stage_private / "checkpoints",
        stage_private / "memberships",
        stage_private / "selected",
        stage_evidence,
    ):
        path.mkdir(parents=True, exist_ok=True)
    broker, provider, vault = _synthetic_foundation()
    plan = _synthetic_plan()
    reference_leaf = plan[0]
    memberships = membership_records(reference_leaf, broker)
    membership_paths = _write_memberships(
        stage_private / "memberships", memberships, reference_leaf
    )
    leaf_records: list[Mapping[str, Any]] = []
    leaf_results: dict[ProductionLeaf, CandidateOOF] = {}
    try:
        encoders_by_family = {
            family: encoder_digests(
                next(leaf for leaf in plan if leaf.model_family == family),
                broker,
                provider,
                memberships,
            )
            for family in FAMILIES
        }
        for leaf in plan:
            identity = leaf_identity(
                leaf, context, memberships, encoders_by_family[leaf.model_family]
            )
            result = run_leaf(leaf, broker, provider, config)
            checkpoint, reused = write_leaf_checkpoint(
                stage_private / "checkpoints", identity, result
            )
            if reused:
                raise Goal029Error("fresh_synthetic_checkpoint_reused")
            leaf_results[leaf] = result
            leaf_records.append(
                {
                    "leaf": asdict(leaf),
                    "identity": identity,
                    "checkpoint": str(checkpoint.relative_to(stage_private)),
                    "semantic_result_digest": _read_json(
                        checkpoint / "checkpoint_manifest.json"
                    )["semantic_result_digest"],
                }
            )

        selected_by_family: dict[str, CandidateOOF] = {}
        selection_private: list[Mapping[str, Any]] = []
        refit_receipts: list[Mapping[str, Any]] = []
        for family in FAMILIES:
            complete: dict[str, CandidateOOF] = {}
            for candidate_id in CANDIDATE_IDS[family]:
                relevant = [
                    leaf
                    for leaf in plan
                    if leaf.model_family == family
                    and leaf.candidate_id == candidate_id
                ]
                if not relevant:
                    continue
                complete[candidate_id] = merge_seed_leaves(
                    {
                        leaf.seed_label: leaf_results[leaf]
                        for leaf in relevant
                    },
                    family,
                    candidate_id,
                )
            selected = validate_family_candidates(family, complete, set())
            selected_by_family[family] = selected
            selection_private.append(
                {
                    "model_family": family,
                    "selected_candidate_id": selected.candidate_id,
                    "candidate_count": len(complete),
                    "selection_digest": _sha(
                        {
                            candidate_id: {
                                "primary": result.mean_fold_roc_auc,
                                "tie": result.mean_fold_tss_at_oof_threshold,
                                "threshold": result.threshold,
                            }
                            for candidate_id, result in sorted(complete.items())
                        }
                    ),
                }
            )
            refit_receipts.extend(
                refit_selected_candidate(
                    selected,
                    broker,
                    provider,
                    vault,
                    config,
                    stage_private / "selected",
                    context,
                )
            )
        for receipt in refit_receipts:
            validate_selected_refit_receipt(
                receipt,
                stage_private,
                expected_task=TaskKey(**receipt["selected_task"]),
                broker=broker,
                provider=provider,
                config=config,
                context=context,
            )
        if vault.attempted_open_count != 0 or vault.open_count != 0:
            raise Goal029Error("synthetic_vault_unexpected_access")

        semantic_digest = _sha(
            {
                "leaves": [
                    {
                        "leaf": record["leaf"],
                        "semantic_result_digest": record["semantic_result_digest"],
                    }
                    for record in leaf_records
                ],
                "selection": selection_private,
                "refits": [
                    {
                        "selected_task": receipt["selected_task"],
                        "model_sha256": receipt["model_sha256"],
                        "challenge_digest": receipt["challenge_digest"],
                        "canonical_prediction_bytes_sha256": receipt[
                            "canonical_prediction_bytes_sha256"
                        ],
                    }
                    for receipt in refit_receipts
                ],
            }
        )
        run_record = {
            "schema_version": "1.0",
            "mode": "synthetic",
            "synthetic": True,
            "execution_context": asdict(context),
            "membership_paths": {
                split: str(Path(path).relative_to(stage_private))
                for split, path in membership_paths.items()
            },
            "membership_digests": {
                split: memberships[split]["record_digest"]
                for split in sorted(memberships)
            },
            "leaf_records": leaf_records,
            "selection": selection_private,
            "refit_receipts": refit_receipts,
            "candidate_seed_leaf_count": len(plan),
            "selected_family_count": len(selected_by_family),
            "selected_model_seed_count": len(refit_receipts),
            "semantic_digest": semantic_digest,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        _write_canonical_json(stage_private / "run.json", run_record)
        tracked_summary = {
            "schema_version": "1.0",
            "goal_id": config["identity"]["goal_id"],
            "mode": "synthetic",
            "synthetic": True,
            "status": "pass",
            "candidate_seed_leaf_count": len(plan),
            "family_count": len(selected_by_family),
            "selected_model_seed_count": len(refit_receipts),
            "semantic_digest": semantic_digest,
            "source_tree_digest": context.source_tree_digest,
            "source_audit_leaf_count": 0,
            "source_audit_digest": "0" * 64,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
            "performance_values_tracked": False,
            "response_identifiers_tracked": False,
            "private_paths_tracked": False,
        }
        _validate_tracked_summary(tracked_summary)
        _write_canonical_json(stage_evidence / "summary.json", tracked_summary)
        # Gate 1: complete staged artifact validation before any independent
        # source work or publication.
        _validate_synthetic_artifacts(
            stage_private, stage_evidence, require_source_audit=False
        )
        # Gate 2: fresh process, no checkpoint reads, and a disposable
        # destination. Only its digest/count cross the tracked boundary.
        source_audit = run_fresh_synthetic_source_audit(
            root, context, leaf_records
        )
        _write_canonical_json(
            stage_private / "source_audit.json", source_audit
        )
        run_record["source_audit_receipt_digest"] = source_audit["receipt_digest"]
        run_record["source_audit_leaf_count"] = source_audit["leaf_count"]
        _write_canonical_json(stage_private / "run.json", run_record)
        tracked_summary["source_audit_leaf_count"] = source_audit["leaf_count"]
        tracked_summary["source_audit_digest"] = source_audit["receipt_digest"]
        _validate_tracked_summary(tracked_summary)
        _write_canonical_json(stage_evidence / "summary.json", tracked_summary)
        _validate_synthetic_artifacts(
            stage_private, stage_evidence, require_source_audit=True
        )
        transaction_id = _sha(
            {
                "mode": "synthetic",
                "context": asdict(context),
                "semantic_digest": semantic_digest,
            }
        )
        publish_transaction_pair(
            stage_private,
            stage_evidence,
            output_root / "private",
            output_root / "evidence",
            transaction_id,
        )
        result = validate_synthetic_publication(
            output_root / "private", output_root / "evidence"
        )
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise
    shutil.rmtree(stage_root, ignore_errors=True)
    return {
        **result,
        "private_directory": str(output_root / "private"),
        "evidence_directory": str(output_root / "evidence"),
    }


def validate_synthetic_publication(
    private_directory: Path, evidence_directory: Path
) -> Mapping[str, Any]:
    transaction = validate_transaction_pair(private_directory, evidence_directory)
    result = _validate_synthetic_artifacts(
        private_directory, evidence_directory, require_source_audit=True
    )
    return {**result, "transaction_id": transaction["transaction_id"]}


def _validate_synthetic_artifacts(
    private_directory: Path,
    evidence_directory: Path,
    *,
    require_source_audit: bool,
) -> Mapping[str, Any]:
    run = _read_json(Path(private_directory) / "run.json")
    broker, provider, vault = _synthetic_foundation()
    context = ExecutionContext(**run["execution_context"])
    synthetic_validation_config = {
        "hardening": {"challenge_rows_maximum": 32}
    }
    summary = _read_json(Path(evidence_directory) / "summary.json")
    _validate_tracked_summary(summary)
    if (
        run.get("mode") != "synthetic"
        or run.get("synthetic") is not True
        or summary.get("mode") != "synthetic"
        or summary.get("synthetic") is not True
        or run.get("real_outer_attempted_open_count") != 0
        or run.get("real_outer_open_count") != 0
        or summary.get("real_outer_attempted_open_count") != 0
        or summary.get("real_outer_open_count") != 0
    ):
        raise Goal029Error("synthetic_publication_scope_mismatch")
    reference_leaf = _synthetic_plan()[0]
    membership_values: dict[str, Mapping[str, Any]] = {}
    paths = run.get("membership_paths", {})
    digests = run.get("membership_digests", {})
    expected_splits = {*(f"cv_{fold}" for fold in FOLDS), "outer"}
    if (
        set(paths) != expected_splits
        or set(digests) != expected_splits
        or len(set(paths.values())) != 6
        or len(set(digests.values())) != 6
    ):
        raise Goal029Error("synthetic_membership_index_invalid")
    for split_id in sorted(expected_splits):
        path = Path(private_directory) / paths[split_id]
        record = _read_json(path)
        if record.get("record_digest") != digests[split_id]:
            raise Goal029Error("synthetic_membership_digest_mismatch")
        membership_values[split_id] = record
    _validate_membership_records(membership_values, reference_leaf)
    leaf_results: dict[ProductionLeaf, CandidateOOF] = {}
    for record in run["leaf_records"]:
        leaf = ProductionLeaf(**record["leaf"])
        checkpoint = Path(private_directory) / record["checkpoint"]
        result = load_leaf_checkpoint(checkpoint, record["identity"])
        if (
            _read_json(checkpoint / "checkpoint_manifest.json")[
                "semantic_result_digest"
            ]
            != record["semantic_result_digest"]
        ):
            raise Goal029Error("synthetic_leaf_digest_mismatch")
        if record["identity"].get("split_membership_digests") != digests:
            raise Goal029Error("synthetic_leaf_membership_identity_mismatch")
        leaf_results[leaf] = result
    selection_expected: list[Mapping[str, Any]] = []
    for family in FAMILIES:
        complete: dict[str, CandidateOOF] = {}
        for candidate_id in CANDIDATE_IDS[family]:
            relevant = [
                leaf
                for leaf in leaf_results
                if leaf.model_family == family and leaf.candidate_id == candidate_id
            ]
            if relevant:
                complete[candidate_id] = merge_seed_leaves(
                    {
                        leaf.seed_label: leaf_results[leaf]
                        for leaf in relevant
                    },
                    family,
                    candidate_id,
                )
        selected = validate_family_candidates(family, complete, set())
        selection_expected.append(
            {
                "model_family": family,
                "selected_candidate_id": selected.candidate_id,
                "candidate_count": len(complete),
                "selection_digest": _sha(
                    {
                        candidate_id: {
                            "primary": result.mean_fold_roc_auc,
                            "tie": result.mean_fold_tss_at_oof_threshold,
                            "threshold": result.threshold,
                        }
                        for candidate_id, result in sorted(complete.items())
                    }
                ),
            }
        )
    if selection_expected != run["selection"]:
        raise Goal029Error("synthetic_selection_recompute_mismatch")
    expected_refit_tasks = [
        TaskKey(
            SPECIES[0],
            "outer",
            "fraction100",
            "full",
            record["model_family"],
            record["selected_candidate_id"],
            seed_label,
        )
        for record in selection_expected
        for seed_label in SEEDS_BY_FAMILY[record["model_family"]]
    ]
    if len(run["refit_receipts"]) != len(expected_refit_tasks):
        raise Goal029Error("synthetic_selected_refit_count")
    for receipt, expected_task in zip(
        run["refit_receipts"], expected_refit_tasks, strict=True
    ):
        validate_selected_refit_receipt(
            receipt,
            private_directory,
            expected_task=expected_task,
            broker=broker,
            provider=provider,
            config=synthetic_validation_config,
            context=context,
        )
    if vault.attempted_open_count != 0 or vault.open_count != 0:
        raise Goal029Error("synthetic_validation_outer_access")
    if (
        summary.get("semantic_digest") != run.get("semantic_digest")
        or summary.get("candidate_seed_leaf_count") != len(leaf_results)
        or summary.get("family_count") != len(FAMILIES)
        or summary.get("selected_model_seed_count") != len(run["refit_receipts"])
    ):
        raise Goal029Error("synthetic_summary_reconciliation_mismatch")
    if require_source_audit:
        audit_path = Path(private_directory) / "source_audit.json"
        if audit_path.is_symlink() or not audit_path.is_file():
            raise Goal029Error("synthetic_source_audit_missing")
        audit = _read_json(audit_path)
        body = dict(audit)
        claimed = body.pop("receipt_digest", None)
        if (
            claimed != _sha(body)
            or run.get("source_audit_receipt_digest") != claimed
            or run.get("source_audit_leaf_count") != audit.get("leaf_count")
            or summary.get("source_audit_digest") != claimed
            or summary.get("source_audit_leaf_count") != audit.get("leaf_count")
            or audit.get("cache_disabled") is not True
            or audit.get("fresh_process") is not True
            or audit.get("fresh_destination") is not True
        ):
            raise Goal029Error("synthetic_source_audit_reconciliation")
    elif (
        summary.get("source_audit_leaf_count") != 0
        or summary.get("source_audit_digest") != "0" * 64
    ):
        raise Goal029Error("synthetic_source_audit_premature")
    return {
        "status": "pass",
        "mode": "synthetic",
        "candidate_seed_leaf_count": len(leaf_results),
        "selected_family_count": len(FAMILIES),
        "selected_model_seed_count": len(run["refit_receipts"]),
        "semantic_digest": run["semantic_digest"],
        "source_audit_leaf_count": summary["source_audit_leaf_count"],
        "outer_attempted_open_count": 0,
        "outer_open_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--mode",
        choices=("plan", "synthetic", "calibration", "production"),
        default="plan",
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "plan":
        config = load_goal029_config(root)
        context = execution_context(root, config)
        plan = production_plan(config)
        audit = audit_plan(plan, audit_salt(plan, context))
        result = {
            "status": "pass",
            "mode": "plan",
            "candidate_seed_leaf_count": len(plan),
            "family_strata_count": len(
                {leaf.family_stratum for leaf in plan}
            ),
            "candidate_strata_count": len(
                {leaf.candidate_stratum for leaf in plan}
            ),
            "oof_producing_fold_units": len(plan) * len(FOLDS),
            "actual_inner_estimator_fits": config["models"]["planned_counts"][
                "actual_inner_estimator_fits"
            ],
            "selected_refits_maximum": SELECTED_REFIT_MAXIMUM,
            "source_audit_leaf_count": len(audit),
            "source_tree_digest": context.source_tree_digest,
            "outer_attempted_open_count": 0,
            "outer_open_count": 0,
        }
    elif args.mode == "synthetic":
        output_root = args.output_root or root / "temp/goal029-synthetic"
        if args.validate:
            result = validate_synthetic_publication(
                output_root / "private", output_root / "evidence"
            )
        else:
            result = run_synthetic(root, output_root)
    elif args.mode == "calibration":
        if args.validate:
            raise Goal029Error("calibration_validate_use_receipt_validator")
        result = run_calibration(root)
    else:
        config = load_goal029_config(root)
        if args.output_root is not None:
            raise Goal029Error("production_output_root_forbidden")
        if args.validate:
            result = validate_production_publication(
                root,
                _safe_bound_path(
                    root, config["artifacts"]["private_destination"]
                ),
                _safe_bound_path(
                    root, config["artifacts"]["tracked_destination"]
                ),
            )
        else:
            result = run_production(root)
    print(canonical_json(result))


if __name__ == "__main__":
    main()
