"""Goal 043 mainland spatial partitions and split-fitted transformations."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from .goal040_normalisation import MANIFEST_PATH as NORMALISATION_MANIFEST_PATH, _sha
from .goal040_support import SUPPORT_MANIFEST_PATH, TRANSFORM, _load_cells, _load_species_cells
from .goal042_transfer_response import (
    MAINLAND_FILE as GOAL042_MAINLAND_FILE,
    MANIFEST_PATH as GOAL042_MANIFEST_PATH,
    OUTPUT_ROOT as GOAL042_OUTPUT_ROOT,
    materialise_mainland_rows,
    validate as validate_goal042,
)


CONFIG_PATH = Path("config/goal043_mainland_partitions.json")
MANIFEST_PATH = Path("metadata/goal043_manifest.json")
TRANSFORM_PATH = Path("metadata/goal043_transforms.json")
DECISION_PATH = Path("metadata/goal043_decision_receipt.json")
GOAL041_MANIFEST_PATH = Path("metadata/goal041_table_manifest.json")
PREDICTOR_PATH = Path("data/raw/goal041/predictor_substrate.parquet")
OUTPUT_ROOT = Path("data/raw/goal043")
ASSIGNMENT_FILE = "mainland_cell_partitions.parquet"
RESPONSE_FILE = "split_responses.parquet"
DIAGNOSTIC_FILE = "diagnostics.json"
MAINLAND_REGION = "southeast_mainland"
SCALES_KM = (100, 50, 25)
N_FOLDS = 5
N_SEEDS = 64
THRESHOLDS = (2, 3, 5)
CONTINUOUS = tuple([f"bio{i:02d}" for i in range(1, 20)] + ["elevation_mean", "elevation_sd"])
CATEGORICAL = ("nvis_mvg", "soil_order", "alum_secondary")
MISSING = "__MISSING__"
UNSEEN = "__UNSEEN__"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

ASSIGNMENT_SCHEMA = pa.schema([
    pa.field("cell_id", pa.string(), nullable=False),
    pa.field("block_x", pa.int16(), nullable=False),
    pa.field("block_y", pa.int16(), nullable=False),
    pa.field("fold", pa.int8(), nullable=False),
    pa.field("continuous_complete", pa.bool_(), nullable=False),
])
RESPONSE_SCHEMA = pa.schema([
    pa.field("fold", pa.int8(), nullable=False),
    pa.field("role", pa.string(), nullable=False),
    pa.field("target", pa.string(), nullable=False),
    pa.field("cell_id", pa.string(), nullable=False),
    pa.field("is_presence", pa.bool_(), nullable=False),
    pa.field("other_species_count", pa.int8(), nullable=False),
    pa.field("nearest_target_presence_m", pa.float64(), nullable=False),
    pa.field("eligible_x2", pa.bool_(), nullable=False),
    pa.field("eligible_x3", pa.bool_(), nullable=False),
    pa.field("eligible_x5", pa.bool_(), nullable=False),
    pa.field("continuous_complete", pa.bool_(), nullable=False),
])
PRIVACY = {
    "tracked_cell_ids": False,
    "tracked_coordinates": False,
    "tracked_row_payloads": False,
    "tracked_donor_to_cell_associations": False,
    "tracked_camera_identifiers": False,
    "tracked_private_paths": False,
}


class Goal043Error(ValueError):
    """Fail-closed Goal 043 contract error."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal043Error(reason)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal043Error(reason) from exc
    _require(isinstance(value, dict), reason)
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _schema_sha(schema: pa.Schema) -> str:
    contract = [{"name": x.name, "type": str(x.type), "nullable": x.nullable} for x in schema]
    return hashlib.sha256(_canonical(contract)).hexdigest()


