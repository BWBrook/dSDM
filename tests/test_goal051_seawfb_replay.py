from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import dsdm_phase1.goal051_seawfb_conventional as goal051
from dsdm_phase1.mainland_modeling import summarize_oof
from dsdm_phase1.seawfb_modeling import ResponseRows, SeawfbModelingError, sha256_file


def _folds(scores):
    return [
        {"fold": fold, "y": np.array([0, 0, 1, 1]), "score": np.asarray(scores) + fold * 1e-5}
        for fold in range(5)
    ]


def _public(candidate, scores):
    return {
        "candidate_id": candidate,
        "seed_labels": ["seed00"],
        "metrics": summarize_oof(_folds(scores)),
        "physical_fits": 5,
        "runtime_seconds": 1.0,
        "best_epoch_range": None,
    }


def _rows(method, family, candidate, auxiliary, scores):
    rows = []
    for fold in range(5):
        for index, (y, score) in enumerate(zip((0, 0, 1, 1), np.asarray(scores) + fold * 1e-5)):
            rows.append(
                {
                    "target": "Target bird",
                    "target_fraction": 100,
                    "auxiliary_size": auxiliary,
                    "fold": fold,
                    "cell_id": f"f{fold}c{index}",
                    "y": y,
                    "method": method,
                    "family": family,
                    "candidate_id": candidate,
                    "score": float(score),
                }
            )
    return rows


class _FixtureStore:
    def target_rows(self, target, fold, fraction, role):
        assert target == "Target bird" and fraction == 100 and role == "validation"
        return ResponseRows(
            np.arange(4),
            tuple(f"f{fold}c{index}" for index in range(4)),
            np.array([0, 0, 1, 1], dtype=np.int8),
            np.full(4, fold, dtype=np.int8),
        )


def _support():
    return {
        "presence": 10,
        "background": 10,
        "rows": 20,
        "constructed_prevalence": 0.5,
        "folds": [
            {"fold": fold, "presence": 2, "background": 2, "rows": 4}
            for fold in range(5)
        ],
    }


