"""Goal025 deterministic spatial partition and leakage diagnostics.

Geometry is derived only from the frozen Goal024 D_struct map. Response
information is used after geometry construction for explicit gates, ranking,
assignments, and diagnostics. No transformations or models are fitted here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from pyproj import (
    CRS,
    Transformer,
    __version__ as PYPROJ_VERSION,
    proj_version_str,
)

DATE = "2026-07-26"
GOAL_ID = "goal025-spatial-partition-2026-07-26"
PLAN_SCHEMA_VERSION = "2.0"
N_MICRO = 50
N_MACRO = 5
N_FOLDS = 5
CLUSTERS_PER_FOLD = 9
SEED_STOP = 4096

SPECIES = (
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
    "notamacropus_rufogriseus",
    "pseudocheirus_peregrinus",
    "sarcophilus_harrisii",
    "thylogale_billardierii",
    "trichosurus_vulpecula",
    "vombatus_ursinus",
)
ACTIVE = (
    "annmeantemp",
    "meandiurnrange",
    "isothermality",
    "tempseason",
    "maxtempwarmmonth",
    "mintempcoldmonth",
    "tempannrange",
    "meantempwetq",
    "meantempdryq",
    "meantempwarmq",
    "meantempcoldq",
    "annprecip",
    "precipwetmonth",
    "precipdrymonth",
    "precipseason",
    "precipwetq",
    "precipdryq",
    "precipwarmq",
    "precipcoldq",
    "elevation",
    "top_roughness",
    "soil_class",
    "dist_fw",
    "dist_road",
    "fpar",
    "veg_mvg",
    "landuse_secondary",
    "human_footprint",
)
CATEGORICAL = ("soil_class", "veg_mvg", "landuse_secondary")
CONTINUOUS = tuple(name for name in ACTIVE if name not in CATEGORICAL)
FAMILIES = {
    "temperature": ACTIVE[:11],
    "precipitation": ACTIVE[11:19],
    "terrain_soil": ("elevation", "top_roughness", "soil_class"),
    "proximity": ("dist_fw", "dist_road"),
    "vegetation": ("fpar", "veg_mvg"),
    "landuse_pressure": ("landuse_secondary", "human_footprint"),
}

MAP_ROWS = 71_023
RESPONSE_CELLS = 5_087
RESPONSE_ROWS = 12_711
ALL_RESPONSE_CELLS = 5_407
ALL_RESPONSE_ROWS = 13_455
EXCLUDED_CELLS = 320
EXCLUDED_ROWS = 744
EXPECTED_COUNTS = {
    "map_cells": MAP_ROWS,
    "response_cells": RESPONSE_CELLS,
    "response_rows": RESPONSE_ROWS,
    "species": 8,
    "predictors": 28,
    "excluded_response_cells": EXCLUDED_CELLS,
    "excluded_response_rows": EXCLUDED_ROWS,
}
CORRECTED_ORACLE = {
    "unique_outer_candidates": 3_694,
    "outer_hard_gate_viable": 166,
    "joint_feasible_outer": 6,
    "viable_cv_assignments": 9,
}
JOINT_CV_ORACLE = {
    (2, 16, 29, 40, 49): (3105,),
    (2, 16, 36, 40, 49): (1092,),
    (4, 26, 28, 40, 46): (1810,),
    (8, 20, 35, 40, 49): (422, 2831),
    (8, 20, 40, 41, 46): (422, 2036, 2694),
    (8, 26, 32, 42, 46): (422,),
}
JOINT_OUTER_ORACLE = set(JOINT_CV_ORACLE)

PRIVACY = {
    "tracked_grid_ids_or_coordinates": False,
    "tracked_row_payloads": False,
    "tracked_private_paths": False,
    "tracked_response_identifiers": False,
    "tracked_site_or_camera_ids": False,
    "tracked_private_observation_timing": False,
}
STOPPED_BEFORE = [
    "transformations",
    "imputation",
    "encoding",
    "scaling",
    "mapping",
    "tuning",
    "modelling",
]
ESTIMAND = (
    "species-specific pre-model held-patch interpolation assessment within "
    "Goal024 D_struct, conditional on the accepted response construction; "
    "not unbiased confirmatory transfer, occupancy, prevalence, isolated "
    "regional extrapolation, temporal transfer, or outside-domain inference"
)
CHECKLIST = [
    (
        "dominant components spatially coherent; island and D_struct "
        "fragmentation quantified and accepted"
    ),
    "plausible islands/coast",
    "five-region outer coverage",
    "no empty/effectively empty test patch",
    (
        "aggregate class imbalance visible; split-specific source/class "
        "concentrations checked from diagnostics"
    ),
    "no site IDs, timing, activity, or finer-than-0.01 source detail",
]
RANKING_CONTRACT = {
    "outer": {
        "equal_thirds": [
            "geographic_dispersion",
            "environmental_similarity",
            "species_binary_representation",
        ],
        "geography": [
            "minimum_pairwise_projected_microcentre_distance",
            "mean_pairwise_projected_microcentre_distance",
        ],
        "environment": "equal map/response and equal six-family KS/TV loss",
        "representation": (
            "mean and worst species-binary allocation deviation"
        ),
    },
    "cv": {
        "equal_thirds": [
            "fold_geographic_dispersion",
            "fold_environmental_similarity",
            "map_response_species_binary_balance",
        ],
        "aggregation": "mean and worst-fold losses",
        "environment": (
            "same six families relative to outer-training substrate"
        ),
    },
    "performance_input": False,
    "tie_policy": [
        "equal_third_score",
        "geography",
        "environment",
        "representation_or_balance_loss",
        "lexical_tuple",
        "seed",
    ],
}

MAP_SCHEMA = [
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    *ACTIVE,
    "predictor_complete",
    "missing_predictor_count",
    "missing_predictor_ids",
]
RESPONSE_SCHEMA = [
    "species_id",
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "pa",
    "pa_type",
    "survey_supported_absence_rule_id",
    "source_combination",
    "cross_source_conflict",
    "ala_presence",
    "ala_source_row_count",
    "ala_unique_provider_record_count",
    "ala_resource_count",
    "ala_dataset_count",
    "ala_unknown_uncertainty_count",
    "ala_qa_flag_count",
    "ala_low_cell_certainty_only",
    "camera_evidence",
    "camera_pa",
    "camera_pa_type",
    "camera_survey_supported_absence_rule_id",
    "camera_site_count",
    "camera_presence_site_count",
    "camera_survey_supported_absence_site_count",
    "camera_positive_source_row_count",
    "camera_internal_conflict",
    "response_origin",
    "pseudoabsence_rule_id",
    "pseudoabsence_support_species_count",
    "pseudoabsence_support_species_ids",
    "nearest_target_presence_grid_cell_id",
    "nearest_target_presence_source_combination",
    "nearest_target_presence_distance_m",
    "distance_crs",
]
ASSIGNMENT_FIELDS = ["microcluster", "macroregion", "outer_role", "cv_fold"]
MAP_ASSIGNMENT_SCHEMA = ["grid_cell_id", *ASSIGNMENT_FIELDS]
RESPONSE_CELL_ASSIGNMENT_SCHEMA = ["grid_cell_id", *ASSIGNMENT_FIELDS]
RESPONSE_PARTITION_SCHEMA = [*RESPONSE_SCHEMA, *ASSIGNMENT_FIELDS]
EXCLUDED_CELL_SCHEMA = [
    "grid_cell_id",
    "centroid_lon",
    "centroid_lat",
    "microcluster",
    "macroregion",
    "audit_role",
    "reason",
]
EXCLUDED_ROW_SCHEMA = [
    *RESPONSE_SCHEMA,
    "microcluster",
    "macroregion",
    "audit_role",
    "reason",
]

OUTER_CANDIDATE_SCHEMA = [
    "outer_tuple",
    "first_seed",
    "seed_count",
    "map_cells",
    "map_share",
    "response_cells",
    "response_cell_share",
    "minimum_cluster_response_cells",
    "minimum_test_species_binary_rows",
    "minimum_complement_species_binary_rows",
    "distinct_cluster_gate",
    "macroregion_gate",
    "map_share_gate",
    "response_share_gate",
    "cluster_response_gate",
    "test_class_gate",
    "complement_class_gate",
    "outer_viable",
    "cv_viable_seed_count",
    "joint_feasible",
    "geography_min_m",
    "geography_mean_m",
    "environment_map_loss",
    "environment_response_loss",
    "environment_loss",
    "representation_mean_loss",
    "representation_worst_loss",
    "geography_midrank_score",
    "environment_midrank_score",
    "representation_midrank_score",
    "equal_third_score",
    "rank",
    "selected",
]
for _substrate in ("map", "response"):
    for _family in FAMILIES:
        OUTER_CANDIDATE_SCHEMA.append(
            f"environment_{_substrate}_{_family}_loss"
        )

OUTER_CV_SCHEMA = [
    "outer_tuple",
    "outer_viable",
    "cv_scanned",
    "cv_attempts",
    "stratified_invariant_pass_seeds",
    "four_macroregions_all_folds_seeds",
    "response_share_all_folds_pass_seeds",
    "validation_class_all_folds_pass_seeds",
    "training_class_all_folds_pass_seeds",
    "viable_cv_seed_count",
    "viable_cv_seeds",
    "joint_feasible",
    "selected_outer",
]
CV_CANDIDATE_SCHEMA = [
    "cv_seed",
    "fold00",
    "fold01",
    "fold02",
    "fold03",
    "fold04",
    "fold_response_cells",
    "fold_response_shares",
    "fold_macroregion_counts",
    "fold_macroregion_cluster_counts",
    "minimum_fold_macroregions",
    "total_fold_macroregion_incidence",
    "maximum_macro_fold_count_imbalance",
    "minimum_validation_species_binary_rows",
    "minimum_training_species_binary_rows",
    "stratified_geometry_gate",
    "response_share_gate",
    "validation_class_gate",
    "training_class_gate",
    "viable",
    "geography_mean_fold_mean_m",
    "geography_worst_fold_min_m",
    "environment_mean_fold_loss",
    "environment_worst_fold_loss",
    "balance_mean_loss",
    "balance_worst_fold_loss",
    "geography_midrank_score",
    "environment_midrank_score",
    "balance_midrank_score",
    "equal_third_score",
    "rank",
    "selected",
]
PRIVATE_SCHEMAS = {
    "map_assignments.csv": MAP_ASSIGNMENT_SCHEMA,
    "response_cell_assignments.csv": RESPONSE_CELL_ASSIGNMENT_SCHEMA,
    "response_partitioned.csv": RESPONSE_PARTITION_SCHEMA,
    "excluded_cell_audit.csv": EXCLUDED_CELL_SCHEMA,
    "excluded_row_audit.csv": EXCLUDED_ROW_SCHEMA,
    "outer_candidates.csv": OUTER_CANDIDATE_SCHEMA,
    "outer_cv_feasibility.csv": OUTER_CV_SCHEMA,
    "cv_candidates.csv": CV_CANDIDATE_SCHEMA,
}
PRIVATE_NAMES = (
    *PRIVATE_SCHEMAS,
    "support_diagnostics.json",
    "spatial_partition.svg",
)
EVIDENCE_FILES = ("summary.json", "bindings.json", "outputs.json", "review.json")

BINDING_PATHS = {
    "decision_bundle": "config/phase1_decision_bundle.json",
    "goal024_plan": "config/predictor_source_repair_domain_freeze_plan.json",
    "goal024_manifest": (
        "evidence/predictor_source_repair_domain_freeze/2026-07-26/manifest.json"
    ),
    "goal024_review": (
        "evidence/predictor_source_repair_domain_freeze/2026-07-26/review.json"
    ),
    "goal024_outputs": (
        "evidence/predictor_source_repair_domain_freeze/2026-07-26/outputs.json"
    ),
    "goal024_support_contract": (
        "evidence/predictor_source_repair_domain_freeze/2026-07-26/"
        "support_contract.json"
    ),
    "goal024_map": (
        "data/processed/predictors/"
        "goal024-predictor-source-repair-domain-freeze/2026-07-26/"
        "predictor_cell_map_canonical.csv"
    ),
    "goal024_response_cells": (
        "data/processed/predictors/"
        "goal024-predictor-source-repair-domain-freeze/2026-07-26/"
        "predictor_response_cells_canonical.csv"
    ),
    "goal024_response": (
        "data/processed/predictors/"
        "goal024-predictor-source-repair-domain-freeze/2026-07-26/"
        "response_layer_canonical.csv"
    ),
    "goal022_all_response_cells": (
        "data/processed/predictors/goal022-predictor-stack-extraction/"
        "2026-07-26/predictor_response_cells_raw.csv"
    ),
    "goal021_all_response": (
        "data/processed/response/goal021-pseudoabsence-derivation/"
        "2026-07-26/response_layer.csv"
    ),
    "legacy_partition_comparison": "temp/src/2_tas_sdm_data_cv_split.r",
    "legacy_response_comparison": "temp/src/sdm_data_func.R",
}


class SpatialPartitionError(ValueError):
    """Fail-closed Goal025 contract or replay error."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _safe_relative(path_text: str) -> Path:
    path = Path(path_text)
    if not path_text or path.is_absolute() or ".." in path.parts:
        raise SpatialPartitionError("unsafe_binding_path")
    return path


def _read_csv(path: Path, expected_schema: Sequence[str] | None = None) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise SpatialPartitionError(f"missing_or_symlink:{path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if expected_schema is not None and reader.fieldnames != list(expected_schema):
            raise SpatialPartitionError(f"source_schema_drift:{path.name}")
        return list(reader)


def _csv_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)):
            return ""
        return format(float(value), ".12g")
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (tuple, list)):
        return ";".join(_csv_scalar(item) for item in value)
    return value


def csv_bytes(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(fields),
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_scalar(row.get(field, "")) for field in fields})
    return stream.getvalue().encode("utf-8")


def project_lonlat(
    lon: Sequence[float], lat: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    transformer = Transformer.from_crs(
        CRS.from_epsg(4326), CRS.from_epsg(7855), always_xy=True
    )
    x, y = transformer.transform(
        np.asarray(lon, dtype=np.float64),
        np.asarray(lat, dtype=np.float64),
    )
    return np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)


