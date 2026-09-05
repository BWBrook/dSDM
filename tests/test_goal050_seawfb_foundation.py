from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dsdm_phase1 import goal050_seawfb_foundation as foundation


def test_spatial_fold_assignment_is_deterministic_and_block_complete():
    bx = np.repeat(np.arange(10), 3)
    by = np.tile(np.arange(3), 10)
    first = foundation.assign_spatial_folds(bx, by, 394)
    assert np.array_equal(first, foundation.assign_spatial_folds(bx, by, 394))
    for block in zip(bx, by):
        assert len(set(first[(bx == block[0]) & (by == block[1])])) == 1


def test_lazy_complement_formula_and_background_exclusion():
    assert np.array_equal(foundation.lazy_complement_richness([10, 4, 2], [2, 1, 0]), [8, 3, 2])
    memberships = {"a": [True, False, True], "b": [False, True, False]}
    assert np.array_equal(foundation.lazy_block_richness([10, 4, 2], memberships, ["a"]), [9, 4, 1])
    assert foundation.complement_heads(["a", "b", "c"], ["b"]) == ["a", "c"]
    bg10, bg20 = foundation.target_background_masks([True, False, False], [20, 19, 9])
    assert np.array_equal(bg10, [False, True, False])
    assert np.array_equal(bg20, [False, False, False])


def test_species_blocks_have_frozen_balanced_sizes():
    blocks = foundation.species_blocks([f"species-{i:03d}" for i in range(157)])
    sizes = [sum(value == block for value in blocks.values()) for block in range(10)]
    assert sorted(sizes) == [15, 15, 15, 16, 16, 16, 16, 16, 16, 16]


def test_nested_hash_subsets_are_nested_and_reproducible():
    items = [f"s{i}" for i in range(20)]
    first = foundation.nested_hash_subset(items, [0.25, 0.5, 1.0])
    assert first == foundation.nested_hash_subset(items, [0.25, 0.5, 1.0])
    assert set(first["0.25"]) <= set(first["0.5"]) <= set(first["1.0"])
    strata = {item: "even" if int(item[1:]) % 2 == 0 else "odd" for item in items}
    stratified = foundation.nested_stratified_indices(items, [0.5, 1.0], strata)
    assert set(stratified["0.5"]) <= set(stratified["1.0"])


def test_transform_fit_uses_population_sd_and_explicit_missing_unseen():
    frame = pd.DataFrame({**{col: [1.0, 2.0, 3.0] for col in foundation.CONTINUOUS}, **{col: ["known", None, "known"] for col in foundation.CATEGORICAL}})
    spec = foundation.fit_transforms(frame, {"retained_full": np.array([True, True, True])})["retained_full"]
    assert spec["continuous"]["bio01"]["population_sd"] == pytest.approx(np.std([1.0, 2.0, 3.0]))
    assert spec["categorical"]["nvis_mvg"][:2] == ["__MISSING__", "__UNSEEN__"]
    transformed = foundation.apply_transforms(pd.DataFrame({**{col: [99.0] for col in foundation.CONTINUOUS}, **{col: ["new"] for col in foundation.CATEGORICAL}}), spec)
    assert transformed.loc[0, "nvis_mvg"] == "__UNSEEN__"


@pytest.mark.real_scope
def test_tracked_validation_is_clean_for_built_foundation():
    root = Path(__file__).parents[1]
    result = foundation.validate(root, tracked_only=True)
    assert result["status"] == "passed"
    assert result["privacy"]["models"] == 0
    manifest = json.loads((root / "metadata/goal050_manifest.json").read_text())
    assert manifest["fold_search"]["model_metrics_used"] is False


@pytest.mark.real_scope
def test_built_foundation_replays_folds_receipts_and_target_plans():
    root = Path(__file__).parents[1]
    result = foundation.validate(root, tracked_only=False)
    manifest = json.loads((root / "metadata/goal050_manifest.json").read_text())
    selected = manifest["fold_search"]["selected"]
    assert result["status"] == "passed"
    assert selected["seed"] == 394
    assert selected["primary_presence_gate"] is True
    assert selected["focal_presence_gate"] is True
    assert selected["head_presence_gate"] is True
    assert selected["head_complement_gate"] is True
    assert selected["adequate_background_gate"] is True
    curves = json.loads((root / "data/processed/dsdm/goal050-seawfb-modeling-foundation/learning_curves.json").read_text())
    plan = curves["response_row_plan"]
    assert len(plan) == 157 * 5
    assert sum(row["endpoint_plan"] == "nested_25_50_100" for row in plan) == 73 * 5
    assert sum(row["endpoint_plan"] == "full_only" for row in plan) == 84 * 5
    for row in plan:
        assert set(row["fractions"]) == ({"0.25", "0.5", "1.0"} if row["endpoint_plan"] == "nested_25_50_100" else {"1.0"})


def test_tracked_privacy_guard_rejects_coordinates_and_cell_payloads():
    with pytest.raises(foundation.Goal050Error, match="privacy"):
        foundation._privacy({"longitude": [146.0]})
    with pytest.raises(foundation.Goal050Error, match="privacy"):
        foundation._privacy({"private_species_cells": ["x"]})


def test_config_loader_fails_closed_on_schema_drift(tmp_path):
    config_path = tmp_path / foundation.CONFIG
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(foundation.Goal050Error, match="config_schema_drift"):
        foundation.load_config(tmp_path)
