import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from dsdm_phase1 import goal046_mainland_dsdm as goal046
from dsdm_phase1 import goal045_mainland_dsdm as goal045

from dsdm.contracts import ArchitectureSpec
from dsdm_phase1.goal046_mainland_dsdm import (
    _endpoint_tasks,
    _final_tasks,
    _apply_strict_support,
    _target_seed,
    _q_seed,
    _validate_held_prediction,
    _identity,
    _selection_pretraining_tasks,
    _selection_tasks,
    validate_inputs,
)
from dsdm_phase1.mainland_dsdm import (
    MainlandDsdmError,
    NeuralDataset,
    equal_head_weights,
    fit_pretraining_lifecycle,
    fit_target_lifecycle,
)
from dsdm_phase1.mainland_modeling import ResponseRows
from dsdm_phase1.mainland_modeling import stable_seed


ROOT = Path(__file__).resolve().parents[1]


def _config():
    return json.loads((ROOT / "config/goal046_mainland_dsdm.json").read_text())


def _binary(seed, rows, width):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(rows, width)).astype(np.float32)
    y = (x[:, 0] + 0.3 * x[:, 1] > 0).astype(np.float32)
    return x, y


def test_goal046_preserves_the_goal045_seed_and_architecture_authority():
    goal046 = _config()
    goal045 = json.loads((ROOT / "config/goal045_mainland_dsdm.json").read_text())

    assert goal046["design"]["architecture_candidates"] == goal045["design"]["architecture_candidates"]
    assert goal046["design"]["arms"] == goal045["design"]["arms"]
    assert goal046["design"]["seed_labels"] == goal045["design"]["seed_labels"]
    assert goal046["lifecycle"]["architecture_selection_seed_labels"] == ["seed00"]
    assert goal046["privacy"]["tasmania_response_rows_read"] == 0
    assert goal046["privacy"]["tasmania_predictor_rows_used"] == 0


def test_goal046_reuses_goal045_numeric_seed_authority():
    identity = _identity(ROOT)
    target = "Dasyurus maculatus"
    fold = 2
    architecture = "bridge_control"
    seed_label = "seed03"
    expected_pretraining = stable_seed(
        goal045._identity(ROOT)["config_sha256"], "pretrain", target, fold, architecture, seed_label
    )
    assert expected_pretraining == stable_seed(
        identity["goal045_config_sha256"], "pretrain", target, fold, architecture, seed_label
    )
    assert goal045._target_seed(
        goal045._identity(ROOT), target, 100, "full", fold, architecture, seed_label
    ) == _target_seed(identity, target, 100, "full", fold, architecture, seed_label)
    assert _target_seed(identity, target, 100, "full", fold, architecture, seed_label) == stable_seed(
        identity["goal045_config_sha256"], "target", target, 100, "full", fold, architecture, seed_label
    )
    assert identity["config_sha256"] != identity["goal045_config_sha256"]


def test_goal046_q_seeds_match_goal044_for_all_target_folds():
    config = _config()
    goal044 = json.loads((ROOT / "config/goal044_mainland_conventional.json").read_text())
    for target in config["scope"]["targets"]:
        for fold in config["scope"]["folds"]:
            expected = stable_seed(goal044["target_subsets"]["master_seed"], "q", target, fold)
            assert _q_seed(config, target, fold) == expected


def test_neural_held_prediction_binding_rejects_wrong_cells_or_labels():
    class Store:
        def response_rows(self, target, fold, role):
            return ResponseRows(("a", "b"), np.array([0, 1]), np.array([1, 1]))

    wrong_cells = pa.table({"cell_id": ["a", "wrong"], "y": np.array([0, 1], dtype=np.int8), "score": np.array([0.1, 0.9])})
    with pytest.raises(goal046.Goal046Error, match="prediction_held_cells_invalid"):
        _validate_held_prediction(Store(), "target", 0, wrong_cells, ["score"])
    wrong_labels = pa.table({"cell_id": ["a", "b"], "y": np.array([1, 1], dtype=np.int8), "score": np.array([0.1, 0.9])})
    with pytest.raises(goal046.Goal046Error, match="prediction_held_labels_invalid"):
        _validate_held_prediction(Store(), "target", 0, wrong_labels, ["score"])


