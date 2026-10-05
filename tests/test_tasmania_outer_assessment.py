from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import pytest

from dsdm.tasmania_outer_assessment import (
    AssessmentConfig,
    CATEGORICAL,
    CONTINUOUS,
    CONVENTIONAL_FAMILIES,
    ENDPOINTS,
    NEURAL_METHODS,
    PATCHES,
    SPECIES,
    TasmaniaOuterError,
    _open_response_once,
    _score_species_arrays,
    _thresholds_and_selection,
    _validate_conventional_prediction,
    _validate_neural_prediction,
    _write_json_new,
    build_response_free_rows,
    metric_block,
)


def _levels() -> dict[str, tuple[str, ...]]:
    return {
        "soil_class": tuple(str(value) for value in range(2, 15)),
        "veg_mvg": tuple(str(value) for value in (1, 2, 3, 4, 5, 7, 9, 10, 11, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 29, 31)),
        "landuse_secondary": tuple(str(value) for value in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18)),
    }


def _response_free_fixture():
    support = []
    predictors = []
    assignments = []
    levels = _levels()
    for index, species in enumerate(SPECIES):
        cell = f"cell{index:02d}"
        support.append({
            "species_id": species, "grid_cell_id": cell, "transform_id": "outer",
            "transform_role": "assessment", "outer_role": "test", "cv_fold": "",
        })
        row = {"grid_cell_id": cell}
        row.update({name: str(index + 1) for name in CONTINUOUS})
        row.update({name: levels[name][0] for name in CATEGORICAL})
        predictors.append(row)
        assignments.append({"grid_cell_id": cell, "outer_role": "test", "microcluster": PATCHES[index % len(PATCHES)]})
    fit = {"means": {name: 0.0 for name in CONTINUOUS}, "population_sd": {name: 1.0 for name in CONTINUOUS}}
    return support, predictors, assignments, fit, levels


def test_response_free_alignment_builds_exact_77_columns_without_labels():
    support, predictors, assignments, fit, levels = _response_free_fixture()
    with pytest.raises(TasmaniaOuterError, match="row/cell inventory"):
        build_response_free_rows(support, predictors, assignments, fit, levels)
    built = build_response_free_rows(
        support, predictors, assignments, fit, levels, enforce_frozen_inventory=False
    )
    assert tuple(built) == SPECIES
    assert {patch for value in built.values() for patch in value["patch"]} == set(PATCHES)
    for species in SPECIES:
        value = built[species]
        assert value["x_neural"].shape == (1, 77)
        assert value["continuous"].dtype == np.float64
        assert value["x_neural"].dtype == np.float32
        assert {"pa", "label", "response"}.isdisjoint(value)


def test_response_free_alignment_rejects_missing_predictor_cell():
    support, predictors, assignments, fit, levels = _response_free_fixture()
    with pytest.raises(TasmaniaOuterError, match="alignment"):
        build_response_free_rows(
            support, predictors[:-1], assignments, fit, levels,
            enforce_frozen_inventory=False,
        )


def test_metric_block_applies_fixed_threshold_and_classless_policy():
    result = metric_block([0, 0, 1, 1], [0.1, 0.8, 0.4, 0.9], 0.5)
    assert (result["tp"], result["fn"], result["tn"], result["fp"]) == (1, 1, 1, 1)
    assert result["tss"] == 0.0
    assert result["threshold"] == 0.5
    assert result["average_precision"] is not None

    classless = metric_block([1, 1], [0.4, 0.9], 0.5)
    assert (classless["tp"], classless["fn"], classless["tn"], classless["fp"]) == (1, 1, 0, 0)
    for name in ("roc_auc", "tss", "average_precision", "mcc", "sensitivity", "specificity"):
        assert classless[name] is None
    assert classless["na_reason"] == "single_response_class"

    negative_only = metric_block([0, 0], [0.2, 0.7], 0.5)
    empty = metric_block([], [], 0.5)
    for value in (negative_only, empty):
        for name in ("roc_auc", "tss", "average_precision", "mcc", "sensitivity", "specificity"):
            assert value[name] is None
    assert negative_only["na_reason"] == "single_response_class"
    assert empty["na_reason"] == "empty_scope"


def test_scoring_seed_averages_all_11_methods_and_retains_every_patch():
    species = SPECIES[0]
    y = np.asarray([0, 1, 0, 1, 0, 1, 0, 1, 0, 1], dtype=np.int8)
    patches = np.asarray([patch for patch in PATCHES for _ in range(2)])
    neural = np.empty((7, 5, 6, len(y)), dtype=np.float32)
    for seed_index in range(5):
        neural[:, seed_index] = np.asarray(y * 0.6 + 0.1 + seed_index * 0.01, dtype=np.float32)
    conventional = np.full((7, 5, 5, len(y)), np.nan, dtype=np.float64)
    active = np.zeros((7, 5, 5), dtype=np.uint8)
    seed_counts = (1, 5, 5, 1, 5)
    for family_index, count in enumerate(seed_counts):
        active[:, family_index, :count] = 1
        for seed_index in range(count):
            conventional[:, family_index, seed_index] = y * 0.55 + 0.2 + seed_index * 0.005
    thresholds = {
        (species, endpoint, method): 0.5
        for endpoint in ENDPOINTS
        for method in (*NEURAL_METHODS, *(f"conventional/{family}" for family in CONVENTIONAL_FAMILIES))
    }
    selected = {(species, endpoint): "random_forest" for endpoint in ENDPOINTS}
    records, contrasts = _score_species_arrays(species, y, patches, neural, conventional, active, thresholds, selected)
    assert len(records) == 7 * 11 * 6
    assert len(contrasts) == 7 * 6 * 3 * 2
    assert {row["patch"] for row in records if row["scope"] == "patch"} == set(PATCHES)
    assert all(row["threshold"] == 0.5 for row in records)
    assert all(row["selected_conventional_family"] == "random_forest" for row in contrasts if row["contrast"].endswith("selected_conventional"))