def _validate_config(config: Mapping[str, Any]) -> None:
    partition = config.get("partition", {})
    response = config.get("response", {})
    transform = config.get("transformation", {})
    firewall = config.get("firewall", {})
    _require(
        config.get("schema_version") == "goal043-contract-v1"
        and config.get("goal_id") == "goal043-mainland-spatial-development-substrate"
        and partition.get("region") == MAINLAND_REGION
        and partition.get("projected_crs") == "EPSG:3577"
        and partition.get("candidate_block_sizes_km") == list(SCALES_KM)
        and partition.get("folds") == N_FOLDS
        and partition.get("assignment_seeds") == N_SEEDS
        and partition.get("fold_map_share_minimum") == 0.15
        and partition.get("fold_map_share_maximum") == 0.25
        and partition.get("shared_target_validation_minimum_per_class") == 30
        and partition.get("all_head_training_minimum_per_class") == 100
        and partition.get("performance_inputs_permitted") is False
        and response.get("primary_support_threshold") == 3
        and response.get("sensitivity_support_thresholds") == [2, 5]
        and response.get("minimum_nearest_target_presence_distance_m") == 5000
        and response.get("materialise_separately_for_each_fold_role") is True
        and response.get("authorised_records_only") is True
        and response.get("full_goal042_reference_is_model_input") is False
        and tuple(transform.get("continuous", [])) == CONTINUOUS
        and tuple(transform.get("categorical", [])) == CATEGORICAL
        and transform.get("continuous_formula") == "z=(x-training_mean)/training_population_sd"
        and transform.get("continuous_nodata") == "exclude_from_modelable_rows_without_imputation"
        and transform.get("maximum_whole_target_class_exclusion_fraction") == 0.02
        and transform.get("categorical_missing_token") == MISSING
        and transform.get("categorical_unseen_token") == UNSEEN
        and transform.get("fit_ids") == [f"fold{i:02d}" for i in range(5)] + ["mainland_full"]
        and firewall == {
            "tasmania_response_rows_read": 0,
            "tasmania_predictor_rows_used": 0,
            "tasmania_in_partition_selection": False,
            "tasmania_in_transform_fitting": False,
        },
        "goal043_contract_drift",
    )


def block_fold(seed: int, scale_km: int, block_x: int, block_y: int) -> int:
    value = f"{seed}:{scale_km}:{block_x}:{block_y}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big") % N_FOLDS


def _authorities(root: Path, *, require_raw: bool) -> tuple[dict[str, str], list[str], list[str]]:
    config = _read_json(root / CONFIG_PATH, "goal043_config_invalid")
    _validate_config(config)
    validate_goal042(root, require_raw=False)
    normal = _read_json(root / NORMALISATION_MANIFEST_PATH, "goal043_normalisation_invalid")
    goal042 = _read_json(root / GOAL042_MANIFEST_PATH, "goal043_goal042_manifest_invalid")
    goal041 = _read_json(root / GOAL041_MANIFEST_PATH, "goal043_goal041_manifest_invalid")
    heads = goal042.get("summary", {}).get("cohort", {}).get("response_heads", [])
    targets = goal042.get("summary", {}).get("cohort", {}).get("shared_targets", [])
    support_taxa = goal042.get("summary", {}).get("cohort", {}).get("support_taxa", [])
    _require(
        len(heads) == 20 and len(targets) == 5 and len(support_taxa) == 21
        and set(targets) <= set(heads)
        and goal041.get("rows") == 1_125_325
        and goal041.get("regions") == {MAINLAND_REGION: 1_053_032, "tasmania": 72_293},
        "goal043_upstream_contract_drift",
    )
    goal042_output = goal042["outputs"]["private_output_roles"]["mainland_response_reference"]
    bindings = {
        "config_sha256": _sha(root / CONFIG_PATH),
        "goal040_normalisation_manifest_sha256": _sha(root / NORMALISATION_MANIFEST_PATH),
        "goal040_support_manifest_sha256": _sha(root / SUPPORT_MANIFEST_PATH),
        "goal042_response_manifest_sha256": _sha(root / GOAL042_MANIFEST_PATH),
        "goal042_mainland_reference_sha256": goal042_output["sha256"],
        "goal041_table_manifest_sha256": _sha(root / GOAL041_MANIFEST_PATH),
        "goal041_predictor_table_sha256": goal041["final_sha256"],
    }
    _require(all(isinstance(value, str) and SHA256_RE.fullmatch(value) for value in bindings.values()), "goal043_binding_digest_drift")
    if require_raw:
        _require(
            _sha(root / GOAL042_OUTPUT_ROOT / GOAL042_MAINLAND_FILE) == goal042_output["sha256"]
            and _sha(root / PREDICTOR_PATH) == goal041["final_sha256"],
            "goal043_raw_authority_drift",
        )
    return bindings, list(heads), list(targets)


def _mainland_cells(root: Path) -> tuple[list[str], dict[str, tuple[Any, Any]], np.ndarray, np.ndarray]:
    cells = _load_cells(root)
    selected = sorted(cell for cell, (_, _, region) in cells.items() if region == MAINLAND_REGION)
    coordinates = {cell: cells[cell][:2] for cell in selected}
    longitude = np.asarray([float(coordinates[cell][0]) for cell in selected])
    latitude = np.asarray([float(coordinates[cell][1]) for cell in selected])
    x, y = TRANSFORM.transform(longitude, latitude)
    _require(len(selected) == 1_053_032, "goal043_mainland_cell_count_drift")
    return selected, coordinates, np.asarray(x), np.asarray(y)


