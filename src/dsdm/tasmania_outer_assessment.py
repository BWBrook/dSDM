"""One-shot original Tasmania outer assessment for the frozen Goal037 panel.

The controller has four strict phases: recover the exact Goal037 source archive,
prepare response-free held-patch predictors, close all neural and conventional
predictions, and only then open the frozen response once for aggregate scoring.
It never fits a model or selects a threshold/model from outer responses.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np


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
    "fraction25/ladder00",
    "fraction25/ladder01",
    "fraction25/ladder02",
    "fraction50/ladder00",
    "fraction50/ladder01",
    "fraction50/ladder02",
    "fraction100/full",
)
NEURAL_METHODS = (
    "target_only_resmlp",
    "legacy_pooled_finetune",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
    "target_plus_q_linear",
    "target_plus_q_deep",
)
CONVENTIONAL_FAMILIES = (
    "intercept",
    "elastic_net",
    "random_forest",
    "hist_gradient_boosting",
    "shallow_ann",
)
SEEDS = (31031, 31032, 31033, 31034, 31035)
SEED_LABELS_BY_FAMILY = {
    "intercept": ("seed00",),
    "elastic_net": ("seed00", "seed01", "seed02", "seed03", "seed04"),
    "random_forest": ("seed00", "seed01", "seed02", "seed03", "seed04"),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": ("seed00", "seed01", "seed02", "seed03", "seed04"),
}
PATCHES = ("mc08", "mc20", "mc35", "mc40", "mc49")
EXPECTED_RESPONSE_ROWS = 1672
EXPECTED_DOMAIN_CELLS = 606
EXPECTED_SPECIES_ROWS = {
    "thylogale_billardierii": 217,
    "notamacropus_rufogriseus": 225,
    "trichosurus_vulpecula": 198,
    "pseudocheirus_peregrinus": 174,
    "vombatus_ursinus": 145,
    "sarcophilus_harrisii": 387,
    "dasyurus_maculatus": 166,
    "dasyurus_viverrinus": 160,
}
CONTINUOUS = (
    "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
    "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
    "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
    "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
    "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
    "dist_fw", "dist_road", "fpar", "human_footprint",
)
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
PRIMARY_CONTRASTS = {
    "multihead_full_finetune_minus_target_only": (
        "multihead_full_finetune", "target_only_resmlp"
    ),
    "multihead_full_finetune_minus_target_plus_q_deep": (
        "multihead_full_finetune", "target_plus_q_deep"
    ),
    "multihead_full_finetune_minus_selected_conventional": (
        "multihead_full_finetune", "selected_conventional"
    ),
}
ARCHIVE_COMMIT = "ce70bf1"


class TasmaniaOuterError(ValueError):
    """Raised when the original Tasmania assessment contract fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TasmaniaOuterError(message)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _sha_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_digest(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_new(path: str | Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise TasmaniaOuterError(f"refusing to overwrite: {target.name}") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _atomic_npz(path: str | Path, **arrays: np.ndarray) -> None:
    target = Path(path)
    _require(not target.exists(), f"refusing to overwrite: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".tas-outer-", suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_relative(root: Path, raw: str) -> Path:
    relative = Path(raw)
    _require(raw != "" and not relative.is_absolute() and ".." not in relative.parts, "unsafe relative path")
    target = (root / relative).resolve()
    _require(target == root or root in target.parents, "path escape")
    return target


def _read_json(path: str | Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TasmaniaOuterError(f"invalid JSON: {Path(path).name}") from exc
    _require(isinstance(value, Mapping), f"JSON object required: {Path(path).name}")
    return value


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    _require(source.is_file() and not source.is_symlink(), f"invalid CSV binding: {source.name}")
    with source.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _verified_receipt(path: str | Path, schema_version: str) -> Mapping[str, Any]:
    receipt = _read_json(path)
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    _require(receipt.get("schema_version") == schema_version, f"receipt schema drift: {Path(path).name}")
    _require(isinstance(claimed, str) and claimed == _digest(body), f"receipt digest mismatch: {Path(path).name}")
    return receipt


def _require_preopen(config: "AssessmentConfig") -> None:
    _require(
        not any(path.exists() for path in (
            config.private_root / "response-access-intent.json",
            config.private_root / "response-access.json",
            config.tracked_receipt,
        )),
        "response access already attempted",
    )


def _require_prediction_stage_open(config: "AssessmentConfig") -> None:
    _require_preopen(config)
    _require(
        not (config.private_root / "prediction-closure.json").exists(),
        "predictions are already closed",
    )


@dataclass(frozen=True)
class AssessmentConfig:
    source_path: Path
    root: Path
    raw: Mapping[str, Any]
    config_digest: str
    private_root: Path
    archive_root: Path
    tracked_receipt: Path


def load_config(path: str | Path, *, verify_response: bool = False) -> AssessmentConfig:
    source = Path(path).resolve()
    root = source.parents[1]
    raw = _read_json(source)
    _require(
        set(raw) == {
            "schema_version", "assessment_id", "approval", "goal037", "authorities",
            "execution", "response_free_inputs", "response_vault", "scope", "metrics", "evidence",
        },
        "assessment config schema drift",
    )
    _require(
        raw["schema_version"] == "1.0"
        and raw["assessment_id"] == "original-tasmania-held-patch-outer-20261005",
        "assessment config identity drift",
    )
    bindings: list[tuple[str, Mapping[str, Any]]] = [("approval", raw["approval"])]
    bindings.extend((f"goal037/{name}", item) for name, item in raw["goal037"]["bindings"].items())
    bindings.extend((f"authority/{name}", item) for name, item in raw["authorities"].items())
    bindings.extend((f"response_free/{name}", item) for name, item in raw["response_free_inputs"].items())
    for label, binding in bindings:
        _require(set(binding) == {"path", "sha256"}, f"{label} binding schema drift")
        target = _safe_relative(root, str(binding["path"]))
        _require(target.is_file() and not target.is_symlink(), f"{label} binding missing")
        _require(_sha_file(target) == binding["sha256"], f"{label} binding digest mismatch")
    response = raw["response_vault"]
    _require(set(response) == {"path", "sha256", "opening_policy"}, "response-vault binding schema drift")
    response_path = _safe_relative(root, str(response["path"]))
    _require(response_path.is_file() and not response_path.is_symlink(), "response vault missing")
    if verify_response:
        _require(_sha_file(response_path) == response["sha256"], "response vault digest mismatch")
    scope = raw["scope"]
    _require(
        scope == {
            "species": list(SPECIES), "endpoints": list(ENDPOINTS),
            "neural_methods": list(NEURAL_METHODS), "conventional_families": list(CONVENTIONAL_FAMILIES),
            "seeds": list(SEEDS), "patches": list(PATCHES), "predictor_count": 77,
            "response_rows": EXPECTED_RESPONSE_ROWS, "domain_cells": EXPECTED_DOMAIN_CELLS,
            "fitting_allowed": False, "postopen_rescue_allowed": False,
        },
        "assessment scope drift",
    )
    _require(
        raw["metrics"] == {
            "seed_aggregation": "arithmetic_mean_scores_before_metrics",
            "threshold_source": "goal036_frozen_inner_oof",
            "positive_rule": "score_greater_than_or_equal_threshold",
            "co_primary": ["roc_auc", "tss"],
            "supplementary": ["average_precision", "mcc", "sensitivity", "specificity", "confusion_counts"],
            "pr_auc_definition": "sklearn_average_precision_noninterpolated_step_integral",
            "classless_policy": "all_performance_metrics_na_counts_retained",
            "inference": "descriptive_no_p_values_no_row_bootstrap",
        },
        "assessment metric contract drift",
    )
    execution = raw["execution"]
    _require(
        execution["archive_commit"] == ARCHIVE_COMMIT
        and execution["goal037_transaction_digest"] == "677b8706333dd3df30a0c07bec648ab11e591bfe016bde73dc867d9e78af3d9c",
        "assessment execution authority drift",
    )
    own_source = _safe_relative(root, execution["controller"]["path"])
    _require(_sha_file(own_source) == execution["controller"]["sha256"], "assessment controller digest mismatch")
    private_root = _safe_relative(root, raw["evidence"]["private_root"])
    archive_root = _safe_relative(root, raw["evidence"]["archive_root"])
    tracked_receipt = _safe_relative(root, raw["evidence"]["tracked_receipt"])
    _require(private_root.is_relative_to(root / "data"), "private root outside data")
    _require(tracked_receipt.is_relative_to(root / "evidence"), "tracked receipt outside evidence")
    return AssessmentConfig(source, root, raw, _sha_file(source), private_root, archive_root, tracked_receipt)


def _goal037_paths(config: AssessmentConfig) -> tuple[Path, Path]:
    bindings = config.raw["goal037"]["bindings"]
    return (
        _safe_relative(config.root, bindings["config"]["path"]),
        _safe_relative(config.root, bindings["receipt"]["path"]),
    )


def _validate_goal037_receipt(config: AssessmentConfig) -> Mapping[str, Any]:
    _, path = _goal037_paths(config)
    receipt = _read_json(path)
    _require(receipt.get("success") is True, "Goal037 receipt not successful")
    _require(receipt.get("outer_attempted") == receipt.get("outer_opened") == 0, "historical Goal037 access drift")
    _require(receipt.get("transaction_digest") == config.raw["execution"]["goal037_transaction_digest"], "Goal037 transaction drift")
    _require(receipt.get("counts") == {
        "species": 8, "endpoints": 7, "neural_packages": 8,
        "neural_logical_artifacts": 1768, "neural_physical_fits": 1769,
        "conventional_selected_refits": 952, "scorer_model_artifacts": 2720,
    }, "Goal037 receipt count drift")
    return receipt


def _archive_paths_from_goal037(config: AssessmentConfig) -> tuple[list[str], Mapping[str, Any]]:
    goal_config_path, _ = _goal037_paths(config)
    goal = _read_json(goal_config_path)
    paths = {"src", "pyproject.toml", "uv.lock", "config/dsdm_outer_ready.json"}
    paths.update(str(binding["path"]) for binding in goal["authorities"].values())
    return sorted(paths), goal


def _link_readonly_tree(source: Path, destination: Path, relative_paths: Sequence[str]) -> None:
    for relative in relative_paths:
        origin = source / relative
        target = destination / relative
        if origin.is_dir():
            for child in sorted(origin.rglob("*")):
                if child.is_file():
                    child_target = target / child.relative_to(origin)
                    child_target.parent.mkdir(parents=True, exist_ok=True)
                    os.link(child, child_target)
        else:
            _require(origin.is_file() and not origin.is_symlink(), f"archive data source invalid: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(origin, target)


def build_archive(config: AssessmentConfig) -> Mapping[str, Any]:
    """Export exact Goal037 code/authorities and hard-link its immutable artifacts."""
    _require_prediction_stage_open(config)
    _validate_goal037_receipt(config)
    _require(not config.archive_root.exists(), "Goal037 archive already exists")
    requested, goal = _archive_paths_from_goal037(config)
    archive_parent = config.archive_root.parent
    archive_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".goal037-archive-", dir=archive_parent))
    tar_path = stage / "archive.tar"
    export_root = stage / "root"
    export_root.mkdir()
    try:
        with tar_path.open("wb") as stream:
            result = subprocess.run(
                ["git", "archive", "--format=tar", ARCHIVE_COMMIT, *requested],
                cwd=config.root, stdout=stream, stderr=subprocess.PIPE, check=False,
            )
        _require(result.returncode == 0, f"git archive failed: {result.stderr.decode('utf-8', 'replace').strip()}")
        with tarfile.open(tar_path, "r") as archive:
            for member in archive.getmembers():
                member_path = Path(member.name)
                _require(not member_path.is_absolute() and ".." not in member_path.parts and not member.issym() and not member.islnk(), "unsafe Git archive member")
            archive.extractall(export_root, filter="data")
        tar_path.unlink()
        shutil.copy2(config.source_path, export_root / "config/tasmania_outer_assessment.json")
        controller = config.root / config.raw["execution"]["controller"]["path"]
        shutil.copy2(controller, export_root / "src/dsdm/tasmania_outer_assessment.py")
        goal_archived = _read_json(export_root / "config/dsdm_outer_ready.json")
        _require(goal_archived == goal, "archived Goal037 config drift")
        for name, binding in goal["execution_sources"].items():
            path = export_root / binding["path"]
            _require(path.is_file() and _sha_file(path) == binding["sha256"], f"archived Goal037 source mismatch: {name}")
        for name, binding in goal["authorities"].items():
            path = export_root / binding["path"]
            _require(path.is_file() and _sha_file(path) == binding["sha256"], f"archived Goal037 authority mismatch: {name}")
        live_private = config.root / goal["evidence"]["private_root"]
        private_rel = goal["evidence"]["private_root"]
        required_private = [
            "bundles", "canary", "neural/leaves", "epoch_policy.json",
            "conventional/copy", "conventional/import_receipt.json",
            "conventional/producer-reference.json",
            "conventional/producer-validation.json",
        ]
        _link_readonly_tree(live_private, export_root / private_rel, required_private)
        for relative in (goal["evidence"]["canary_receipt"], goal["evidence"]["aggregate_receipt"]):
            _link_readonly_tree(config.root, export_root, [relative])
        receipt = {
            "schema_version": "tasmania-goal037-archive-v1", "success": True,
            "assessment_config_sha256": config.config_digest,
            "archive_commit": ARCHIVE_COMMIT, "goal037_config_sha256": _sha_file(export_root / "config/dsdm_outer_ready.json"),
            "execution_source_hashes": {name: binding["sha256"] for name, binding in sorted(goal["execution_sources"].items())},
            "authority_hashes": {name: binding["sha256"] for name, binding in sorted(goal["authorities"].items())},
            "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
            "artifact_binding": "regular-file hardlinks to immutable accepted Goal037 private artifacts",
            "response_rows_read": 0,
        }
        receipt["receipt_digest"] = _digest(receipt)
        _write_json_new(export_root / "archive-receipt.json", receipt)
        os.replace(export_root, config.archive_root)
        shutil.rmtree(stage)
        return receipt
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def validate_archive(config: AssessmentConfig) -> Mapping[str, Any]:
    _require(config.archive_root.is_dir() and not config.archive_root.is_symlink(), "Goal037 archive missing")
    receipt = _read_json(config.archive_root / "archive-receipt.json")
    body = dict(receipt); claimed = body.pop("receipt_digest", None)
    _require(claimed == _digest(body), "Goal037 archive receipt digest mismatch")
    archived_assessment = config.archive_root / "config/tasmania_outer_assessment.json"
    _require(
        receipt.get("assessment_config_sha256") == config.config_digest
        and archived_assessment.is_file()
        and _sha_file(archived_assessment) == config.config_digest,
        "archived assessment config mismatch",
    )
    goal = _read_json(config.archive_root / "config/dsdm_outer_ready.json")
    for group in ("execution_sources", "authorities"):
        for name, binding in goal[group].items():
            path = config.archive_root / binding["path"]
            _require(path.is_file() and not path.is_symlink() and _sha_file(path) == binding["sha256"], f"Goal037 archive {group} mismatch: {name}")
    own = config.archive_root / "src/dsdm/tasmania_outer_assessment.py"
    _require(_sha_file(own) == config.raw["execution"]["controller"]["sha256"], "archived assessment controller mismatch")
    return receipt


def _frozen_levels(config: AssessmentConfig) -> dict[str, tuple[str, ...]]:
    contract_path = _safe_relative(config.root, config.raw["authorities"]["goal026_feature_contract"]["path"])
    contract = _read_json(contract_path)
    vocabulary = contract.get("categorical_vocabulary")
    _require(isinstance(vocabulary, Mapping) and set(vocabulary) == set(CATEGORICAL), "categorical vocabulary drift")
    levels = {name: tuple(str(value) for value in vocabulary[name]["levels"]) for name in CATEGORICAL}
    _require(len(CONTINUOUS) + sum(len(values) for values in levels.values()) == 77, "encoded predictor width drift")
    return levels


def build_response_free_rows(
    support_rows: Sequence[Mapping[str, str]],
    predictor_rows: Sequence[Mapping[str, str]],
    assignment_rows: Sequence[Mapping[str, str]],
    fit: Mapping[str, Any],
    levels: Mapping[str, Sequence[str]],
    *,
    enforce_frozen_inventory: bool = True,
) -> dict[str, dict[str, np.ndarray]]:
    """Align held-patch membership and predictors without reading responses."""
    selected = [
        row for row in support_rows
        if row.get("transform_id") == "outer" and row.get("outer_role") == "test"
    ]
    _require(selected and all(row.get("transform_role") == "assessment" for row in selected), "outer support role drift")
    identities = [(str(row.get("species_id", "")), str(row.get("grid_cell_id", ""))) for row in selected]
    if enforce_frozen_inventory:
        _require(
            len(identities) == EXPECTED_RESPONSE_ROWS
            and len(set(identities)) == EXPECTED_RESPONSE_ROWS
            and len({cell for _, cell in identities}) == EXPECTED_DOMAIN_CELLS,
            "response-free row/cell inventory drift",
        )
    else:
        _require(len(set(identities)) == len(identities), "duplicate response-free species-cell")
    _require({species for species, _ in identities} == set(SPECIES), "response-free species scope drift")
    predictors = {str(row.get("grid_cell_id", "")): row for row in predictor_rows}
    assignments = {str(row.get("grid_cell_id", "")): row for row in assignment_rows}
    _require(len(predictors) == len(predictor_rows) and len(assignments) == len(assignment_rows), "duplicate predictor/assignment cell")
    means, sds = fit.get("means"), fit.get("population_sd")
    _require(isinstance(means, Mapping) and isinstance(sds, Mapping), "outer transform parameters missing")
    result: dict[str, dict[str, np.ndarray]] = {}
    for species in SPECIES:
        rows = sorted((row for row in selected if row["species_id"] == species), key=lambda row: row["grid_cell_id"])
        if enforce_frozen_inventory:
            _require(len(rows) == EXPECTED_SPECIES_ROWS[species], f"response-free species row-count drift: {species}")
        else:
            _require(rows, f"empty response-free species: {species}")
        keys: list[str] = []
        patches: list[str] = []
        continuous: list[list[float]] = []
        categorical: list[list[str]] = []
        encoded: list[list[float]] = []
        for row in rows:
            cell = row["grid_cell_id"]
            _require(cell in predictors and cell in assignments, "response-free cell alignment failure")
            assignment = assignments[cell]
            _require(assignment.get("outer_role") == "test" and assignment.get("microcluster") in PATCHES, "held-patch assignment drift")
            predictor = predictors[cell]
            cvalues = [(float(predictor[name]) - float(means[name])) / float(sds[name]) for name in CONTINUOUS]
            _require(np.isfinite(np.asarray(cvalues)).all(), "non-finite transformed predictor")
            cats = [str(predictor[name]) for name in CATEGORICAL]
            vector = list(cvalues)
            for name, value in zip(CATEGORICAL, cats, strict=True):
                _require(value in levels[name], "unknown outer categorical level")
                vector.extend(float(value == level) for level in levels[name])
            _require(len(vector) == 77, "response-free encoding width drift")
            keys.append(cell); patches.append(str(assignment["microcluster"])); continuous.append(cvalues); categorical.append(cats); encoded.append(vector)
        result[species] = {
            "grid_cell_id": np.asarray(keys, dtype=str),
            "patch": np.asarray(patches, dtype=str),
            "continuous": np.asarray(continuous, dtype=np.float64),
            "categorical": np.asarray(categorical, dtype=str),
            "x_neural": np.asarray(encoded, dtype=np.float32),
        }
    _require({str(value) for data in result.values() for value in data["patch"]} == set(PATCHES), "held-patch inventory drift")
    return result


def prepare(config: AssessmentConfig) -> Mapping[str, Any]:
    _validate_goal037_receipt(config)
    _require_prediction_stage_open(config)
    inputs = config.raw["response_free_inputs"]
    support = _read_csv(_safe_relative(config.root, inputs["response_support"]["path"]))
    predictors = _read_csv(_safe_relative(config.root, inputs["predictor_response_cells"]["path"]))
    assignments = _read_csv(_safe_relative(config.root, inputs["response_cell_assignments"]["path"]))
    fit_parameters = _read_json(_safe_relative(config.root, config.raw["authorities"]["goal026_fit_parameters"]["path"]))
    fit = fit_parameters.get("fits", {}).get("outer")
    _require(isinstance(fit, Mapping) and fit.get("transform_id") == "outer" and fit.get("training_role") == "outer_train", "outer transform drift")
    rows = build_response_free_rows(support, predictors, assignments, fit, _frozen_levels(config))
    output_root = config.private_root / "inputs"
    records: list[dict[str, Any]] = []
    for species in SPECIES:
        path = output_root / f"{species}.npz"
        data = rows[species]
        if path.exists():
            _require(_validate_input_file(path, species) == len(data["grid_cell_id"]), "existing input row-count mismatch")
            with np.load(path, allow_pickle=False) as loaded:
                _require(
                    all(np.array_equal(np.asarray(loaded[name]), value) for name, value in data.items()),
                    f"existing response-free input content mismatch: {species}",
                )
        else:
            _atomic_npz(path, **data)
        records.append({
            "species": species, "rows": len(data["grid_cell_id"]), "sha256": _sha_file(path),
            "identity_digest": _digest(list(zip(data["grid_cell_id"].tolist(), data["patch"].tolist(), strict=True))),
            "patch_counts": {patch: int(np.sum(data["patch"] == patch)) for patch in PATCHES},
        })
    receipt = {
        "schema_version": "tasmania-response-free-input-closure-v1", "success": True,
        "config_digest": config.config_digest, "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
        "files": records, "species": 8, "patches": list(PATCHES), "predictor_count": 77,
        "response_rows": EXPECTED_RESPONSE_ROWS, "domain_cells": EXPECTED_DOMAIN_CELLS,
        "response_rows_read": 0, "labels_read": 0,
    }
    receipt["receipt_digest"] = _digest(receipt)
    receipt_path = config.private_root / "input-closure.json"
    if receipt_path.exists():
        _require(_read_json(receipt_path) == receipt, "existing input closure drift")
    else:
        _write_json_new(receipt_path, receipt)
    return receipt


def _validate_input_file(path: Path, species: str) -> int:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            _require(set(loaded.files) == {"grid_cell_id", "patch", "continuous", "categorical", "x_neural"}, "input array inventory drift")
            key = np.asarray(loaded["grid_cell_id"]); patch = np.asarray(loaded["patch"])
            continuous = np.asarray(loaded["continuous"]); categorical = np.asarray(loaded["categorical"]); x = np.asarray(loaded["x_neural"])
    except (OSError, ValueError) as exc:
        raise TasmaniaOuterError(f"invalid response-free input: {species}") from exc
    n = len(key)
    _require(n > 0 and patch.shape == (n,) and continuous.shape == (n, 25) and categorical.shape == (n, 3) and x.shape == (n, 77), "response-free input shape drift")
    _require(
        key.dtype.kind == patch.dtype.kind == categorical.dtype.kind == "U"
        and continuous.dtype == np.float64 and x.dtype == np.float32,
        "response-free input dtype drift",
    )
    _require(len(set(key.tolist())) == n and set(patch.tolist()) <= set(PATCHES), "response-free input identity drift")
    _require(np.isfinite(continuous).all() and np.isfinite(x).all(), "response-free input non-finite")
    return n


def _input_data(config: AssessmentConfig, species: str) -> dict[str, np.ndarray]:
    path = config.private_root / "inputs" / f"{species}.npz"
    _validate_input_file(path, species)
    with np.load(path, allow_pickle=False) as loaded:
        return {name: np.asarray(loaded[name]).copy() for name in loaded.files}


def _require_archive_import(config: AssessmentConfig, module_file: str | Path) -> None:
    source = Path(module_file).resolve()
    _require(source.is_relative_to((config.archive_root / "src").resolve()), "prediction lane is not using archived Goal037 source")


def _goal037_archive_paths(config: AssessmentConfig) -> Mapping[str, Path]:
    goal = _read_json(config.archive_root / "config/dsdm_outer_ready.json")
    private = config.archive_root / goal["evidence"]["private_root"]
    return {
        "private": private,
        "bundles": private / "bundles",
        "packages": private / "neural/leaves",
        "policy": private / "epoch_policy.json",
        "conventional_copy": private / "conventional/copy",
        "producer_validation": private / "conventional/producer-validation.json",
        "producer_reference": private / "conventional/producer-reference.json",
        "conventional_receipt": private / "conventional/import_receipt.json",
    }


def predict_neural(config: AssessmentConfig) -> Mapping[str, Any]:
    _require_prediction_stage_open(config)
    validate_archive(config); _validate_goal037_receipt(config)
    from dsdm import outer_ready
    _require_archive_import(config, outer_ready.__file__)
    goal_config = outer_ready.load_config(config.archive_root / "config/dsdm_outer_ready.json")
    runtime = outer_ready.neural_runtime(goal_config, strict=True)
    archived = _goal037_archive_paths(config)
    policy = _read_json(archived["policy"])
    outer_ready.validate_epoch_policy(policy)
    package_by_species: dict[str, Path] = {}
    for metadata_path in sorted(archived["packages"].glob("*/metadata.json")):
        metadata = _read_json(metadata_path)
        target = str(metadata.get("target", ""))
        _require(target in SPECIES and target not in package_by_species, "neural package target inventory drift")
        package_by_species[target] = metadata_path.parent
    _require(set(package_by_species) == set(SPECIES), "neural package species inventory drift")
    output_root = config.private_root / "predictions/neural"
    records: list[dict[str, Any]] = []
    for species in SPECIES:
        data = _input_data(config, species); n = len(data["grid_cell_id"])
        bundle = outer_ready.load_outer_bundle(archived["bundles"] / f"{species}.npz")
        scores = np.empty((len(ENDPOINTS), len(SEEDS), len(NEURAL_METHODS), n), dtype=np.float32)
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            scores[endpoint_index] = outer_ready.score_species_package(
                package_by_species[species], bundle, goal_config, policy, endpoint, data["x_neural"]
            )
        _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "neural prediction invalid")
        path = output_root / f"{species}.npz"
        if path.exists():
            stored = _validate_neural_prediction(path, n)
            _require(np.array_equal(stored, scores), f"existing neural prediction content mismatch: {species}")
        else:
            _atomic_npz(path, scores=scores)
        records.append({"species": species, "rows": n, "sha256": _sha_file(path), "array_digest": _array_digest(scores)})
    receipt = {
        "schema_version": "tasmania-neural-predictions-v1", "success": True,
        "config_digest": config.config_digest, "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
        "runtime": runtime, "files": records, "models": 1768, "endpoints": 7, "seed_scores_retained": True,
        "response_rows_read": 0,
    }
    receipt["receipt_digest"] = _digest(receipt)
    path = config.private_root / "neural-prediction-receipt.json"
    if path.exists(): _require(_read_json(path) == receipt, "existing neural prediction receipt drift")
    else: _write_json_new(path, receipt)
    return receipt


def _validate_neural_prediction(path: Path, n: int) -> np.ndarray:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            _require(set(loaded.files) == {"scores"}, "neural prediction inventory drift")
            scores = np.asarray(loaded["scores"])
    except (OSError, ValueError) as exc:
        raise TasmaniaOuterError("neural prediction invalid") from exc
    _require(scores.shape == (7, 5, 6, n) and scores.dtype == np.float32, "neural prediction shape/dtype drift")
    _require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "neural prediction range drift")
    return scores


def _conventional_batch(model: Any, species: str, data: Mapping[str, np.ndarray]) -> Any:
    from dsdm_phase1.modeling_contract import FeatureBatch, RowKey
    schema = model.schema
    names = tuple(schema["feature_names"]); continuous_count = int(schema["continuous_count"])
    _require(tuple(names[:continuous_count]) == CONTINUOUS, "conventional continuous schema drift")
    source_continuous = np.asarray(data["continuous"], dtype=np.float64)
    source_categorical = np.asarray(data["categorical"], dtype=str)
    matrix = np.empty((len(source_continuous), len(names)), dtype=np.float64)
    matrix[:, :continuous_count] = source_continuous
    category_lookup = {name: source_categorical[:, index] for index, name in enumerate(CATEGORICAL)}
    for column, feature in enumerate(names[continuous_count:], start=continuous_count):
        _require("__" in feature, "conventional categorical feature invalid")
        name, level = feature.split("__", 1)
        _require(name in category_lookup and level != "", "conventional categorical feature invalid")
        matrix[:, column] = category_lookup[name] == level
    keys = tuple(RowKey(species, str(cell)) for cell in data["grid_cell_id"])
    return FeatureBatch(
        keys, matrix, np.zeros(len(keys), dtype=np.float64), names, tuple(schema["feature_kinds"]),
        continuous_count, str(schema["feature_schema_digest"]), {}, str(schema["transform_id"]),
        str(schema["transform_digest"]), str(schema["encoder_digest"]),
    )


def _selection_index(copy_root: Path) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    selection = _read_json(copy_root / "selection.json")
    _require(selection.get("selected_model_seed_count") == 952 and len(selection.get("family_records", [])) == 280, "conventional selection arithmetic drift")
    index: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for item in selection["family_records"]:
        stratum = item["family_stratum"]
        endpoint = f"{stratum['fraction_id']}/{stratum['ladder_id']}"
        key = (str(stratum["species_id"]), endpoint, str(stratum["model_family"]))
        _require(key not in index, "duplicate conventional family stratum")
        path = copy_root / str(item["relative_path"])
        record = _read_json(path)
        _require(record.get("record_digest") == item.get("record_digest"), "conventional selection record digest drift")
        index[key] = record
    _require(len(index) == 8 * 7 * 5, "conventional family-stratum inventory drift")
    return index


def predict_conventional(config: AssessmentConfig) -> Mapping[str, Any]:
    _require_prediction_stage_open(config)
    validate_archive(config); _validate_goal037_receipt(config)
    from dsdm import conventional_refit_import
    from dsdm_phase1 import model_adapters
    _require_archive_import(config, conventional_refit_import.__file__)
    _require_archive_import(config, model_adapters.__file__)
    goal_config = conventional_refit_import.load_config(config.archive_root / "config/dsdm_outer_ready.json")
    runtime = conventional_refit_import.conventional_runtime(goal_config, strict=True)
    archived = _goal037_archive_paths(config)
    replay = conventional_refit_import.validate_conventional_receipt(
        goal_config, archived["conventional_copy"], archived["producer_validation"],
        archived["producer_reference"], archived["conventional_receipt"],
    )
    selection = _selection_index(archived["conventional_copy"])
    output_root = config.private_root / "predictions/conventional"
    records: list[dict[str, Any]] = []; model_hashes: list[dict[str, Any]] = []
    for species in SPECIES:
        data = _input_data(config, species); n = len(data["grid_cell_id"])
        scores = np.full((7, 5, 5, n), np.nan, dtype=np.float64)
        active = np.zeros((7, 5, 5), dtype=np.uint8)
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            for family_index, family in enumerate(CONVENTIONAL_FAMILIES):
                record = selection[(species, endpoint, family)]
                receipts = record["refit_receipts"]
                expected_labels = SEED_LABELS_BY_FAMILY[family]
                _require(tuple(row["selected_task"]["seed_label"] for row in receipts) == expected_labels, "conventional seed inventory drift")
                for seed_index, receipt in enumerate(receipts):
                    task = receipt["selected_task"]
                    _require(
                        task["species_id"] == species and f"{task['fraction_id']}/{task['ladder_id']}" == endpoint
                        and task["model_family"] == family and task["candidate_id"] == record["selected_candidate_id"]
                        and task["transform_id"] == "outer",
                        "conventional selected task drift",
                    )
                    model_path = archived["conventional_copy"] / receipt["bundle_path"] / "model.model"
                    model = model_adapters.load_fitted_model(model_path, receipt["model_sha256"])
                    predicted = np.asarray(model.predict_scores(_conventional_batch(model, species, data)), dtype=np.float64)
                    _require(predicted.shape == (n,) and np.isfinite(predicted).all() and np.all((predicted >= 0) & (predicted <= 1)), "conventional prediction invalid")
                    scores[endpoint_index, family_index, seed_index] = predicted
                    active[endpoint_index, family_index, seed_index] = 1
                    model_hashes.append({"task": task, "sha256": receipt["model_sha256"]})
        path = output_root / f"{species}.npz"
        if path.exists():
            stored_scores, stored_active = _validate_conventional_prediction(path, n)
            _require(
                np.array_equal(stored_scores, scores, equal_nan=True)
                and np.array_equal(stored_active, active),
                f"existing conventional prediction content mismatch: {species}",
            )
        else: _atomic_npz(path, scores=scores, active=active)
        records.append({"species": species, "rows": n, "sha256": _sha_file(path), "scores_digest": _array_digest(scores), "active_digest": _array_digest(active)})
    _require(len(model_hashes) == 952, "conventional scored model inventory drift")
    receipt = {
        "schema_version": "tasmania-conventional-predictions-v1", "success": True,
        "config_digest": config.config_digest, "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
        "runtime": runtime, "goal037_replay_receipt_digest": replay["receipt_digest"], "files": records,
        "models": 952, "model_inventory_digest": _digest(model_hashes), "endpoints": 7,
        "seed_scores_retained": True, "response_rows_read": 0,
    }
    receipt["receipt_digest"] = _digest(receipt)
    path = config.private_root / "conventional-prediction-receipt.json"
    if path.exists(): _require(_read_json(path) == receipt, "existing conventional prediction receipt drift")
    else: _write_json_new(path, receipt)
    return receipt


def _validate_conventional_prediction(path: Path, n: int) -> tuple[np.ndarray, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            _require(set(loaded.files) == {"scores", "active"}, "conventional prediction inventory drift")
            scores = np.asarray(loaded["scores"]); active = np.asarray(loaded["active"])
    except (OSError, ValueError) as exc:
        raise TasmaniaOuterError("conventional prediction invalid") from exc
    _require(
        scores.shape == (7, 5, 5, n) and active.shape == (7, 5, 5)
        and scores.dtype == np.float64 and active.dtype == np.uint8
        and np.isin(active, (0, 1)).all(),
        "conventional prediction shape/dtype drift",
    )
    expected = np.asarray([[1, 5, 5, 1, 5]] * 7)
    _require(np.array_equal(active.sum(axis=2), expected), "conventional prediction seed-count drift")
    expanded = np.broadcast_to(active[..., None].astype(bool), scores.shape)
    _require(np.isfinite(scores[expanded]).all() and np.isnan(scores[~expanded]).all(), "conventional prediction inactive/finite drift")
    _require(np.all((scores[expanded] >= 0) & (scores[expanded] <= 1)), "conventional prediction range drift")
    return scores, active


def _seed_mean_predictions(
    neural: np.ndarray, conventional: np.ndarray, active: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    neural_mean = np.mean(neural.astype(np.float64), axis=1)
    conventional_mean = np.empty((7, 5, neural.shape[-1]), dtype=np.float64)
    for endpoint_index in range(7):
        for family_index in range(5):
            use = active[endpoint_index, family_index].astype(bool)
            conventional_mean[endpoint_index, family_index] = np.mean(
                conventional[endpoint_index, family_index, use], axis=0
            )
    _require(
        np.isfinite(neural_mean).all() and np.isfinite(conventional_mean).all()
        and np.all((neural_mean >= 0) & (neural_mean <= 1))
        and np.all((conventional_mean >= 0) & (conventional_mean <= 1)),
        "seed-mean prediction invalid",
    )
    return neural_mean, conventional_mean


def _validate_averaged_prediction(path: Path, n: int) -> tuple[np.ndarray, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            _require(set(loaded.files) == {"neural_mean", "conventional_mean"}, "averaged prediction inventory drift")
            neural_mean = np.asarray(loaded["neural_mean"])
            conventional_mean = np.asarray(loaded["conventional_mean"])
    except (OSError, ValueError) as exc:
        raise TasmaniaOuterError("averaged prediction invalid") from exc
    _require(
        neural_mean.shape == (7, 6, n) and conventional_mean.shape == (7, 5, n)
        and neural_mean.dtype == conventional_mean.dtype == np.float64,
        "averaged prediction shape/dtype drift",
    )
    _require(
        np.isfinite(neural_mean).all() and np.isfinite(conventional_mean).all()
        and np.all((neural_mean >= 0) & (neural_mean <= 1))
        and np.all((conventional_mean >= 0) & (conventional_mean <= 1)),
        "averaged prediction range drift",
    )
    return neural_mean, conventional_mean


def _validate_stage_receipts(
    config: AssessmentConfig,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    input_receipt = _verified_receipt(
        config.private_root / "input-closure.json", "tasmania-response-free-input-closure-v1"
    )
    neural_receipt = _verified_receipt(
        config.private_root / "neural-prediction-receipt.json", "tasmania-neural-predictions-v1"
    )
    conventional_receipt = _verified_receipt(
        config.private_root / "conventional-prediction-receipt.json", "tasmania-conventional-predictions-v1"
    )
    receipts = (input_receipt, neural_receipt, conventional_receipt)
    _require(
        all(
            value.get("success") is True
            and value.get("config_digest") == config.config_digest
            and value.get("goal037_transaction_digest") == config.raw["execution"]["goal037_transaction_digest"]
            and value.get("response_rows_read") == 0
            for value in receipts
        ),
        "prediction-stage receipt drift",
    )
    _require(
        input_receipt.get("species") == 8
        and input_receipt.get("patches") == list(PATCHES)
        and input_receipt.get("predictor_count") == 77
        and input_receipt.get("response_rows") == EXPECTED_RESPONSE_ROWS
        and input_receipt.get("domain_cells") == EXPECTED_DOMAIN_CELLS
        and input_receipt.get("labels_read") == 0,
        "response-free input receipt scope drift",
    )
    _require(
        neural_receipt.get("models") == 1768 and neural_receipt.get("endpoints") == 7
        and neural_receipt.get("seed_scores_retained") is True,
        "neural prediction receipt scope drift",
    )
    _require(
        conventional_receipt.get("models") == 952 and conventional_receipt.get("endpoints") == 7
        and conventional_receipt.get("seed_scores_retained") is True,
        "conventional prediction receipt scope drift",
    )
    input_files = {str(row.get("species")): row for row in input_receipt.get("files", [])}
    neural_files = {str(row.get("species")): row for row in neural_receipt.get("files", [])}
    conventional_files = {str(row.get("species")): row for row in conventional_receipt.get("files", [])}
    _require(
        set(input_files) == set(neural_files) == set(conventional_files) == set(SPECIES)
        and len(input_receipt["files"]) == len(neural_receipt["files"]) == len(conventional_receipt["files"]) == 8,
        "prediction-stage species inventory drift",
    )
    total_rows = 0
    domain_cells: set[str] = set()
    for species in SPECIES:
        input_path = config.private_root / "inputs" / f"{species}.npz"
        n = _validate_input_file(input_path, species)
        data = _input_data(config, species)
        total_rows += n
        domain_cells.update(str(value) for value in data["grid_cell_id"])
        input_record = input_files[species]
        _require(
            input_record.get("rows") == n
            and input_record.get("sha256") == _sha_file(input_path)
            and input_record.get("identity_digest") == _digest(
                list(zip(data["grid_cell_id"].tolist(), data["patch"].tolist(), strict=True))
            )
            and input_record.get("patch_counts") == {
                patch: int(np.sum(data["patch"] == patch)) for patch in PATCHES
            },
            f"response-free input receipt mismatch: {species}",
        )
        neural_path = config.private_root / "predictions/neural" / f"{species}.npz"
        neural = _validate_neural_prediction(neural_path, n)
        neural_record = neural_files[species]
        _require(
            neural_record.get("rows") == n and neural_record.get("sha256") == _sha_file(neural_path)
            and neural_record.get("array_digest") == _array_digest(neural),
            f"neural prediction receipt mismatch: {species}",
        )
        conventional_path = config.private_root / "predictions/conventional" / f"{species}.npz"
        conventional, active = _validate_conventional_prediction(conventional_path, n)
        conventional_record = conventional_files[species]
        _require(
            conventional_record.get("rows") == n
            and conventional_record.get("sha256") == _sha_file(conventional_path)
            and conventional_record.get("scores_digest") == _array_digest(conventional)
            and conventional_record.get("active_digest") == _array_digest(active),
            f"conventional prediction receipt mismatch: {species}",
        )
    _require(
        total_rows == EXPECTED_RESPONSE_ROWS and len(domain_cells) == EXPECTED_DOMAIN_CELLS,
        "prediction-stage response row/cell inventory drift",
    )
    return receipts


def close_predictions(config: AssessmentConfig) -> Mapping[str, Any]:
    _require_prediction_stage_open(config)
    input_receipt, neural_receipt, conventional_receipt = _validate_stage_receipts(config)
    files: list[dict[str, Any]] = []
    for species in SPECIES:
        input_path = config.private_root / "inputs" / f"{species}.npz"; n = _validate_input_file(input_path, species)
        neural_path = config.private_root / "predictions/neural" / f"{species}.npz"; neural = _validate_neural_prediction(neural_path, n)
        conventional_path = config.private_root / "predictions/conventional" / f"{species}.npz"; conventional, active = _validate_conventional_prediction(conventional_path, n)
        neural_mean, conventional_mean = _seed_mean_predictions(neural, conventional, active)
        averaged_path = config.private_root / "predictions/averaged" / f"{species}.npz"
        if averaged_path.exists():
            stored_neural, stored_conventional = _validate_averaged_prediction(averaged_path, n)
            _require(
                np.array_equal(stored_neural, neural_mean)
                and np.array_equal(stored_conventional, conventional_mean),
                f"existing averaged prediction content mismatch: {species}",
            )
        else:
            _atomic_npz(averaged_path, neural_mean=neural_mean, conventional_mean=conventional_mean)
        files.extend([
            {"role": "input", "species": species, "sha256": _sha_file(input_path)},
            {"role": "neural", "species": species, "sha256": _sha_file(neural_path)},
            {"role": "conventional", "species": species, "sha256": _sha_file(conventional_path)},
            {"role": "averaged", "species": species, "sha256": _sha_file(averaged_path),
             "neural_mean_digest": _array_digest(neural_mean),
             "conventional_mean_digest": _array_digest(conventional_mean)},
        ])
    receipt = {
        "schema_version": "tasmania-prediction-closure-v1", "success": True,
        "status": "predictions_closed_before_response", "config_digest": config.config_digest,
        "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
        "input_receipt_digest": input_receipt["receipt_digest"],
        "neural_receipt_digest": neural_receipt["receipt_digest"],
        "conventional_receipt_digest": conventional_receipt["receipt_digest"],
        "file_inventory_digest": _digest(files), "files": files,
        "species": 8, "endpoints": 7, "methods": 11, "patches": 5,
        "seed_aggregation": "arithmetic_mean_scores_before_response_access",
        "neural_seed_aggregation_pending": False, "conventional_seed_aggregation_pending": False,
        "response_rows_read": 0, "labels_read": 0, "closed_at": _now(),
    }
    receipt["receipt_digest"] = _digest(receipt)
    path = config.private_root / "prediction-closure.json"
    _require(not path.exists(), "prediction closure already exists")
    _write_json_new(path, receipt)
    return receipt


def _validate_prediction_closure(config: AssessmentConfig) -> Mapping[str, Any]:
    closure = _verified_receipt(
        config.private_root / "prediction-closure.json", "tasmania-prediction-closure-v1"
    )
    _require(
        closure.get("success") is True
        and closure.get("status") == "predictions_closed_before_response"
        and closure.get("config_digest") == config.config_digest
        and closure.get("goal037_transaction_digest") == config.raw["execution"]["goal037_transaction_digest"]
        and closure.get("response_rows_read") == 0
        and closure.get("labels_read") == 0
        and closure.get("species") == 8
        and closure.get("endpoints") == 7
        and closure.get("methods") == 11
        and closure.get("patches") == 5
        and closure.get("seed_aggregation") == "arithmetic_mean_scores_before_response_access"
        and closure.get("neural_seed_aggregation_pending") is False
        and closure.get("conventional_seed_aggregation_pending") is False,
        "prediction closure scope drift",
    )
    input_receipt, neural_receipt, conventional_receipt = _validate_stage_receipts(config)
    _require(
        closure.get("input_receipt_digest") == input_receipt["receipt_digest"]
        and closure.get("neural_receipt_digest") == neural_receipt["receipt_digest"]
        and closure.get("conventional_receipt_digest") == conventional_receipt["receipt_digest"],
        "prediction closure stage binding drift",
    )
    files = closure.get("files")
    _require(isinstance(files, list) and len(files) == 8 * 4, "prediction closure file inventory drift")
    _require(closure.get("file_inventory_digest") == _digest(files), "prediction closure inventory digest mismatch")
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in files:
        _require(isinstance(row, Mapping), "prediction closure file record invalid")
        key = (str(row.get("role")), str(row.get("species")))
        _require(key not in index, "duplicate prediction closure file record")
        index[key] = row
    _require(
        set(index) == {(role, species) for role in ("input", "neural", "conventional", "averaged") for species in SPECIES},
        "prediction closure file roles drift",
    )
    for species in SPECIES:
        paths = {
            "input": config.private_root / "inputs" / f"{species}.npz",
            "neural": config.private_root / "predictions/neural" / f"{species}.npz",
            "conventional": config.private_root / "predictions/conventional" / f"{species}.npz",
            "averaged": config.private_root / "predictions/averaged" / f"{species}.npz",
        }
        _require(
            all(index[(role, species)].get("sha256") == _sha_file(path) for role, path in paths.items()),
            f"prediction closure file hash mismatch: {species}",
        )
        n = _validate_input_file(paths["input"], species)
        neural = _validate_neural_prediction(paths["neural"], n)
        conventional, active = _validate_conventional_prediction(paths["conventional"], n)
        expected_neural, expected_conventional = _seed_mean_predictions(neural, conventional, active)
        stored_neural, stored_conventional = _validate_averaged_prediction(paths["averaged"], n)
        averaged_record = index[("averaged", species)]
        _require(
            np.array_equal(stored_neural, expected_neural)
            and np.array_equal(stored_conventional, expected_conventional)
            and averaged_record.get("neural_mean_digest") == _array_digest(stored_neural)
            and averaged_record.get("conventional_mean_digest") == _array_digest(stored_conventional),
            f"prediction closure seed-mean mismatch: {species}",
        )
    return closure


def _thresholds_and_selection(config: AssessmentConfig) -> tuple[dict[tuple[str, str, str], float], dict[tuple[str, str], str]]:
    metrics_path = _safe_relative(config.root, config.raw["authorities"]["goal036_stratum_metrics"]["path"])
    selection_path = _safe_relative(config.root, config.raw["authorities"]["goal036_conventional_selection"]["path"])
    thresholds: dict[tuple[str, str, str], float] = {}
    for row in _read_csv(metrics_path):
        method = str(row["method"])
        key = (str(row["species"]), str(row["endpoint"]), method)
        _require(key not in thresholds, "duplicate frozen threshold")
        threshold = float(row["threshold"])
        _require(np.isfinite(threshold) and 0 <= threshold <= 1, "invalid frozen threshold")
        thresholds[key] = threshold
    expected_methods = set(NEURAL_METHODS) | {f"conventional/{family}" for family in CONVENTIONAL_FAMILIES}
    expected_keys = {(species, endpoint, method) for species in SPECIES for endpoint in ENDPOINTS for method in expected_methods}
    _require(set(thresholds) == expected_keys, "frozen threshold inventory drift")
    selected: dict[tuple[str, str], str] = {}
    for row in _read_csv(selection_path):
        key = (str(row["species"]), str(row["endpoint"]))
        _require(key not in selected and row["selected_family"] in CONVENTIONAL_FAMILIES, "frozen conventional selection drift")
        selected[key] = str(row["selected_family"])
    _require(set(selected) == {(species, endpoint) for species in SPECIES for endpoint in ENDPOINTS}, "frozen conventional selection inventory drift")
    return thresholds, selected


def metric_block(y: Sequence[int], score: Sequence[float], threshold: float) -> dict[str, Any]:
    labels = np.asarray(y, dtype=np.int8); values = np.asarray(score, dtype=np.float64)
    _require(labels.ndim == values.ndim == 1 and len(labels) == len(values), "metric vector shape drift")
    _require(np.isin(labels, (0, 1)).all() and np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "metric vector invalid")
    predicted = values >= float(threshold)
    tp = int(np.sum(predicted & (labels == 1))); fn = int(np.sum(~predicted & (labels == 1)))
    tn = int(np.sum(~predicted & (labels == 0))); fp = int(np.sum(predicted & (labels == 0)))
    n_pos, n_neg = tp + fn, tn + fp
    base = {
        "n": int(len(labels)), "n_positive": n_pos, "n_negative": n_neg,
        "prevalence": float(n_pos / len(labels)) if len(labels) else None,
        "threshold": float(threshold), "tp": tp, "fn": fn, "tn": tn, "fp": fp,
    }
    if not n_pos or not n_neg:
        return {**base, "roc_auc": None, "tss": None, "average_precision": None, "mcc": None,
                "sensitivity": None, "specificity": None,
                "na_reason": "empty_scope" if not len(labels) else "single_response_class"}
    from sklearn.metrics import average_precision_score, matthews_corrcoef, roc_auc_score
    return {
        **base, "roc_auc": float(roc_auc_score(labels, values)),
        "tss": float(tp / n_pos + tn / n_neg - 1),
        "average_precision": float(average_precision_score(labels, values)),
        "mcc": float(matthews_corrcoef(labels, predicted)),
        "sensitivity": float(tp / n_pos), "specificity": float(tn / n_neg), "na_reason": None,
    }


def _score_species_arrays(
    species: str, y: np.ndarray, patches: np.ndarray, neural: np.ndarray,
    conventional: np.ndarray, active: np.ndarray,
    thresholds: Mapping[tuple[str, str, str], float], selected: Mapping[tuple[str, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    neural_mean, conventional_mean = _seed_mean_predictions(neural, conventional, active)
    return _score_species_mean_arrays(
        species, y, patches, neural_mean, conventional_mean, thresholds, selected
    )


def _score_species_mean_arrays(
    species: str, y: np.ndarray, patches: np.ndarray,
    neural_mean: np.ndarray, conventional_mean: np.ndarray,
    thresholds: Mapping[tuple[str, str, str], float], selected: Mapping[tuple[str, str], str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _require(y.shape == patches.shape and set(patches.tolist()) <= set(PATCHES), "score identity alignment drift")
    _require(
        neural_mean.shape == (7, 6, len(y)) and conventional_mean.shape == (7, 5, len(y)),
        "seed-mean score shape drift",
    )
    records: list[dict[str, Any]] = []; contrasts: list[dict[str, Any]] = []
    scopes = [("pooled", None, np.ones(len(y), dtype=bool))] + [("patch", patch, patches == patch) for patch in PATCHES]
    for endpoint_index, endpoint in enumerate(ENDPOINTS):
        metric_lookup: dict[tuple[str, str | None, str], Mapping[str, Any]] = {}
        for method_index, method in enumerate(NEURAL_METHODS):
            threshold = thresholds[(species, endpoint, method)]
            for scope, patch, mask in scopes:
                metrics = metric_block(y[mask], neural_mean[endpoint_index, method_index, mask], threshold)
                records.append({"species": species, "endpoint": endpoint, "model": method, "model_group": "neural", "scope": scope, "patch": patch, **metrics})
                metric_lookup[(scope, patch, method)] = metrics
        for family_index, family in enumerate(CONVENTIONAL_FAMILIES):
            method = f"conventional/{family}"; threshold = thresholds[(species, endpoint, method)]
            for scope, patch, mask in scopes:
                metrics = metric_block(y[mask], conventional_mean[endpoint_index, family_index, mask], threshold)
                records.append({"species": species, "endpoint": endpoint, "model": method, "model_group": "conventional", "scope": scope, "patch": patch, **metrics})
                metric_lookup[(scope, patch, method)] = metrics
        selected_family = selected[(species, endpoint)]
        for scope, patch, _ in scopes:
            aliases = {
                "multihead_full_finetune": "multihead_full_finetune",
                "target_only_resmlp": "target_only_resmlp",
                "target_plus_q_deep": "target_plus_q_deep",
                "selected_conventional": f"conventional/{selected_family}",
            }
            for name, (left, right) in PRIMARY_CONTRASTS.items():
                left_metrics = metric_lookup[(scope, patch, aliases[left])]
                right_metrics = metric_lookup[(scope, patch, aliases[right])]
                for metric in ("roc_auc", "tss"):
                    lv, rv = left_metrics[metric], right_metrics[metric]
                    contrasts.append({
                        "species": species, "endpoint": endpoint, "scope": scope, "patch": patch,
                        "contrast": name, "metric": metric,
                        "difference": None if lv is None or rv is None else float(lv - rv),
                        "selected_conventional_family": selected_family if right == "selected_conventional" else None,
                    })
    return records, contrasts


def _open_response_once(config: AssessmentConfig, closure: Mapping[str, Any]) -> list[dict[str, str]]:
    intent = {
        "schema_version": "tasmania-response-access-intent-v1", "config_digest": config.config_digest,
        "prediction_closure_digest": closure["receipt_digest"], "approval_sha256": config.raw["approval"]["sha256"],
        "attempted_at": _now(), "outer_attempted": 1, "outer_opened": 0,
        "policy": "single attempt; any interruption after this marker forbids automated rescue",
    }
    _write_json_new(config.private_root / "response-access-intent.json", intent)
    response_path = _safe_relative(config.root, config.raw["response_vault"]["path"])
    actual = _sha_file(response_path)
    _require(actual == config.raw["response_vault"]["sha256"], "response vault digest mismatch after access intent")
    rows = _read_csv(response_path)
    access = {
        "schema_version": "tasmania-response-access-v1", "config_digest": config.config_digest,
        "prediction_closure_digest": closure["receipt_digest"], "response_sha256": actual,
        "opened_at": _now(), "outer_attempted": 1, "outer_opened": 1,
    }
    access["receipt_digest"] = _digest(access)
    _write_json_new(config.private_root / "response-access.json", access)
    return rows


def _headline(contrasts: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    full = [row for row in contrasts if row["endpoint"] == "fraction100/full" and row["scope"] == "pooled"]
    summaries: list[dict[str, Any]] = []
    for contrast in PRIMARY_CONTRASTS:
        for metric in ("roc_auc", "tss"):
            rows = [row for row in full if row["contrast"] == contrast and row["metric"] == metric]
            values = [float(row["difference"]) for row in rows if row["difference"] is not None]
            summaries.append({
                "contrast": contrast, "metric": metric, "species_results": rows,
                "species_with_defined_difference": len(values),
                "positive_species": sum(value > 0 for value in values),
                "zero_species": sum(value == 0 for value in values),
                "negative_species": sum(value < 0 for value in values),
                "median_difference": float(np.median(values)) if values else None,
            })
    return {"endpoint": "fraction100/full", "scope": "pooled", "descriptive_only": True, "summaries": summaries}


def score(config: AssessmentConfig) -> Mapping[str, Any]:
    _require_preopen(config)
    closure = _validate_prediction_closure(config)
    thresholds, selected = _thresholds_and_selection(config)
    prediction_cache: dict[str, tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]] = {}
    for species in SPECIES:
        data = _input_data(config, species)
        averaged_path = config.private_root / "predictions/averaged" / f"{species}.npz"
        neural_mean, conventional_mean = _validate_averaged_prediction(
            averaged_path, len(data["grid_cell_id"])
        )
        prediction_cache[species] = (data, neural_mean, conventional_mean)
    response_rows = _open_response_once(config, closure)
    response_index: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in response_rows:
        if row.get("outer_role") != "test" or row.get("species_id") not in SPECIES:
            continue
        key = (str(row["species_id"]), str(row["grid_cell_id"]))
        _require(key not in response_index, "duplicate opened response species-cell")
        _require(row.get("microcluster") in PATCHES and row.get("pa") in {"0", "1"}, "opened response row invalid")
        response_index[key] = row
    metric_records: list[dict[str, Any]] = []; contrast_records: list[dict[str, Any]] = []
    response_counts: list[dict[str, Any]] = []
    for species in SPECIES:
        data, neural_mean, conventional_mean = prediction_cache[species]
        keys = data["grid_cell_id"].tolist(); patches = data["patch"]
        expected = {(species, str(cell)) for cell in keys}
        observed = {key for key in response_index if key[0] == species}
        _require(observed == expected, "opened response/prediction identity mismatch")
        _require(all(response_index[(species, str(cell))]["microcluster"] == str(patch) for cell, patch in zip(keys, patches, strict=True)), "opened response patch mismatch")
        y = np.asarray([int(response_index[(species, str(cell))]["pa"]) for cell in keys], dtype=np.int8)
        records, contrasts = _score_species_mean_arrays(
            species, y, patches, neural_mean, conventional_mean, thresholds, selected
        )
        metric_records.extend(records); contrast_records.extend(contrasts)
        response_counts.append({"species": species, "n": len(y), "n_positive": int(y.sum()), "n_negative": int(len(y) - y.sum()), "patch_counts": {patch: int(np.sum(patches == patch)) for patch in PATCHES}})
    _require(len(response_index) == sum(item["n"] for item in response_counts), "opened response outer scope drift")
    _require(
        len(response_index) == EXPECTED_RESPONSE_ROWS
        and sum(item["n"] for item in response_counts) == EXPECTED_RESPONSE_ROWS,
        "opened response row-count drift",
    )
    receipt = {
        "schema_version": "tasmania-outer-assessment-v1", "success": True,
        "assessment_id": config.raw["assessment_id"], "config_digest": config.config_digest,
        "approval_sha256": config.raw["approval"]["sha256"],
        "goal037_transaction_digest": config.raw["execution"]["goal037_transaction_digest"],
        "prediction_closure_digest": closure["receipt_digest"],
        "response_access_receipt_digest": _read_json(config.private_root / "response-access.json")["receipt_digest"],
        "scientific_target": "species-specific relative habitat-suitability index over Goal024 D_struct",
        "prediction_target": "resolved species-cell rows in the five pre-model-frozen touching held patches",
        "scope_of_inference": "held-patch interpolation within Tasmania D_struct conditional on the accepted 2001-2025 response construction",
        "metric_definitions": dict(config.raw["metrics"]),
        "response_counts": response_counts,
        "metrics": metric_records, "primary_contrasts": contrast_records,
        "full_data_headline": _headline(contrast_records),
        "counts": {"species": 8, "endpoints": 7, "models": 11, "patches": 5,
                   "response_rows": EXPECTED_RESPONSE_ROWS, "domain_cells": EXPECTED_DOMAIN_CELLS,
                   "metric_records": len(metric_records), "contrast_records": len(contrast_records)},
        "interpretation": "descriptive; no statistical significance, causal effect, occupancy probability, or independent regional transfer is inferred",
        "outer_attempted": 1, "outer_opened": 1, "completed_at": _now(),
        "privacy": {"aggregate_only": True, "labels_tracked": False, "predictions_tracked": False, "row_identifiers": False, "coordinates": False},
    }
    receipt["receipt_digest"] = _digest(receipt)
    _write_json_new(config.tracked_receipt, receipt)
    return receipt


def status(config: AssessmentConfig) -> Mapping[str, Any]:
    roles = {
        "archive": config.archive_root / "archive-receipt.json",
        "inputs": config.private_root / "input-closure.json",
        "neural_predictions": config.private_root / "neural-prediction-receipt.json",
        "conventional_predictions": config.private_root / "conventional-prediction-receipt.json",
        "prediction_closure": config.private_root / "prediction-closure.json",
        "response_access_intent": config.private_root / "response-access-intent.json",
        "response_access": config.private_root / "response-access.json",
        "aggregate_receipt": config.tracked_receipt,
    }
    return {"assessment_id": config.raw["assessment_id"], "stages": {name: path.exists() for name, path in roles.items()}}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dsdm.tasmania_outer_assessment")
    parser.add_argument("--config", default="config/tasmania_outer_assessment.json")
    parser.add_argument("command", choices=("validate", "archive", "validate-archive", "prepare", "predict-neural", "predict-conventional", "close", "score", "status"))
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "validate":
        value: Mapping[str, Any] = {"success": True, "config_digest": config.config_digest, "goal037": _validate_goal037_receipt(config)["receipt_digest"], "response_opened": False}
    elif args.command == "archive": value = build_archive(config)
    elif args.command == "validate-archive": value = validate_archive(config)
    elif args.command == "prepare": value = prepare(config)
    elif args.command == "predict-neural": value = predict_neural(config)
    elif args.command == "predict-conventional": value = predict_conventional(config)
    elif args.command == "close": value = close_predictions(config)
    elif args.command == "score": value = score(config)
    else: value = status(config)
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AssessmentConfig", "TasmaniaOuterError", "build_archive", "build_response_free_rows",
    "close_predictions", "load_config", "metric_block", "predict_conventional", "predict_neural",
    "prepare", "score", "status", "validate_archive",
]
