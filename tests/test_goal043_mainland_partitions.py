from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import dsdm_phase1.goal043_mainland_partitions as goal043


ROOT = Path(__file__).parents[1]


def test_block_fold_is_deterministic_and_bounded():
    first = goal043.block_fold(0, 50, 2, -7)
    assert first == goal043.block_fold(0, 50, 2, -7)
    assert 0 <= first < 5
    assert len({goal043.block_fold(seed, 50, 2, -7) for seed in range(16)}) > 1


def _parameters():
    parameters = {
        "continuous_mean": [10.0] * len(goal043.CONTINUOUS),
        "continuous_population_sd": [2.0] * len(goal043.CONTINUOUS),
    }
    vocabulary = {
            name: {"observed_levels": ["known", goal043.MISSING],
                   "encoded_levels": ["known", goal043.MISSING, goal043.UNSEEN]}
            for name in goal043.CATEGORICAL
    }
    return parameters, vocabulary


def test_transform_row_scales_and_maps_missing_and_unseen_categories():
    row = {name: 12.0 for name in goal043.CONTINUOUS}
    row.update({"nvis_mvg": "known", "soil_order": None, "alum_secondary": "novel"})
    continuous, categorical = goal043.transform_row(row, *_parameters())
    assert continuous == [1.0] * len(goal043.CONTINUOUS)
    assert categorical == ["known", goal043.MISSING, goal043.UNSEEN]


def test_missing_category_stays_missing_when_training_never_observed_it():
    parameters, vocabulary = _parameters()
    for item in vocabulary.values():
        item["observed_levels"] = ["known"]
    row = {name: 12.0 for name in goal043.CONTINUOUS}
    row.update({"nvis_mvg": None, "soil_order": "known", "alum_secondary": "novel"})
    _, categorical = goal043.transform_row(row, parameters, vocabulary)
    assert categorical == [goal043.MISSING, "known", goal043.UNSEEN]


def test_transform_row_rejects_continuous_nodata_instead_of_imputing():
    row = {name: 12.0 for name in goal043.CONTINUOUS}
    row.update({name: "known" for name in goal043.CATEGORICAL})
    row[goal043.CONTINUOUS[0]] = None
    with pytest.raises(goal043.Goal043Error, match="nodata"):
        goal043.transform_row(row, *_parameters())


def test_live_tracked_goal043_surface_is_valid():
    assert goal043.validate(ROOT, require_raw=False) == {
        "status": "tracked_goal043_valid_private_replay_required",
        "private_replay_required": True,
    }


def test_manifest_rejects_tasmania_access_claim():
    bindings, _, _ = goal043._authorities(ROOT, require_raw=False)
    transforms = json.loads((ROOT / goal043.TRANSFORM_PATH).read_text())
    manifest = json.loads((ROOT / goal043.MANIFEST_PATH).read_text())
    manifest = copy.deepcopy(manifest)
    manifest["summary"]["firewall"]["tasmania_predictor_rows_used"] = 1
    with pytest.raises(goal043.Goal043Error, match="manifest"):
        goal043._validate_manifest(manifest, bindings, goal043._sha(ROOT / goal043.TRANSFORM_PATH))


def test_manifest_rejects_a_smaller_than_largest_feasible_scale():
    bindings, _, _ = goal043._authorities(ROOT, require_raw=False)
    manifest = json.loads((ROOT / goal043.MANIFEST_PATH).read_text())
    manifest = copy.deepcopy(manifest)
    manifest["summary"]["partition"]["selected_scale_km"] = 25
    manifest["summary"]["partition"]["selected_seed"] = 45
    with pytest.raises(goal043.Goal043Error, match="manifest"):
        goal043._validate_manifest(manifest, bindings, goal043._sha(ROOT / goal043.TRANSFORM_PATH))


def test_transform_gate_rejects_nonpositive_scale():
    bindings, _, _ = goal043._authorities(ROOT, require_raw=False)
    transforms = json.loads((ROOT / goal043.TRANSFORM_PATH).read_text())
    transforms = copy.deepcopy(transforms)
    transforms["transforms"]["fold00"]["continuous_population_sd"][0] = 0
    with pytest.raises(goal043.Goal043Error, match="parameter"):
        goal043._validate_transforms(transforms, bindings)