def _fixture(tmp_path: Path, monkeypatch):
    result_path = tmp_path / "endpoint.json"
    prediction_path = tmp_path / "endpoint.parquet"
    intercept_scores = [0.5, 0.5, 0.5, 0.5]
    enet_scores = [0.1, 0.3, 0.7, 0.9]
    q_scores = [0.05, 0.2, 0.8, 0.95]
    rows = [
        *_rows("candidate_screen", "intercept", "null00", "none", intercept_scores),
        *_rows("family_selected", "intercept", "null00", "none", intercept_scores),
        *_rows("candidate_screen", "elastic_net", "enet00", "none", enet_scores),
        *_rows("family_selected", "elastic_net", "enet00", "none", enet_scores),
        *_rows("q_linear", "elastic_net", "enet00", "full", q_scores),
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=goal051.PREDICTION_SCHEMA), prediction_path)
    result = {
        "schema_version": "goal051-endpoint-v1",
        "identity": {"test": "identity"},
        "target": "Target bird",
        "target_fraction": 100,
        "validation_support": _support(),
        "families": {
            "intercept": {"status": "available", "candidates": [_public("null00", intercept_scores)], "selected": _public("null00", intercept_scores)},
            "elastic_net": {"status": "available", "candidates": [_public("enet00", enet_scores)], "selected": _public("enet00", enet_scores)},
        },
        "best_non_null_family": "elastic_net",
        "q_linear": {"full": {"family": "elastic_net", "candidate_retuned": False, **_public("enet00", q_scores)}},
        "prediction_rows": len(rows),
        "prediction_sha256": sha256_file(prediction_path),
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    result_path.write_text(json.dumps(result))
    monkeypatch.setattr(goal051, "_identity", lambda root: {"test": "identity"})
    monkeypatch.setattr(goal051, "_task_paths", lambda root, config, target, fraction: (result_path, prediction_path))
    return result_path, prediction_path, _FixtureStore()


def test_replay_recomputes_metrics_and_selection_from_private_rows(tmp_path, monkeypatch):
    _, _, store = _fixture(tmp_path, monkeypatch)
    replay = goal051.replay_endpoint(tmp_path, {}, "Target bird", 100, store)
    assert replay["status"] == "replayed"
    assert replay["prediction_rows"] == 100


def test_replay_detects_prediction_tampering_even_with_updated_file_digest(tmp_path, monkeypatch):
    result_path, prediction_path, store = _fixture(tmp_path, monkeypatch)
    table = pq.read_table(prediction_path)
    frame = table.to_pandas()
    selected = (frame.method == "q_linear") & (frame.fold == 0) & (frame.y == 1)
    frame.loc[selected, "score"] = 0.0
    pq.write_table(pa.Table.from_pandas(frame, schema=goal051.PREDICTION_SCHEMA, preserve_index=False), prediction_path)
    result = json.loads(result_path.read_text())
    result["prediction_sha256"] = sha256_file(prediction_path)
    result_path.write_text(json.dumps(result))
    with pytest.raises(SeawfbModelingError, match="q_metric_replay_failed"):
        goal051.replay_endpoint(tmp_path, {}, "Target bird", 100, store)


def test_replay_detects_noncanonical_assessment_cells_with_updated_digest(tmp_path, monkeypatch):
    result_path, prediction_path, store = _fixture(tmp_path, monkeypatch)
    frame = pq.read_table(prediction_path).to_pandas()
    frame.loc[0, "cell_id"] = "substituted-cell"
    pq.write_table(pa.Table.from_pandas(frame, schema=goal051.PREDICTION_SCHEMA, preserve_index=False), prediction_path)
    result = json.loads(result_path.read_text())
    result["prediction_sha256"] = sha256_file(prediction_path)
    result_path.write_text(json.dumps(result))
    with pytest.raises(SeawfbModelingError, match="prediction_assessment_cells_drift"):
        goal051.replay_endpoint(tmp_path, {}, "Target bird", 100, store)


def test_endpoint_records_failed_non_null_family_as_unavailable(tmp_path, monkeypatch):
    scores = [0.1, 0.3, 0.7, 0.9]

    def evaluated(config, target, fraction, family, candidate, seeds, prepared):
        if family == "elastic_net":
            raise SeawfbModelingError("synthetic_fit_failure")
        folds = []
        for fold in range(5):
            folds.append(
                {
                    "fold": fold,
                    "cell_ids": tuple(f"f{fold}c{i}" for i in range(4)),
                    "y": np.array([0, 0, 1, 1]),
                    "score": np.asarray(scores) + fold * 1e-5,
                    "scores_by_seed": {seed: np.asarray(scores) + fold * 1e-5 for seed in seeds},
                }
            )
        return {
            "candidate_id": candidate,
            "seed_labels": list(seeds),
            "folds": folds,
            "metrics": summarize_oof(folds),
            "fit_records": [{"physical_fits": 1, "runtime_seconds": 0.1, "best_epoch": None}],
            "physical_fits": 1,
            "runtime_seconds": 0.1,
        }

    config = {
        "goal_id": "fixture",
        "_test_fixture": True,
        "execution": {"private_root": str(tmp_path / "private")},
        "community_control": {},
        "conventional": {
            "families": ["intercept", "elastic_net", "random_forest"],
            "candidate_ids": {"intercept": ["null00"], "elastic_net": ["enet00", "enet04"], "random_forest": ["rf00", "rf02"]},
            "screen_seed_labels": {"intercept": ["seed00"], "elastic_net": ["seed00"], "random_forest": ["seed00"]},
            "selected_seed_labels": {"intercept": ["seed00"], "elastic_net": ["seed00"], "random_forest": ["seed00"]},
            "minimum_complete_candidates": {"intercept": 1, "elastic_net": 2, "random_forest": 2},
        },
    }

    class Store:
        primary_targets = ()

    prepared = [
        {"fold": fold, "validation_rows": _FixtureStore().target_rows("Target bird", fold, 100, "validation")}
        for fold in range(5)
    ]
    monkeypatch.setattr(goal051, "_prepared_folds", lambda *args, **kwargs: prepared)
    monkeypatch.setattr(goal051, "_evaluate", evaluated)
    monkeypatch.setattr(goal051, "_identity", lambda root: {"test": "identity"})
    result = goal051.run_endpoint(tmp_path, Store(), config, "Target bird", 100)
    assert result["families"]["intercept"]["status"] == "available"
    assert result["families"]["elastic_net"]["status"] == "unavailable"
    assert result["families"]["elastic_net"]["selected"] is None
    assert result["families"]["random_forest"]["status"] == "available"
    assert result["best_non_null_family"] == "random_forest"
    assert result["q_linear"]["full"]["candidate_retuned"] is False


def test_complete_validation_replays_all_endpoints_with_one_store(tmp_path, monkeypatch):
    identity = {"fixture": "identity"}
    config = {
        "execution": {"tracked_summary": "summary.json"},
        "conventional": {"families": ["intercept", "elastic_net", "random_forest", "hist_gradient_boosting", "shallow_ann"]},
        "planned_inventory": {"prevalence_failure_gate": {"extreme_quartile_minimum_coverage": 0.9}},
    }
    specs = [(f"bird-{index:03d}", 100) for index in range(303)]
    families = {family: {"status": "available"} for family in config["conventional"]["families"]}
    results = {}
    endpoints = []
    private = []
    for index, (target, fraction) in enumerate(specs):
        q_linear = {"full": {}, **({"20": {}, "80": {}} if index < 73 else {})}
        support = {
            "presence": index + 1,
            "background": 304 - index,
            "rows": 305,
            "constructed_prevalence": (index + 1) / 305,
            "folds": [],
        }
        result = {
            "target": target,
            "target_fraction": fraction,
            "validation_support": support,
            "families": families,
            "best_non_null_family": "elastic_net",
            "q_linear": q_linear,
            "candidate_failures": [],
            "physical_fits": 1,
            "prediction_rows": 2,
            "runtime_seconds": 0.25,
        }
        results[(target, fraction)] = result
        endpoints.append(
            {
                "target": target,
                "target_fraction": fraction,
                "validation_support": support,
                "best_non_null_family": "elastic_net",
                "families": families,
                "q_linear": q_linear,
                "candidate_failures": [],
            }
        )
        private.append(
            {
                "endpoint": f"bird-{index:03d}_target100",
                "result_sha256": f"sha-bird-{index:03d}.json",
                "prediction_sha256": f"sha-bird-{index:03d}.parquet",
                "prediction_rows": 2,
            }
        )
    prevalence = goal051._prevalence_diagnostic(endpoints, config["conventional"]["families"], 0.9)
    q_receipt = {"ready": 150, "total": 150}
    summary = {
        "identity": identity,
        "target_endpoints": 303,
        "q_conditions": 449,
        "q_surface_provenance": q_receipt,
        "endpoints": endpoints,
        "family_availability": {
            "available_groups": 1515,
            "planned_groups": 1515,
            "coverage": 1.0,
            "minimum_accepted": 0.95,
            "primary_full_required": "intercept_elastic_net_shallow_ann_and_at_least_one_tree",
            "by_family": {
                family: {"available": 303, "planned": 303, "coverage": 1.0}
                for family in config["conventional"]["families"]
            },
        },
        "prevalence_failure_diagnostic": prevalence,
        "private_outputs": private,
        "totals": {"physical_fits": 303, "prediction_rows": 606, "runtime_seconds": 75.75, "candidate_failures": 0},
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    curves = {"applies_to": {"primary_targets": [target for target, _ in specs[:73]]}}
    original_read = goal051._read_json
    monkeypatch.setattr(goal051, "validate_inputs", lambda root: {"status": "inputs_valid"})
    monkeypatch.setattr(goal051, "_config", lambda root: config)
    monkeypatch.setattr(goal051, "_identity", lambda root: identity)
    monkeypatch.setattr(
        goal051,
        "_read_json",
        lambda path: curves if path == tmp_path / goal051.CURVES_PATH else ({} if path == tmp_path / goal051.CROSSFIT_PATH else original_read(path)),
    )
    monkeypatch.setattr(goal051, "q_surface_specs", lambda crossfit: [])
    monkeypatch.setattr(goal051, "q_provenance", lambda root, config, require_complete: q_receipt)
    monkeypatch.setattr(goal051, "target_endpoints", lambda curves: specs)
    monkeypatch.setattr(goal051, "_checkpoint", lambda root, config, identity, target, fraction: results[(target, fraction)])
    monkeypatch.setattr(
        goal051,
        "_task_paths",
        lambda root, config, target, fraction: (tmp_path / f"{target}.json", tmp_path / f"{target}.parquet"),
    )
    monkeypatch.setattr(goal051, "sha256_file", lambda path: f"sha-{path.name}")
    store = object()
    monkeypatch.setattr(goal051, "SeawfbStore", lambda root: store)
    replayed = []
    monkeypatch.setattr(
        goal051,
        "replay_endpoint",
        lambda root, config, target, fraction, seen_store: replayed.append((target, fraction, seen_store)),
    )
    receipt = goal051.validate(tmp_path, complete=True)
    assert receipt["status"] == "goal051_complete_valid"
    assert len(replayed) == 303
    assert {id(item[2]) for item in replayed} == {id(store)}