def test_prediction_validators_fail_on_tampered_shapes_and_active_masks(tmp_path: Path):
    neural = tmp_path / "neural.npz"
    np.savez_compressed(neural, scores=np.zeros((7, 5, 6, 3), dtype=np.float32))
    assert _validate_neural_prediction(neural, 3).shape == (7, 5, 6, 3)
    np.savez_compressed(neural, scores=np.zeros((7, 5, 6, 2), dtype=np.float32))
    with pytest.raises(TasmaniaOuterError, match="shape"):
        _validate_neural_prediction(neural, 3)

    conventional = tmp_path / "conventional.npz"
    scores = np.full((7, 5, 5, 3), np.nan)
    active = np.zeros((7, 5, 5), dtype=np.uint8)
    for family, count in enumerate((1, 5, 5, 1, 5)):
        active[:, family, :count] = 1
        scores[:, family, :count] = 0.5
    np.savez_compressed(conventional, scores=scores, active=active)
    _validate_conventional_prediction(conventional, 3)
    active[0, 0, 1] = 1
    scores[0, 0, 1] = 0.5
    np.savez_compressed(conventional, scores=scores, active=active)
    with pytest.raises(TasmaniaOuterError, match="seed-count"):
        _validate_conventional_prediction(conventional, 3)


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def test_frozen_threshold_and_selection_inventory_is_exact(tmp_path: Path):
    metrics = tmp_path / "metrics.csv"
    selections = tmp_path / "selection.csv"
    methods = (*NEURAL_METHODS, *(f"conventional/{family}" for family in CONVENTIONAL_FAMILIES))
    metric_rows = [
        {"species": species, "endpoint": endpoint, "method": method, "threshold": "0.42"}
        for species in SPECIES for endpoint in ENDPOINTS for method in methods
    ]
    selection_rows = [
        {"species": species, "endpoint": endpoint, "selected_family": "random_forest"}
        for species in SPECIES for endpoint in ENDPOINTS
    ]
    _write_csv(metrics, metric_rows, ["species", "endpoint", "method", "threshold"])
    _write_csv(selections, selection_rows, ["species", "endpoint", "selected_family"])
    raw = {"authorities": {
        "goal036_stratum_metrics": {"path": metrics.name},
        "goal036_conventional_selection": {"path": selections.name},
    }}
    config = AssessmentConfig(tmp_path / "config.json", tmp_path, raw, "a" * 64, tmp_path / "private", tmp_path / "archive", tmp_path / "receipt.json")
    thresholds, selected = _thresholds_and_selection(config)
    assert len(thresholds) == 8 * 7 * 11
    assert len(selected) == 8 * 7
    assert set(thresholds.values()) == {0.42}

    _write_csv(metrics, metric_rows[:-1], ["species", "endpoint", "method", "threshold"])
    with pytest.raises(TasmaniaOuterError, match="inventory"):
        _thresholds_and_selection(config)


def test_one_shot_access_marker_blocks_reopening_after_synthetic_open(tmp_path: Path):
    response = tmp_path / "response.csv"
    response.write_text("species_id,grid_cell_id,pa,microcluster,outer_role\nsp,cell,1,mc08,test\n", encoding="utf-8")
    raw = {
        "approval": {"sha256": "b" * 64},
        "response_vault": {"path": response.name, "sha256": hashlib.sha256(response.read_bytes()).hexdigest()},
    }
    private = tmp_path / "private"
    config = AssessmentConfig(tmp_path / "config.json", tmp_path, raw, "a" * 64, private, tmp_path / "archive", tmp_path / "receipt.json")
    rows = _open_response_once(config, {"receipt_digest": "c" * 64})
    assert rows[0]["pa"] == "1"
    assert (private / "response-access-intent.json").is_file()
    assert (private / "response-access.json").is_file()
    with pytest.raises(TasmaniaOuterError, match="overwrite"):
        _open_response_once(config, {"receipt_digest": "c" * 64})


def test_exclusive_json_writer_is_a_tamper_gate(tmp_path: Path):
    target = tmp_path / "receipt.json"
    _write_json_new(target, {"x": 1})
    with pytest.raises(TasmaniaOuterError, match="overwrite"):
        _write_json_new(target, {"x": 2})