def _q_cache_fixture(tmp_path, monkeypatch):
    identity = {"id": "identity"}
    cache_json = tmp_path / "cache.json"
    cache_parquet = tmp_path / "cache.parquet"
    q_paths = {fold: (tmp_path / f"q{fold}.json", tmp_path / f"q{fold}.parquet") for fold in range(5)}
    monkeypatch.setattr(goal046, "_identity", lambda _root: identity)
    monkeypatch.setattr(goal046, "_q_conventional_paths", lambda _root, _target: (cache_json, cache_parquet))
    monkeypatch.setattr(goal046, "_q_paths", lambda _root, _target, fold: q_paths[fold])
    monkeypatch.setattr(goal046, "_goal044_q_authority", lambda _root, _config, _target: ("rf", "rf00", ["seed00"]))

    class Store:
        def response_rows(self, target, fold, role):
            return ResponseRows(("a", "b"), np.array([0, 1]), np.array([fold, fold]))

    folds = [{"fold": fold, "cell_ids": ("a", "b"), "y": np.array([0, 1], dtype=np.int8), "score": np.array([0.1, 0.9])} for fold in range(5)]
    metrics = goal046.summarize_oof(folds)
    rows = [{"cell_id": cell, "fold": fold["fold"], "y": int(y), "score": float(score)} for fold in folds for cell, y, score in zip(fold["cell_ids"], fold["y"], fold["score"], strict=True)]
    table = pa.Table.from_pylist(rows, schema=goal046.Q_CONVENTIONAL_SCHEMA)
    goal046._atomic_parquet(cache_parquet, table)
    q_digests = {}
    for fold, (q_json, q_parquet) in q_paths.items():
        q_table = pa.table({"cell_id": ["a", "b"], "q_linear": [0.2, 0.8]})
        goal046._atomic_parquet(q_parquet, q_table)
        q_digests[str(fold)] = goal046.sha256_file(q_parquet)
        q_json.write_text(json.dumps({
            "schema_version": "goal046-q-receipt-v1", "identity": identity,
            "target": "target", "held_fold": fold, "excluded_target": True,
            "auxiliary_head_count": 19, "parquet_rows": 2,
            "parquet_sha256": q_digests[str(fold)],
        }))
    cache_json.write_text(json.dumps({
        "identity": identity,
        "key": {"identity": identity, "target": "target", "fraction": 100, "ladder": "full", "family": "rf", "candidate_id": "rf00", "seed_labels": ["seed00"]},
        "family": "rf", "candidate_id": "rf00", "seed_labels": ["seed00"], "metrics": metrics,
        "q_surface_digests": q_digests, "prediction_rows": len(rows), "prediction_parquet_sha256": goal046.sha256_file(cache_parquet),
    }))
    return cache_json, cache_parquet, q_paths, Store(), table, rows


def test_verified_q_conventional_cache_rejects_tampered_predictions(tmp_path, monkeypatch):
    cache_json, cache_parquet, _q_paths, store, table, rows = _q_cache_fixture(tmp_path, monkeypatch)
    assert goal046._load_verified_q_conventional(tmp_path, store, {"scope": {"folds": list(range(5))}}, "target")["candidate_id"] == "rf00"
    table = pa.Table.from_pylist([{**row, "score": 0.2 if row["cell_id"] == "a" else row["score"]} for row in rows], schema=goal046.Q_CONVENTIONAL_SCHEMA)
    goal046._atomic_parquet(cache_parquet, table)
    with pytest.raises(goal046.Goal046Error, match="q_conventional_prediction_digest_mismatch"):
        goal046._load_verified_q_conventional(tmp_path, store, {"scope": {"folds": list(range(5))}}, "target")


def test_verified_q_conventional_cache_rejects_receipt_controlled_model_choice(tmp_path, monkeypatch):
    cache_json, _cache_parquet, _q_paths, store, _table, _rows = _q_cache_fixture(tmp_path, monkeypatch)
    receipt = json.loads(cache_json.read_text())
    receipt["family"] = "hgb"
    receipt["candidate_id"] = "hgb00"
    receipt["seed_labels"] = ["seed01"]
    receipt["key"].update({"family": "hgb", "candidate_id": "hgb00", "seed_labels": ["seed01"]})
    cache_json.write_text(json.dumps(receipt))
    with pytest.raises(goal046.Goal046Error, match="q_conventional_authority_drift"):
        goal046._load_verified_q_conventional(tmp_path, store, {"scope": {"folds": list(range(5))}}, "target")


def test_verified_q_conventional_cache_rejects_tampered_q_surface(tmp_path, monkeypatch):
    _cache_json, _cache_parquet, q_paths, store, _table, _rows = _q_cache_fixture(tmp_path, monkeypatch)
    q_parquet = q_paths[0][1]
    goal046._atomic_parquet(q_parquet, pa.table({"cell_id": ["a", "b"], "q_linear": [0.3, 0.7]}))
    with pytest.raises(goal046.Goal046Error, match="q_parquet_digest_mismatch"):
        goal046._load_verified_q_conventional(tmp_path, store, {"scope": {"folds": list(range(5))}}, "target")


def test_verified_q_conventional_cache_rejects_extra_fold_rows(tmp_path, monkeypatch):
    cache_json, cache_parquet, _q_paths, store, table, _rows = _q_cache_fixture(tmp_path, monkeypatch)
    extra = pa.table({"cell_id": ["extra"], "fold": np.array([5], dtype=np.int8), "y": np.array([0], dtype=np.int8), "score": np.array([0.4])}, schema=goal046.Q_CONVENTIONAL_SCHEMA)
    combined = pa.concat_tables([table, extra])
    goal046._atomic_parquet(cache_parquet, combined)
    receipt = json.loads(cache_json.read_text())
    receipt["prediction_rows"] = combined.num_rows
    receipt["prediction_parquet_sha256"] = goal046.sha256_file(cache_parquet)
    cache_json.write_text(json.dumps(receipt))
    with pytest.raises(goal046.Goal046Error, match="q_conventional_fold_inventory_invalid"):
        goal046._load_verified_q_conventional(tmp_path, store, {"scope": {"folds": list(range(5))}}, "target")


