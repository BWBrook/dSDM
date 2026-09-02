"""Goal 050: model-free SEAWFB modelling foundation.

This module freezes a private retained-training cell substrate, sparse response
memberships, spatial folds, leakage-safe species blocks, learning-curve plans,
and training-only feature transforms.  It deliberately contains no model,
prediction, outcome, or threshold-fitting code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import geopandas as gpd
from pyproj import Transformer
from shapely import covers, make_valid, points

CONFIG = Path("config/goal050_seawfb_modeling_foundation.json")
PRIVATE = Path("data/processed/dsdm/goal050-seawfb-modeling-foundation")
CONTINUOUS = [f"bio{i:02d}" for i in range(1, 20)] + ["elevation_mean", "elevation_sd"]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
PREDICTORS = CONTINUOUS + CATEGORICAL
REGIONS = ("NCP", "SEH", "NNC")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CELL_FIELDS = ["cell_id", "block_x", "block_y", "fold", "predictor_complete", "effort_richness", *PREDICTORS]


class Goal050Error(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Goal050Error(reason)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def stable_hash(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16], 16)


def _atomic_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        pq.write_table(table, temporary, compression="zstd", use_dictionary=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(root: Path) -> dict[str, Any]:
    config = json.loads((root / CONFIG).read_text())
    _require(config.get("schema_version") == "goal050-seawfb-modeling-foundation-v1", "config_schema_drift")
    _require(config.get("regions") == list(REGIONS), "region_contract_drift")
    _require(config["predictors"]["continuous"] == CONTINUOUS and config["predictors"]["categorical"] == CATEGORICAL, "predictor_order_drift")
    _require(config["effort_support"] == {"primary_x": 10, "evaluation_only_x": 20}, "effort_threshold_drift")
    _require(set(config.get("provenance", {})) == {"generator_source", "uv_lock", "ibra_authority"}, "provenance_contract_drift")
    return config


def _path(root: Path, config: Mapping[str, Any], section: str, name: str) -> Path:
    return root / (config[section][name] if section in config else name)


def _read_upstream(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    paths = {key: root / value for key, value in config["upstream"].items()}
    for key, path in paths.items():
        _require(path.is_file(), f"missing_upstream:{key}")
    domain = pd.read_csv(paths["goal048_domain"], usecols=["cell_id", "row", "column", "longitude", "latitude"])
    ledger = pd.read_parquet(paths["goal048_region_ledger"], columns=["cell_id", "longitude", "latitude", "region"])
    pred = pd.read_parquet(paths["goal048_predictors"], columns=["cell_id", *PREDICTORS])
    _require(domain.cell_id.is_unique and ledger.cell_id.is_unique and pred.cell_id.is_unique, "upstream_duplicate_cell_id")
    ids = set(domain.cell_id.astype(str))
    _require(set(ledger.cell_id.astype(str)) == ids and set(pred.cell_id.astype(str)) == ids, "upstream_cell_id_mismatch")
    registry = json.loads(paths["goal049_registry"].read_text())
    completion = json.loads(paths["goal049_completion"].read_text())
    _require(completion.get("status") == "complete", "goal049_completion_not_complete")
    completion_bindings = completion.get("bindings", {})
    _require(completion_bindings.get("canonical_species_cells_sha256") == sha256(paths["goal049_canonical"]), "goal049_canonical_receipt_hash_drift")
    _require(completion_bindings.get("panel_ledger_sha256") == sha256(paths["goal049_panel"]), "goal049_panel_receipt_hash_drift")
    _require(completion_bindings.get("registry_sha256") == sha256(paths["goal049_registry"]), "goal049_registry_receipt_hash_drift")
    _require(completion_bindings.get("taxonomy_sha256") == sha256(paths["goal049_taxonomy"]), "goal049_taxonomy_receipt_hash_drift")
    completion_counts = completion.get("counts", {})
    _require(completion_counts.get("active_species") == 505 and completion_counts.get("effort_donors") == 505 and completion_counts.get("auxiliary_heads") == 259 and completion_counts.get("focal_candidates") == 259 and completion_counts.get("common_primary_targets") == 73, "goal049_completion_count_drift")
    _require(json.loads(paths["goal048_prerequisite"].read_text()).get("joint_sha256"), "goal048_prerequisite_receipt_invalid")
    panel = pd.read_parquet(paths["goal049_panel"], columns=["species", "training_pass", "regional_secondary_member", "primary_common_member"])
    _require(panel.species.nunique() == 259, "panel_species_count_drift")
    training_heads = sorted(panel.loc[panel.training_pass, "species"].astype(str).unique())
    focal = sorted(panel.loc[panel.regional_secondary_member, "species"].astype(str).unique())
    primary = sorted(panel.loc[panel.primary_common_member, "species"].astype(str).unique())
    _require((len(training_heads), len(focal), len(primary)) == (183, 157, 73), "frozen_panel_counts_drift")
    _require(set(primary) <= set(focal) <= set(training_heads), "panel_nesting_drift")
    _require(len(registry.get("rows", [])) == 653, "registry_count_drift")
    return {"paths": paths, "domain": domain, "ledger": ledger, "predictors": pred, "training_heads": training_heads, "focal": focal, "primary": primary}


def projected_blocks(longitude: Sequence[float], latitude: Sequence[float], block_m: int = 50_000) -> tuple[np.ndarray, np.ndarray]:
    x, y = Transformer.from_crs(4326, 3577, always_xy=True).transform(np.asarray(longitude), np.asarray(latitude))
    return np.floor(np.asarray(x) / block_m).astype(np.int64), np.floor(np.asarray(y) / block_m).astype(np.int64)


def assign_spatial_folds(block_x: Sequence[int], block_y: Sequence[int], seed: int, n_folds: int = 5) -> np.ndarray:
    """Assign complete projected blocks with the frozen Goal 043 hash rule."""
    bx, by = np.asarray(block_x), np.asarray(block_y)
    blocks, inverse = np.unique(np.column_stack((bx, by)), axis=0, return_inverse=True)
    assignment = _assign_block_folds(blocks, seed, n_folds)
    return assignment[inverse]


def _assign_block_folds(blocks: np.ndarray, seed: int, n_folds: int = 5) -> np.ndarray:
    """Apply the frozen Goal 043 hash assignment to complete blocks."""
    _require(n_folds == 5, "spatial_fold_count_drift")
    return np.fromiter(
        (int.from_bytes(hashlib.sha256(f"{int(seed)}:50:{int(x)}:{int(y)}".encode()).digest()[:8], "big") % n_folds for x, y in blocks),
        dtype=np.int8,
        count=len(blocks),
    )


def lazy_complement_richness(full_richness: Sequence[int], held_presence_counts: Sequence[int]) -> np.ndarray:
    """Exact lazy complement formula: R_complement(c)=R_full(c)-sum held I_s(c)."""
    full = np.asarray(full_richness, dtype=np.int64)
    held = np.asarray(held_presence_counts, dtype=np.int64)
    _require(full.shape == held.shape and np.all(held >= 0) and np.all(held <= full), "invalid_lazy_complement")
    return (full - held).astype(np.uint16)


def complement_heads(training_heads: Sequence[str], held_species: Iterable[str]) -> list[str]:
    """Return the species-block complement without materialising responses."""
    held = set(map(str, held_species)); names = sorted(map(str, training_heads))
    _require(held <= set(names), "held_species_not_training_head")
    return [name for name in names if name not in held]


def lazy_block_richness(full_richness: Sequence[int], memberships: Mapping[str, Sequence[bool]], held_species: Iterable[str]) -> np.ndarray:
    """Subtract held-head membership indicators from full donor richness."""
    held = list(map(str, held_species)); _require(all(name in memberships for name in held), "held_membership_missing")
    if not held:
        return np.asarray(full_richness, dtype=np.uint16).copy()
    indicators = np.sum(np.vstack([np.asarray(memberships[name], dtype=np.int8) for name in held]), axis=0)
    return lazy_complement_richness(full_richness, indicators)


def target_background_masks(presence: Sequence[bool], richness: Sequence[int], x10: int = 10, x20: int = 20) -> tuple[np.ndarray, np.ndarray]:
    present, rich = np.asarray(presence, dtype=bool), np.asarray(richness)
    _require(present.shape == rich.shape and x10 > 0 and x20 >= x10, "invalid_background_inputs")
    return (~present) & (rich >= x10), (~present) & (rich >= x20)


def fold_gate_metrics(presence: Mapping[str, np.ndarray], richness: np.ndarray, folds: np.ndarray, complete: np.ndarray, target_names: Sequence[str], thresholds: Mapping[str, int]) -> dict[str, Any]:
    """Return response/support-only metrics for a candidate partition."""
    n = int(folds.max()) + 1
    per_fold: list[dict[str, Any]] = []
    target_background = {s: target_background_masks(presence[s], richness)[0] for s in target_names}
    for fold in range(n):
        validation = folds == fold
        training = ~validation
        target_pres = {s: int(np.sum(presence[s] & validation)) for s in target_names}
        target_bg = {s: int(np.sum(target_background[s] & validation & complete)) for s in target_names}
        per_fold.append({"fold": fold, "map_share": float(np.mean(validation)), "target_validation_presences": target_pres, "target_validation_x10_backgrounds": target_bg})
    shares = [item["map_share"] for item in per_fold]
    gate = all(thresholds["primary_validation_presences"] <= per_fold[f]["target_validation_presences"].get(s, 0) for f in range(n) for s in target_names)
    bg_gate = all(thresholds["validation_backgrounds"] <= per_fold[f]["target_validation_x10_backgrounds"].get(s, 0) for f in range(n) for s in target_names)
    return {"folds": per_fold, "map_share_min": min(shares), "map_share_max": max(shares), "primary_presence_gate": gate, "adequate_background_gate": bg_gate, "complete_predictor_rows": int(np.sum(complete)), "map_share_gate": min(shares) >= 0.15 and max(shares) <= 0.25}


def select_fold_seed(block_x: Sequence[int], block_y: Sequence[int], presence: Mapping[str, np.ndarray], richness: np.ndarray, complete: np.ndarray, primary: Sequence[str], focal: Sequence[str], training_heads: Sequence[str], seed_range: Iterable[int] = range(512), thresholds: Mapping[str, int] | None = None) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    """Search seeds using only map/support gates; ties are deterministic."""
    thresholds = thresholds or {"primary_validation_presences": 30, "focal_validation_presences": 10, "head_validation_presences": 1, "head_complement_training_presences": 100, "validation_backgrounds": 100}
    bx, by = np.asarray(block_x), np.asarray(block_y)
    blocks, inverse = np.unique(np.column_stack((bx, by)), axis=0, return_inverse=True)
    block_sizes = np.bincount(inverse, minlength=len(blocks))
    block_presence = {s: np.bincount(inverse, weights=np.asarray(values, dtype=np.int8), minlength=len(blocks)).astype(np.int64) for s, values in presence.items()}
    block_background = {s: np.bincount(inverse, weights=((~np.asarray(values, dtype=bool)) & (np.asarray(richness) >= 10) & np.asarray(complete, dtype=bool)).astype(np.int8), minlength=len(blocks)).astype(np.int64) for s, values in presence.items()}
    totals_presence = {s: int(np.sum(values)) for s, values in presence.items()}
    candidates: list[dict[str, Any]] = []
    for seed in seed_range:
        # Evaluate candidate folds from block-level sufficient statistics. This
        # preserves the exact cell-level result while making the 512-seed search
        # practical for the 1.1M-cell domain.
        block_folds = _assign_block_folds(blocks, seed)
        fold_counts = np.bincount(block_folds, weights=block_sizes, minlength=5)
        fold_rows = []
        for fold in range(5):
            selected = block_folds == fold
            fold_rows.append({"fold": fold, "map_share": float(fold_counts[fold] / len(bx)), "target_validation_presences": {s: int(block_presence[s][selected].sum()) for s in primary}, "target_validation_x10_backgrounds": {s: int(block_background[s][selected].sum()) for s in primary}})
        metrics = {"folds": fold_rows, "map_share_min": min(row["map_share"] for row in fold_rows), "map_share_max": max(row["map_share"] for row in fold_rows), "primary_presence_gate": all(row["target_validation_presences"][s] >= thresholds["primary_validation_presences"] for row in fold_rows for s in primary), "adequate_background_gate": all(int(block_background[s][block_folds == f].sum()) >= thresholds["validation_backgrounds"] for s in focal for f in range(5)), "complete_predictor_rows": int(np.sum(complete))}
        metrics["map_share_gate"] = metrics["map_share_min"] >= 0.15 and metrics["map_share_max"] <= 0.25
        # All focal/head presence and complementary presence gates are explicit.
        ok = metrics["map_share_gate"] and metrics["primary_presence_gate"] and metrics["adequate_background_gate"]
        focal_gate = all(int(block_presence[species][block_folds == f].sum()) >= thresholds["focal_validation_presences"] for species in focal for f in range(5))
        ok &= focal_gate
        head_gate = True; complement_gate = True
        for species in training_heads:
            head_gate &= all(int(block_presence[species][block_folds == f].sum()) >= thresholds["head_validation_presences"] for f in range(5))
            complement_gate &= all(totals_presence[species] - int(block_presence[species][block_folds == f].sum()) >= thresholds["head_complement_training_presences"] for f in range(5))
        ok &= head_gate and complement_gate
        metrics["focal_presence_gate"] = bool(focal_gate); metrics["head_presence_gate"] = bool(head_gate); metrics["head_complement_gate"] = bool(complement_gate)
        metrics["eligible"] = bool(ok); metrics["seed"] = int(seed)
        focal_share_deviation = [abs(int(block_presence[s][block_folds == f].sum()) / totals_presence[s] - 0.2) for s in focal for f in range(5) if totals_presence[s]]
        metrics["worst_focal_presence_share_deviation"] = float(max(focal_share_deviation, default=1.0))
        metrics["map_share_deviation"] = float(max(abs(row["map_share"] - 0.2) for row in metrics["folds"]))
        metrics["fold_assignment_digest"] = digest(block_folds[inverse].tolist())
        candidates.append(metrics)
    eligible = [item for item in candidates if item["eligible"]]
    _require(eligible, "no_spatial_fold_seed_passes_frozen_gates")
    chosen = min(eligible, key=lambda item: (item["worst_focal_presence_share_deviation"], item["map_share_deviation"], item["seed"]))
    return int(chosen["seed"]), chosen, candidates


def species_blocks(focal: Sequence[str], n_blocks: int = 10) -> dict[str, int]:
    _require(len(focal) == 157 and n_blocks == 10, "focal_block_contract_drift")
    ordered = sorted(map(str, focal), key=lambda species: (stable_hash("focal-block", species), species))
    return {species: i % n_blocks for i, species in enumerate(ordered)}


def nested_hash_subset(items: Sequence[str], fractions: Sequence[float], strata: Mapping[str, Any] | None = None, seed: str = "goal050") -> dict[str, list[str]]:
    """Nested stable-hash subsets, optionally balancing by a supplied stratum."""
    names = sorted(map(str, items), key=lambda item: (stable_hash(seed, item), item))
    if strata:
        groups: dict[Any, list[str]] = {}
        for item in names: groups.setdefault(strata[item], []).append(item)
        names = [item for key in sorted(groups, key=str) for item in sorted(groups[key], key=lambda x: (stable_hash(seed, key, x), x))]
    result: dict[str, list[str]] = {}; previous: list[str] = []
    for fraction in fractions:
        count = len(names) if fraction == 1.0 else int(np.ceil(len(names) * float(fraction)))
        previous = names[:count]
        result[str(fraction)] = list(previous)
    return result


def nested_stratified_indices(items: Sequence[str], fractions: Sequence[float], strata: Mapping[str, Any], seed: str = "goal050") -> dict[str, list[str]]:
    """Stable nested sampling with deterministic proportional stratum quotas."""
    names = sorted(map(str, items)); groups: dict[str, list[str]] = {}
    for item in names:
        _require(item in strata, "missing_sampling_stratum")
        groups.setdefault(str(strata[item]), []).append(item)
    ordered = {key: sorted(values, key=lambda item: (stable_hash(seed, key, item), item)) for key, values in groups.items()}
    result: dict[str, list[str]] = {}
    for fraction in fractions:
        total = len(names) if float(fraction) == 1.0 else int(np.ceil(len(names) * float(fraction)))
        quotas = {key: int(np.floor(total * len(values) / len(names))) for key, values in ordered.items()}
        for key in sorted(ordered, key=lambda key: (stable_hash(seed, key), key)):
            if sum(quotas.values()) < total and quotas[key] < len(ordered[key]):
                quotas[key] += 1
        result[str(fraction)] = sorted((item for key in ordered for item in ordered[key][:quotas[key]]), key=lambda item: (stable_hash(seed, item), item))
    return result


def nested_response_rows(cell_ids: Sequence[str], presence: Sequence[bool], richness: Sequence[int], folds: Sequence[int], held_fold: int, fractions: Sequence[float] = (0.25, 0.5, 1.0), seed: str = "goal050") -> dict[str, list[str]]:
    """Return nested target/background row IDs for one held spatial fold.

    Rows are restricted to non-held folds and stratified by spatial fold and
    binary class. IDs remain a private intermediate; tracked receipts retain
    only counts and selection digests.
    """
    ids = np.asarray(cell_ids, dtype=str); y = np.asarray(presence, dtype=bool); rich = np.asarray(richness); fold = np.asarray(folds)
    _require(len(ids) == len(y) == len(rich) == len(fold) and len(set(ids)) == len(ids), "response_row_input_mismatch")
    eligible = (fold != held_fold) & (y | ((~y) & (rich >= 10)))
    strata = {str(ids[i]): f"{int(fold[i])}:{int(y[i])}" for i in np.flatnonzero(eligible)}
    return nested_stratified_indices(ids[eligible].tolist(), fractions, strata, seed=f"{seed}:held{held_fold}")


def auxiliary_learning_sets(training_heads: Sequence[str], focal_blocks: Mapping[str, int], held_block: int) -> dict[str, list[str]]:
    """Nested 20/80/full auxiliary sets from each held-block complement."""
    held = [species for species, block in focal_blocks.items() if block == held_block]
    complement = complement_heads(training_heads, held)
    ordered = sorted(complement, key=lambda species: (stable_hash("auxiliary-order", species), species))
    return {"20": ordered[:20], "80": ordered[:80], "full": ordered}


def fit_transforms(frame: pd.DataFrame, training_masks: Mapping[str, np.ndarray]) -> dict[str, Any]:
    """Fit means/population SD and explicit categorical vocabularies per mask."""
    transforms: dict[str, Any] = {}
    for name, mask in training_masks.items():
        mask = np.asarray(mask, dtype=bool); _require(len(mask) == len(frame) and mask.any(), "empty_transform_training_mask")
        continuous: dict[str, Any] = {}; categorical: dict[str, Any] = {}
        for col in CONTINUOUS:
            values = pd.to_numeric(frame.loc[mask, col], errors="coerce").to_numpy(dtype=float); values = values[np.isfinite(values)]
            _require(len(values) > 0, f"no_finite_training_values:{col}")
            mean = float(np.mean(values)); sd = float(np.std(values, ddof=0)); continuous[col] = {"mean": mean, "population_sd": sd if sd > 0 else 1.0}
        for col in CATEGORICAL:
            values = frame.loc[mask, col].astype("string"); vocab = sorted({str(v) for v in values.dropna()})
            categorical[col] = ["__MISSING__", "__UNSEEN__", *vocab]
        transforms[name] = {"continuous": continuous, "categorical": categorical}
    return transforms


def apply_transforms(frame: pd.DataFrame, transform: Mapping[str, Any]) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for col in CONTINUOUS:
        spec = transform["continuous"][col]; values = pd.to_numeric(frame[col], errors="coerce").fillna(spec["mean"])
        out[col] = (values - spec["mean"]) / spec["population_sd"]
    for col in CATEGORICAL:
        vocab = set(transform["categorical"][col]); values = frame[col].astype("string").fillna("__MISSING__").astype(str)
        out[col] = values.where(values.isin(vocab), "__UNSEEN__")
    return out


def _privacy(value: Any, path: str = "") -> None:
    forbidden = ("longitude", "latitude", "cell_id", "species_cells", "raw_occurrence", "model_outcome", "prediction")
    if isinstance(value, dict):
        for key, item in value.items():
            _require(not any(token in str(key).lower() for token in forbidden), f"tracked_privacy_key:{path}/{key}")
            _privacy(item, f"{path}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value): _privacy(item, f"{path}/{i}")
    elif isinstance(value, str):
        lower = value.lower(); _require("cell_id" not in lower and "longitude" not in lower and "latitude" not in lower, f"tracked_privacy_value:{path}")


def build(root: Path) -> dict[str, Any]:
    root = Path(root); config = load_config(root)
    private = root / PRIVATE
    # A prior completion marker is never evidence for a new build.
    (private / config["private_outputs"]["run_exit"]).unlink(missing_ok=True)
    upstream = _read_upstream(root, config)
    domain = upstream["domain"].sort_values("cell_id", kind="mergesort").reset_index(drop=True)
    ledger = upstream["ledger"].set_index("cell_id").loc[domain.cell_id].reset_index()
    pred = upstream["predictors"].set_index("cell_id").loc[domain.cell_id].reset_index()
    bx, by = projected_blocks(domain.longitude, domain.latitude)
    # Goal 049's exact official whole-region geometries and simultaneous buffers.
    xy = np.column_stack(Transformer.from_crs(4326, 3577, always_xy=True).transform(domain.longitude.to_numpy(), domain.latitude.to_numpy()))
    ibra_path = root / config["provenance"]["ibra_authority"]
    _require(ibra_path.is_file(), "missing_goal048_ibra_authority")
    ibra = gpd.read_file(ibra_path).to_crs(3577)
    _require(len(ibra) == 419 and ibra["REG_CODE_7"].nunique() == 89, "ibra_authority_identity_drift")
    projected_points = points(xy[:, 0], xy[:, 1])
    buffer = np.zeros(len(domain), dtype=bool)
    for code in REGIONS:
        geometry = make_valid(ibra.loc[ibra["REG_CODE_7"] == code].geometry.union_all()).buffer(50_000.0)
        buffer |= np.asarray(covers(geometry, projected_points), dtype=bool)
    _require(np.all(buffer[ledger.region.astype("string").isin(REGIONS).to_numpy()]), "selected_region_outside_buffer")
    retained = ~buffer
    complete = pred[CONTINUOUS].notna().all(axis=1).to_numpy() & pred[CATEGORICAL].notna().all(axis=1).to_numpy()
    richness = np.zeros(len(domain), dtype=np.uint16)
    canonical = pq.ParquetFile(upstream["paths"]["goal049_canonical"])
    cell_index = {cell: i for i, cell in enumerate(domain.cell_id.astype(str))}
    presence: dict[str, np.ndarray] = {s: np.zeros(len(domain), dtype=bool) for s in upstream["training_heads"]}
    for batch in canonical.iter_batches(columns=["species", "cell_id"], batch_size=250_000):
        species = batch.column("species").to_pylist(); cells = batch.column("cell_id").to_pylist()
        for sp, cell in zip(species, cells):
            if sp in presence and cell in cell_index:
                i = cell_index[cell]; presence[sp][i] = True
            # all 505 effort donors contribute; non-head donors are reconstructed from
            # the canonical table by counting rows only once per species-cell row.
        # Count all donors without retaining their memberships.
        for sp, cell in zip(species, cells):
            if cell in cell_index:
                richness[cell_index[cell]] += 1
    richness = np.minimum(richness, 505).astype(np.uint16)
    # Fold selection is response/support-only and is run on retained cells with complete predictors.
    retained_presence = {s: values & retained for s, values in presence.items()}
    thresholds = config["folds"]
    seed, chosen, search = select_fold_seed(bx[retained], by[retained], {s: v[retained] for s, v in retained_presence.items()}, richness[retained], complete[retained], upstream["primary"], upstream["focal"], upstream["training_heads"], range(512), thresholds)
    folds = assign_spatial_folds(bx[retained], by[retained], seed)
    _require(chosen["fold_assignment_digest"] == digest(folds.tolist()), "fold_assignment_search_write_mismatch")
    cell_frame = pred.loc[retained, ["cell_id", *PREDICTORS]].copy().reset_index(drop=True)
    cell_frame.insert(1, "block_x", bx[retained]); cell_frame.insert(2, "block_y", by[retained]); cell_frame.insert(3, "fold", folds); cell_frame.insert(4, "predictor_complete", complete[retained]); cell_frame.insert(5, "effort_richness", richness[retained].astype(np.uint16))
    private.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(private / config["private_outputs"]["cells"], pa.Table.from_pandas(cell_frame, preserve_index=False))
    membership_rows = []
    for species in upstream["training_heads"]:
        indices = np.flatnonzero(presence[species] & retained)
        membership_rows.extend((species, str(domain.cell_id.iloc[i])) for i in indices)
    membership = pd.DataFrame(membership_rows, columns=["species", "cell_id"]).sort_values(["species", "cell_id"], kind="mergesort")
    _atomic_parquet(private / config["private_outputs"]["memberships"], pa.Table.from_pandas(membership, preserve_index=False))
    full_folds = np.full(len(domain), -1, dtype=np.int8); full_folds[retained] = folds
    masks = {f"fold_{fold}": retained & (full_folds != fold) for fold in range(5)}; masks["retained_full"] = retained
    transform_frame = pred.copy(); transforms = fit_transforms(transform_frame, masks)
    _atomic_json(root / config["tracked_outputs"]["transforms"], {"schema_version": "goal050-transforms-v1", "seed": seed, "training_cells": {k: int(v.sum()) for k, v in masks.items()}, "transforms": transforms, "bindings": {"config_sha256": sha256(root / CONFIG)}})
    blocks = species_blocks(upstream["focal"])
    auxiliary_sets = {str(block): auxiliary_learning_sets(upstream["training_heads"], blocks, block) for block in range(10)}
    crossfit = {"schema_version": "goal050-crossfit-v1", "focal_blocks": blocks, "block_sizes": {str(i): sum(v == i for v in blocks.values()) for i in range(10)}, "lazy_complement_formula": "R_complement(c)=R_full(c)-sum_{s in held block} I_s(c)", "richness_scope": {"auxiliary_pretraining_backgrounds": "held-block-adjusted complement richness", "target_fine_tuning_and_evaluation": "target-specific X10 background mask using full richness; a target-absent row contributes zero for that target while co-block species remain legitimate donors"}, "full_complement_sizes": {"15_species_block": 168, "16_species_block": 167}, "auxiliary_sets": auxiliary_sets}
    _atomic_json(private / config["private_outputs"]["crossfit"], crossfit)
    row_plan = []
    retained_ids = domain.loc[retained, "cell_id"].astype(str).to_numpy()
    for target in upstream["focal"]:
        for held_fold in range(5):
            fractions = (0.25, 0.5, 1.0) if target in upstream["primary"] else (1.0,)
            subsets = nested_response_rows(retained_ids, retained_presence[target][retained], richness[retained], folds, held_fold, fractions=fractions, seed=f"{target}")
            if target in upstream["primary"]:
                ordered = [subsets[str(fraction)] for fraction in fractions]
                _require(set(ordered[0]) <= set(ordered[1]) <= set(ordered[2]), "response_curve_subset_not_nested")
            row_plan.append({"target": target, "held_fold": held_fold, "endpoint_plan": "nested_25_50_100" if target in upstream["primary"] else "full_only", "fractions": {fraction: {"count": len(values), "selection_digest": digest(values)} for fraction, values in subsets.items()}})
    curve = {"schema_version": "goal050-learning-curves-v1", "unique_endpoints": 5, "auxiliary": {"20": {"heads": 20, "target_fraction": 1.0}, "80": {"heads": 80, "target_fraction": 1.0}, "full": {"heads": "block_complement", "sizes_by_block": {str(block): len(auxiliary_sets[str(block)]["full"]) for block in range(10)}, "target_fraction": 1.0}}, "target": {str(frac): {"target_fraction": frac, "auxiliary_heads": "block_complement", "auxiliary_sizes_by_block": {str(block): len(auxiliary_sets[str(block)]["full"]) for block in range(10)} } for frac in [0.25, 0.5, 1.0]}, "richness_scope": "Target fine-tuning/evaluation uses target-specific X10 against full richness; held-block-adjusted richness is auxiliary-pretraining-only.", "applies_to": {"primary_targets": upstream["primary"], "full_full_focal_targets": upstream["focal"]}, "response_row_plan": row_plan, "target_sampling_rule": "stable hashes stratified by spatial fold and binary class; nested subsets"}
    _atomic_json(private / config["private_outputs"]["curves"], curve)
    manifest = {"schema_version": "goal050-manifest-v1", "status": "complete", "seed": seed, "counts": {"domain_cells": len(domain), "retained_training_cells": int(retained.sum()), "predictor_complete_cells": int(np.sum(retained & complete)), "effort_donors": 505, "training_heads": 183, "focal_targets": 157, "primary_targets": 73, "sparse_memberships": len(membership)}, "fold_search": {"selected_seed": seed, "selected": chosen, "searched_seeds": len(search), "model_metrics_used": False}, "auxiliary_complement_counts": {str(block): len(auxiliary_sets[str(block)]["full"]) for block in range(10)}, "privacy": {"coordinates_tracked": False, "species_cell_payload_tracked": False, "models": 0, "outcomes": 0}, "bindings": {"config": sha256(root / CONFIG), **{key: sha256(path) for key, path in upstream["paths"].items()}, "cells": sha256(private / config["private_outputs"]["cells"]), "memberships": sha256(private / config["private_outputs"]["memberships"]), "crossfit": sha256(private / config["private_outputs"]["crossfit"]), "curves": sha256(private / config["private_outputs"]["curves"]), "transforms": sha256(root / config["tracked_outputs"]["transforms"])}}
    manifest["counts"].update({
        "response_row_plan_entries": len(row_plan),
        "response_row_plan_primary_entries": 73 * 5,
        "response_row_plan_full_only_entries": 84 * 5,
    })
    manifest["bindings"].update({key: sha256(root / value) for key, value in config["provenance"].items()})
    manifest["richness_scope"] = {"auxiliary_pretraining_backgrounds": "held-block-adjusted complement richness", "target_fine_tuning_and_evaluation": "target-specific X10 background mask using full richness; target-absent rows already contribute zero for that target and co-block species remain donors"}
    manifest["fold_search"]["eligible_seed_count"] = sum(bool(item.get("eligible")) for item in search)
    _privacy(manifest); _atomic_json(root / config["tracked_outputs"]["manifest"], manifest)
    decision = {"schema_version": "goal050-decision-receipt-v1", "status": "complete", "selected_seed": seed, "fold_count": 5, "x10_primary": True, "x20_evaluation_only": True, "model_fitting": False, "outer_regions_opened": False, "bindings": {"manifest_sha256": sha256(root / config["tracked_outputs"]["manifest"]), "transforms_sha256": sha256(root / config["tracked_outputs"]["transforms"])}, "privacy": {"coordinates_tracked": False, "species_cell_payload_tracked": False, "models": 0, "outcomes": 0}}
    decision["richness_scope"] = manifest["richness_scope"]
    _privacy(decision); _atomic_json(root / config["tracked_outputs"]["decision"], decision)
    validation = validate(root, tracked_only=False, require_run_exit=False); _atomic_json(root / config["tracked_outputs"]["validation"], validation)
    _atomic_json(private / config["private_outputs"]["run_exit"], {"status": "complete", "manifest_sha256": sha256(root / config["tracked_outputs"]["manifest"])})
    validation = validate(root, tracked_only=False); _atomic_json(root / config["tracked_outputs"]["validation"], validation)
    return manifest


def validate(root: Path, tracked_only: bool = False, require_run_exit: bool = True) -> dict[str, Any]:
    root = Path(root); config = load_config(root)
    private_required = ("cells", "memberships", "crossfit", "curves", "run_exit") if require_run_exit else ("cells", "memberships", "crossfit", "curves")
    required = [root / config["tracked_outputs"][name] for name in ("transforms", "manifest", "decision")] + ([] if tracked_only else [root / PRIVATE / config["private_outputs"][name] for name in private_required])
    for path in required: _require(path.is_file(), f"missing_output:{path}")
    manifest = json.loads((root / config["tracked_outputs"]["manifest"]).read_text()); decision = json.loads((root / config["tracked_outputs"]["decision"]).read_text()); transforms = json.loads((root / config["tracked_outputs"]["transforms"]).read_text())
    _privacy(manifest); _privacy(decision); _require(manifest.get("status") == "complete" and decision.get("status") == "complete", "incomplete_receipt")
    _require(manifest.get("fold_search", {}).get("eligible_seed_count") == 4, "eligible_seed_count_drift")
    _require(decision.get("selected_seed") == manifest.get("seed"), "seed_binding_drift"); _require(decision.get("x10_primary") is True and decision.get("x20_evaluation_only") is True, "threshold_contract_drift")
    _require(transforms.get("bindings", {}).get("config_sha256") == sha256(root / CONFIG), "transform_config_binding_drift")
    private = root / PRIVATE
    for key, expected in manifest.get("bindings", {}).items():
        if key == "config":
            path = root / CONFIG
        elif key in config["upstream"]:
            path = root / config["upstream"][key]
        elif key in config["private_outputs"]:
            if tracked_only:
                continue
            path = private / config["private_outputs"][key]
        elif key in config["provenance"]:
            path = root / config["provenance"][key]
        elif key == "transforms":
            path = root / config["tracked_outputs"]["transforms"]
        else:
            raise Goal050Error(f"unknown_manifest_binding:{key}")
        _require(path.is_file() and sha256(path) == expected, f"output_hash_drift:{key}")
    _require(decision.get("bindings", {}).get("manifest_sha256") == sha256(root / config["tracked_outputs"]["manifest"]), "decision_manifest_binding_drift")
    _require(decision.get("bindings", {}).get("transforms_sha256") == sha256(root / config["tracked_outputs"]["transforms"]), "decision_transform_binding_drift")
    _require(set(transforms.get("transforms", {})) == {*(f"fold_{i}" for i in range(5)), "retained_full"}, "transform_set_drift")
    if not tracked_only:
        if require_run_exit:
            receipt = json.loads((private / config["private_outputs"]["run_exit"]).read_text())
            _require(receipt.get("status") == "complete", "run_exit_incomplete")
            _require(receipt.get("manifest_sha256") == sha256(root / config["tracked_outputs"]["manifest"]), "run_exit_manifest_binding_drift")
        cells = pq.read_table(private / config["private_outputs"]["cells"]).to_pandas(); memberships = pq.read_table(private / config["private_outputs"]["memberships"]).to_pandas()
        _require(list(cells.columns) == CELL_FIELDS and cells.cell_id.is_unique and cells.fold.between(0, 4).all(), "cell_schema_or_fold_drift")
        _require(cells.effort_richness.dtype == np.dtype("uint16") and memberships.species.nunique() == 183 and memberships.duplicated().sum() == 0, "membership_schema_drift")
        upstream = _read_upstream(root, config)
        _require(set(memberships.cell_id.astype(str)) <= set(cells.cell_id.astype(str)) and set(memberships.species.astype(str)) <= set(upstream["training_heads"]), "membership_domain_drift")
        index = {cell: i for i, cell in enumerate(cells.cell_id.astype(str))}
        presence = {species: np.zeros(len(cells), dtype=bool) for species in upstream["training_heads"]}
        for species, group in memberships.groupby("species", sort=False):
            presence[str(species)][np.fromiter((index[cell] for cell in group.cell_id.astype(str)), dtype=np.int64)] = True
        thresholds = config["folds"]; folds = cells.fold.to_numpy(); complete = cells.predictor_complete.to_numpy(bool); richness = cells.effort_richness.to_numpy(np.uint16)
        _require(chosen := manifest.get("fold_search", {}).get("selected"), "missing_selected_fold_receipt")
        actual = fold_gate_metrics(presence, richness, folds, complete, upstream["primary"], thresholds)
        _require(actual["map_share_gate"] and actual["primary_presence_gate"], "written_fold_primary_gate_failed")
        for species in upstream["focal"]:
            _require(all(int(np.sum(presence[species] & (folds == fold))) >= thresholds["focal_validation_presences"] for fold in range(5)), "written_fold_focal_gate_failed")
            _require(all(int(np.sum((~presence[species]) & (richness >= 10) & complete & (folds == fold))) >= thresholds["validation_backgrounds"] for fold in range(5)), "written_fold_background_gate_failed")
        for species in upstream["training_heads"]:
            _require(all(int(np.sum(presence[species] & (folds == fold))) >= thresholds["head_validation_presences"] and int(np.sum(presence[species] & (folds != fold))) >= thresholds["head_complement_training_presences"] for fold in range(5)), "written_fold_head_gate_failed")
        _require(chosen.get("fold_assignment_digest") == digest(folds.tolist()), "written_fold_assignment_drift")
        crossfit = json.loads((private / config["private_outputs"]["crossfit"]).read_text()); blocks = crossfit.get("focal_blocks", {})
        _require(crossfit.get("richness_scope", {}).get("auxiliary_pretraining_backgrounds") == "held-block-adjusted complement richness", "auxiliary_richness_scope_drift")
        _require("target-specific X10" in crossfit.get("richness_scope", {}).get("target_fine_tuning_and_evaluation", ""), "target_richness_scope_drift")
        _require(crossfit.get("block_sizes") == {str(i): sum(value == i for value in blocks.values()) for i in range(10)}, "crossfit_block_size_drift")
        for block in range(10):
            expected = auxiliary_learning_sets(upstream["training_heads"], blocks, block)
            _require(crossfit["auxiliary_sets"][str(block)] == expected and len(expected["full"]) in (167, 168), "auxiliary_complement_drift")
            _require(expected["20"] == expected["full"][:20] and expected["80"] == expected["full"][:80], "auxiliary_learning_curve_not_nested")
        curves = json.loads((private / config["private_outputs"]["curves"]).read_text()); plan = curves.get("response_row_plan", [])
        _require(len(plan) == 157 * 5 and curves.get("unique_endpoints") == 5, "response_curve_plan_drift")
        _require({row.get("target") for row in plan} == set(upstream["focal"]), "response_curve_target_coverage_drift")
        _require(curves.get("auxiliary", {}).get("full", {}).get("heads") == "block_complement" and all(curves["target"][str(frac)]["auxiliary_heads"] == "block_complement" for frac in (0.25, 0.5, 1.0)), "curve_complement_metadata_drift")
        _require("full richness" in curves.get("richness_scope", ""), "curve_richness_scope_drift")
        for row in plan:
            expected_fractions = {"0.25", "0.5", "1.0"} if row["target"] in upstream["primary"] else {"1.0"}
            _require(set(row.get("fractions", {})) == expected_fractions, "response_curve_shape_drift")
            if row["target"] in upstream["primary"]:
                counts = [row["fractions"][fraction]["count"] for fraction in ("0.25", "0.5", "1.0")]
                _require(0 < counts[0] <= counts[1] <= counts[2], "response_curve_not_nested")
    return {"status": "passed", "tracked_only": tracked_only, "seed": manifest["seed"], "counts": manifest["counts"], "privacy": {"coordinates_tracked": False, "models": 0, "outcomes": 0}}


def summary(root: Path) -> dict[str, Any]:
    config = load_config(Path(root)); path = Path(root) / config["tracked_outputs"]["manifest"]; return json.loads(path.read_text()) if path.exists() else {"status": "not_built"}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("build", "validate", "validate-tracked", "summary", "plan")); parser.add_argument("--root", type=Path, default=Path.cwd()); args = parser.parse_args(argv)
    if args.command == "build": result = build(args.root)
    elif args.command == "validate": result = validate(args.root)
    elif args.command == "validate-tracked": result = validate(args.root, tracked_only=True)
    else: result = summary(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