def _predictors(root: Path, cell_ids: list[str]) -> tuple[pa.Table, np.ndarray]:
    table = ds.dataset(root / PREDICTOR_PATH, format="parquet").to_table(
        columns=["cell_id", "region", *CONTINUOUS, *CATEGORICAL],
        filter=ds.field("region") == MAINLAND_REGION,
    )
    observed = table.column("cell_id").to_pylist()
    _require(len(observed) == len(set(observed)) == len(cell_ids), "goal043_predictor_identity_drift")
    if observed != cell_ids:
        index = {cell: i for i, cell in enumerate(observed)}
        _require(set(index) == set(cell_ids), "goal043_predictor_identity_drift")
        table = table.take(pa.array([index[cell] for cell in cell_ids], type=pa.int64()))
    complete = np.ones(len(cell_ids), dtype=bool)
    for name in CONTINUOUS:
        values = np.asarray(table.column(name).to_numpy(zero_copy_only=False), dtype=float)
        complete &= np.isfinite(values)
    _require(table.column("region").to_pylist() == [MAINLAND_REGION] * len(cell_ids), "goal043_tasmania_predictor_access")
    return table, complete


def _reference_arrays(root: Path, cell_index: Mapping[str, int]) -> dict[str, np.ndarray]:
    table = pq.read_table(
        root / GOAL042_OUTPUT_ROOT / GOAL042_MAINLAND_FILE,
        columns=["target", "cell_id", "is_presence", "eligible_x3"],
    )
    presence = np.asarray(table.column("is_presence").to_numpy(), dtype=bool)
    x3 = np.asarray(table.column("eligible_x3").to_numpy(), dtype=bool)
    active = presence | x3
    targets = np.asarray(table.column("target").to_pylist(), dtype=object)[active]
    cells = np.asarray(table.column("cell_id").to_pylist(), dtype=object)[active]
    indices = np.fromiter((cell_index[cell] for cell in cells), dtype=np.int64, count=len(cells))
    return {"target": targets, "cell_index": indices, "is_presence": presence[active]}


