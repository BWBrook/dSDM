"""Response-blind IBRA region scoring for Goal 048.

This module reads only the frozen domain/geography surfaces, the frozen NVIS
ontology, and the expanded predictor table.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import rankdata
from shapely import covers, intersects, make_valid, points, union_all


REGIONS = ["AUA", "BBS", "KAN", "NAN", "NCP", "NET", "NNC", "NSS", "SCP", "SEC", "SEH", "SEQ", "SVP", "SYB", "VIM"]
CONTINUOUS = [
    *(f"bio{i:02d}" for i in range(1, 20)),
    "elevation_mean",
    "elevation_sd",
]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
PREDICTORS = CONTINUOUS + CATEGORICAL
ROLES = ("supported", "edge", "mosaic")
NATIVE_WOODY = set(range(1, 19)) | {23, 31, 32}
NON_WOODY = {19, 20, 21, 25, 27}
MISSING_NVIS = {22, 24, 26, 28, 29, 30, 99}
OUTPUT_DIR = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/response_free")
IBRA_PATH = Path("data/raw/goal040/domain/ibra7_1_subregions.geojson")
DOMAIN_PATH = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/domain_cells.csv")
PREDICTOR_PATH = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/predictors/predictor_substrate.parquet")
NVIS_PATH = Path("data/processed/dsdm/goal048-seawfb-bioregional-freeze/nvis_freeze.json")
CONFIG_PATH = Path("config/goal048_seawfb_bioregional_freeze.json")


class ScoringError(ValueError):
    """Raised when a frozen scoring contract is not satisfied."""


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_text(json.dumps(_json_safe(value), sort_keys=True, indent=2) + "\n")
    temp.replace(path)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def _write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    frame.to_parquet(temp, index=False)
    temp.replace(path)


def even_sample_indices(n: int, maximum: int) -> np.ndarray:
    """Return sorted, endpoint-inclusive evenly spaced integer indices."""
    if n < 0 or maximum < 0:
        raise ScoringError("sample sizes must be non-negative")
    m = min(n, maximum)
    if m == 0:
        return np.empty(0, dtype=np.int64)
    if m == 1:
        return np.array([0], dtype=np.int64)
    return np.floor(np.arange(m, dtype=np.float64) * (n - 1) / (m - 1)).astype(np.int64)


def empirical_percentiles(values: Sequence[float]) -> np.ndarray:
    """Average-tie empirical percentiles, scaled to [0, 1]."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) == 0 or not np.isfinite(array).all():
        raise ScoringError("percentile values must be a finite non-empty vector")
    if len(array) == 1:
        return np.zeros(1, dtype=float)
    return (rankdata(array, method="average") - 1.0) / (len(array) - 1.0)


def shannon_entropy(values: Iterable[Any], global_levels: Sequence[str] | None = None) -> tuple[float, float]:
    """Return Shannon H and H/log(K_global), using valid strings only."""
    clean = [str(value).strip() for value in values if value is not None and str(value).strip() and str(value).lower() != "nan"]
    levels = sorted(set(global_levels or clean))
    if not clean:
        return math.nan, math.nan
    counts = pd.Series(clean).value_counts(sort=False)
    probabilities = counts.to_numpy(dtype=float) / len(clean)
    entropy = float(-(probabilities * np.log(probabilities)).sum())
    return entropy, (0.0 if len(levels) <= 1 else entropy / math.log(len(levels)))