def unproject_xy(
    x: Sequence[float], y: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    transformer = Transformer.from_crs(
        CRS.from_epsg(7855), CRS.from_epsg(4326), always_xy=True
    )
    lon, lat = transformer.transform(
        np.asarray(x, dtype=np.float64),
        np.asarray(y, dtype=np.float64),
    )
    return np.asarray(lon, dtype=np.float64), np.asarray(lat, dtype=np.float64)


def nearest_center(
    points: np.ndarray,
    centers: np.ndarray,
    center_ids: Sequence[str] | None = None,
) -> np.ndarray:
    """Assign to the nearest centre; exact ties use lexical centre identity."""
    point_array = np.asarray(points, dtype=np.float64)
    center_array = np.asarray(centers, dtype=np.float64)
    distances = (
        (point_array[:, None, :] - center_array[None, :, :]) ** 2
    ).sum(axis=2)
    identities = (
        [str(index) for index in range(len(center_array))]
        if center_ids is None
        else [str(value) for value in center_ids]
    )
    order = np.argsort(np.asarray(identities, dtype=str), kind="stable")
    return order[np.argmin(distances[:, order], axis=1)]


def maximin_centers(
    points: np.ndarray, ids: Sequence[str], k: int
) -> list[int]:
    """Select deterministic maximin centres with explicit lexical ties."""
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or len(values) < k or k < 1:
        raise SpatialPartitionError("insufficient_points")
    identities = [str(value) for value in ids]
    centroid = values.mean(axis=0, dtype=np.float64)
    centroid_distance = ((values - centroid) ** 2).sum(axis=1)
    minimum = centroid_distance.min()
    first = min(
        np.flatnonzero(centroid_distance == minimum),
        key=lambda index: identities[int(index)],
    )
    selected = [int(first)]
    nearest = ((values - values[first]) ** 2).sum(axis=1)
    nearest[first] = 0.0
    while len(selected) < k:
        maximum = nearest.max()
        next_index = min(
            np.flatnonzero(nearest == maximum),
            key=lambda index: identities[int(index)],
        )
        selected.append(int(next_index))
        nearest = np.minimum(
            nearest, ((values - values[next_index]) ** 2).sum(axis=1)
        )
        nearest[np.asarray(selected, dtype=np.int64)] = 0.0
    return selected


def geometry(
    map_rows: Sequence[Mapping[str, Any]],
    *,
    n_micro: int = N_MICRO,
    n_macro: int = N_MACRO,
) -> dict[str, Any]:
    """Build map-only microgeometry, then macrogeometry over microcentres."""
    rows = sorted(map_rows, key=lambda row: str(row["grid_cell_id"]))
    ids = [str(row["grid_cell_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise SpatialPartitionError("duplicate_map_grid_cell_id")
    x, y = project_lonlat(
        [float(row["centroid_lon"]) for row in rows],
        [float(row["centroid_lat"]) for row in rows],
    )
    points = np.column_stack([x, y]).astype(np.float64, copy=False)

    raw_micro = maximin_centers(points, ids, n_micro)
    micro_order = sorted(
        range(n_micro),
        key=lambda raw_index: (
            points[raw_micro[raw_index], 1],
            points[raw_micro[raw_index], 0],
            ids[raw_micro[raw_index]],
        ),
    )
    canonical_micro_indices = [raw_micro[index] for index in micro_order]
    micro_centers = points[canonical_micro_indices]
    micro_center_grid_ids = [ids[index] for index in canonical_micro_indices]
    micro_assignments = nearest_center(
        points,
        micro_centers,
        [f"{index:02d}" for index in range(n_micro)],
    ).astype(np.int64)

    raw_macro = maximin_centers(
        micro_centers,
        [f"{index:02d}" for index in range(n_micro)],
        n_macro,
    )
    macro_order = sorted(
        range(n_macro),
        key=lambda raw_index: (
            micro_centers[raw_macro[raw_index], 1],
            micro_centers[raw_macro[raw_index], 0],
            micro_center_grid_ids[raw_macro[raw_index]],
        ),
    )
    macro_center_microclusters = [raw_macro[index] for index in macro_order]
    macro_centers = micro_centers[macro_center_microclusters]
    micro_macro = nearest_center(
        micro_centers,
        macro_centers,
        [f"{index:02d}" for index in range(n_macro)],
    ).astype(np.int64)

    return {
        "rows": rows,
        "ids": ids,
        "points": points,
        "micro_centers": micro_centers,
        "micro_center_grid_ids": micro_center_grid_ids,
        "micro_assignments": micro_assignments,
        "macro_centers": macro_centers,
        "macro_center_microclusters": macro_center_microclusters,
        "micro_macro": micro_macro,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyproj": PYPROJ_VERSION,
            "proj": proj_version_str,
            "input_crs": "EPSG:4326",
            "projected_crs": "EPSG:7855",
            "always_xy": True,
            "dtype": "float64",
        },
    }


def priority(seed: int, cluster: int) -> str:
    return hashlib.sha256(
        f"{int(seed)}:{int(cluster)}".encode("utf-8")
    ).hexdigest()


def priority_order(seed: int, clusters: Sequence[int]) -> list[int]:
    return sorted(
        (int(cluster) for cluster in clusters),
        key=lambda cluster: (
            hashlib.sha256(
                f"{int(seed)}:{cluster}".encode("utf-8")
            ).digest(),
            cluster,
        ),
    )


def canonical_fold_tuples(
    folds: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        sorted(tuple(sorted(int(cluster) for cluster in fold)) for fold in folds)
    )


def folds_for_seed(
    seed: int, remaining: Sequence[int], *, n_folds: int = N_FOLDS
) -> tuple[tuple[int, ...], ...]:
    order = priority_order(seed, remaining)
    if len(order) % n_folds:
        raise SpatialPartitionError("fold_shape_drift")
    width = len(order) // n_folds
    return canonical_fold_tuples(
        [order[start : start + width] for start in range(0, len(order), width)]
    )


def _priority_orders(
    seed_stop: int = SEED_STOP, n_clusters: int = N_MICRO
) -> np.ndarray:
    return np.asarray(
        [
            priority_order(seed, range(n_clusters))
            for seed in range(seed_stop)
        ],
        dtype=np.int16,
    )


def _fold_priority_ranks(seed_stop: int = SEED_STOP) -> np.ndarray:
    ranks = np.empty((seed_stop, N_FOLDS), dtype=np.int8)
    for seed in range(seed_stop):
        order = sorted(
            range(N_FOLDS),
            key=lambda fold: (
                hashlib.sha256(
                    f"{seed}:fold:{fold}".encode("utf-8")
                ).digest(),
                fold,
            ),
        )
        for rank, fold in enumerate(order):
            ranks[seed, fold] = rank
    return ranks


def literal_all_macroregions_per_fold_possible(
    remaining_macro_counts: Sequence[int],
    *,
    n_folds: int = N_FOLDS,
) -> bool:
    """Return whether every fold can contain every represented macroregion."""
    return all(int(count) >= n_folds for count in remaining_macro_counts)


def _stratified_chunks(
    outer: Sequence[int],
    macro: Sequence[int],
    orders: np.ndarray,
    fold_priority_ranks: np.ndarray,
) -> np.ndarray:
    """Generate deterministic balanced 5x9 folds for every CV seed."""
    chosen = np.asarray(tuple(int(value) for value in outer), dtype=np.int64)
    macro_array = np.asarray(macro, dtype=np.int64)
    n_seeds, n_clusters = orders.shape
    keep = ~np.isin(orders, chosen)
    remaining_orders = orders[keep].reshape(n_seeds, n_clusters - len(chosen))
    remaining_counts = [
        int(np.sum(macro_array[np.setdiff1d(np.arange(n_clusters), chosen)] == value))
        for value in range(N_MACRO)
    ]
    macro_order = sorted(
        range(N_MACRO),
        key=lambda value: (remaining_counts[value], value),
    )

    chunks = np.full(
        (n_seeds, N_FOLDS, CLUSTERS_PER_FOLD), -1, dtype=np.int16
    )
    totals = np.zeros((n_seeds, N_FOLDS), dtype=np.int8)
    same_macro = np.zeros((n_seeds, N_FOLDS, N_MACRO), dtype=np.int8)
    seed_index = np.arange(n_seeds)
    for macroregion in macro_order:
        count = remaining_counts[macroregion]
        within_macro = remaining_orders[
            macro_array[remaining_orders] == macroregion
        ].reshape(n_seeds, count)
        for position in range(count):
            cluster = within_macro[:, position]
            eligible = totals < CLUSTERS_PER_FOLD
            same_score = np.where(
                eligible, same_macro[:, :, macroregion], 127
            )
            minimum_same = same_score.min(axis=1)
            candidates = eligible & (same_score == minimum_same[:, None])
            total_score = np.where(candidates, totals, 127)
            minimum_total = total_score.min(axis=1)
            candidates &= total_score == minimum_total[:, None]
            rank_score = np.where(candidates, fold_priority_ranks, 127)
            selected_fold = np.argmin(rank_score, axis=1)
            selected_position = totals[seed_index, selected_fold]
            chunks[
                seed_index,
                selected_fold,
                selected_position,
            ] = cluster
            totals[seed_index, selected_fold] += 1
            same_macro[seed_index, selected_fold, macroregion] += 1

    if not np.all(totals == CLUSTERS_PER_FOLD) or np.any(chunks < 0):
        raise SpatialPartitionError("stratified_fold_shape_drift")
    for macroregion in range(N_MACRO):
        counts = same_macro[:, :, macroregion]
        if np.any(counts.max(axis=1) - counts.min(axis=1) > 1):
            raise SpatialPartitionError("stratified_macro_balance_drift")
    return chunks


def stratified_folds_for_seed(
    seed: int,
    outer: Sequence[int],
    macro: Sequence[int],
) -> tuple[tuple[int, ...], ...]:
    orders = np.asarray(
        [priority_order(seed, range(len(macro)))], dtype=np.int16
    )
    ranks = _fold_priority_ranks(seed + 1)[seed : seed + 1]
    return canonical_fold_tuples(
        _stratified_chunks(outer, macro, orders, ranks)[0].tolist()
    )


def build_cluster_arrays(
    geometry_result: Mapping[str, Any],
    response_cells: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    *,
    species: Sequence[str] = SPECIES,
) -> dict[str, Any]:
    ids = list(geometry_result["ids"])
    assignments = np.asarray(
        geometry_result["micro_assignments"], dtype=np.int64
    )
    n_micro = len(geometry_result["micro_centers"])
    id_index = {grid_id: index for index, grid_id in enumerate(ids)}
    if len(id_index) != len(ids):
        raise SpatialPartitionError("duplicate_geometry_id")

    cell_ids = [str(row["grid_cell_id"]) for row in response_cells]
    if len(cell_ids) != len(set(cell_ids)):
        raise SpatialPartitionError("duplicate_response_cell")
    response_cell_count = np.zeros(n_micro, dtype=np.int64)
    for grid_id in cell_ids:
        if grid_id not in id_index:
            raise SpatialPartitionError("response_cell_outside_map")
        response_cell_count[assignments[id_index[grid_id]]] += 1

    species_order = tuple(species)
    species_index = {name: index for index, name in enumerate(species_order)}
    class_count = np.zeros((n_micro, len(species_order) * 2), dtype=np.int64)
    seen_response_keys: set[tuple[str, str]] = set()
    for row in responses:
        name = str(row["species_id"])
        pa = str(row["pa"])
        grid_id = str(row["grid_cell_id"])
        if name not in species_index or pa not in {"0", "1"}:
            raise SpatialPartitionError("response_species_binary_drift")
        key = (name, grid_id)
        if key in seen_response_keys:
            raise SpatialPartitionError("duplicate_species_cell_response")
        seen_response_keys.add(key)
        if grid_id not in id_index:
            raise SpatialPartitionError("response_row_outside_map")
        class_index = species_index[name] * 2 + int(pa)
        class_count[assignments[id_index[grid_id]], class_index] += 1

    return {
        "map_count": np.bincount(assignments, minlength=n_micro).astype(np.int64),
        "response_cell_count": response_cell_count,
        "class_count": class_count,
        "class_total": class_count.sum(axis=0),
        "map_total": len(ids),
        "response_cell_total": len(response_cells),
        "response_row_total": len(responses),
        "class_labels": tuple(
            f"{name}|{pa}" for name in species_order for pa in ("0", "1")
        ),
    }


def evaluate_outer(
    outer: Sequence[int],
    macro: Sequence[int],
    aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    chosen = np.asarray(tuple(int(value) for value in outer), dtype=np.int64)
    macro_array = np.asarray(macro, dtype=np.int64)
    map_count = np.asarray(aggregate["map_count"], dtype=np.int64)
    response_count = np.asarray(
        aggregate["response_cell_count"], dtype=np.int64
    )
    class_count = np.asarray(aggregate["class_count"], dtype=np.int64)
    class_total = np.asarray(aggregate["class_total"], dtype=np.int64)

    selected_map = int(map_count[chosen].sum())
    selected_response = int(response_count[chosen].sum())
    selected_class = class_count[chosen].sum(axis=0)
    complement_class = class_total - selected_class
    map_share = selected_map / int(aggregate["map_total"])
    response_share = selected_response / int(
        aggregate["response_cell_total"]
    )
    gates = {
        "distinct_cluster_gate": len(set(chosen.tolist())) == 5,
        "macroregion_gate": len(set(macro_array[chosen].tolist())) == 5,
        "map_share_gate": 0.075 <= map_share <= 0.125,
        "response_share_gate": 0.075 <= response_share <= 0.125,
        "cluster_response_gate": bool(np.all(response_count[chosen] >= 20)),
        "test_class_gate": bool(np.all(selected_class >= 10)),
        "complement_class_gate": bool(np.all(complement_class >= 50)),
    }
    return {
        "map_cells": selected_map,
        "map_share": map_share,
        "response_cells": selected_response,
        "response_cell_share": response_share,
        "minimum_cluster_response_cells": int(response_count[chosen].min()),
        "minimum_test_species_binary_rows": int(selected_class.min()),
        "minimum_complement_species_binary_rows": int(
            complement_class.min()
        ),
        **gates,
        "outer_viable": all(gates.values()),
    }


def _enumerate_outer_candidates(
    macro: np.ndarray,
    aggregate: Mapping[str, Any],
    orders: np.ndarray,
) -> list[dict[str, Any]]:
    macro_values = sorted(set(int(value) for value in macro))
    if macro_values != list(range(N_MACRO)):
        raise SpatialPartitionError("macroregion_identity_drift")
    first_seed: dict[tuple[int, ...], int] = {}
    seed_count: Counter[tuple[int, ...]] = Counter()
    for seed, order in enumerate(orders):
        chosen = []
        for macroregion in macro_values:
            chosen.append(
                next(
                    int(cluster)
                    for cluster in order
                    if int(macro[int(cluster)]) == macroregion
                )
            )
        outer = tuple(sorted(chosen))
        seed_count[outer] += 1
        first_seed.setdefault(outer, seed)

    records = []
    for outer in sorted(first_seed):
        records.append(
            {
                "outer_tuple": outer,
                "first_seed": first_seed[outer],
                "seed_count": seed_count[outer],
                **evaluate_outer(outer, macro, aggregate),
            }
        )
    return records


def _canonical_folds_from_chunks(
    chunks: np.ndarray,
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    raw = [tuple(sorted(int(value) for value in fold)) for fold in chunks]
    order = tuple(sorted(range(len(raw)), key=lambda index: raw[index]))
    return tuple(raw[index] for index in order), order


def scan_cv_assignments(
    outer: Sequence[int],
    macro: Sequence[int],
    aggregate: Mapping[str, Any],
    orders: np.ndarray,
    *,
    fold_priority_ranks: np.ndarray | None = None,
    capture_attempts: bool = False,
) -> dict[str, Any]:
    """Scan all CV seeds using only fixed cluster-level NumPy arrays."""
    chosen = np.asarray(tuple(int(value) for value in outer), dtype=np.int64)
    if fold_priority_ranks is None:
        fold_priority_ranks = _fold_priority_ranks(len(orders))
    chunks = _stratified_chunks(
        chosen,
        macro,
        orders,
        fold_priority_ranks,
    )

    macro_array = np.asarray(macro, dtype=np.int64)
    fold_macro = macro_array[chunks]
    macro_counts = np.zeros((len(orders), N_FOLDS), dtype=np.int8)
    macro_cluster_counts = np.zeros(
        (len(orders), N_FOLDS, N_MACRO), dtype=np.int8
    )
    for macroregion in range(N_MACRO):
        macro_cluster_counts[:, :, macroregion] = np.sum(
            fold_macro == macroregion, axis=2
        )
        macro_counts += (
            macro_cluster_counts[:, :, macroregion] > 0
        ).astype(np.int8)
    macro_imbalance = (
        macro_cluster_counts.max(axis=1)
        - macro_cluster_counts.min(axis=1)
    ).max(axis=1)
    stratified_gate = (
        (macro_counts == 4).all(axis=1) & (macro_imbalance <= 1)
    )

    response_count = np.asarray(
        aggregate["response_cell_count"], dtype=np.int64
    )
    fold_response = response_count[chunks].sum(axis=2)
    remaining_response = int(response_count.sum() - response_count[chosen].sum())
    fold_response_share = fold_response / remaining_response
    response_gate = (
        (fold_response_share >= 0.15) & (fold_response_share <= 0.25)
    ).all(axis=1)

    class_count = np.asarray(aggregate["class_count"], dtype=np.int64)
    fold_class = class_count[chunks].sum(axis=2)
    remaining_class = class_count.sum(axis=0) - class_count[chosen].sum(axis=0)
    validation_gate = (fold_class >= 10).all(axis=(1, 2))
    training_class = remaining_class[None, None, :] - fold_class
    training_gate = (training_class >= 50).all(axis=(1, 2))
    viable_mask = (
        stratified_gate & response_gate & validation_gate & training_gate
    )
    viable_seeds = np.flatnonzero(viable_mask)

    viable = []
    for seed_index in viable_seeds:
        seed = int(seed_index)
        folds, canonical_order = _canonical_folds_from_chunks(chunks[seed])
        viable.append(
            {
                "cv_seed": seed,
                "folds": folds,
                "fold_macroregion_counts": tuple(
                    int(macro_counts[seed, index])
                    for index in canonical_order
                ),
                "fold_macroregion_cluster_counts": tuple(
                    tuple(
                        int(value)
                        for value in macro_cluster_counts[seed, index]
                    )
                    for index in canonical_order
                ),
                "minimum_validation_species_binary_rows": int(
                    fold_class[seed].min()
                ),
                "minimum_training_species_binary_rows": int(
                    training_class[seed].min()
                ),
            }
        )

    attempts: list[dict[str, Any]] = []
    if capture_attempts:
        for seed in range(len(orders)):
            folds, canonical_order = _canonical_folds_from_chunks(chunks[seed])
            row = {
                "cv_seed": seed,
                **{
                    f"fold{index:02d}": fold
                    for index, fold in enumerate(folds)
                },
                "fold_response_cells": tuple(
                    int(fold_response[seed, index])
                    for index in canonical_order
                ),
                "fold_response_shares": tuple(
                    float(fold_response_share[seed, index])
                    for index in canonical_order
                ),
                "fold_macroregion_counts": tuple(
                    int(macro_counts[seed, index])
                    for index in canonical_order
                ),
                "fold_macroregion_cluster_counts": tuple(
                    ",".join(
                        str(int(value))
                        for value in macro_cluster_counts[seed, index]
                    )
                    for index in canonical_order
                ),
                "minimum_fold_macroregions": int(macro_counts[seed].min()),
                "total_fold_macroregion_incidence": int(
                    macro_counts[seed].sum()
                ),
                "maximum_macro_fold_count_imbalance": int(
                    macro_imbalance[seed]
                ),
                "minimum_validation_species_binary_rows": int(
                    fold_class[seed].min()
                ),
                "minimum_training_species_binary_rows": int(
                    training_class[seed].min()
                ),
                "stratified_geometry_gate": bool(stratified_gate[seed]),
                "response_share_gate": bool(response_gate[seed]),
                "validation_class_gate": bool(validation_gate[seed]),
                "training_class_gate": bool(training_gate[seed]),
                "viable": bool(viable_mask[seed]),
            }
            attempts.append(row)

    return {
        "summary": {
            "cv_scanned": True,
            "cv_attempts": len(orders),
            "stratified_invariant_pass_seeds": int(stratified_gate.sum()),
            "four_macroregions_all_folds_seeds": int(
                (macro_counts == 4).all(axis=1).sum()
            ),
            "response_share_all_folds_pass_seeds": int(response_gate.sum()),
            "validation_class_all_folds_pass_seeds": int(validation_gate.sum()),
            "training_class_all_folds_pass_seeds": int(training_gate.sum()),
            "viable_cv_seed_count": int(viable_mask.sum()),
            "viable_cv_seeds": tuple(int(seed) for seed in viable_seeds),
        },
        "viable": viable,
        "attempts": attempts,
    }


def search_candidates(
    geometry_result: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    *,
    seed_stop: int = SEED_STOP,
    enforce_oracle: bool = True,
) -> dict[str, Any]:
    macro = np.asarray(geometry_result["micro_macro"], dtype=np.int64)
    orders = _priority_orders(seed_stop, len(macro))
    fold_priority_ranks = _fold_priority_ranks(seed_stop)
    outer_records = _enumerate_outer_candidates(macro, aggregate, orders)
    summaries: list[dict[str, Any]] = []
    viable_cv: dict[tuple[int, ...], list[dict[str, Any]]] = {}

    for record in outer_records:
        outer = tuple(record["outer_tuple"])
        if record["outer_viable"]:
            scan = scan_cv_assignments(
                outer,
                macro,
                aggregate,
                orders,
                fold_priority_ranks=fold_priority_ranks,
            )
            summary = scan["summary"]
            viable_cv[outer] = scan["viable"]
        else:
            summary = {
                "cv_scanned": False,
                "cv_attempts": 0,
                "stratified_invariant_pass_seeds": 0,
                "four_macroregions_all_folds_seeds": 0,
                "response_share_all_folds_pass_seeds": 0,
                "validation_class_all_folds_pass_seeds": 0,
                "training_class_all_folds_pass_seeds": 0,
                "viable_cv_seed_count": 0,
                "viable_cv_seeds": (),
            }
        record["cv_viable_seed_count"] = summary["viable_cv_seed_count"]
        record["joint_feasible"] = bool(summary["viable_cv_seed_count"])
        summaries.append(
            {
                "outer_tuple": outer,
                "outer_viable": record["outer_viable"],
                **summary,
                "joint_feasible": bool(summary["viable_cv_seed_count"]),
                "selected_outer": False,
            }
        )

    joint = [
        tuple(record["outer_tuple"])
        for record in outer_records
        if record["joint_feasible"]
    ]
    result = {
        "outer_records": outer_records,
        "outer_cv_summaries": summaries,
        "unique_outer_count": len(outer_records),
        "outer_viable_count": sum(
            bool(record["outer_viable"]) for record in outer_records
        ),
        "joint_feasible_count": len(joint),
        "joint_feasible": joint,
        "viable_cv": viable_cv,
        "_priority_orders": orders,
        "_fold_priority_ranks": fold_priority_ranks,
    }
    if (
        enforce_oracle
        and seed_stop == SEED_STOP
        and len(macro) == N_MICRO
        and int(aggregate["map_total"]) == MAP_ROWS
    ):
        observed = {
            "unique_outer_candidates": result["unique_outer_count"],
            "outer_hard_gate_viable": result["outer_viable_count"],
            "joint_feasible_outer": result["joint_feasible_count"],
            "viable_cv_assignments": sum(
                len(candidates) for candidates in viable_cv.values()
            ),
        }
        if observed != {
            key: CORRECTED_ORACLE[key]
            for key in (
                "unique_outer_candidates",
                "outer_hard_gate_viable",
                "joint_feasible_outer",
                "viable_cv_assignments",
            )
        }:
            raise SpatialPartitionError(f"exact_outer_oracle_mismatch:{observed}")
        if set(joint) != JOINT_OUTER_ORACLE:
            raise SpatialPartitionError("joint_outer_oracle_mismatch")
        if {
            outer: tuple(
                candidate["cv_seed"] for candidate in viable_cv[outer]
            )
            for outer in JOINT_OUTER_ORACLE
        } != JOINT_CV_ORACLE:
            raise SpatialPartitionError("cv_seed_oracle_mismatch")
    if not joint:
        raise SpatialPartitionError("no_joint_candidate_passes")
    return result


def ks_distance(first: Sequence[float], second: Sequence[float]) -> float:
    left = np.sort(np.asarray(first, dtype=np.float64))
    right = np.sort(np.asarray(second, dtype=np.float64))
    if not len(left) or not len(right):
        raise SpatialPartitionError("empty_ks_sample")
    support = np.sort(np.concatenate([left, right]))
    left_cdf = np.searchsorted(left, support, side="right") / len(left)
    right_cdf = np.searchsorted(right, support, side="right") / len(right)
    return float(np.max(np.abs(left_cdf - right_cdf)))


def tv_distance(first: Sequence[str], second: Sequence[str]) -> float:
    if not first or not second:
        raise SpatialPartitionError("empty_tv_sample")
    left = Counter(str(value) for value in first)
    right = Counter(str(value) for value in second)
    levels = sorted(set(left) | set(right))
    return 0.5 * sum(
        abs(left[level] / len(first) - right[level] / len(second))
        for level in levels
    )


def midrank_scores(
    values: Sequence[float], *, higher_is_better: bool
) -> list[float]:
    numbers = [float(value) for value in values]
    if not numbers:
        return []
    if len(numbers) == 1:
        return [1.0]
    order = sorted(
        range(len(numbers)),
        key=lambda index: (
            -numbers[index] if higher_is_better else numbers[index],
            index,
        ),
    )
    ranks = [0.0] * len(numbers)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and numbers[order[stop]] == numbers[order[start]]:
            stop += 1
        midrank = ((start + 1) + stop) / 2
        for position in range(start, stop):
            ranks[order[position]] = midrank
        start = stop
    return [(len(numbers) - rank) / (len(numbers) - 1) for rank in ranks]


def rank_outer_candidates(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranked = [dict(record) for record in records]
    geography_min = midrank_scores(
        [record["geography_min_m"] for record in ranked],
        higher_is_better=True,
    )
    geography_mean = midrank_scores(
        [record["geography_mean_m"] for record in ranked],
        higher_is_better=True,
    )
    environment = midrank_scores(
        [record["environment_loss"] for record in ranked],
        higher_is_better=False,
    )
    representation_mean = midrank_scores(
        [record["representation_mean_loss"] for record in ranked],
        higher_is_better=False,
    )
    representation_worst = midrank_scores(
        [record["representation_worst_loss"] for record in ranked],
        higher_is_better=False,
    )
    for index, record in enumerate(ranked):
        record["geography_midrank_score"] = (
            geography_min[index] + geography_mean[index]
        ) / 2
        record["environment_midrank_score"] = environment[index]
        record["representation_midrank_score"] = (
            representation_mean[index] + representation_worst[index]
        ) / 2
        record["equal_third_score"] = (
            record["geography_midrank_score"]
            + record["environment_midrank_score"]
            + record["representation_midrank_score"]
        ) / 3
    ranked.sort(
        key=lambda record: (
            -record["equal_third_score"],
            -record["geography_midrank_score"],
            -record["environment_midrank_score"],
            record["representation_mean_loss"],
            record["representation_worst_loss"],
            tuple(record["outer_tuple"]),
            int(record["seed"]),
        )
    )
    for index, record in enumerate(ranked, start=1):
        record["rank"] = index
    return ranked


def _environment_loss(
    rows: Sequence[Mapping[str, Any]],
    sample_ids: set[str],
    reference_ids: set[str],
) -> dict[str, Any]:
    sample = [row for row in rows if str(row["grid_cell_id"]) in sample_ids]
    reference = [
        row for row in rows if str(row["grid_cell_id"]) in reference_ids
    ]
    if not sample or not reference:
        raise SpatialPartitionError("empty_environment_substrate")
    family_loss: dict[str, float] = {}
    predictor_loss: dict[str, float] = {}
    for family, predictors in FAMILIES.items():
        losses = []
        for predictor in predictors:
            if predictor in CATEGORICAL:
                loss = tv_distance(
                    [str(row[predictor]) for row in sample],
                    [str(row[predictor]) for row in reference],
                )
            else:
                loss = ks_distance(
                    [float(row[predictor]) for row in sample],
                    [float(row[predictor]) for row in reference],
                )
            predictor_loss[predictor] = loss
            losses.append(loss)
        family_loss[family] = float(np.mean(losses))
    return {
        "loss": float(np.mean(list(family_loss.values()))),
        "families": family_loss,
        "predictors": predictor_loss,
    }


def _outer_raw_metrics(
    outer: tuple[int, ...],
    geometry_result: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    maps: Sequence[Mapping[str, Any]],
    response_cells: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    centres = np.asarray(geometry_result["micro_centers"], dtype=np.float64)[
        np.asarray(outer, dtype=np.int64)
    ]
    pair_distances = [
        float(np.linalg.norm(centres[left] - centres[right]))
        for left in range(len(centres))
        for right in range(left + 1, len(centres))
    ]
    assignments = np.asarray(geometry_result["micro_assignments"], dtype=np.int64)
    selected_mask = np.isin(assignments, np.asarray(outer, dtype=np.int64))
    ids = np.asarray(geometry_result["ids"], dtype=object)
    selected_ids = set(ids[selected_mask].tolist())
    all_map_ids = set(ids.tolist())
    all_response_ids = {str(row["grid_cell_id"]) for row in response_cells}
    map_environment = _environment_loss(maps, selected_ids, all_map_ids)
    response_environment = _environment_loss(
        response_cells, selected_ids & all_response_ids, all_response_ids
    )

    selected_class = np.asarray(aggregate["class_count"], dtype=np.int64)[
        np.asarray(outer, dtype=np.int64)
    ].sum(axis=0)
    class_total = np.asarray(aggregate["class_total"], dtype=np.int64)
    response_share = int(
        np.asarray(aggregate["response_cell_count"], dtype=np.int64)[
            np.asarray(outer, dtype=np.int64)
        ].sum()
    ) / int(aggregate["response_cell_total"])
    deviations = np.abs(selected_class / class_total - response_share)
    metrics: dict[str, Any] = {
        "geography_min_m": min(pair_distances),
        "geography_mean_m": float(np.mean(pair_distances)),
        "environment_map_loss": map_environment["loss"],
        "environment_response_loss": response_environment["loss"],
        "environment_loss": (
            map_environment["loss"] + response_environment["loss"]
        )
        / 2,
        "representation_mean_loss": float(np.mean(deviations)),
        "representation_worst_loss": float(np.max(deviations)),
    }
    for substrate, environment in (
        ("map", map_environment),
        ("response", response_environment),
    ):
        for family, loss in environment["families"].items():
            metrics[f"environment_{substrate}_{family}_loss"] = loss
    return metrics


def _cv_raw_metrics(
    outer: tuple[int, ...],
    folds: tuple[tuple[int, ...], ...],
    geometry_result: Mapping[str, Any],
    aggregate: Mapping[str, Any],
    maps: Sequence[Mapping[str, Any]],
    response_cells: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    centres = np.asarray(geometry_result["micro_centers"], dtype=np.float64)
    assignments = np.asarray(geometry_result["micro_assignments"], dtype=np.int64)
    ids = np.asarray(geometry_result["ids"], dtype=object)
    outer_train_clusters = set(range(N_MICRO)) - set(outer)
    outer_train_ids = set(
        ids[np.isin(assignments, list(outer_train_clusters))].tolist()
    )
    response_ids = {str(row["grid_cell_id"]) for row in response_cells}
    outer_train_response_ids = outer_train_ids & response_ids

    fold_mean_distance = []
    fold_min_distance = []
    environment_losses = []
    balance_mean_losses = []
    balance_worst_losses = []
    map_count = np.asarray(aggregate["map_count"], dtype=np.int64)
    response_count = np.asarray(
        aggregate["response_cell_count"], dtype=np.int64
    )
    class_count = np.asarray(aggregate["class_count"], dtype=np.int64)
    train_clusters_array = np.asarray(sorted(outer_train_clusters), dtype=np.int64)
    outer_map_total = int(map_count[train_clusters_array].sum())
    outer_response_total = int(response_count[train_clusters_array].sum())
    outer_class_total = class_count[train_clusters_array].sum(axis=0)

    for fold in folds:
        fold_array = np.asarray(fold, dtype=np.int64)
        fold_centres = centres[fold_array]
        distances = [
            float(np.linalg.norm(fold_centres[left] - fold_centres[right]))
            for left in range(len(fold_centres))
            for right in range(left + 1, len(fold_centres))
        ]
        fold_mean_distance.append(float(np.mean(distances)))
        fold_min_distance.append(min(distances))

        fold_ids = set(ids[np.isin(assignments, fold_array)].tolist())
        map_environment = _environment_loss(
            maps, fold_ids, outer_train_ids
        )
        response_environment = _environment_loss(
            response_cells,
            fold_ids & response_ids,
            outer_train_response_ids,
        )
        environment_losses.append(
            (map_environment["loss"] + response_environment["loss"]) / 2
        )

        map_deviation = abs(int(map_count[fold_array].sum()) / outer_map_total - 0.2)
        response_deviation = abs(
            int(response_count[fold_array].sum()) / outer_response_total - 0.2
        )
        class_deviations = np.abs(
            class_count[fold_array].sum(axis=0) / outer_class_total - 0.2
        )
        balance_mean_losses.append(
            float(
                np.mean(
                    [
                        map_deviation,
                        response_deviation,
                        float(np.mean(class_deviations)),
                    ]
                )
            )
        )
        balance_worst_losses.append(
            max(
                map_deviation,
                response_deviation,
                float(np.max(class_deviations)),
            )
        )
    return {
        "geography_mean_fold_mean_m": float(np.mean(fold_mean_distance)),
        "geography_worst_fold_min_m": min(fold_min_distance),
        "environment_mean_fold_loss": float(np.mean(environment_losses)),
        "environment_worst_fold_loss": max(environment_losses),
        "balance_mean_loss": float(np.mean(balance_mean_losses)),
        "balance_worst_fold_loss": max(balance_worst_losses),
    }


def rank_cv_candidates(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranked = [dict(record) for record in records]
    mean_geo = midrank_scores(
        [record["geography_mean_fold_mean_m"] for record in ranked],
        higher_is_better=True,
    )
    worst_geo = midrank_scores(
        [record["geography_worst_fold_min_m"] for record in ranked],
        higher_is_better=True,
    )
    mean_environment = midrank_scores(
        [record["environment_mean_fold_loss"] for record in ranked],
        higher_is_better=False,
    )
    worst_environment = midrank_scores(
        [record["environment_worst_fold_loss"] for record in ranked],
        higher_is_better=False,
    )
    mean_balance = midrank_scores(
        [record["balance_mean_loss"] for record in ranked],
        higher_is_better=False,
    )
    worst_balance = midrank_scores(
        [record["balance_worst_fold_loss"] for record in ranked],
        higher_is_better=False,
    )
    for index, record in enumerate(ranked):
        record["geography_midrank_score"] = (
            mean_geo[index] + worst_geo[index]
        ) / 2
        record["environment_midrank_score"] = (
            mean_environment[index] + worst_environment[index]
        ) / 2
        record["balance_midrank_score"] = (
            mean_balance[index] + worst_balance[index]
        ) / 2
        record["equal_third_score"] = (
            record["geography_midrank_score"]
            + record["environment_midrank_score"]
            + record["balance_midrank_score"]
        ) / 3
    ranked.sort(
        key=lambda record: (
            -record["equal_third_score"],
            -record["geography_midrank_score"],
            -record["environment_midrank_score"],
            record["balance_mean_loss"],
            record["balance_worst_fold_loss"],
            tuple(tuple(fold) for fold in record["folds"]),
            int(record["cv_seed"]),
        )
    )
    for index, record in enumerate(ranked, start=1):
        record["rank"] = index
    return ranked


def build_assignments(
    geometry_result: Mapping[str, Any],
    response_cells: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    outer: Sequence[int],
    folds: Sequence[Sequence[int]],
) -> dict[str, list[dict[str, Any]]]:
    outer_set = {int(cluster) for cluster in outer}
    fold_lookup: dict[int, int] = {}
    for fold_index, fold in enumerate(folds):
        for cluster in fold:
            cluster_index = int(cluster)
            if cluster_index in fold_lookup or cluster_index in outer_set:
                raise SpatialPartitionError("fold_cluster_overlap")
            fold_lookup[cluster_index] = fold_index
    if outer_set | set(fold_lookup) != set(
        range(len(geometry_result["micro_macro"]))
    ):
        raise SpatialPartitionError("partition_cluster_coverage")
    if len(outer_set) != 5 or any(
        sum(value == fold for value in fold_lookup.values()) != 9
        for fold in range(5)
    ):
        raise SpatialPartitionError("partition_cluster_shape")

    by_id: dict[str, dict[str, str]] = {}
    map_assignments = []
    for index, row in enumerate(geometry_result["rows"]):
        cluster = int(geometry_result["micro_assignments"][index])
        assignment = {
            "microcluster": f"mc{cluster:02d}",
            "macroregion": f"mr{int(geometry_result['micro_macro'][cluster]):02d}",
            "outer_role": "test" if cluster in outer_set else "outer_train",
            "cv_fold": (
                "" if cluster in outer_set else f"fold{fold_lookup[cluster]:02d}"
            ),
        }
        grid_id = str(row["grid_cell_id"])
        by_id[grid_id] = assignment
        map_assignments.append({"grid_cell_id": grid_id, **assignment})

    response_cell_assignments = []
    for row in sorted(response_cells, key=lambda item: str(item["grid_cell_id"])):
        grid_id = str(row["grid_cell_id"])
        if grid_id not in by_id:
            raise SpatialPartitionError("response_assignment_outside_map")
        response_cell_assignments.append({"grid_cell_id": grid_id, **by_id[grid_id]})

    response_partitioned = []
    for row in responses:
        grid_id = str(row["grid_cell_id"])
        if grid_id not in by_id:
            raise SpatialPartitionError("response_assignment_outside_map")
        response_partitioned.append({**dict(row), **by_id[grid_id]})

    for row in response_partitioned:
        if row["outer_role"] == "test" and row["cv_fold"]:
            raise SpatialPartitionError("outer_test_in_cv")
    return {
        "map_assignments": map_assignments,
        "response_cell_assignments": response_cell_assignments,
        "response_partitioned": response_partitioned,
    }


def _composition(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def counted(field: str) -> dict[str, int]:
        return {
            str(key): int(value)
            for key, value in sorted(
                Counter(str(row.get(field, "")) for row in rows).items()
            )
        }

    return {
        "rows": len(rows),
        "binary_pa": counted("pa"),
        "pa_type": counted("pa_type"),
        "response_origin": counted("response_origin"),
        "source_combination": counted("source_combination"),
    }


def _nearest_distance_summary(
    training_points: np.ndarray, assessment_points: np.ndarray
) -> dict[str, Any]:
    if not len(assessment_points):
        return {
            "assessment_cells": 0,
            "training_cells": len(training_points),
            "minimum_m": None,
            "q25_m": None,
            "median_m": None,
            "mean_m": None,
            "q75_m": None,
            "maximum_m": None,
            "within_1km": 0,
            "within_5km": 0,
            "within_10km": 0,
        }
    if not len(training_points):
        raise SpatialPartitionError("empty_species_training_response")
    nearest_parts = []
    training_square = np.sum(training_points**2, axis=1)[None, :]
    for start in range(0, len(assessment_points), 256):
        batch = assessment_points[start : start + 256]
        distances_square = (
            np.sum(batch**2, axis=1)[:, None]
            + training_square
            - 2 * batch @ training_points.T
        )
        nearest_parts.append(
            np.sqrt(np.maximum(distances_square.min(axis=1), 0.0))
        )
    nearest = np.concatenate(nearest_parts)
    return {
        "assessment_cells": len(assessment_points),
        "training_cells": len(training_points),
        "minimum_m": round(float(np.min(nearest)), 6),
        "q25_m": round(float(np.quantile(nearest, 0.25)), 6),
        "median_m": round(float(np.median(nearest)), 6),
        "mean_m": round(float(np.mean(nearest)), 6),
        "q75_m": round(float(np.quantile(nearest, 0.75)), 6),
        "maximum_m": round(float(np.max(nearest)), 6),
        "within_1km": int(np.sum(nearest <= 1_000)),
        "within_5km": int(np.sum(nearest <= 5_000)),
        "within_10km": int(np.sum(nearest <= 10_000)),
    }


def support_for_split(
    split_name: str,
    training_cells: set[str],
    assessment_cells: set[str],
    maps: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    *,
    active: Sequence[str] = ACTIVE,
    categorical: Sequence[str] = CATEGORICAL,
    species: Sequence[str] = SPECIES,
) -> dict[str, Any]:
    """Fit support summaries from each species' training response rows only."""
    map_lookup = {str(row["grid_cell_id"]): row for row in maps}
    if len(map_lookup) != len(maps):
        raise SpatialPartitionError("duplicate_support_map_cell")
    categorical_set = set(categorical)
    continuous = tuple(name for name in active if name not in categorical_set)
    global_dictionaries = {
        predictor: sorted({str(row[predictor]) for row in maps})
        for predictor in categorical
    }
    out_of_dictionary = 0
    species_output: dict[str, Any] = {}

    has_coordinates = all(
        "centroid_lon" in row and "centroid_lat" in row for row in maps
    )
    projected: dict[str, np.ndarray] = {}
    if has_coordinates:
        ids = list(map_lookup)
        x, y = project_lonlat(
            [float(map_lookup[grid_id]["centroid_lon"]) for grid_id in ids],
            [float(map_lookup[grid_id]["centroid_lat"]) for grid_id in ids],
        )
        projected = {
            grid_id: np.array([x[index], y[index]], dtype=np.float64)
            for index, grid_id in enumerate(ids)
        }

    for species_id in species:
        training_rows = [
            row
            for row in responses
            if str(row["species_id"]) == species_id
            and str(row["grid_cell_id"]) in training_cells
        ]
        assessment_rows = [
            row
            for row in responses
            if str(row["species_id"]) == species_id
            and str(row["grid_cell_id"]) in assessment_cells
        ]
        if not training_rows:
            raise SpatialPartitionError(
                f"empty_species_training_response:{split_name}:{species_id}"
            )
        for row in [*training_rows, *assessment_rows]:
            if str(row["grid_cell_id"]) not in map_lookup:
                raise SpatialPartitionError("support_response_outside_map")

        categorical_output = {}
        for predictor in categorical:
            global_levels = set(global_dictionaries[predictor])
            training_levels = sorted(
                {
                    str(map_lookup[str(row["grid_cell_id"])][predictor])
                    for row in training_rows
                }
            )
            training_level_set = set(training_levels)
            assessment_values = [
                str(map_lookup[str(row["grid_cell_id"])][predictor])
                for row in assessment_rows
            ]
            map_values = [str(row[predictor]) for row in maps]
            out_of_dictionary += sum(
                value not in global_levels
                for value in [*assessment_values, *map_values]
            )
            categorical_output[predictor] = {
                "training_levels": training_levels,
                "training_level_count": len(training_levels),
                "global_level_count": len(global_levels),
                "assessment_rows": len(assessment_values),
                "assessment_unseen": sum(
                    value not in training_level_set
                    for value in assessment_values
                ),
                "map_cells": len(map_values),
                "map_unseen": sum(
                    value not in training_level_set for value in map_values
                ),
            }

        continuous_output = {}
        for predictor in continuous:
            training_values = [
                float(map_lookup[str(row["grid_cell_id"])][predictor])
                for row in training_rows
            ]
            minimum = min(training_values)
            maximum = max(training_values)
            assessment_values = [
                float(map_lookup[str(row["grid_cell_id"])][predictor])
                for row in assessment_rows
            ]
            map_values = [float(row[predictor]) for row in maps]
            continuous_output[predictor] = {
                "training_min": minimum,
                "training_max": maximum,
                "assessment_rows": len(assessment_values),
                "assessment_below": sum(
                    value < minimum for value in assessment_values
                ),
                "assessment_above": sum(
                    value > maximum for value in assessment_values
                ),
                "map_cells": len(map_values),
                "map_below": sum(value < minimum for value in map_values),
                "map_above": sum(value > maximum for value in map_values),
            }

        if has_coordinates:
            training_ids = sorted(
                {str(row["grid_cell_id"]) for row in training_rows}
            )
            assessment_ids = sorted(
                {str(row["grid_cell_id"]) for row in assessment_rows}
            )
            distance = _nearest_distance_summary(
                np.asarray([projected[grid_id] for grid_id in training_ids]),
                np.asarray(
                    [projected[grid_id] for grid_id in assessment_ids]
                ).reshape(-1, 2),
            )
        else:
            distance = {"status": "coordinates_not_supplied"}
        species_output[species_id] = {
            "training": _composition(training_rows),
            "assessment": _composition(assessment_rows),
            "categorical": categorical_output,
            "continuous": continuous_output,
            "assessment_to_training_response_cell_distance": distance,
        }

    if out_of_dictionary:
        raise SpatialPartitionError("out_of_global_categorical_dictionary")
    return {
        "split": split_name,
        "training_map_cells": len(training_cells),
        "assessment_map_cells": len(assessment_cells),
        "global_categorical_dictionaries": global_dictionaries,
        "out_of_dictionary_count": out_of_dictionary,
        "species": species_output,
    }


def build_support_diagnostics(
    geometry_result: Mapping[str, Any],
    maps: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    outer: Sequence[int],
    folds: Sequence[Sequence[int]],
) -> dict[str, Any]:
    assignments = np.asarray(geometry_result["micro_assignments"], dtype=np.int64)
    ids = np.asarray(geometry_result["ids"], dtype=object)
    outer_set = set(int(cluster) for cluster in outer)
    outer_test_ids = set(ids[np.isin(assignments, list(outer_set))].tolist())
    outer_train_ids = set(ids.tolist()) - outer_test_ids
    split_output = {
        "outer_test": support_for_split(
            "outer_test",
            outer_train_ids,
            outer_test_ids,
            maps,
            responses,
        )
    }
    for fold_index, fold in enumerate(folds):
        assessment_ids = set(
            ids[np.isin(assignments, list(fold))].tolist()
        )
        split_output[f"cv_fold{fold_index:02d}"] = support_for_split(
            f"cv_fold{fold_index:02d}",
            outer_train_ids - assessment_ids,
            assessment_ids,
            maps,
            responses,
        )
    dictionaries = split_output["outer_test"].pop(
        "global_categorical_dictionaries"
    )
    for name, payload in split_output.items():
        if name == "outer_test":
            continue
        if payload.pop("global_categorical_dictionaries") != dictionaries:
            raise SpatialPartitionError("global_dictionary_split_drift")
    return {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "method": {
            "categorical_dictionary": "all D_struct map cells",
            "training_support": (
                "per species from that species' training response rows only"
            ),
            "assessment_and_map_counts": "diagnostic only; no filtering",
            "distance_crs": "EPSG:7855",
            "distance_thresholds_m": [1_000, 5_000, 10_000],
            "post_freeze_no_reselection": True,
        },
        "global_categorical_dictionaries": dictionaries,
        "out_of_dictionary_count": 0,
        "splits": split_output,
    }


def assign_excluded_audit(
    geometry_result: Mapping[str, Any],
    excluded_cells: Sequence[Mapping[str, Any]],
    excluded_rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    coordinate_lookup = {
        str(row["grid_cell_id"]): (
            float(row["centroid_lon"]),
            float(row["centroid_lat"]),
        )
        for row in excluded_cells
    }

    def assigned(
        row: Mapping[str, Any],
    ) -> tuple[int, int, float, float]:
        grid_id = str(row["grid_cell_id"])
        try:
            lon = float(row.get("centroid_lon", ""))
            lat = float(row.get("centroid_lat", ""))
        except (TypeError, ValueError):
            if grid_id not in coordinate_lookup:
                raise SpatialPartitionError("excluded_coordinate_missing")
            lon, lat = coordinate_lookup[grid_id]
        x, y = project_lonlat([lon], [lat])
        cluster = int(
            nearest_center(
                np.column_stack([x, y]),
                np.asarray(geometry_result["micro_centers"]),
                [f"{index:02d}" for index in range(N_MICRO)],
            )[0]
        )
        return cluster, int(geometry_result["micro_macro"][cluster]), lon, lat

    cell_output = []
    for row in sorted(excluded_cells, key=lambda item: str(item["grid_cell_id"])):
        cluster, macro, lon, lat = assigned(row)
        cell_output.append(
            {
                "grid_cell_id": row["grid_cell_id"],
                "centroid_lon": row.get("centroid_lon", lon),
                "centroid_lat": row.get("centroid_lat", lat),
                "microcluster": f"mc{cluster:02d}",
                "macroregion": f"mr{macro:02d}",
                "audit_role": "excluded_from_D_struct_audit_only",
                "reason": "outside_D_struct",
            }
        )
    row_output = []
    for row in excluded_rows:
        cluster, macro, _, _ = assigned(row)
        row_output.append(
            {
                **dict(row),
                "microcluster": f"mc{cluster:02d}",
                "macroregion": f"mr{macro:02d}",
                "audit_role": "excluded_from_D_struct_audit_only",
                "reason": "outside_D_struct",
            }
        )
    return {
        "excluded_cell_audit": cell_output,
        "excluded_row_audit": row_output,
    }


def _svg_path(
    points: np.ndarray,
    indices: Sequence[int],
    panel: tuple[float, float, float, float],
    bounds: tuple[float, float, float, float],
) -> str:
    x0, y0, width, height = panel
    xmin, xmax, ymin, ymax = bounds
    usable_width = width - 20
    usable_height = height - 35
    commands = []
    for index in indices:
        x, y = points[int(index)]
        px = x0 + 10 + (float(x) - xmin) / (xmax - xmin) * usable_width
        py = y0 + 25 + (ymax - float(y)) / (ymax - ymin) * usable_height
        commands.append(f"M{px:.1f},{py:.1f}h0.7")
    return "".join(commands)


def svg_artifact(
    geometry_result: Mapping[str, Any],
    assignments: Mapping[str, Sequence[Mapping[str, Any]]],
    responses: Sequence[Mapping[str, Any]],
) -> str:
    """Render all D_struct cells in four map panels plus aggregate counts."""
    points = np.asarray(geometry_result["points"], dtype=np.float64)
    bounds = (
        float(points[:, 0].min()),
        float(points[:, 0].max()),
        float(points[:, 1].min()),
        float(points[:, 1].max()),
    )
    panels = {
        "macro": (20.0, 55.0, 500.0, 440.0),
        "outer": (550.0, 55.0, 500.0, 440.0),
        "cv": (1080.0, 55.0, 500.0, 440.0),
        "response": (20.0, 545.0, 760.0, 510.0),
    }
    macro_colors = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00"]
    fold_colors = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#AA3377"]
    body = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1100" '
        'viewBox="0 0 1600 1100" role="img">',
        "<title>Goal025 deterministic spatial partition review</title>",
        '<rect width="1600" height="1100" fill="#ffffff"/>',
        '<text x="20" y="30" font-family="sans-serif" font-size="20" '
        'font-weight="bold">Goal025 spatial partition: pending orchestrator review</text>',
    ]
    for panel in panels.values():
        body.append(
            f'<rect x="{panel[0]}" y="{panel[1]}" width="{panel[2]}" '
            f'height="{panel[3]}" fill="#f7f7f7" stroke="#666"/>'
        )
    labels = {
        "macro": "A. 50 microclusters within 5 macroregions",
        "outer": "B. Selected outer test versus outer training",
        "cv": "C. Five spatial CV folds (outer test in grey)",
        "response": "D. D_struct unique response-cell distribution",
    }
    for name, panel in panels.items():
        body.append(
            f'<text x="{panel[0] + 10}" y="{panel[1] + 19}" '
            f'font-family="sans-serif" font-size="14" font-weight="bold">'
            f"{labels[name]}</text>"
        )

    for macroregion, color in enumerate(macro_colors):
        indices = np.flatnonzero(
            np.asarray(geometry_result["micro_macro"])[
                np.asarray(geometry_result["micro_assignments"])
            ]
            == macroregion
        )
        body.append(
            f'<path d="{_svg_path(points, indices, panels["macro"], bounds)}" '
            f'stroke="{color}" stroke-width="1" fill="none"/>'
        )
    map_rows = assignments["map_assignments"]
    outer_indices = [
        index for index, row in enumerate(map_rows) if row["outer_role"] == "test"
    ]
    train_indices = [
        index
        for index, row in enumerate(map_rows)
        if row["outer_role"] == "outer_train"
    ]
    body.append(
        f'<path d="{_svg_path(points, train_indices, panels["outer"], bounds)}" '
        'stroke="#777777" stroke-width="0.8" fill="none"/>'
    )
    body.append(
        f'<path d="{_svg_path(points, outer_indices, panels["outer"], bounds)}" '
        'stroke="#D55E00" stroke-width="1.2" fill="none"/>'
    )
    body.append(
        f'<path d="{_svg_path(points, outer_indices, panels["cv"], bounds)}" '
        'stroke="#bdbdbd" stroke-width="0.8" fill="none"/>'
    )
    for fold, color in enumerate(fold_colors):
        indices = [
            index
            for index, row in enumerate(map_rows)
            if row["cv_fold"] == f"fold{fold:02d}"
        ]
        body.append(
            f'<path d="{_svg_path(points, indices, panels["cv"], bounds)}" '
            f'stroke="{color}" stroke-width="0.9" fill="none"/>'
        )

    id_index = {
        grid_id: index
        for index, grid_id in enumerate(geometry_result["ids"])
    }
    response_indices = [
        id_index[row["grid_cell_id"]]
        for row in assignments["response_cell_assignments"]
    ]
    response_outer = [
        id_index[row["grid_cell_id"]]
        for row in assignments["response_cell_assignments"]
        if row["outer_role"] == "test"
    ]
    body.append(
        f'<path d="{_svg_path(points, response_indices, panels["response"], bounds)}" '
        'stroke="#222222" stroke-width="1.2" fill="none"/>'
    )
    body.append(
        f'<path d="{_svg_path(points, response_outer, panels["response"], bounds)}" '
        'stroke="#D55E00" stroke-width="1.8" fill="none"/>'
    )

    count_panel = (820, 545, 760, 510)
    body.append(
        f'<rect x="{count_panel[0]}" y="{count_panel[1]}" '
        f'width="{count_panel[2]}" height="{count_panel[3]}" '
        'fill="#f7f7f7" stroke="#666"/>'
    )
    body.append(
        '<text x="830" y="564" font-family="sans-serif" font-size="14" '
        'font-weight="bold">E. Aggregate species by binary response class</text>'
    )
    counts = Counter((row["species_id"], str(row["pa"])) for row in responses)
    maximum = max(counts.values())
    for index, species_id in enumerate(SPECIES):
        y = 600 + index * 53
        absence = counts[(species_id, "0")]
        presence = counts[(species_id, "1")]
        absence_width = 500 * absence / maximum
        presence_width = 500 * presence / maximum
        body.append(
            f'<text x="835" y="{y + 13}" font-family="sans-serif" '
            f'font-size="11">{species_id}</text>'
        )
        body.append(
            f'<rect x="1055" y="{y}" width="{absence_width:.1f}" height="16" '
            'fill="#0072B2"/>'
        )
        body.append(
            f'<rect x="1055" y="{y + 19}" width="{presence_width:.1f}" '
            'height="16" fill="#E69F00"/>'
        )
        body.append(
            f'<text x="{1060 + absence_width:.1f}" y="{y + 13}" '
            f'font-family="sans-serif" font-size="10">{absence}</text>'
        )
        body.append(
            f'<text x="{1060 + presence_width:.1f}" y="{y + 32}" '
            f'font-family="sans-serif" font-size="10">{presence}</text>'
        )
    body.extend(
        [
            '<rect x="835" y="1030" width="12" height="12" fill="#0072B2"/>',
            '<text x="852" y="1041" font-family="sans-serif" font-size="11">'
            "pa=0</text>",
            '<rect x="900" y="1030" width="12" height="12" fill="#E69F00"/>',
            '<text x="917" y="1041" font-family="sans-serif" font-size="11">'
            "pa=1</text>",
            '<text x="20" y="1083" font-family="sans-serif" font-size="11">'
            "Private ignored artifact. Spatial marks derive only from 0.01-degree "
            "grid-cell centres; no site IDs, timing, activity, or finer source "
            "coordinates are included.</text>",
            "</svg>",
        ]
    )
    return "".join(body)


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    required_keys = {
        "schema_version",
        "goal_id",
        "action_main_base",
        "expected_counts",
        "decision_ids",
        "n_microclusters",
        "n_macroregions",
        "geometry",
        "sha_serialization",
        "seed_range",
        "outer_gates",
        "cv_gates",
        "ranking",
        "corrected_oracle",
        "joint_cv_oracle",
        "active_predictors",
        "privacy",
        "bindings",
        "outputs",
        "stopped_before",
    }
    if set(plan) != required_keys:
        raise SpatialPartitionError("plan_schema_drift")
    if (
        plan["schema_version"] != PLAN_SCHEMA_VERSION
        or plan["goal_id"] != GOAL_ID
        or plan["action_main_base"] != "37214228763208b2c262c8feaf117e10bb4c3d6a"
    ):
        raise SpatialPartitionError("plan_identity_drift")
    if plan["expected_counts"] != EXPECTED_COUNTS:
        raise SpatialPartitionError("plan_count_contract_drift")
    if plan["decision_ids"] != [
        "P1-D019",
        "P1-D021",
        "P1-D022",
        "P1-D023",
        "P1-D028",
    ]:
        raise SpatialPartitionError("decision_binding_drift")
    expected_geometry = {
        "source": "all D_struct map-cell centroids exactly once",
        "input_crs": "EPSG:4326",
        "projected_crs": "EPSG:7855",
        "always_xy": True,
        "dtype": "float64",
        "micro_method": "maximin over all map cells",
        "macro_method": "maximin over 50 canonical microcentres",
        "canonical_labels": "south_to_north_then_west_to_east_then_centre_id",
        "response_independent": True,
    }
    if (
        plan["n_microclusters"] != N_MICRO
        or plan["n_macroregions"] != N_MACRO
        or plan["geometry"] != expected_geometry
    ):
        raise SpatialPartitionError("geometry_contract_drift")
    if (
        plan["sha_serialization"]
        != 'ascending sha256(UTF-8 f"{seed}:{zero_based_microcluster_index}")'
        or plan["seed_range"] != [0, SEED_STOP - 1]
    ):
        raise SpatialPartitionError("seed_contract_drift")
    if plan["corrected_oracle"] != CORRECTED_ORACLE:
        raise SpatialPartitionError("oracle_contract_drift")
    if plan["joint_cv_oracle"] != [
        {
            "outer_tuple": list(outer),
            "viable_cv_seeds": list(JOINT_CV_ORACLE[outer]),
        }
        for outer in sorted(JOINT_CV_ORACLE)
    ]:
        raise SpatialPartitionError("joint_oracle_contract_drift")
    if plan["active_predictors"] != list(ACTIVE):
        raise SpatialPartitionError("predictor_contract_drift")
    if plan["privacy"] != PRIVACY or plan["stopped_before"] != STOPPED_BEFORE:
        raise SpatialPartitionError("privacy_or_stop_contract_drift")
    if set(plan["bindings"]) != set(BINDING_PATHS):
        raise SpatialPartitionError("binding_role_drift")
    for role, expected_path in BINDING_PATHS.items():
        entry = plan["bindings"][role]
        if set(entry) != {"path", "sha256"} or entry["path"] != expected_path:
            raise SpatialPartitionError(f"binding_schema_drift:{role}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"])):
            raise SpatialPartitionError(f"binding_sha_schema:{role}")
    if plan["outputs"] != {
        "private_destination": (
            "data/processed/partitions/goal025-spatial-partition/2026-07-26"
        ),
        "evidence_destination": "evidence/spatial_partition/2026-07-26",
        "private_outputs_ignored": True,
        "private_roles": list(PRIVATE_NAMES),
    }:
        raise SpatialPartitionError("output_contract_drift")
    if plan["outer_gates"] != {
        "clusters": 5,
        "one_per_macroregion": True,
        "map_cell_share": [0.075, 0.125],
        "response_cell_share": [0.075, 0.125],
        "minimum_response_cells_per_cluster": 20,
        "species_binary_test_minimum": 10,
        "species_binary_complement_minimum": 50,
        "fallback": False,
    }:
        raise SpatialPartitionError("outer_gate_contract_drift")
    if plan["cv_gates"] != {
        "folds": 5,
        "clusters_per_fold": 9,
        "generator": "macro_stratified_balanced_greedy_v1",
        "macro_process_order": "ascending remaining_count then macro_id",
        "within_macro_priority": (
            "ascending sha256 UTF-8 f'{seed}:{cluster}' then cluster_id"
        ),
        "fold_priority": (
            "ascending sha256 UTF-8 f'{seed}:fold:{fold}' then fold_id"
        ),
        "assignment_minimization": [
            "current_same_macro_count",
            "current_total_fold_size",
            "fold_priority_hash",
            "fold_id",
        ],
        "maximum_per_macro_fold_count_range": 1,
        "production_macroregions_per_fold": 4,
        "literal_all_five_per_fold_feasible": False,
        "superseded_probe": (
            "earlier 3/3612 oracle omitted the impossible macro gate"
        ),
        "response_cell_share": [0.15, 0.25],
        "species_binary_validation_minimum": 10,
        "species_binary_training_minimum": 50,
        "scan_each_unique_outer_independently": True,
        "fallback": False,
    }:
        raise SpatialPartitionError("cv_gate_contract_drift")
    if plan["ranking"] != RANKING_CONTRACT:
        raise SpatialPartitionError("ranking_contract_drift")
    return {"goal_id": GOAL_ID, "validated": True}


def validate_bindings(
    root: Path, plan: Mapping[str, Any]
) -> dict[str, Path]:
    validate_plan(plan)
    resolved: dict[str, Path] = {}
    for role, entry in plan["bindings"].items():
        path = root / _safe_relative(entry["path"])
        if not path.is_file() or path.is_symlink():
            raise SpatialPartitionError(f"binding_missing_or_symlink:{role}")
        if sha256(path) != entry["sha256"]:
            raise SpatialPartitionError(f"binding_drift:{role}")
        resolved[role] = path
    bundle = json.loads(resolved["decision_bundle"].read_text())
    decisions = {
        entry["id"]: entry
        for entry in bundle.get("decisions", [])
        if entry.get("id") in plan["decision_ids"]
    }
    if set(decisions) != set(plan["decision_ids"]) or any(
        entry.get("status") != "resolved" for entry in decisions.values()
    ):
        raise SpatialPartitionError("decision_bundle_semantic_drift")
    if json.loads(resolved["goal024_review"].read_text()).get("decision") != (
        "supported_structural_domain_frozen"
    ):
        raise SpatialPartitionError("goal024_review_not_frozen")
    goal024_support = json.loads(
        resolved["goal024_support_contract"].read_text()
    )
    if (
        goal024_support.get("primary_structural_domain") != "D_struct"
        or goal024_support.get("operational_estimand")
        != (
            "species-specific relative response score over canonical cells in "
            "D_struct, conditional on the accepted presence/survey-supported-"
            "absence/pseudoabsence construction; not detection-corrected "
            "occupancy, abundance, population prevalence, or inference outside "
            "D_struct"
        )
    ):
        raise SpatialPartitionError("goal024_support_contract_drift")
    return resolved


def _load_sources(
    root: Path, plan: Mapping[str, Any]
) -> dict[str, Any]:
    bindings = validate_bindings(root, plan)
    maps = _read_csv(bindings["goal024_map"], MAP_SCHEMA)
    response_cells = _read_csv(
        bindings["goal024_response_cells"], MAP_SCHEMA
    )
    responses = _read_csv(bindings["goal024_response"], RESPONSE_SCHEMA)
    all_response_cells = _read_csv(
        bindings["goal022_all_response_cells"], MAP_SCHEMA
    )
    all_responses = _read_csv(
        bindings["goal021_all_response"], RESPONSE_SCHEMA
    )
    if (
        len(maps),
        len(response_cells),
        len(responses),
        len(all_response_cells),
        len(all_responses),
    ) != (
        MAP_ROWS,
        RESPONSE_CELLS,
        RESPONSE_ROWS,
        ALL_RESPONSE_CELLS,
        ALL_RESPONSE_ROWS,
    ):
        raise SpatialPartitionError("source_row_count_drift")
    primary_cell_ids = {row["grid_cell_id"] for row in response_cells}
    excluded_cells = [
        row
        for row in all_response_cells
        if row["grid_cell_id"] not in primary_cell_ids
    ]
    primary_response_keys = {
        (row["species_id"], row["grid_cell_id"]) for row in responses
    }
    excluded_rows = [
        row
        for row in all_responses
        if (row["species_id"], row["grid_cell_id"])
        not in primary_response_keys
    ]
    if len(excluded_cells) != EXCLUDED_CELLS or len(excluded_rows) != EXCLUDED_ROWS:
        raise SpatialPartitionError("exclusion_count_drift")
    if any(row["grid_cell_id"] in primary_cell_ids for row in excluded_cells):
        raise SpatialPartitionError("excluded_cell_overlap")
    return {
        "bindings": bindings,
        "maps": maps,
        "response_cells": response_cells,
        "responses": responses,
        "excluded_cells": excluded_cells,
        "excluded_rows": excluded_rows,
    }


def compute_outputs(
    root: Path, plan: Mapping[str, Any]
) -> dict[str, Any]:
    sources = _load_sources(root, plan)
    maps = sources["maps"]
    response_cells = sources["response_cells"]
    responses = sources["responses"]
    geometry_result = geometry(maps)
    aggregate = build_cluster_arrays(
        geometry_result, response_cells, responses
    )
    search = search_candidates(geometry_result, aggregate)

    outer_rank_input = []
    record_by_outer = {
        tuple(record["outer_tuple"]): record
        for record in search["outer_records"]
    }
    for outer in search["joint_feasible"]:
        record = record_by_outer[tuple(outer)]
        outer_rank_input.append(
            {
                "outer_tuple": tuple(outer),
                "seed": int(record["first_seed"]),
                **_outer_raw_metrics(
                    tuple(outer),
                    geometry_result,
                    aggregate,
                    maps,
                    response_cells,
                ),
            }
        )
    ranked_outer = rank_outer_candidates(outer_rank_input)
    selected_outer_record = ranked_outer[0]
    selected_outer = tuple(selected_outer_record["outer_tuple"])

    for record in search["outer_records"]:
        ranked = next(
            (
                candidate
                for candidate in ranked_outer
                if candidate["outer_tuple"] == tuple(record["outer_tuple"])
            ),
            None,
        )
        record["selected"] = tuple(record["outer_tuple"]) == selected_outer
        if ranked is not None:
            record.update(
                {
                    key: value
                    for key, value in ranked.items()
                    if key not in {"outer_tuple", "seed"}
                }
            )
        else:
            for field in OUTER_CANDIDATE_SCHEMA:
                record.setdefault(field, "")
    for summary in search["outer_cv_summaries"]:
        summary["selected_outer"] = (
            tuple(summary["outer_tuple"]) == selected_outer
        )

    viable_cv_rank_input = []
    for candidate in search["viable_cv"][selected_outer]:
        viable_cv_rank_input.append(
            {
                **candidate,
                **_cv_raw_metrics(
                    selected_outer,
                    candidate["folds"],
                    geometry_result,
                    aggregate,
                    maps,
                    response_cells,
                ),
            }
        )
    ranked_cv = rank_cv_candidates(viable_cv_rank_input)
    selected_cv = ranked_cv[0]
    selected_folds = tuple(selected_cv["folds"])

    selected_scan = scan_cv_assignments(
        selected_outer,
        geometry_result["micro_macro"],
        aggregate,
        search["_priority_orders"],
        fold_priority_ranks=search["_fold_priority_ranks"],
        capture_attempts=True,
    )
    cv_rank_by_seed = {record["cv_seed"]: record for record in ranked_cv}
    for attempt in selected_scan["attempts"]:
        ranked = cv_rank_by_seed.get(attempt["cv_seed"])
        attempt["selected"] = attempt["cv_seed"] == selected_cv["cv_seed"]
        if ranked is not None:
            attempt.update(
                {
                    key: value
                    for key, value in ranked.items()
                    if key not in {"cv_seed", "folds"}
                }
            )
        for field in CV_CANDIDATE_SCHEMA:
            attempt.setdefault(field, "")

    assignments = build_assignments(
        geometry_result,
        response_cells,
        responses,
        selected_outer,
        selected_folds,
    )
    excluded = assign_excluded_audit(
        geometry_result,
        sources["excluded_cells"],
        sources["excluded_rows"],
    )
    diagnostics = build_support_diagnostics(
        geometry_result,
        maps,
        responses,
        selected_outer,
        selected_folds,
    )
    svg = svg_artifact(geometry_result, assignments, responses)

    return {
        "sources": sources,
        "geometry": geometry_result,
        "aggregate": aggregate,
        "search": search,
        "ranked_outer": ranked_outer,
        "selected_outer": selected_outer_record,
        "ranked_cv": ranked_cv,
        "selected_cv": selected_cv,
        **assignments,
        **excluded,
        "outer_candidates": search["outer_records"],
        "outer_cv_feasibility": search["outer_cv_summaries"],
        "cv_candidates": selected_scan["attempts"],
        "support_diagnostics": diagnostics,
        "svg": svg,
    }


def _private_bytes(computed: Mapping[str, Any]) -> dict[str, bytes]:
    return {
        "map_assignments.csv": csv_bytes(
            computed["map_assignments"], MAP_ASSIGNMENT_SCHEMA
        ),
        "response_cell_assignments.csv": csv_bytes(
            computed["response_cell_assignments"],
            RESPONSE_CELL_ASSIGNMENT_SCHEMA,
        ),
        "response_partitioned.csv": csv_bytes(
            computed["response_partitioned"], RESPONSE_PARTITION_SCHEMA
        ),
        "excluded_cell_audit.csv": csv_bytes(
            computed["excluded_cell_audit"], EXCLUDED_CELL_SCHEMA
        ),
        "excluded_row_audit.csv": csv_bytes(
            computed["excluded_row_audit"], EXCLUDED_ROW_SCHEMA
        ),
        "outer_candidates.csv": csv_bytes(
            computed["outer_candidates"], OUTER_CANDIDATE_SCHEMA
        ),
        "outer_cv_feasibility.csv": csv_bytes(
            computed["outer_cv_feasibility"], OUTER_CV_SCHEMA
        ),
        "cv_candidates.csv": csv_bytes(
            computed["cv_candidates"], CV_CANDIDATE_SCHEMA
        ),
        "support_diagnostics.json": json_text(
            computed["support_diagnostics"]
        ).encode("utf-8"),
        "spatial_partition.svg": computed["svg"].encode("utf-8"),
    }


def _private_metadata(
    payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    for name in PRIVATE_NAMES:
        data = payloads[name]
        role: dict[str, Any] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if name in PRIVATE_SCHEMAS:
            with io.StringIO(data.decode("utf-8"), newline="") as handle:
                reader = csv.reader(handle)
                schema = next(reader)
                rows = sum(1 for _ in reader)
            role.update(
                {
                    "rows": rows,
                    "schema": schema,
                    "media_type": "text/csv",
                }
            )
        elif name.endswith(".json"):
            json.loads(data)
            role["media_type"] = "application/json"
        else:
            role["media_type"] = "image/svg+xml"
        roles[name] = role
    return {"private_outputs_ignored": True, "roles": roles}


def validate_regular_file_set(
    directory: Path, expected: Mapping[str, Mapping[str, Any]]
) -> None:
    if not directory.is_dir() or directory.is_symlink():
        raise SpatialPartitionError("regular_file_set_missing_or_symlink")
    actual = {path.name for path in directory.iterdir()}
    if actual != set(expected):
        raise SpatialPartitionError("regular_file_set_footprint_drift")
    for name, metadata in expected.items():
        path = directory / name
        if path.is_symlink():
            raise SpatialPartitionError("regular_file_set_symlink")
        if not path.is_file():
            raise SpatialPartitionError("regular_file_set_non_file")
        if (
            path.stat().st_size != metadata["bytes"]
            or sha256(path) != metadata["sha256"]
        ):
            raise SpatialPartitionError("regular_file_set_byte_or_sha_drift")


def _validate_private(
    directory: Path,
    metadata: Mapping[str, Any],
    *,
    expected_bytes: Mapping[str, bytes] | None = None,
) -> None:
    if set(metadata) != {"private_outputs_ignored", "roles"} or (
        metadata["private_outputs_ignored"] is not True
    ):
        raise SpatialPartitionError("private_metadata_schema_drift")
    roles = metadata["roles"]
    if set(roles) != set(PRIVATE_NAMES):
        raise SpatialPartitionError("private_metadata_role_drift")
    validate_regular_file_set(directory, roles)
    for name, schema in PRIVATE_SCHEMAS.items():
        role = roles[name]
        if set(role) != {"bytes", "sha256", "rows", "schema", "media_type"}:
            raise SpatialPartitionError("private_csv_metadata_schema_drift")
        if role["schema"] != schema or role["media_type"] != "text/csv":
            raise SpatialPartitionError("private_csv_schema_drift")
        rows = _read_csv(directory / name, schema)
        if len(rows) != role["rows"]:
            raise SpatialPartitionError("private_csv_row_drift")
    for name, media_type in (
        ("support_diagnostics.json", "application/json"),
        ("spatial_partition.svg", "image/svg+xml"),
    ):
        if set(roles[name]) != {"bytes", "sha256", "media_type"}:
            raise SpatialPartitionError("private_non_csv_metadata_schema_drift")
        if roles[name]["media_type"] != media_type:
            raise SpatialPartitionError("private_media_type_drift")
    support = json.loads((directory / "support_diagnostics.json").read_text())
    if (
        support.get("goal_id") != GOAL_ID
        or support.get("out_of_dictionary_count") != 0
        or set(support.get("splits", {}))
        != {
            "outer_test",
            "cv_fold00",
            "cv_fold01",
            "cv_fold02",
            "cv_fold03",
            "cv_fold04",
        }
    ):
        raise SpatialPartitionError("support_diagnostics_semantic_drift")
    svg = (directory / "spatial_partition.svg").read_text()
    if (
        not svg.startswith("<svg ")
        or not svg.endswith("</svg>")
        or "A. 50 microclusters" not in svg
        or "E. Aggregate species" not in svg
    ):
        raise SpatialPartitionError("svg_semantic_drift")
    if expected_bytes is not None:
        for name, data in expected_bytes.items():
            if (directory / name).read_bytes() != data:
                raise SpatialPartitionError(f"private_recomputed_byte_drift:{name}")


def manifest_payload(directory: Path, names: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "files": [
            {
                "path": name,
                "bytes": (directory / name).stat().st_size,
                "sha256": sha256(directory / name),
            }
            for name in names
        ],
    }


def _partition_counts(
    computed: Mapping[str, Any],
) -> dict[str, Any]:
    map_rows = computed["map_assignments"]
    cell_rows = computed["response_cell_assignments"]
    response_rows = computed["response_partitioned"]

    def role_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        return {
            str(key): int(value)
            for key, value in sorted(
                Counter(str(row["outer_role"]) for row in rows).items()
            )
        }

    folds = {}
    for fold in range(N_FOLDS):
        label = f"fold{fold:02d}"
        folds[label] = {
            "microclusters": 9,
            "map_cells": sum(row["cv_fold"] == label for row in map_rows),
            "response_cells": sum(
                row["cv_fold"] == label for row in cell_rows
            ),
            "response_rows": sum(
                row["cv_fold"] == label for row in response_rows
            ),
        }
    return {
        "map_cells": role_counts(map_rows),
        "response_cells": role_counts(cell_rows),
        "response_rows": role_counts(response_rows),
        "outer_test_microclusters": 5,
        "outer_train_microclusters": 45,
        "cv_folds": folds,
    }


def _lattice_cell(grid_cell_id: str) -> tuple[int, int]:
    match = re.fullmatch(r"g_(-?\d+)_(-?\d+)", grid_cell_id)
    if match is None:
        raise SpatialPartitionError("audit_grid_identifier_drift")
    return int(match.group(1)), int(match.group(2))


def _component_sizes(
    cells: set[tuple[int, int]],
    offsets: Sequence[tuple[int, int]],
) -> list[int]:
    unseen = set(cells)
    sizes: list[int] = []
    while unseen:
        start = unseen.pop()
        stack = [start]
        size = 1
        while stack:
            x_value, y_value = stack.pop()
            for x_offset, y_offset in offsets:
                neighbour = (x_value + x_offset, y_value + y_offset)
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
                    size += 1
        sizes.append(size)
    return sorted(sizes, reverse=True)


def _graph_component_count(
    nodes: set[str], adjacency: Mapping[str, set[str]]
) -> int:
    unseen = set(nodes)
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            node = stack.pop()
            for neighbour in adjacency[node] & unseen:
                unseen.remove(neighbour)
                stack.append(neighbour)
    return components


def _scientific_audit_payload(
    map_rows: Sequence[Mapping[str, Any]],
    response_rows: Sequence[Mapping[str, Any]],
    support_diagnostics: Mapping[str, Any],
    *,
    distinct_outer_tuples: int,
) -> dict[str, Any]:
    queen_offsets = [
        (x_offset, y_offset)
        for x_offset in (-100, 0, 100)
        for y_offset in (-100, 0, 100)
        if x_offset != 0 or y_offset != 0
    ]
    rook_offsets = [(-100, 0), (100, 0), (0, -100), (0, 100)]
    cell_micro: dict[tuple[int, int], str] = {}
    micro_cells: dict[str, set[tuple[int, int]]] = {
        f"mc{index:02d}": set() for index in range(N_MICRO)
    }
    micro_macro: dict[str, str] = {}
    outer_cells: set[tuple[int, int]] = set()
    training_cells: set[tuple[int, int]] = set()
    fold_microclusters: dict[str, set[str]] = {
        f"fold{index:02d}": set() for index in range(N_FOLDS)
    }
    for row in map_rows:
        cell = _lattice_cell(str(row["grid_cell_id"]))
        microcluster = str(row["microcluster"])
        macroregion = str(row["macroregion"])
        if cell in cell_micro or microcluster not in micro_cells:
            raise SpatialPartitionError("audit_map_assignment_drift")
        cell_micro[cell] = microcluster
        micro_cells[microcluster].add(cell)
        existing_macro = micro_macro.setdefault(microcluster, macroregion)
        if existing_macro != macroregion:
            raise SpatialPartitionError("audit_macro_assignment_drift")
        if row["outer_role"] == "test":
            outer_cells.add(cell)
        elif row["outer_role"] == "outer_train":
            training_cells.add(cell)
            fold = str(row["cv_fold"])
            if fold not in fold_microclusters:
                raise SpatialPartitionError("audit_fold_assignment_drift")
            fold_microclusters[fold].add(microcluster)
        else:
            raise SpatialPartitionError("audit_outer_role_drift")
    if (
        len(cell_micro) != MAP_ROWS
        or len(micro_macro) != N_MICRO
        or set(cell_micro) != outer_cells | training_cells
        or outer_cells & training_cells
    ):
        raise SpatialPartitionError("audit_map_coverage_drift")

    component_sizes = {
        microcluster: _component_sizes(cells, queen_offsets)
        for microcluster, cells in micro_cells.items()
    }
    selected_outer = sorted(
        {
            cell_micro[cell]
            for cell in outer_cells
        }
    )
    selected_outer_payload = {}
    for microcluster in selected_outer:
        sizes = component_sizes[microcluster]
        total = len(micro_cells[microcluster])
        selected_outer_payload[microcluster] = {
            "queen_components": len(sizes),
            "dominant_component_cells": sizes[0],
            "total_cells": total,
            "dominant_component_share": sizes[0] / total,
        }

    adjacency = {microcluster: set() for microcluster in micro_cells}
    for (x_value, y_value), microcluster in cell_micro.items():
        for x_offset, y_offset in queen_offsets:
            neighbour = cell_micro.get(
                (x_value + x_offset, y_value + y_offset)
            )
            if neighbour is not None and neighbour != microcluster:
                adjacency[microcluster].add(neighbour)
    fold_components = [
        _graph_component_count(fold_microclusters[f"fold{index:02d}"], adjacency)
        for index in range(N_FOLDS)
    ]
    rook_touching = sum(
        any(
            (x_value + x_offset, y_value + y_offset) in training_cells
            for x_offset, y_offset in rook_offsets
        )
        for x_value, y_value in outer_cells
    )
    macro_counts = Counter(micro_macro.values())
    possible_outer_tuples = math.prod(macro_counts.values())

    def rare_class_payload(species: str) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        species_rows = [
            row for row in response_rows if row["species_id"] == species
        ]
        outer_absences = [
            row
            for row in species_rows
            if row["outer_role"] == "test" and str(row["pa"]) == "0"
        ]
        return species_rows, outer_absences

    devil_rows, devil_outer_absences = rare_class_payload(
        "sarcophilus_harrisii"
    )
    devil_presences = sum(str(row["pa"]) == "1" for row in devil_rows)
    thylogale_rows, thylogale_outer_absences = rare_class_payload(
        "thylogale_billardierii"
    )
    thylogale_presences = sum(str(row["pa"]) == "1" for row in thylogale_rows)
    thylogale_cv_absences = [
        sum(
            row["outer_role"] == "outer_train"
            and row["cv_fold"] == f"fold{fold:02d}"
            and str(row["pa"]) == "0"
            for row in thylogale_rows
        )
        for fold in range(N_FOLDS)
    ]
    minimum_thylogale_cv_absences = min(thylogale_cv_absences)

    outer_support = support_diagnostics["splits"]["outer_test"]
    categorical_unseen = sum(
        int(details["assessment_unseen"])
        for species_details in outer_support["species"].values()
        for details in species_details["categorical"].values()
    )
    continuous_out_of_range = sum(
        int(details["assessment_below"]) + int(details["assessment_above"])
        for species_details in outer_support["species"].values()
        for details in species_details["continuous"].values()
    )

    return {
        "design": {
            "design_label": "pre-model-frozen held-patch interpolation",
            "geometry_and_fold_allocation_response_independent": True,
            "feasibility_gates_response_conditioned": True,
            "ranking_response_and_covariate_conditioned": True,
            "prediction_or_performance_input": False,
            "unbiased_confirmatory_transfer": False,
            "isolated_regional_extrapolation": False,
            "buffer_m": 0,
            "search_scope": {
                "seed_schedule": [0, SEED_STOP - 1],
                "scheduled_seeds": SEED_STOP,
                "distinct_outer_tuples_scanned": distinct_outer_tuples,
                "possible_one_per_macro_tuples": possible_outer_tuples,
                "scheduled_outer_tuple_fraction": (
                    distinct_outer_tuples / possible_outer_tuples
                ),
                "scope": (
                    "complete prescribed seed schedule; not combinatorially "
                    "exhaustive"
                ),
            },
        },
        "topology": {
            "microclusters_not_queen_contiguous": sum(
                len(sizes) > 1 for sizes in component_sizes.values()
            ),
            "selected_outer_microclusters": selected_outer_payload,
            "outer_union_queen_components": len(
                _component_sizes(outer_cells, queen_offsets)
            ),
            "outer_cells_rook_touching_training": rook_touching,
            "outer_cells": len(outer_cells),
            "outer_rook_touch_share": rook_touching / len(outer_cells),
            "buffer_m": 0,
            "cv_fold_cluster_adjacency_components": fold_components,
            "interpretation": (
                "five dispersed outer held patches and scattered multi-patch "
                "CV folds"
            ),
        },
        "limitations": {
            "sarcophilus_harrisii": {
                "overall_presences": devil_presences,
                "overall_rows": len(devil_rows),
                "presence_fraction": devil_presences / len(devil_rows),
                "presence_percent_2dp": round(
                    100 * devil_presences / len(devil_rows), 2
                ),
                "outer_absences": len(devil_outer_absences),
                "outer_absence_microclusters": len(
                    {row["microcluster"] for row in devil_outer_absences}
                ),
                "outer_camera_survey_supported_absences": sum(
                    row["pa_type"] == "survey_supported_absence"
                    and row["source_combination"] == "camera_absence_retained"
                    for row in devil_outer_absences
                ),
                "outer_pseudoabsences": sum(
                    row["pa_type"] == "pseudoabsence"
                    for row in devil_outer_absences
                ),
            },
            "thylogale_billardierii": {
                "overall_presences": thylogale_presences,
                "overall_rows": len(thylogale_rows),
                "presence_fraction": thylogale_presences / len(thylogale_rows),
                "presence_percent_2dp": round(
                    100 * thylogale_presences / len(thylogale_rows), 2
                ),
                "outer_absences": len(thylogale_outer_absences),
                "outer_absence_microcluster": next(
                    iter(
                        {
                            row["microcluster"]
                            for row in thylogale_outer_absences
                        }
                    )
                ),
                "outer_camera_survey_supported_absences": sum(
                    row["pa_type"] == "survey_supported_absence"
                    and row["source_combination"] == "camera_absence_retained"
                    for row in thylogale_outer_absences
                ),
                "minimum_cv_validation_absences": (
                    minimum_thylogale_cv_absences
                ),
                "cv_folds_at_minimum_absences": sum(
                    value == minimum_thylogale_cv_absences
                    for value in thylogale_cv_absences
                ),
            },
            "outer_support": {
                "training_unseen_categorical_instances": categorical_unseen,
                "continuous_out_of_range_instances": continuous_out_of_range,
                "global_dictionary_out_of_dictionary_count": (
                    support_diagnostics["out_of_dictionary_count"]
                ),
                "global_dictionary_interpretation": (
                    "integrity check only; not evidence of split-specific "
                    "support"
                ),
            },
            "gate_interpretation": (
                "computability only; not stable discrimination or calibration"
            ),
            "required_downstream": [
                "prevalence-aware metrics",
                "spatial-block uncertainty",
                "per-cluster and source reporting",
                "sensitivity interpretation",
            ],
        },
    }


def _review_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in (
            "schema_version",
            "goal_id",
            "receipt_status",
            "criteria_version",
            "svg_sha256",
            "checklist",
            "reviewer",
            "reviewed_at",
            "private_row_or_coordinate_payloads",
        )
    }


def _evidence_payloads(
    computed: Mapping[str, Any],
    metadata: Mapping[str, Any],
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    selected_outer = computed["selected_outer"]
    selected_cv = computed["selected_cv"]
    scientific_audit = _scientific_audit_payload(
        computed["map_assignments"],
        computed["response_partitioned"],
        computed["support_diagnostics"],
        distinct_outer_tuples=computed["search"]["unique_outer_count"],
    )
    summary = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "action_main_base": plan["action_main_base"],
        "estimand": ESTIMAND,
        "counts": EXPECTED_COUNTS,
        "geometry": {
            "microclusters": N_MICRO,
            "macroregions": N_MACRO,
            "macro_source": "50 canonical microcentres",
            "map_cells_used_once": MAP_ROWS,
            "geometry_response_independent": True,
            "versions": computed["geometry"]["versions"],
        },
        "search": {
            "seed_range": [0, SEED_STOP - 1],
            "unique_outer_candidates": computed["search"]["unique_outer_count"],
            "outer_hard_gate_viable": computed["search"]["outer_viable_count"],
            "joint_feasible_outer": computed["search"]["joint_feasible_count"],
            "viable_cv_assignments": sum(
                len(candidates)
                for candidates in computed["search"]["viable_cv"].values()
            ),
            "corrected_oracle": CORRECTED_ORACLE,
            "oracle_reconciled": True,
            "cv_generator": (
                "macro-stratified SHA ordering with balanced greedy fold "
                "assignment"
            ),
            "fold_macroregions": 4,
            "protocol_correction": (
                "pre-freeze all-five-per-fold gate was impossible under "
                "remaining macro counts 8/24/8/4/1; an earlier feasibility "
                "probe omitted that gate and its 3/3612 oracle is superseded"
            ),
            "fallback_or_relaxation": False,
        },
        "selection": {
            "outer_tuple": list(selected_outer["outer_tuple"]),
            "outer_seed": selected_outer["seed"],
            "cv_seed": selected_cv["cv_seed"],
            "cv_folds": [list(fold) for fold in selected_cv["folds"]],
            "outer_scores": {
                key: selected_outer[key]
                for key in (
                    "geography_min_m",
                    "geography_mean_m",
                    "environment_map_loss",
                    "environment_response_loss",
                    "environment_loss",
                    "representation_mean_loss",
                    "representation_worst_loss",
                    "geography_midrank_score",
                    "environment_midrank_score",
                    "representation_midrank_score",
                    "equal_third_score",
                )
            },
            "cv_scores": {
                key: selected_cv[key]
                for key in (
                    "geography_mean_fold_mean_m",
                    "geography_worst_fold_min_m",
                    "environment_mean_fold_loss",
                    "environment_worst_fold_loss",
                    "balance_mean_loss",
                    "balance_worst_fold_loss",
                    "geography_midrank_score",
                    "environment_midrank_score",
                    "balance_midrank_score",
                    "equal_third_score",
                )
            },
            "performance_input": False,
        },
        **scientific_audit,
        "partitions": _partition_counts(computed),
        "diagnostics": {
            "status": "post_freeze_no_reselection",
            "splits": 6,
            "species_training_only": True,
            "global_categorical_dictionary": True,
            "out_of_dictionary_count": 0,
            "distance_thresholds_m": [1_000, 5_000, 10_000],
        },
        "exclusions": {
            "response_cells": EXCLUDED_CELLS,
            "response_rows": EXCLUDED_ROWS,
            "role": "nearest_microcluster_audit_only",
            "influenced_geometry_gates_ranking_or_diagnostics": False,
        },
        "visual_review": receipt["receipt_status"],
        "privacy": PRIVACY,
        "stopped_before": STOPPED_BEFORE,
    }
    bindings = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "bindings": {
            role: {
                "role": role,
                "path": entry["path"],
                "sha256": entry["sha256"],
            }
            for role, entry in plan["bindings"].items()
        },
    }
    return {
        "summary.json": summary,
        "bindings.json": bindings,
        "outputs.json": metadata,
        "review.json": _review_payload(receipt),
    }


def _privacy_walk(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(
                fragment in lowered
                for fragment in (
                    "grid_cell_id",
                    "centroid",
                    "longitude",
                    "latitude",
                    "site_id",
                    "camera_id",
                    "deployment_time",
                    "activity_time",
                )
            ):
                if not (
                    lowered.startswith("tracked_")
                    and item is False
                ):
                    raise SpatialPartitionError(
                        f"tracked_privacy_key:{'.'.join((*path, str(key)))}"
                    )
            _privacy_walk(item, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _privacy_walk(item, (*path, str(index)))
    elif isinstance(value, str):
        if re.search(r"\bg_-?\d+_-?\d+\b", value):
            raise SpatialPartitionError("tracked_privacy_grid_identifier")


def validate_receipt(
    receipt: Mapping[str, Any],
    evidence_review: Mapping[str, Any],
    *,
    mode: str,
) -> dict[str, str]:
    receipt_keys = {
        "schema_version",
        "goal_id",
        "receipt_status",
        "criteria_version",
        "svg_path",
        "svg_sha256",
        "checklist",
        "reviewer",
        "reviewed_at",
        "private_row_or_coordinate_payloads",
    }
    evidence_keys = receipt_keys - {"svg_path"}
    if set(receipt) != receipt_keys or set(evidence_review) != evidence_keys:
        raise SpatialPartitionError("visual_receipt_schema_drift")
    if (
        receipt["schema_version"] != "1.0"
        or receipt["goal_id"] != GOAL_ID
        or receipt["criteria_version"] != "goal025-v2"
        or receipt["checklist"] != CHECKLIST
        or receipt["svg_path"]
        != (
            "data/processed/partitions/goal025-spatial-partition/2026-07-26/"
            "spatial_partition.svg"
        )
        or receipt["private_row_or_coordinate_payloads"] is not False
        or not re.fullmatch(r"[0-9a-f]{64}", receipt["svg_sha256"])
    ):
        raise SpatialPartitionError("visual_receipt_semantic_drift")
    for key in evidence_keys:
        if evidence_review[key] != receipt[key]:
            raise SpatialPartitionError("visual_receipt_evidence_drift")
    if mode == "pending":
        if (
            receipt["receipt_status"] != "pending_orchestrator"
            or receipt["reviewer"] != "orchestrator_pending"
            or receipt["reviewed_at"] is not None
        ):
            raise SpatialPartitionError("pending_review_state_drift")
    elif mode == "final":
        if (
            receipt["receipt_status"] != "passed"
            or receipt["reviewer"] in {"", "orchestrator_pending"}
            or not receipt["reviewed_at"]
        ):
            raise SpatialPartitionError("final_review_not_passed")
    else:
        raise SpatialPartitionError("unknown_validation_mode")
    return {"status": str(receipt["receipt_status"])}


def _validate_tracked_evidence(
    evidence_dir: Path,
    plan: Mapping[str, Any],
    private_metadata: Mapping[str, Any],
    receipt: Mapping[str, Any],
    private_dir: Path,
) -> dict[str, Any]:
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise SpatialPartitionError("missing_or_symlink_evidence")
    names = {path.name for path in evidence_dir.iterdir()}
    if names != set(EVIDENCE_FILES) | {"manifest.json"}:
        raise SpatialPartitionError("evidence_footprint_drift")
    if any(path.is_symlink() or not path.is_file() for path in evidence_dir.iterdir()):
        raise SpatialPartitionError("evidence_nonregular_or_symlink")
    expected_manifest = manifest_payload(evidence_dir, EVIDENCE_FILES)
    manifest = json.loads((evidence_dir / "manifest.json").read_text())
    if manifest != expected_manifest:
        raise SpatialPartitionError("evidence_manifest_drift")

    payloads = {
        name: json.loads((evidence_dir / name).read_text())
        for name in EVIDENCE_FILES
    }
    expected_bindings = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "bindings": {
            role: {
                "role": role,
                "path": entry["path"],
                "sha256": entry["sha256"],
            }
            for role, entry in plan["bindings"].items()
        },
    }
    if payloads["bindings.json"] != expected_bindings:
        raise SpatialPartitionError("bindings_evidence_semantic_drift")
    if payloads["outputs.json"] != private_metadata:
        raise SpatialPartitionError("outputs_evidence_semantic_drift")
    review_status = validate_receipt(
        receipt, payloads["review.json"], mode="pending"
        if receipt["receipt_status"] == "pending_orchestrator"
        else "final"
    )["status"]

    summary = payloads["summary.json"]
    expected_summary_keys = {
        "schema_version",
        "goal_id",
        "action_main_base",
        "estimand",
        "counts",
        "geometry",
        "search",
        "selection",
        "design",
        "topology",
        "limitations",
        "partitions",
        "diagnostics",
        "exclusions",
        "visual_review",
        "privacy",
        "stopped_before",
    }
    if set(summary) != expected_summary_keys:
        raise SpatialPartitionError("summary_semantic_schema_drift")
    nested_keys = {
        "geometry": {
            "microclusters",
            "macroregions",
            "macro_source",
            "map_cells_used_once",
            "geometry_response_independent",
            "versions",
        },
        "search": {
            "seed_range",
            "unique_outer_candidates",
            "outer_hard_gate_viable",
            "joint_feasible_outer",
            "viable_cv_assignments",
            "corrected_oracle",
            "oracle_reconciled",
            "cv_generator",
            "fold_macroregions",
            "protocol_correction",
            "fallback_or_relaxation",
        },
        "selection": {
            "outer_tuple",
            "outer_seed",
            "cv_seed",
            "cv_folds",
            "outer_scores",
            "cv_scores",
            "performance_input",
        },
        "design": {
            "design_label",
            "geometry_and_fold_allocation_response_independent",
            "feasibility_gates_response_conditioned",
            "ranking_response_and_covariate_conditioned",
            "prediction_or_performance_input",
            "unbiased_confirmatory_transfer",
            "isolated_regional_extrapolation",
            "buffer_m",
            "search_scope",
        },
        "topology": {
            "microclusters_not_queen_contiguous",
            "selected_outer_microclusters",
            "outer_union_queen_components",
            "outer_cells_rook_touching_training",
            "outer_cells",
            "outer_rook_touch_share",
            "buffer_m",
            "cv_fold_cluster_adjacency_components",
            "interpretation",
        },
        "limitations": {
            "sarcophilus_harrisii",
            "thylogale_billardierii",
            "outer_support",
            "gate_interpretation",
            "required_downstream",
        },
        "partitions": {
            "map_cells",
            "response_cells",
            "response_rows",
            "outer_test_microclusters",
            "outer_train_microclusters",
            "cv_folds",
        },
        "diagnostics": {
            "status",
            "splits",
            "species_training_only",
            "global_categorical_dictionary",
            "out_of_dictionary_count",
            "distance_thresholds_m",
        },
    }
    if any(set(summary[key]) != expected for key, expected in nested_keys.items()):
        raise SpatialPartitionError("summary_nested_schema_drift")
    if set(summary["selection"]["outer_scores"]) != {
        "geography_min_m",
        "geography_mean_m",
        "environment_map_loss",
        "environment_response_loss",
        "environment_loss",
        "representation_mean_loss",
        "representation_worst_loss",
        "geography_midrank_score",
        "environment_midrank_score",
        "representation_midrank_score",
        "equal_third_score",
    } or set(summary["selection"]["cv_scores"]) != {
        "geography_mean_fold_mean_m",
        "geography_worst_fold_min_m",
        "environment_mean_fold_loss",
        "environment_worst_fold_loss",
        "balance_mean_loss",
        "balance_worst_fold_loss",
        "geography_midrank_score",
        "environment_midrank_score",
        "balance_midrank_score",
        "equal_third_score",
    }:
        raise SpatialPartitionError("summary_score_schema_drift")
    if (
        summary["schema_version"] != "1.0"
        or summary["goal_id"] != GOAL_ID
        or summary["action_main_base"] != plan["action_main_base"]
        or summary["estimand"] != ESTIMAND
        or summary["counts"] != EXPECTED_COUNTS
        or summary["privacy"] != PRIVACY
        or summary["stopped_before"] != STOPPED_BEFORE
        or summary["search"]["corrected_oracle"] != CORRECTED_ORACLE
        or summary["search"]["unique_outer_candidates"]
        != CORRECTED_ORACLE["unique_outer_candidates"]
        or summary["search"]["outer_hard_gate_viable"]
        != CORRECTED_ORACLE["outer_hard_gate_viable"]
        or summary["search"]["joint_feasible_outer"]
        != CORRECTED_ORACLE["joint_feasible_outer"]
        or summary["search"]["viable_cv_assignments"]
        != CORRECTED_ORACLE["viable_cv_assignments"]
        or summary["search"]["fallback_or_relaxation"] is not False
        or summary["design"]["prediction_or_performance_input"] is not False
        or summary["design"]["unbiased_confirmatory_transfer"] is not False
        or summary["design"]["isolated_regional_extrapolation"] is not False
        or tuple(summary["selection"]["outer_tuple"])
        not in JOINT_OUTER_ORACLE
        or summary["selection"]["cv_seed"]
        not in JOINT_CV_ORACLE[
            tuple(summary["selection"]["outer_tuple"])
        ]
        or summary["diagnostics"]["out_of_dictionary_count"] != 0
        or summary["visual_review"] != receipt["receipt_status"]
        or summary["exclusions"]
        != {
            "response_cells": EXCLUDED_CELLS,
            "response_rows": EXCLUDED_ROWS,
            "role": "nearest_microcluster_audit_only",
            "influenced_geometry_gates_ranking_or_diagnostics": False,
        }
    ):
        raise SpatialPartitionError("summary_semantic_drift")

    outer_rows = _read_csv(
        private_dir / "outer_candidates.csv", OUTER_CANDIDATE_SCHEMA
    )
    outer_cv_rows = _read_csv(
        private_dir / "outer_cv_feasibility.csv", OUTER_CV_SCHEMA
    )
    cv_rows = _read_csv(
        private_dir / "cv_candidates.csv", CV_CANDIDATE_SCHEMA
    )
    if (
        len(outer_rows) != CORRECTED_ORACLE["unique_outer_candidates"]
        or sum(row["outer_viable"] == "true" for row in outer_rows)
        != CORRECTED_ORACLE["outer_hard_gate_viable"]
        or sum(row["joint_feasible"] == "true" for row in outer_rows)
        != CORRECTED_ORACLE["joint_feasible_outer"]
        or sum(int(row["viable_cv_seed_count"]) for row in outer_cv_rows)
        != CORRECTED_ORACLE["viable_cv_assignments"]
        or len(cv_rows) != SEED_STOP
    ):
        raise SpatialPartitionError("candidate_private_semantic_drift")
    selected_outer_rows = [
        row for row in outer_rows if row["selected"] == "true"
    ]
    selected_cv_rows = [row for row in cv_rows if row["selected"] == "true"]
    if len(selected_outer_rows) != 1 or len(selected_cv_rows) != 1:
        raise SpatialPartitionError("selected_candidate_cardinality_drift")
    selected_outer = selected_outer_rows[0]
    selected_cv = selected_cv_rows[0]
    if (
        [int(value) for value in selected_outer["outer_tuple"].split(";")]
        != summary["selection"]["outer_tuple"]
        or int(selected_outer["first_seed"])
        != summary["selection"]["outer_seed"]
        or int(selected_cv["cv_seed"]) != summary["selection"]["cv_seed"]
        or [
            [int(value) for value in selected_cv[f"fold{index:02d}"].split(";")]
            for index in range(N_FOLDS)
        ]
        != summary["selection"]["cv_folds"]
    ):
        raise SpatialPartitionError("selected_candidate_semantic_drift")
    for evidence_key in ("outer_scores", "cv_scores"):
        source = selected_outer if evidence_key == "outer_scores" else selected_cv
        for key, expected in summary["selection"][evidence_key].items():
            if not math.isclose(
                float(source[key]),
                float(expected),
                rel_tol=1e-10,
                abs_tol=1e-10,
            ):
                raise SpatialPartitionError("selected_score_semantic_drift")

    map_rows = _read_csv(
        private_dir / "map_assignments.csv", MAP_ASSIGNMENT_SCHEMA
    )
    response_cell_rows = _read_csv(
        private_dir / "response_cell_assignments.csv",
        RESPONSE_CELL_ASSIGNMENT_SCHEMA,
    )
    response_rows = _read_csv(
        private_dir / "response_partitioned.csv", RESPONSE_PARTITION_SCHEMA
    )
    support_diagnostics = json.loads(
        (private_dir / "support_diagnostics.json").read_text()
    )
    scientific_audit = _scientific_audit_payload(
        map_rows,
        response_rows,
        support_diagnostics,
        distinct_outer_tuples=len(outer_rows),
    )
    if any(
        summary[key] != scientific_audit[key]
        for key in ("design", "topology", "limitations")
    ):
        raise SpatialPartitionError("scientific_audit_semantic_drift")
    if summary["partitions"] != _partition_counts(
        {
            "map_assignments": map_rows,
            "response_cell_assignments": response_cell_rows,
            "response_partitioned": response_rows,
        }
    ):
        raise SpatialPartitionError("partition_summary_semantic_drift")
    for payload in payloads.values():
        _privacy_walk(payload)
    return {"review_status": review_status, "payloads": payloads}


def validate_evidence(
    plan_path: Path,
    evidence_dir: Path,
    *,
    root: Path | None = None,
    mode: str = "pending",
    full: bool = False,
    goal024_validator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = plan_path.resolve().parents[1] if root is None else root
    if not plan_path.is_file() or plan_path.is_symlink():
        raise SpatialPartitionError("plan_missing_or_symlink")
    plan = json.loads(plan_path.read_text())
    bindings = validate_bindings(root, plan)
    private_dir = root / _safe_relative(plan["outputs"]["private_destination"])
    receipt_path = root / "config/spatial_partition_visual_review.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise SpatialPartitionError("receipt_missing_or_symlink")
    receipt = json.loads(receipt_path.read_text())

    outputs = json.loads((evidence_dir / "outputs.json").read_text())
    _validate_private(private_dir, outputs)
    tracked = _validate_tracked_evidence(
        evidence_dir, plan, outputs, receipt, private_dir
    )
    validate_receipt(
        receipt,
        tracked["payloads"]["review.json"],
        mode=mode,
    )
    if (
        outputs["roles"]["spatial_partition.svg"]["sha256"]
        != receipt["svg_sha256"]
    ):
        raise SpatialPartitionError("svg_receipt_sha_drift")

    if full:
        if goal024_validator is None:
            from dsdm_phase1.predictor_source_repair_domain_freeze import (
                validate_evidence as goal024_validator,
            )

        goal024_validator(
            bindings["goal024_plan"],
            bindings["goal024_manifest"].parent,
            full=True,
            root=root,
        )
        computed = compute_outputs(root, plan)
        expected_bytes = _private_bytes(computed)
        expected_metadata = _private_metadata(expected_bytes)
        _validate_private(
            private_dir,
            expected_metadata,
            expected_bytes=expected_bytes,
        )
        expected_evidence = _evidence_payloads(
            computed, expected_metadata, plan, receipt
        )
        for name, expected in expected_evidence.items():
            actual = json.loads((evidence_dir / name).read_text())
            if actual != expected:
                raise SpatialPartitionError(
                    f"full_replay_evidence_drift:{name}"
                )
    return {
        "tracked_valid": True,
        "private_valid": True,
        "full_replay": bool(full),
        "review_status": receipt["receipt_status"],
    }


def publish_staged_pair(
    private_destination: Path,
    evidence_destination: Path,
    stage_parent: Path,
    writer: Callable[[Path, Path], None],
) -> None:
    if private_destination.exists() or evidence_destination.exists():
        raise SpatialPartitionError("publication_destination_exists")
    private_destination.parent.mkdir(parents=True, exist_ok=True)
    evidence_destination.parent.mkdir(parents=True, exist_ok=True)
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=".goal025-stage-", dir=stage_parent)
    )
    stage_private = stage_root / "private"
    stage_evidence = stage_root / "evidence"
    stage_private.mkdir()
    stage_evidence.mkdir()
    private_published = False
    try:
        writer(stage_private, stage_evidence)
        stage_private.rename(private_destination)
        private_published = True
        try:
            stage_evidence.rename(evidence_destination)
        except Exception as exc:
            try:
                private_destination.rename(stage_private)
                private_published = False
            except Exception as rollback_exc:
                raise SpatialPartitionError("publication_rollback") from rollback_exc
            raise SpatialPartitionError("publication_second_rename") from exc
    finally:
        if private_published and not evidence_destination.exists():
            # A failed rollback is intentionally left visible for manual recovery.
            pass
        elif stage_root.exists():
            shutil.rmtree(stage_root)


def run_production(root: Path) -> dict[str, Any]:
    plan_path = root / "config/spatial_partition_plan.json"
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    private_destination = root / _safe_relative(
        plan["outputs"]["private_destination"]
    )
    evidence_destination = root / _safe_relative(
        plan["outputs"]["evidence_destination"]
    )
    if private_destination.exists() or evidence_destination.exists():
        raise SpatialPartitionError("publication_destination_exists")

    computed = compute_outputs(root, plan)
    private_payloads = _private_bytes(computed)
    metadata = _private_metadata(private_payloads)
    svg_sha = metadata["roles"]["spatial_partition.svg"]["sha256"]
    receipt_path = root / "config/spatial_partition_visual_review.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["receipt_status"] != "pending_orchestrator":
        raise SpatialPartitionError("production_requires_pending_receipt")
    if receipt["svg_sha256"] != svg_sha:
        raise SpatialPartitionError("receipt_svg_sha_not_prebound")
    evidence_payloads = _evidence_payloads(
        computed, metadata, plan, receipt
    )

    def writer(stage_private: Path, stage_evidence: Path) -> None:
        for name, data in private_payloads.items():
            (stage_private / name).write_bytes(data)
        _validate_private(
            stage_private,
            metadata,
            expected_bytes=private_payloads,
        )
        for name in EVIDENCE_FILES:
            (stage_evidence / name).write_text(
                json_text(evidence_payloads[name])
            )
        (stage_evidence / "manifest.json").write_text(
            json_text(manifest_payload(stage_evidence, EVIDENCE_FILES))
        )
        _validate_tracked_evidence(
            stage_evidence, plan, metadata, receipt, stage_private
        )

    stage_parent = private_destination.parent
    publish_staged_pair(
        private_destination,
        evidence_destination,
        stage_parent,
        writer,
    )
    return {
        "private": str(private_destination),
        "evidence": str(evidence_destination),
        "unique_outer_candidates": computed["search"]["unique_outer_count"],
        "outer_hard_gate_viable": computed["search"]["outer_viable_count"],
        "joint_feasible_outer": computed["search"]["joint_feasible_count"],
        "selected_outer": list(computed["selected_outer"]["outer_tuple"]),
        "selected_cv_seed": computed["selected_cv"]["cv_seed"],
        "svg_sha256": svg_sha,
        "review_status": receipt["receipt_status"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--mode", choices=("pending", "final"), default="pending")
    args = parser.parse_args()
    if args.validate:
        result = validate_evidence(
            args.root / "config/spatial_partition_plan.json",
            args.root / "evidence/spatial_partition" / DATE,
            root=args.root,
            mode=args.mode,
            full=args.full,
        )
    else:
        result = run_production(args.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