def _candidate_search(
    x: np.ndarray,
    y: np.ndarray,
    reference: Mapping[str, np.ndarray],
    heads: list[str],
    shared_targets: list[str],
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    summaries: dict[str, Any] = {}
    feasible_by_scale: dict[int, list[dict[str, Any]]] = {}
    ref_target = reference["target"]
    ref_index = reference["cell_index"]
    ref_presence = reference["is_presence"]
    masks = {target: ref_target == target for target in heads}
    for scale_km in SCALES_KM:
        scale = scale_km * 1000
        bx = np.floor(x / scale).astype(np.int16)
        by = np.floor(y / scale).astype(np.int16)
        blocks, inverse = np.unique(np.column_stack((bx, by)), axis=0, return_inverse=True)
        feasible: list[dict[str, Any]] = []
        failures: Counter[str] = Counter()
        map_balanced = 0
        for seed in range(N_SEEDS):
            block_folds = np.asarray([block_fold(seed, scale_km, int(a), int(b)) for a, b in blocks], dtype=np.int8)
            folds = block_folds[inverse]
            map_counts = np.bincount(folds, minlength=N_FOLDS)
            map_shares = map_counts / len(folds)
            if map_shares.min() < 0.15 or map_shares.max() > 0.25:
                failures["map_share"] += 1
                continue
            map_balanced += 1
            response_folds = folds[ref_index]
            reasons: set[str] = set()
            worst_response_deviation = 0.0
            minima = {"shared_validation_presence": math.inf, "shared_validation_background": math.inf,
                      "all_head_training_presence": math.inf, "all_head_training_background": math.inf}
            for target in heads:
                target_mask = masks[target]
                presence_counts = np.bincount(response_folds[target_mask & ref_presence], minlength=N_FOLDS)
                background_counts = np.bincount(response_folds[target_mask & ~ref_presence], minlength=N_FOLDS)
                train_presence = presence_counts.sum() - presence_counts
                train_background = background_counts.sum() - background_counts
                minima["all_head_training_presence"] = min(minima["all_head_training_presence"], int(train_presence.min()))
                minima["all_head_training_background"] = min(minima["all_head_training_background"], int(train_background.min()))
                if train_presence.min() < 100:
                    reasons.add(f"{target}:training_presence")
                if train_background.min() < 100:
                    reasons.add(f"{target}:training_background")
                if target in shared_targets:
                    minima["shared_validation_presence"] = min(minima["shared_validation_presence"], int(presence_counts.min()))
                    minima["shared_validation_background"] = min(minima["shared_validation_background"], int(background_counts.min()))
                    if presence_counts.min() < 30:
                        reasons.add(f"{target}:validation_presence")
                    if background_counts.min() < 30:
                        reasons.add(f"{target}:validation_background")
                for values in (presence_counts, background_counts):
                    worst_response_deviation = max(
                        worst_response_deviation,
                        float(np.max(np.abs(values / values.sum() - 0.2))),
                    )
            if reasons:
                failures.update(reasons)
                continue
            feasible.append({
                "seed": seed,
                "worst_response_fold_deviation": worst_response_deviation,
                "worst_map_fold_deviation": float(np.max(np.abs(map_shares - 0.2))),
                "map_fold_counts": map_counts.tolist(),
                "map_fold_shares": map_shares.tolist(),
                "hard_gate_minima": minima,
            })
        feasible.sort(key=lambda item: (item["worst_response_fold_deviation"], item["worst_map_fold_deviation"], item["seed"]))
        summaries[str(scale_km)] = {
            "block_count": len(blocks),
            "assignments_evaluated": N_SEEDS,
            "map_balanced_assignments": map_balanced,
            "feasible_assignments": len(feasible),
            "failure_counts": dict(sorted(failures.items())),
            "best_feasible": feasible[0] if feasible else None,
        }
        feasible_by_scale[scale_km] = feasible
    selected_scale = next((scale for scale in SCALES_KM if feasible_by_scale[scale]), None)
    _require(selected_scale is not None, "goal043_no_feasible_partition")
    selected = feasible_by_scale[selected_scale][0]
    bx = np.floor(x / (selected_scale * 1000)).astype(np.int16)
    by = np.floor(y / (selected_scale * 1000)).astype(np.int16)
    pairs, inverse = np.unique(np.column_stack((bx, by)), axis=0, return_inverse=True)
    block_folds = np.asarray([block_fold(selected["seed"], selected_scale, int(a), int(b)) for a, b in pairs], dtype=np.int8)
    folds = block_folds[inverse]
    return {
        "candidate_scales": summaries,
        "selected_scale_km": selected_scale,
        "selected_seed": selected["seed"],
        "selected_block_count": len(pairs),
        **selected,
    }, bx, by, folds


def _reference_missingness(
    root: Path, complete: np.ndarray, cell_index: Mapping[str, int]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    table = pq.read_table(
        root / GOAL042_OUTPUT_ROOT / GOAL042_MAINLAND_FILE,
        columns=["target", "cell_id", "is_presence", "eligible_x3"],
    ).to_pylist()
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in table:
        if not (row["is_presence"] or row["eligible_x3"]):
            continue
        response_class = "presence" if row["is_presence"] else "background_x3"
        key = (row["target"], response_class)
        counts[key][0] += 1
        counts[key][1] += int(not complete[cell_index[row["cell_id"]]])
    rows = []
    for (target, response_class), (total, excluded) in sorted(counts.items()):
        rows.append({"target": target, "response_class": response_class, "rows": total,
                     "continuous_nodata_rows": excluded, "exclusion_fraction": excluded / total})
    worst = max(rows, key=lambda row: row["exclusion_fraction"])
    _require(worst["exclusion_fraction"] <= 0.02, "goal043_continuous_nodata_guard_failed")
    return rows, worst


def _training_hash(cell_ids: list[str], mask: np.ndarray) -> str:
    digest = hashlib.sha256()
    for cell in np.asarray(cell_ids, dtype=object)[mask]:
        digest.update(str(cell).encode() + b"\n")
    return digest.hexdigest()


def _fit_transforms(
    table: pa.Table, cell_ids: list[str], folds: np.ndarray, complete: np.ndarray
) -> tuple[dict[str, Any], dict[str, Any]]:
    continuous = {
        name: np.asarray(table.column(name).to_numpy(zero_copy_only=False), dtype=float)
        for name in CONTINUOUS
    }
    categorical = {
        name: np.asarray([MISSING if value is None else str(value) for value in table.column(name).to_pylist()], dtype=object)
        for name in CATEGORICAL
    }
    transforms: dict[str, Any] = {}
    vocabularies: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}
    for fit_id in [f"fold{i:02d}" for i in range(N_FOLDS)] + ["mainland_full"]:
        held = None if fit_id == "mainland_full" else int(fit_id[-2:])
        train = complete & (np.ones(len(folds), dtype=bool) if held is None else folds != held)
        _require(int(train.sum()) > 0, "goal043_empty_transform_training")
        means = {name: float(np.mean(values[train])) for name, values in continuous.items()}
        sds = {name: float(np.std(values[train], ddof=0)) for name, values in continuous.items()}
        _require(all(math.isfinite(value) and value > 0 for value in sds.values()), "goal043_invalid_transform_sd")
        observed = {name: sorted(set(values[train])) for name, values in categorical.items()}
        categories = {
            name: {"observed_levels": levels, "encoded_levels": [*levels, *[x for x in (MISSING, UNSEEN) if x not in levels]]}
            for name, levels in observed.items()
        }
        vocabulary_id = "vocab_" + hashlib.sha256(_canonical(categories)).hexdigest()[:12]
        vocabularies[vocabulary_id] = categories
        transforms[fit_id] = {
            "training_cell_count": int(train.sum()),
            "excluded_continuous_nodata_cells": int((~complete & (np.ones(len(folds), dtype=bool) if held is None else folds != held)).sum()),
            "training_identity_sha256": _training_hash(cell_ids, train),
            "continuous_mean": [means[name] for name in CONTINUOUS],
            "continuous_population_sd": [sds[name] for name in CONTINUOUS],
            "categorical_vocabulary_id": vocabulary_id,
        }
        if held is not None:
            assessment = complete & (folds == held)
            unseen = {
                name: int(sum(value not in set(observed[name]) for value in values[assessment]))
                for name, values in categorical.items()
            }
            diagnostics[fit_id] = {
                "assessment_complete_cells": int(assessment.sum()),
                "categorical_unseen_cells": unseen,
                "categorical_missing_cells": {name: int(sum(value == MISSING for value in values[assessment])) for name, values in categorical.items()},
            }
    payload = {
        "schema_version": "goal043-transforms-v1",
        "continuous": list(CONTINUOUS),
        "categorical": list(CATEGORICAL),
        "formula": "z=(x-training_mean)/training_population_sd",
        "missing_token": MISSING,
        "unseen_token": UNSEEN,
        "categorical_vocabularies": vocabularies,
        "transforms": transforms,
    }
    return payload, diagnostics


def transform_row(
    row: Mapping[str, Any], parameters: Mapping[str, Any], vocabulary: Mapping[str, Any]
) -> tuple[list[float], list[str]]:
    """Apply one frozen transform without fitting or mutating its inputs."""
    values = []
    for index, name in enumerate(CONTINUOUS):
        raw = row.get(name)
        _require(raw is not None and math.isfinite(float(raw)), "goal043_continuous_nodata")
        values.append((float(raw) - parameters["continuous_mean"][index]) / parameters["continuous_population_sd"][index])
    categories = []
    for name in CATEGORICAL:
        raw = MISSING if row.get(name) is None else str(row[name])
        observed = vocabulary[name]["observed_levels"]
        categories.append(MISSING if raw == MISSING else raw if raw in observed else UNSEEN)
    return values, categories


def _write_parquet(path: Path, schema: pa.Schema, table: pa.Table) -> dict[str, Any]:
    temp = path.with_suffix(path.suffix + ".part")
    _require(not temp.exists(), "goal043_orphaned_partial_output")
    pq.write_table(table.cast(schema), temp, compression="zstd", use_dictionary=True)
    temp.replace(path)
    return _parquet_receipt(path, schema)


def _parquet_receipt(path: Path, schema: pa.Schema) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    _require(parquet.schema_arrow == schema, "goal043_output_schema_drift")
    return {"bytes": path.stat().st_size, "rows": parquet.metadata.num_rows,
            "sha256": _sha(path), "schema_sha256": _schema_sha(schema)}


def _split_responses(
    path: Path,
    heads: list[str],
    shared_targets: list[str],
    coordinates: Mapping[str, tuple[Any, Any]],
    donor_members: Mapping[str, set[str]],
    species_cells: Mapping[str, set[str]],
    fold_by_cell: Mapping[str, int],
    complete_by_cell: Mapping[str, bool],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    temp = path.with_suffix(path.suffix + ".part")
    _require(not temp.exists(), "goal043_orphaned_partial_output")
    writer = pq.ParquetWriter(temp, RESPONSE_SCHEMA, compression="zstd", use_dictionary=True)
    diagnostics: list[dict[str, Any]] = []
    rows_written = 0
    try:
        for fold in range(N_FOLDS):
            for role in ("train", "validation"):
                permitted = lambda cell: (fold_by_cell[cell] != fold) if role == "train" else (fold_by_cell[cell] == fold)
                members = {cell: values for cell, values in donor_members.items() if permitted(cell)}
                role_coordinates = {cell: coordinates[cell] for cell in members}
                for target in heads:
                    target_presence = {cell for cell in species_cells[target] if cell in members}
                    base = materialise_mainland_rows(target, role_coordinates, members, target_presence)
                    rows = [{"fold": fold, "role": role, **row,
                             "continuous_complete": bool(complete_by_cell[row["cell_id"]])} for row in base]
                    writer.write_table(pa.Table.from_pylist(rows, schema=RESPONSE_SCHEMA))
                    rows_written += len(rows)
                    presence = [row for row in rows if row["is_presence"]]
                    background = [row for row in rows if row["eligible_x3"]]
                    diagnostics.append({
                        "fold": fold, "role": role, "target": target,
                        "rows": len(rows), "presence": len(presence),
                        "background_x2": sum(row["eligible_x2"] for row in rows),
                        "background_x3": len(background),
                        "background_x5": sum(row["eligible_x5"] for row in rows),
                        "presence_continuous_nodata": sum(not row["continuous_complete"] for row in presence),
                        "background_x3_continuous_nodata": sum(not row["continuous_complete"] for row in background),
                    })
    finally:
        writer.close()
    temp.replace(path)
    shared_validation = [row for row in diagnostics if row["role"] == "validation" and row["target"] in shared_targets]
    all_training = [row for row in diagnostics if row["role"] == "train"]
    minima = {
        "shared_validation_presence": min(row["presence"] for row in shared_validation),
        "shared_validation_background_x3": min(row["background_x3"] for row in shared_validation),
        "all_head_training_presence": min(row["presence"] for row in all_training),
        "all_head_training_background_x3": min(row["background_x3"] for row in all_training),
    }
    _require(
        minima["shared_validation_presence"] >= 30
        and minima["shared_validation_background_x3"] >= 30
        and minima["all_head_training_presence"] >= 100
        and minima["all_head_training_background_x3"] >= 100,
        "goal043_split_response_hard_gate_failed",
    )
    split_losses = []
    for row in diagnostics:
        for response_class, total_key, missing_key in (
            ("presence", "presence", "presence_continuous_nodata"),
            ("background_x3", "background_x3", "background_x3_continuous_nodata"),
        ):
            if row[total_key]:
                split_losses.append({"fold": row["fold"], "role": row["role"], "target": row["target"],
                                     "response_class": response_class,
                                     "exclusion_fraction": row[missing_key] / row[total_key]})
    return {**_parquet_receipt(path, RESPONSE_SCHEMA), "hard_gate_minima": minima,
            "maximum_split_class_exclusion": max(split_losses, key=lambda row: row["exclusion_fraction"])}, diagnostics


def _build_outputs(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    bindings, heads, targets = _authorities(root, require_raw=True)
    cell_ids, coordinates, x, y = _mainland_cells(root)
    cell_index = {cell: i for i, cell in enumerate(cell_ids)}
    predictors, complete = _predictors(root, cell_ids)
    reference = _reference_arrays(root, cell_index)
    selection, block_x, block_y, folds = _candidate_search(x, y, reference, heads, targets)
    reference_missingness, worst_reference_loss = _reference_missingness(root, complete, cell_index)
    transforms, transform_diagnostics = _fit_transforms(predictors, cell_ids, folds, complete)
    transforms["bindings"] = bindings
    (root / TRANSFORM_PATH).write_text(json.dumps(transforms, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output = root / OUTPUT_ROOT
    output.mkdir(parents=True, exist_ok=True)
    _require({path.name for path in output.iterdir()} <= {ASSIGNMENT_FILE, RESPONSE_FILE, DIAGNOSTIC_FILE}, "goal043_output_footprint_drift")
    assignment_table = pa.Table.from_arrays([
        pa.array(cell_ids), pa.array(block_x, type=pa.int16()), pa.array(block_y, type=pa.int16()),
        pa.array(folds, type=pa.int8()), pa.array(complete),
    ], schema=ASSIGNMENT_SCHEMA)
    assignment_receipt = _write_parquet(output / ASSIGNMENT_FILE, ASSIGNMENT_SCHEMA, assignment_table)

    cells = _load_cells(root)
    species = _load_species_cells(root, cells)
    support_taxa = _read_json(root / GOAL042_MANIFEST_PATH, "goal043_goal042_manifest_invalid")["summary"]["cohort"]["support_taxa"]
    donor_members: dict[str, set[str]] = defaultdict(set)
    for taxon in support_taxa:
        for cell in species[taxon]:
            if cell in cell_index:
                donor_members[cell].add(taxon)
    fold_by_cell = dict(zip(cell_ids, map(int, folds), strict=True))
    complete_by_cell = dict(zip(cell_ids, map(bool, complete), strict=True))
    response_receipt, split_diagnostics = _split_responses(
        output / RESPONSE_FILE, heads, targets, coordinates, donor_members, species,
        fold_by_cell, complete_by_cell,
    )
    diagnostics = {
        "candidate_search": selection,
        "reference_continuous_nodata": reference_missingness,
        "split_responses": split_diagnostics,
        "transforms": transform_diagnostics,
    }
    (output / DIAGNOSTIC_FILE).write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs = {
        "mainland_cell_partitions": assignment_receipt,
        "split_responses": {key: value for key, value in response_receipt.items() if key != "maximum_split_class_exclusion" and key != "hard_gate_minima"},
        "diagnostics": {"bytes": (output / DIAGNOSTIC_FILE).stat().st_size, "sha256": _sha(output / DIAGNOSTIC_FILE)},
    }
    summary = {
        "partition": selection,
        "response_hard_gate_minima": response_receipt["hard_gate_minima"],
        "reference_continuous_nodata_guard": {"maximum_allowed_fraction": 0.02, "worst_observed": worst_reference_loss},
        "maximum_split_class_exclusion_descriptive": response_receipt["maximum_split_class_exclusion"],
        "transform_fit_ids": list(transforms["transforms"]),
        "transform_training_cell_range": [
            min(item["training_cell_count"] for item in transforms["transforms"].values()),
            max(item["training_cell_count"] for item in transforms["transforms"].values()),
        ],
        "maximum_cv_categorical_unseen_cells": max(
            ({"fit_id": fit_id, "predictor": name, "cells": count}
             for fit_id, item in transform_diagnostics.items()
             for name, count in item["categorical_unseen_cells"].items()),
            key=lambda row: row["cells"],
        ),
        "firewall": {
            "tasmania_response_rows_read": 0,
            "tasmania_predictor_rows_used": 0,
            "tasmania_in_partition_selection": False,
            "tasmania_in_transform_fitting": False,
        },
    }
    return {"bindings": bindings, "summary": summary, "outputs": outputs}, diagnostics


def _manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "goal043-manifest-v1",
        "goal_id": "goal043-mainland-spatial-development-substrate",
        "status": "complete_private_replay_required",
        "completed_at": _now(),
        "bindings": payload["bindings"],
        "transform_parameters_sha256": None,
        "summary": payload["summary"],
        "outputs": {"private_outputs_ignored": True, "private_output_roles": payload["outputs"]},
        "privacy": PRIVACY,
    }


def _validate_transforms(payload: Mapping[str, Any], bindings: Mapping[str, str]) -> None:
    _require(
        payload.get("schema_version") == "goal043-transforms-v1"
        and payload.get("continuous") == list(CONTINUOUS)
        and payload.get("categorical") == list(CATEGORICAL)
        and payload.get("missing_token") == MISSING
        and payload.get("unseen_token") == UNSEEN
        and payload.get("bindings") == bindings
        and set(payload.get("transforms", {})) == {f"fold{i:02d}" for i in range(5)} | {"mainland_full"},
        "goal043_transform_contract_drift",
    )
    vocabularies = payload.get("categorical_vocabularies", {})
    _require(isinstance(vocabularies, dict) and bool(vocabularies), "goal043_transform_vocabulary_drift")
    for vocabulary_id, vocabulary in vocabularies.items():
        _require(
            vocabulary_id == "vocab_" + hashlib.sha256(_canonical(vocabulary)).hexdigest()[:12]
            and set(vocabulary) == set(CATEGORICAL)
            and all(UNSEEN in value["encoded_levels"] and MISSING in value["encoded_levels"] for value in vocabulary.values()),
            "goal043_transform_vocabulary_drift",
        )
    for item in payload["transforms"].values():
        _require(
            len(item["continuous_mean"]) == len(CONTINUOUS)
            and len(item["continuous_population_sd"]) == len(CONTINUOUS)
            and all(math.isfinite(value) for value in item["continuous_mean"])
            and all(math.isfinite(value) and value > 0 for value in item["continuous_population_sd"])
            and item["categorical_vocabulary_id"] in vocabularies
            and SHA256_RE.fullmatch(item["training_identity_sha256"]) is not None,
            "goal043_transform_parameter_drift",
        )


def _validate_manifest(manifest: Mapping[str, Any], bindings: Mapping[str, str], transform_sha: str) -> None:
    summary = manifest.get("summary", {})
    partition = summary.get("partition", {})
    minima = summary.get("response_hard_gate_minima", {})
    firewall = summary.get("firewall", {})
    candidates = partition.get("candidate_scales", {})
    largest_feasible = next(
        (scale for scale in SCALES_KM if candidates.get(str(scale), {}).get("feasible_assignments", 0) > 0),
        None,
    )
    selected_candidate = candidates.get(str(partition.get("selected_scale_km")), {}).get("best_feasible")
    _require(
        manifest.get("schema_version") == "goal043-manifest-v1"
        and manifest.get("goal_id") == "goal043-mainland-spatial-development-substrate"
        and manifest.get("status") == "complete_private_replay_required"
        and manifest.get("bindings") == bindings
        and manifest.get("transform_parameters_sha256") == transform_sha
        and manifest.get("privacy") == PRIVACY
        and partition.get("selected_scale_km") == largest_feasible
        and partition.get("selected_seed") in range(N_SEEDS)
        and isinstance(selected_candidate, dict)
        and partition.get("selected_seed") == selected_candidate.get("seed")
        and minima.get("shared_validation_presence", 0) >= 30
        and minima.get("shared_validation_background_x3", 0) >= 30
        and minima.get("all_head_training_presence", 0) >= 100
        and minima.get("all_head_training_background_x3", 0) >= 100
        and summary.get("reference_continuous_nodata_guard", {}).get("worst_observed", {}).get("exclusion_fraction", 1) <= 0.02
        and firewall == {
            "tasmania_response_rows_read": 0,
            "tasmania_predictor_rows_used": 0,
            "tasmania_in_partition_selection": False,
            "tasmania_in_transform_fitting": False,
        },
        "goal043_manifest_contract_drift",
    )
    roles = manifest.get("outputs", {}).get("private_output_roles", {})
    _require(manifest.get("outputs", {}).get("private_outputs_ignored") is True and set(roles) == {"mainland_cell_partitions", "split_responses", "diagnostics"}, "goal043_output_manifest_drift")
    text = json.dumps(manifest, sort_keys=True).lower()
    _require(not any(token in text for token in ("longitude", "latitude", '"cell_id"', "grid_cell_id", "site_id", "data/raw/")), "goal043_tracked_privacy_failure")


def _decision(manifest_sha: str, transform_sha: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "goal043-decision-v1",
        "status": "ready",
        "manifest_sha256": manifest_sha,
        "transform_parameters_sha256": transform_sha,
        "selected_partition": {
            "block_size_km": manifest["summary"]["partition"]["selected_scale_km"],
            "seed": manifest["summary"]["partition"]["selected_seed"],
            "folds": 5,
        },
        "gates": {
            "bounded_partition_search": "validated",
            "split_authorised_responses": "validated",
            "continuous_nodata": "validated_complete_case",
            "split_fitted_transforms": "validated",
            "tasmania_firewall": "validated_zero_access",
            "privacy": "validated",
        },
        "limitations": [
            "Spatial folds are scattered held blocks rather than five contiguous biogeographic regions",
            "Target-group backgrounds remain effort-supported candidates rather than true absences",
            "Continuous source-nodata cells are excluded rather than imputed",
            "The mainland_full transform is reserved for a later final refit after model development is frozen",
        ],
        "next_boundary": "mainland_only_modeling_protocol_and_compute_preflight_without_tasmania_access",
    }


def build(root: Path) -> dict[str, Any]:
    root = Path(root)
    payload, _ = _build_outputs(root)
    transform_sha = _sha(root / TRANSFORM_PATH)
    manifest = _manifest(payload)
    manifest["transform_parameters_sha256"] = transform_sha
    (root / MANIFEST_PATH).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision = _decision(_sha(root / MANIFEST_PATH), transform_sha, manifest)
    (root / DECISION_PATH).write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validate(root, require_raw=True)


def validate(root: Path, *, require_raw: bool = False) -> dict[str, Any]:
    root = Path(root)
    bindings, _, _ = _authorities(root, require_raw=require_raw)
    transforms = _read_json(root / TRANSFORM_PATH, "goal043_transforms_invalid")
    _validate_transforms(transforms, bindings)
    transform_sha = _sha(root / TRANSFORM_PATH)
    manifest = _read_json(root / MANIFEST_PATH, "goal043_manifest_invalid")
    _validate_manifest(manifest, bindings, transform_sha)
    decision = _read_json(root / DECISION_PATH, "goal043_decision_invalid")
    _require(decision == _decision(_sha(root / MANIFEST_PATH), transform_sha, manifest), "goal043_decision_drift")
    if not require_raw:
        return {"status": "tracked_goal043_valid_private_replay_required", "private_replay_required": True}
    output = root / OUTPUT_ROOT
    _require(output.is_dir() and {path.name for path in output.iterdir()} == {ASSIGNMENT_FILE, RESPONSE_FILE, DIAGNOSTIC_FILE}, "goal043_output_footprint_drift")
    roles = manifest["outputs"]["private_output_roles"]
    _require(_parquet_receipt(output / ASSIGNMENT_FILE, ASSIGNMENT_SCHEMA) == roles["mainland_cell_partitions"], "goal043_assignment_receipt_drift")
    _require(_parquet_receipt(output / RESPONSE_FILE, RESPONSE_SCHEMA) == roles["split_responses"], "goal043_response_receipt_drift")
    _require({"bytes": (output / DIAGNOSTIC_FILE).stat().st_size, "sha256": _sha(output / DIAGNOSTIC_FILE)} == roles["diagnostics"], "goal043_diagnostic_receipt_drift")
    return {
        "status": "goal043_ready_private_outputs_validated",
        "selected_block_size_km": manifest["summary"]["partition"]["selected_scale_km"],
        "selected_seed": manifest["summary"]["partition"]["selected_seed"],
        "assignment_rows": roles["mainland_cell_partitions"]["rows"],
        "split_response_rows": roles["split_responses"]["rows"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate", "validate-tracked"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = build(args.root) if args.command == "build" else validate(args.root, require_raw=args.command == "validate")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Goal043Error", "block_fold", "transform_row", "build", "validate", "main"]