def _nvis_code(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    match = re.match(r"^\s*(\d+)\s*(?::.*)?$", str(value))
    return int(match.group(1)) if match else None


def fragmentation_metrics(rows: pd.DataFrame, nvis_classes: Mapping[int, str] | None = None) -> dict[str, Any]:
    """Compute rook-edge native woody/non-woody fragmentation for one region."""
    required = {"row", "column", "nvis_mvg"}
    if not required <= set(rows):
        raise ScoringError(f"fragmentation rows lack {sorted(required - set(rows))}")
    cells: dict[tuple[int, int], int | None] = {}
    for item in rows[["row", "column", "nvis_mvg"]].itertuples(index=False):
        code = _nvis_code(item.nvis_mvg)
        if nvis_classes is not None and code not in nvis_classes:
            code = None
        cells[(int(item.row), int(item.column))] = code
    mapped = {key: code for key, code in cells.items() if code in NATIVE_WOODY or code in NON_WOODY}
    numerator = denominator = 0
    for (row, column), left_code in mapped.items():
        left_class = left_code in NATIVE_WOODY
        for neighbour in ((row, column + 1), (row + 1, column)):
            right_code = mapped.get(neighbour)
            if right_code is None:
                continue
            denominator += 1
            if left_class != (right_code in NATIVE_WOODY):
                numerator += 1
    woody = sum(code in NATIVE_WOODY for code in mapped.values())
    return {
        "fragmentation_numerator": numerator,
        "fragmentation_denominator": denominator,
        "fragmentation": (numerator / denominator if denominator else math.nan),
        "mapped_cells": len(mapped),
        "native_woody_fraction": (woody / len(mapped) if mapped else math.nan),
    }


def _finite_mask(frame: pd.DataFrame, fields: Sequence[str]) -> np.ndarray:
    mask = np.ones(len(frame), dtype=bool)
    for field in fields:
        values = pd.to_numeric(frame[field], errors="coerce").to_numpy(dtype=float)
        mask &= np.isfinite(values)
    return mask


def _complete_mask(frame: pd.DataFrame) -> np.ndarray:
    mask = _finite_mask(frame, CONTINUOUS)
    for field in CATEGORICAL:
        values = frame[field]
        mask &= values.notna().to_numpy()
        mask &= values.astype(str).str.strip().ne("").to_numpy()
        mask &= values.astype(str).str.lower().ne("nan").to_numpy()
    return mask


def _projected_xy(frame: pd.DataFrame) -> np.ndarray:
    geometry = gpd.GeoSeries(points(frame["longitude"].to_numpy(), frame["latitude"].to_numpy()), crs=4326).to_crs(3577)
    return np.column_stack((geometry.x.to_numpy(), geometry.y.to_numpy()))


def _nearest_distances(query: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if len(query) == 0 or len(reference) == 0:
        raise ScoringError("nearest-distance calculation requires both samples")
    tree = cKDTree(reference)
    return tree.query(query, k=1, workers=1)[0]


def retained_complement_mask(frame: pd.DataFrame, codes: Sequence[str], regions: Mapping[str, Any]) -> np.ndarray:
    """Mark domain centroids outside the simultaneous 50 km exclusion."""
    holdout = make_valid(union_all([regions[code] for code in codes]))
    projected_holdout = gpd.GeoSeries([holdout], crs=4326).to_crs(3577).iloc[0]
    buffer = projected_holdout.buffer(50_000.0)
    projected_points = gpd.GeoSeries(points(frame["longitude"].to_numpy(), frame["latitude"].to_numpy()), crs=4326).to_crs(3577)
    return ~np.asarray(covers(buffer, projected_points.array), dtype=bool)


def _read_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    config = json.loads(path.read_text())
    if config["domain"]["prospective_region_codes"] != REGIONS:
        raise ScoringError("candidate region order drift")
    if config["response_free_scoring"]["systematic_sample_max_cells_per_region"] != 2000:
        raise ScoringError("region sample ceiling drift")
    response = config["response_free_scoring"]
    environment = response["environment"]
    if environment["pca_variance_retained_minimum"] != 0.90 or response["systematic_sample_max_domain_cells"] != 100_000:
        raise ScoringError("PCA or domain sample constant drift")
    if config["buffer"]["external_training_exclusion_km"] != 50.0:
        raise ScoringError("buffer constant drift")
    joint = config["joint_selection"]
    if joint["minimum_pairwise_centroid_distance_km"] != 250.0:
        raise ScoringError("centroid distance constant drift")
    ambiguity = joint["ambiguity"]
    if ambiguity["minimum_role_score_margin_below"] != 0.01 or ambiguity["summed_role_score_margin_below"] != 0.02:
        raise ScoringError("ambiguity margin drift")
    estimability = config["estimability"]
    if estimability["candidate_region_minimum_predictor_complete_fraction"] != 0.95 or estimability["candidate_region_minimum_eligible_land_cells"] != 5000:
        raise ScoringError("candidate gate drift")
    if response["mosaic_native_woody_fraction_minimum"] != 0.20 or response["mosaic_native_woody_fraction_maximum"] != 0.80:
        raise ScoringError("mosaic gate drift")
    return config


def _read_nvis(root: Path) -> dict[int, str]:
    receipt = json.loads((root / NVIS_PATH).read_text())
    rows = receipt.get("rows", [])
    by_code = {int(row["code"]): row["class"] for row in rows}
    expected = {code: "native_woody" for code in NATIVE_WOODY} | {code: "non_woody" for code in NON_WOODY} | {code: "missing" for code in MISSING_NVIS}
    if by_code != expected or sorted(receipt.get("missing_codes", [])) != sorted(MISSING_NVIS - {30}):
        raise ScoringError("NVIS ontology drift")
    return by_code


def _load_regions(root: Path) -> dict[str, Any]:
    frame = gpd.read_file(root / IBRA_PATH).to_crs(4326)
    if len(frame) != 419 or frame["REG_CODE_7"].nunique() != 89:
        raise ScoringError("IBRA authority count drift")
    regions = {}
    for code in REGIONS:
        subset = frame.loc[frame["REG_CODE_7"] == code]
        if subset.empty:
            raise ScoringError(f"missing candidate region {code}")
        regions[code] = make_valid(union_all(subset.geometry.array))
    return regions


def _load_table(root: Path, expected_ids: Sequence[str] | None = None) -> pd.DataFrame:
    path = root / PREDICTOR_PATH
    if not path.is_file():
        raise ScoringError(f"predictor substrate missing: {path}")
    table = pd.read_parquet(path, columns=["cell_id", *PREDICTORS])
    table["cell_id"] = table["cell_id"].astype(str)
    if len(table) != 1_144_286 or table["cell_id"].duplicated().any() or set(PREDICTORS) - set(table):
        raise ScoringError("predictor table identity or schema drift")
    table = table.sort_values("cell_id", kind="mergesort").reset_index(drop=True)
    if expected_ids is not None and table["cell_id"].tolist() != list(expected_ids):
        raise ScoringError("predictor table does not exactly match frozen domain identity")
    return table


def _load_cells(root: Path) -> pd.DataFrame:
    path = root / DOMAIN_PATH
    if not path.is_file():
        raise ScoringError(f"domain ledger missing: {path}")
    cells = pd.read_csv(path, dtype={"cell_id": str})
    required = {"cell_id", "row", "column", "longitude", "latitude"}
    if len(cells) != 1_144_286 or not required <= set(cells) or cells["cell_id"].duplicated().any():
        raise ScoringError("domain ledger identity or schema drift")
    return cells.sort_values("cell_id", kind="mergesort").reset_index(drop=True)


def assign_regions(cells: pd.DataFrame, regions: Mapping[str, Any]) -> pd.Series:
    """Assign candidate region by centroid; overlapping assignments are fatal."""
    pts = points(cells["longitude"].to_numpy(), cells["latitude"].to_numpy())
    assignment = np.full(len(cells), None, dtype=object)
    count = np.zeros(len(cells), dtype=np.int8)
    for code in REGIONS:
        mask = np.asarray(covers(regions[code], pts), dtype=bool)
        assignment[mask & (count == 0)] = code
        count += mask.astype(np.int8)
    if np.any(count > 1):
        raise ScoringError("cell centroid has multiple candidate-region assignments")
    return pd.Series(assignment, index=cells.index, name="region", dtype="string")


def fit_common_pca(table: pd.DataFrame, maximum: int = 100_000) -> dict[str, Any]:
    """Fit the prescribed median/IQR and deterministic full-SVD PCA transform."""
    complete = table.loc[_finite_mask(table, CONTINUOUS)].sort_values("cell_id", kind="mergesort")
    sample = complete.iloc[even_sample_indices(len(complete), maximum)]
    if sample.empty:
        raise ScoringError("no complete environmental cells for PCA")
    values = sample[CONTINUOUS].to_numpy(dtype=float)
    median = np.median(values, axis=0)
    iqr = np.percentile(values, 75, axis=0) - np.percentile(values, 25, axis=0)
    keep = iqr != 0.0
    if not np.any(keep):
        raise ScoringError("all environmental dimensions have zero IQR")
    scaled = (values[:, keep] - median[keep]) / iqr[keep]
    centre = scaled.mean(axis=0)
    centred = scaled - centre
    _, singular, components = np.linalg.svd(centred, full_matrices=False)
    variance = singular * singular
    total = float(variance.sum())
    if total == 0:
        raise ScoringError("environmental PCA has zero variance")
    cumulative = np.cumsum(variance) / total
    k = int(np.searchsorted(cumulative, 0.90, side="left") + 1)
    return {
        "fields": [field for field, used in zip(CONTINUOUS, keep) if used],
        "median": median[keep].tolist(),
        "iqr": iqr[keep].tolist(),
        "centre": centre.tolist(),
        "components": components[:k].tolist(),
        "variance_explained": float(cumulative[k - 1]),
        "component_count": k,
        "sample_count": len(sample),
        "sample_cell_id_sha256": _digest(sample["cell_id"].tolist()),
        "selection_only": True,
    }


def apply_pca(frame: pd.DataFrame, transform: Mapping[str, Any]) -> np.ndarray:
    fields = list(transform["fields"])
    values = frame[fields].to_numpy(dtype=float)
    scaled = (values - np.asarray(transform["median"], dtype=float)) / np.asarray(transform["iqr"], dtype=float)
    centred = scaled - np.asarray(transform["centre"], dtype=float)
    return centred @ np.asarray(transform["components"], dtype=float).T


def _region_metrics(table: pd.DataFrame, assigned: pd.Series, nvis_classes: Mapping[int, str]) -> pd.DataFrame:
    rows = []
    for code in REGIONS:
        subset = table.loc[assigned.eq(code).fillna(False).to_numpy(dtype=bool)]
        complete = _complete_mask(subset)
        rows.append({
            "region": code,
            "domain_cells": len(subset),
            "complete_cells": int(complete.sum()),
            "predictor_complete_fraction": float(complete.mean()) if len(subset) else 0.0,
            **fragmentation_metrics(subset, nvis_classes),
        })
    result = pd.DataFrame(rows)
    region_mask = assigned.isin(REGIONS).fillna(False).to_numpy(dtype=bool)
    global_levels = sorted({str(value).strip() for value in table.loc[region_mask, "alum_secondary"] if pd.notna(value) and str(value).strip() and str(value).lower() != "nan"})
    entropies = {code: shannon_entropy(table.loc[assigned.eq(code).fillna(False).to_numpy(dtype=bool), "alum_secondary"], global_levels) for code in REGIONS}
    result["alum_entropy"] = result["region"].map({code: value[0] for code, value in entropies.items()})
    result["alum_entropy_normalized"] = result["region"].map({code: value[1] for code, value in entropies.items()})
    result["mosaic_allowed"] = result["native_woody_fraction"].map(lambda value: bool(np.isfinite(value) and 0.20 <= value <= 0.80))
    return result


def _structural_matrix(regions: Mapping[str, Any]) -> tuple[dict[tuple[str, str], bool], dict[str, float], dict[str, Any]]:
    projected = {code: gpd.GeoSeries([regions[code]], crs=4326).to_crs(3577).iloc[0] for code in REGIONS}
    centroids = {code: projected[code].centroid for code in REGIONS}
    adjacent = {}
    distances = {}
    for left, right in itertools.combinations(REGIONS, 2):
        adjacent[(left, right)] = bool(intersects(regions[left], regions[right]))
        distances[(left, right)] = float(centroids[left].distance(centroids[right]) / 1000.0)
    return adjacent, distances, projected


def _run_identity(root: Path) -> str:
    paths = [root / "scripts/goal048_response_free_scoring.py", root / CONFIG_PATH, root / DOMAIN_PATH, root / IBRA_PATH, root / NVIS_PATH, root / PREDICTOR_PATH]
    if not all(path.is_file() for path in paths):
        missing = [str(path) for path in paths if not path.is_file()]
        raise ScoringError(f"run identity inputs missing: {', '.join(missing)}")
    return _digest({str(path.relative_to(root)): _sha(path) for path in paths})


def _validate_live_invariants(cells: pd.DataFrame, assigned: pd.Series, metrics: pd.DataFrame, valid_sets: Sequence[tuple[str, str, str]]) -> None:
    for row in metrics.to_dict("records"):
        if float(row["predictor_complete_fraction"]) < 0.95 or int(row["domain_cells"]) < 5000:
            raise ScoringError(f"candidate predictor/cell gate failed: {row['region']}")
    candidate_cells = int(assigned.notna().sum())
    if candidate_cells != 756_836 or len(cells) - candidate_cells != 387_450:
        raise ScoringError("live geography cell-count invariant failed")
    if len(valid_sets) != 149:
        raise ScoringError("live structural-set invariant failed")


def _valid_set(codes: tuple[str, str, str], metrics: Mapping[str, Mapping[str, Any]], adjacent: Mapping[tuple[str, str], bool], distances: Mapping[tuple[str, str], float]) -> tuple[bool, list[str]]:
    reasons = []
    if len(set(codes)) != 3:
        reasons.append("not_distinct")
    for left, right in itertools.combinations(sorted(codes), 2):
        if adjacent.get((left, right), adjacent.get((right, left), False)):
            reasons.append("adjacent")
        elif distances.get((left, right), distances.get((right, left), 0.0)) < 250.0:
            reasons.append("centroid_distance")
    for code in codes:
        row = metrics[code]
        if float(row["predictor_complete_fraction"]) < 0.95:
            reasons.append(f"{code}_predictor_completeness")
        if int(row["domain_cells"]) < 5000:
            reasons.append(f"{code}_cell_count")
    return not reasons, sorted(set(reasons))


def role_permutation_scores(codes: tuple[str, str, str], values: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    """Choose the best of six role assignments for one unordered region set."""
    candidates = []
    for supported, edge, mosaic in itertools.permutations(sorted(codes)):
        if not values[mosaic].get("mosaic_allowed", True):
            continue
        scores = {
            "supported": float(values[supported]["supported"]),
            "edge": float(values[edge]["edge"]),
            "mosaic": float(values[mosaic]["mosaic"]),
        }
        candidates.append({"roles": {"supported": supported, "edge": edge, "mosaic": mosaic}, "scores": scores, "minimum": min(scores.values()), "sum": sum(scores.values())})
    if not candidates:
        raise ScoringError("no role permutation passes the mosaic role gate")
    candidates.sort(key=lambda row: (-row["minimum"], -row["sum"], tuple(row["roles"][role] for role in ROLES)))
    return candidates[0]


def select_ranked_sets(contexts: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    feasible = [context for context in contexts if context.get("structurally_valid") and context.get("role_feasible", True)]
    ranked = sorted(feasible, key=lambda row: (-float(row["minimum_role_score"]), -float(row["sum_role_scores"]), tuple(sorted(row["regions"]))))
    ambiguous = False
    if len(ranked) > 1 and tuple(sorted(ranked[0]["regions"])) != tuple(sorted(ranked[1]["regions"])):
        min_margin = float(ranked[0]["minimum_role_score"]) - float(ranked[1]["minimum_role_score"])
        sum_margin = float(ranked[0]["sum_role_scores"]) - float(ranked[1]["sum_role_scores"])
        ambiguous = min_margin < 0.01 and sum_margin < 0.02
    return ranked, ambiguous


def _precompute_scoring_arrays(table: pd.DataFrame, assigned: pd.Series, regions: Mapping[str, Any], transform: Mapping[str, Any]) -> dict[str, Any]:
    """Build all geometry and environmental arrays once for the 455 contexts."""
    xy = _projected_xy(table)
    projected_points = points(xy[:, 0], xy[:, 1])
    exclusion_masks = {}
    for code in REGIONS:
        projected_region = gpd.GeoSeries([regions[code]], crs=4326).to_crs(3577).iloc[0]
        exclusion_masks[code] = np.asarray(covers(projected_region.buffer(50_000.0), projected_points), dtype=bool)
    complete = _finite_mask(table, CONTINUOUS)
    complete_indices = np.flatnonzero(complete)
    embeddings = apply_pca(table.iloc[complete_indices], transform)
    safe_assigned = assigned.fillna("").astype(str).to_numpy()
    eval_positions = {code: np.flatnonzero(safe_assigned[complete_indices] == code) for code in REGIONS}
    return {"xy": xy, "exclusion_masks": exclusion_masks, "complete_indices": complete_indices, "embeddings": embeddings, "eval_positions": eval_positions}


def _context_score(arrays: Mapping[str, Any], codes: tuple[str, str, str]) -> dict[str, Any]:
    complete_indices = np.asarray(arrays["complete_indices"], dtype=np.int64)
    exclusion_masks = arrays["exclusion_masks"]
    excluded = np.logical_or.reduce([exclusion_masks[code] for code in codes])
    reference_complete_pool = np.flatnonzero(~excluded[complete_indices])
    reference_positions = even_sample_indices(len(reference_complete_pool), 100_000)
    reference_complete_positions = reference_complete_pool[reference_positions]
    reference_indices = complete_indices[reference_complete_positions]
    if len(reference_indices) == 0:
        raise ScoringError("context has no retained environmental reference")
    reference_embedding = arrays["embeddings"][reference_complete_positions]
    reference_xy = arrays["xy"][reference_indices]
    values = {}
    for code in codes:
        eval_positions = np.asarray(arrays["eval_positions"][code], dtype=np.int64)
        positions = even_sample_indices(len(eval_positions), 2_000)
        evaluation_positions = eval_positions[positions]
        evaluation_indices = complete_indices[evaluation_positions]
        if len(evaluation_indices) == 0:
            values[code] = {"environmental_raw": math.nan, "geographic_raw": math.nan, "evaluation_cells": 0}
            continue
        evaluation_embedding = arrays["embeddings"][evaluation_positions]
        evaluation_xy = arrays["xy"][evaluation_indices]
        values[code] = {
            "environmental_raw": float(np.percentile(_nearest_distances(evaluation_embedding, reference_embedding), 90)),
            "geographic_raw": float(np.median(_nearest_distances(evaluation_xy, reference_xy) / 1000.0)),
            "evaluation_cells": len(evaluation_indices),
            "reference_cells": len(reference_indices),
        }
    return {"regions": list(codes), "values": values, "reference_cells": len(reference_indices), "structurally_valid": True}


def load_context_progress(path: Path, run_identity: str, context_codes: Sequence[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """Load a resumable prefix and reject progress from another input identity."""
    if not path.is_file():
        return []
    progress = json.loads(path.read_text())
    if progress.get("run_identity") != run_identity:
        raise ScoringError("stale context progress run identity")
    contexts = progress.get("contexts", [])
    if not isinstance(contexts, list) or len(contexts) > len(context_codes):
        raise ScoringError("context progress drift")
    if [tuple(item.get("regions", [])) for item in contexts] != list(context_codes)[: len(contexts)]:
        raise ScoringError("context progress order drift")
    return contexts


def preflight(root: Path) -> dict[str, Any]:
    config = _read_config(root)
    nvis_classes = _read_nvis(root)
    cells = _load_cells(root)
    regions = _load_regions(root)
    table = _load_table(root, cells.cell_id.tolist())
    table = cells.merge(table, on="cell_id", how="left", validate="one_to_one", sort=False)
    assigned = assign_regions(cells, regions)
    metrics = _region_metrics(table, assigned, nvis_classes)
    adjacent, distances, _ = _structural_matrix(regions)
    valid_sets = []
    for codes in itertools.combinations(REGIONS, 3):
        valid, reasons = _valid_set(codes, metrics.set_index("region").to_dict("index"), adjacent, distances)
        if valid:
            valid_sets.append(codes)
    _validate_live_invariants(cells, assigned, metrics, valid_sets)
    return {"status": "ready", "run_identity": _run_identity(root), "region_count": len(REGIONS), "domain_cells": len(cells), "candidate_region_cells": int(assigned.notna().sum()), "domain_complement_cells": int(assigned.isna().sum()), "multiply_assigned_cells": 0, "structurally_feasible_set_count": len(valid_sets), "all_context_count": math.comb(len(REGIONS), 3), "config_sha256": _sha(root / CONFIG_PATH), "predictor_sha256": _sha(root / PREDICTOR_PATH), "metrics": metrics.to_dict("records"), "candidate_sets": [list(codes) for codes in valid_sets], "selection_only": config["response_free_scoring"]["environment"]["scaling"]}


def score(root: Path) -> dict[str, Any]:
    config = _read_config(root)
    nvis_classes = _read_nvis(root)
    cells = _load_cells(root)
    regions = _load_regions(root)
    raw = _load_table(root, cells.cell_id.tolist())
    table = cells.merge(raw, on="cell_id", how="inner", validate="one_to_one", sort=False)
    if len(table) != len(cells):
        raise ScoringError("predictor table does not cover frozen domain")
    assigned = assign_regions(cells, regions)
    table["region"] = assigned.to_numpy()
    transform = fit_common_pca(table)
    run_identity = _run_identity(root)
    transform["run_identity"] = run_identity
    out = root / OUTPUT_DIR
    _write_json(out / "transform_receipt.json", transform)
    ledger = table[["cell_id", "row", "column", "longitude", "latitude", "region"]].copy()
    _write_parquet(out / "cell_region_ledger.parquet", ledger)
    _write_json(out / "cell_region_ledger_receipt.json", {"run_identity": run_identity, "row_count": len(ledger), "cell_id_sha256": _digest(ledger.cell_id.tolist()), "ledger_sha256": _sha(out / "cell_region_ledger.parquet")})
    metrics = _region_metrics(table, assigned, nvis_classes)
    metric_map = metrics.set_index("region").to_dict("index")
    adjacent, distances, _ = _structural_matrix(regions)
    valid_sets = []
    for codes in itertools.combinations(REGIONS, 3):
        valid, _ = _valid_set(codes, metric_map, adjacent, distances)
        if valid:
            valid_sets.append(codes)
    _validate_live_invariants(cells, assigned, metrics, valid_sets)
    _write_json(out / "candidate_metrics.json", {"run_identity": run_identity, "rows": metrics.to_dict("records")})
    arrays = _precompute_scoring_arrays(table, assigned, regions, transform)
    progress_path = out / "context_raw_scores.progress.json"
    context_codes = list(itertools.combinations(REGIONS, 3))
    contexts = load_context_progress(progress_path, run_identity, context_codes)
    if contexts and [tuple(item.get("regions", [])) for item in contexts] != context_codes[: len(contexts)]:
        raise ScoringError("context progress order drift")
    for codes in context_codes[len(contexts):]:
        valid, reasons = _valid_set(codes, metric_map, adjacent, distances)
        context = _context_score(arrays, codes)
        context.update({"structurally_valid": valid, "invalid_reasons": reasons})
        contexts.append(context)
        _write_json(progress_path, {"run_identity": run_identity, "completed_contexts": len(contexts), "contexts": contexts})
    raw_values = [(context["regions"], code, context["values"][code]["environmental_raw"], context["values"][code]["geographic_raw"]) for context in contexts for code in context["regions"] if math.isfinite(context["values"][code]["environmental_raw"])]
    if len(raw_values) != 1365:
        raise ScoringError("context member-score accounting drift")
    env_pct = empirical_percentiles([item[2] for item in raw_values])
    geo_pct = empirical_percentiles([item[3] for item in raw_values])
    per_region = {(tuple(codes), code): (float(env), float(geo)) for (codes, code, _, _), env, geo in zip(raw_values, env_pct, geo_pct)}
    frag_pct = dict(zip(metrics.region, empirical_percentiles(metrics.fragmentation.to_numpy(dtype=float))))
    entropy_pct = dict(zip(metrics.region, empirical_percentiles(metrics.alum_entropy_normalized.to_numpy(dtype=float))))
    scored = []
    for context in contexts:
        codes = tuple(context["regions"])
        role_values = {}
        for code in codes:
            env, geo = per_region[(codes, code)]
            role_values[code] = {"supported": (1 - env + geo) / 2, "edge": env, "mosaic": (frag_pct[code] + entropy_pct[code]) / 2, "mosaic_allowed": bool(metric_map[code]["mosaic_allowed"])}
        try:
            best = role_permutation_scores(codes, role_values)
        except ScoringError:
            best = {"roles": None, "scores": {}, "minimum": None, "sum": None}
        scored.append({"regions": list(codes), "structurally_valid": context["structurally_valid"], "role_feasible": best["roles"] is not None, "invalid_reasons": context["invalid_reasons"], "role_assignment": best["roles"], "role_scores": best["scores"], "minimum_role_score": best["minimum"], "sum_role_scores": best["sum"], "raw": context["values"]})
    ranked, ambiguous = select_ranked_sets(scored)
    _write_json(out / "context_raw_scores.json", {"run_identity": run_identity, "context_count": len(contexts), "member_value_count": len(raw_values), "contexts": contexts})
    _write_json(out / "ranked_structurally_feasible_sets.json", {"run_identity": run_identity, "ranked": ranked, "ambiguous": ambiguous, "ambiguity_rule": config["joint_selection"]["ambiguity"]})
    return {"status": "complete", "context_count": len(contexts), "member_value_count": len(raw_values), "feasible_count": len(ranked), "ambiguous": ambiguous, "output_dir": str(OUTPUT_DIR)}


def status(root: Path) -> dict[str, Any]:
    out = root / OUTPUT_DIR
    files = sorted(path.name for path in out.glob("*") if path.is_file()) if out.is_dir() else []
    return {"status": "complete" if "ranked_structurally_feasible_sets.json" in files else "not_scored", "files": files}


def validate(root: Path) -> dict[str, Any]:
    state = status(root)
    if state["status"] != "complete":
        raise ScoringError("score outputs are incomplete")
    required = ("transform_receipt.json", "cell_region_ledger.parquet", "cell_region_ledger_receipt.json", "candidate_metrics.json", "context_raw_scores.json", "ranked_structurally_feasible_sets.json")
    output_dir = root / OUTPUT_DIR
    if any(not (output_dir / name).is_file() for name in required):
        raise ScoringError("required score output missing")
    identity = _run_identity(root)
    transform = json.loads((output_dir / "transform_receipt.json").read_text())
    ledger_receipt = json.loads((output_dir / "cell_region_ledger_receipt.json").read_text())
    metrics_receipt = json.loads((output_dir / "candidate_metrics.json").read_text())
    ranked = json.loads((output_dir / "ranked_structurally_feasible_sets.json").read_text())
    raw = json.loads((output_dir / "context_raw_scores.json").read_text())
    if any(item.get("run_identity") != identity for item in (transform, ledger_receipt, metrics_receipt, ranked, raw)):
        raise ScoringError("score output run identity drift")
    if transform.get("selection_only") is not True or ledger_receipt.get("row_count") != 1_144_286:
        raise ScoringError("transform or ledger receipt drift")
    if _sha(output_dir / "cell_region_ledger.parquet") != ledger_receipt.get("ledger_sha256"):
        raise ScoringError("cell-region ledger checksum drift")
    ledger = pd.read_parquet(output_dir / "cell_region_ledger.parquet", columns=["cell_id", "region"])
    if len(ledger) != 1_144_286 or int(ledger["region"].notna().sum()) != 756_836 or int(ledger["region"].isna().sum()) != 387_450:
        raise ScoringError("cell-region geography invariant drift")
    if raw["context_count"] != 455 or raw["member_value_count"] != 1365:
        raise ScoringError("context accounting drift")
    contexts = raw.get("contexts", [])
    if len(contexts) != 455 or sum(len(context.get("regions", [])) for context in contexts) != 1365:
        raise ScoringError("context ledger accounting drift")
    if Counter(code for context in contexts for code in context.get("regions", [])) != Counter({code: 91 for code in REGIONS}):
        raise ScoringError("context member accounting drift")
    if sum(bool(context.get("structurally_valid")) for context in contexts) != 149:
        raise ScoringError("structural-set count drift")
    for context in contexts:
        for value in context.get("values", {}).values():
            if not np.isfinite(float(value["environmental_raw"])) or not np.isfinite(float(value["geographic_raw"])):
                raise ScoringError("non-finite context metric")
    for row in metrics_receipt.get("rows", []):
        for field, value in row.items():
            if field != "region" and isinstance(value, (int, float)) and not np.isfinite(float(value)):
                raise ScoringError("non-finite candidate metric")
    for row in ranked.get("ranked", []):
        if not np.isfinite(float(row["minimum_role_score"])) or not np.isfinite(float(row["sum_role_scores"])) or any(not np.isfinite(float(value)) for value in row.get("role_scores", {}).values()):
            raise ScoringError("non-finite role score")
    return {"status": "valid", "context_count": raw["context_count"], "member_value_count": raw["member_value_count"], "structural_set_count": 149, "ranked_count": len(ranked["ranked"]), "ambiguous": ranked["ambiguous"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "score", "status", "validate"))
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        result = {"preflight": preflight, "score": score, "status": status, "validate": validate}[args.command](args.root.resolve())
    except (OSError, ScoringError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