def test_goal045_task_plan_is_bounded_and_complete():
    config = _config()
    assert len(_endpoint_tasks(config)) == 5
    assert len(_selection_pretraining_tasks(config)) == 75
    assert len(_selection_tasks(config)) == 75
    assert len(_final_tasks(config, "bridge_control")) == 125


def test_equal_head_weights_equalize_heads_without_using_response_class():
    head = np.asarray([0, 0, 0, 1, 2, 2], dtype=np.int64)
    weights = equal_head_weights(head, 3)
    totals = np.bincount(head, weights=weights, minlength=3)

    assert np.allclose(totals, totals[0])
    assert np.mean(weights) == pytest.approx(1.0)
    assert weights[0] == weights[1] == weights[2]


def test_equal_head_weights_accepts_float32_roundoff_at_production_scale():
    counts = np.asarray([
        14393, 24361, 14289, 14234, 13478, 12742, 11466, 13771, 13125,
        24901, 14347, 15322, 13988, 13425, 14085, 14425, 13268, 20724, 17847,
    ])
    head = np.repeat(np.arange(len(counts)), counts)
    weights = equal_head_weights(head, len(counts))
    totals = np.bincount(head, weights=weights.astype(np.float64))

    assert weights.dtype == np.float32
    assert (totals.max() - totals.min()) / totals.mean() < 2 * np.finfo(np.float32).eps


def test_strict_support_removes_focal_presence_contribution_before_x3():
    base = ResponseRows(("a", "b", "c", "d"), np.array([0, 0, 1, 0]), np.array([1, 2, 3, 4]))
    rows, audit = _apply_strict_support(base, np.array([3, 3, 2, 3]), {"a"})
    assert rows.cell_ids == ("b", "c", "d")
    assert rows.y.tolist() == [0, 1, 0]
    assert audit["dropped_backgrounds_adjusted_below_x3"] == 1
    assert audit["focal_target_overlap_backgrounds"] == 1


def test_goal046_is_full_endpoint_only_and_tasmania_sealed():
    config = _config()
    assert config["target_subsets"]["fractions"] == [100]
    assert config["scope"]["tasmania_evaluation"] == "sealed"
    gate = validate_inputs(ROOT)
    assert gate["status"] == "goal046_inputs_ready"
    assert gate["tasmania_response_rows_read"] == 0
    assert gate["tasmania_predictor_rows_used"] == 0


def test_neural_dataset_rejects_nonpositive_weights():
    x, y = _binary(1, 8, 3)
    with pytest.raises(MainlandDsdmError, match="dataset_weights_invalid"):
        NeuralDataset(x, y, np.repeat([0, 1], 4), np.zeros(8))


def test_tiny_pretraining_and_transfer_lifecycle_runs_on_cpu():
    spec = ArchitectureSpec("tiny", 1, 8, 4, "constant", 0.0, 0.001)
    heads = ("aux_a", "aux_b")

    def auxiliary(seed, rows):
        x, y = _binary(seed, rows, 4)
        head = np.tile(np.asarray([0, 1], dtype=np.int64), rows // 2)
        return NeuralDataset(x, y, head, equal_head_weights(head, 2))

    state, pretraining = fit_pretraining_lifecycle(
        spec, auxiliary(1, 16), auxiliary(2, 8), auxiliary(3, 24), heads,
        seed=45, device_name="cpu", batch_size=8, max_epochs=2, patience=1,
        min_delta=0.0,
    )
    x_discovery, y_discovery = _binary(4, 16, 4)
    x_stopping, y_stopping = _binary(5, 8, 4)
    x_replay, y_replay = _binary(6, 24, 4)
    held_x, _ = _binary(7, 6, 4)
    scores, receipt = fit_target_lifecycle(
        spec,
        NeuralDataset(x_discovery, y_discovery),
        NeuralDataset(x_stopping, y_stopping),
        NeuralDataset(x_replay, y_replay),
        held_x,
        seed=46, device_name="cpu", batch_size=8, max_epochs=2, patience=1,
        min_delta=0.0, transferred_state=state, freeze_trunk=True,
    )

    assert pretraining["auxiliary_heads"] == list(heads)
    assert pretraining["within_head_class_balancing"] is False
    assert receipt["transferred"] is True
    assert receipt["freeze_trunk"] is True
    assert scores.shape == (6,)
    assert np.isfinite(scores).all()
    assert np.all((scores >= 0) & (scores <= 1))


def test_live_input_gate_keeps_tasmania_sealed():
    gate = validate_inputs(ROOT)
    assert gate["status"] == "goal046_inputs_ready"
    assert gate["tasmania_response_rows_read"] == 0
    assert gate["tasmania_predictor_rows_used"] == 0
