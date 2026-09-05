from __future__ import annotations

import json
import inspect
import copy
import platform
import warnings
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

from dsdm_phase1.goal050_seawfb_foundation import CATEGORICAL, CONTINUOUS
from dsdm_phase1.goal051_seawfb_conventional import (
    _canary_receipt_path,
    _expected_canary_tags,
    _interval_peak,
    _prevalence_diagnostic,
    _primary_full_family_gate,
    _validate_goal052,
    _validate_q_numerical_fit,
    EXPECTED_Q_NUMERICAL_FIT,
    _family_coverage,
    _family_gate,
    _fit_seed,
    _seed_namespace,
    _selection_key,
    q_conditions,
    q_surface_specs,
    target_endpoints,
    validate_inputs,
    canary_summary,
    canary_batch,
    canary_route,
)
from dsdm_phase1.seawfb_modeling import (
    EncodedFeatures,
    CollapsedBinaryRows,
    QLinearModel,
    ResponseRows,
    SeawfbModelingError,
    SeawfbStore,
    collapse_equal_head_rows,
    standardized_q,
    weighted_logistic_loss,
    fit_q_linear,
    q_parameter_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_endpoint_inventories_are_exact_and_noncartesian():
    curves = json.loads(
        (ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/learning_curves.json").read_text()
    )
    crossfit = json.loads(
        (ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/crossfit_plan.json").read_text()
    )
    endpoints = target_endpoints(curves)
    conditions = q_conditions(curves)
    assert len(endpoints) == 303
    assert len(conditions) == 449
    assert len(q_surface_specs(crossfit)) == 150
    assert sum(fraction == 25 for _, fraction in endpoints) == 73
    assert sum(auxiliary in {"20", "80"} for _, _, auxiliary in conditions) == 146


def test_collapsed_q_rows_preserve_expanded_weighted_likelihood_exactly():
    indices = [np.array([0, 1, 2, 3]), np.array([0, 1, 3]), np.array([0, 2, 3, 4, 5])]
    labels = [np.array([1, 0, 1, 0]), np.array([0, 1, 0]), np.array([1, 0, 1, 0, 1])]
    collapsed = collapse_equal_head_rows(indices, labels)
    eta_by_cell = np.array([-1.2, 0.3, 1.7, -0.4, 0.8, -2.0])
    total = sum(map(len, indices))
    expanded_eta, expanded_y, expanded_weight = [], [], []
    for head_indices, head_y in zip(indices, labels):
        expanded_eta.extend(eta_by_cell[head_indices])
        expanded_y.extend(head_y)
        expanded_weight.extend([total / (len(indices) * len(head_indices))] * len(head_indices))
    expanded_loss = weighted_logistic_loss(expanded_eta, expanded_y, expanded_weight)
    collapsed_loss = weighted_logistic_loss(
        eta_by_cell[collapsed.indices], collapsed.y, collapsed.sample_weight
    )
    assert np.isclose(expanded_loss, collapsed_loss, rtol=0, atol=1e-12)
    assert np.isclose(collapsed.sample_weight.sum(), total)
    assert len(collapsed.indices) < total


def test_q_rows_exclude_whole_focal_block_and_use_complement_richness():
    store = object.__new__(SeawfbStore)
    store.cell_ids = np.array([f"c{i}" for i in range(6)])
    store.folds = np.array([1, 1, 1, 1, 0, 1], dtype=np.int8)
    store.richness = np.array([10, 12, 10, 9, 20, 10])
    store.presence_indices = {
        "held_a": np.array([0, 2]),
        "held_b": np.array([0]),
        "donor": np.array([0, 3, 4]),
    }
    store.crossfit = {
        "focal_blocks": {"held_a": 0, "held_b": 0},
        "auxiliary_sets": {"0": {"20": ["donor"], "80": ["donor"], "full": ["donor"]}},
    }
    collapsed, receipt = store.q_collapsed_rows(0, 0, "full")
    assert receipt["held_species"] == ["held_a", "held_b"]
    assert receipt["heads"] == ["donor"]
    # c0 has R_full=10 and two held-block presences, so it survives only as a
    # donor presence; c2 drops because its complement richness is nine.
    observed = set(zip(collapsed.indices.tolist(), collapsed.y.tolist()))
    assert (0, 1) in observed
    assert not any(index == 2 for index, _ in observed)
    assert not any(index == 4 for index, _ in observed)  # held validation fold


def test_q_feature_follows_21_continuous_columns_and_missing_values_are_imputed():
    store = object.__new__(SeawfbStore)
    data = {name: [np.nan, 3.0] for name in CONTINUOUS}
    data.update({name: [None, "novel"] for name in CATEGORICAL})
    store.cells = pd.DataFrame(data)
    continuous = {name: {"mean": 1.0, "population_sd": 2.0} for name in CONTINUOUS}
    categorical = {name: ["__MISSING__", "__UNSEEN__", "known"] for name in CATEGORICAL}
    store.transforms = {"transforms": {"fold_0": {"continuous": continuous, "categorical": categorical}}}
    encoded = store.encoded([0, 1], 0, [0.25, -0.25])
    assert encoded.names[len(CONTINUOUS)] == "q_linear"
    assert encoded.continuous_count == len(CONTINUOUS) + 1
    assert np.all(encoded.x[0, : len(CONTINUOUS)] == 0)
    assert encoded.x[0, len(CONTINUOUS)] == 0.25
    assert np.isfinite(encoded.x).all()


class _QStore:
    def encoded(self, indices, held_fold, q=None):
        x = np.asarray(indices, dtype=np.float64).reshape(-1, 1)
        return EncodedFeatures(x, ("x",), ("continuous",), 1, f"fold_{held_fold}", "a", "b")


def _response(indices):
    indices = np.asarray(indices, dtype=np.int64)
    return ResponseRows(indices, tuple(map(str, indices)), indices % 2, np.ones(len(indices), dtype=np.int8))


def test_q_standardization_is_fit_on_current_endpoint_training_rows():
    model = QLinearModel(np.array([0.8]), -0.3, 0, 0, "full", "fold_0", 10)
    training = _response([0, 1, 2, 3])
    requested = _response([4, 5])
    scaled_training, scale = standardized_q(model, _QStore(), "target", 0, training, training)
    scaled_requested, repeated = standardized_q(model, _QStore(), "target", 0, requested, training)
    assert np.isclose(np.mean(scaled_training), 0, atol=1e-12)
    assert np.isclose(np.std(scaled_training), 1, atol=1e-12)
    assert scale == repeated
    assert np.all(scaled_requested > scaled_training.max())


class _FitQStore:
    def q_collapsed_rows(self, held_block, held_fold, auxiliary_size):
        return (
            CollapsedBinaryRows(np.array([0, 1]), np.array([0, 1]), np.ones(2), (2,), 2),
            {"held_block": held_block, "held_fold": held_fold, "auxiliary_size": auxiliary_size},
        )

    def encoded(self, indices, held_fold, q=None):
        return EncodedFeatures(
            np.asarray(indices, dtype=np.float64).reshape(-1, 1),
            ("x",),
            ("continuous",),
            1,
            f"fold_{held_fold}",
            "transform",
            "encoder",
        )


def _script_q_fits(monkeypatch, specifications):
    calls = []
    queue = iter(specifications)

    class FakeLogistic:
        def __init__(self, kwargs, specification):
            self.kwargs = kwargs
            self.specification = specification

        def fit(self, x, y, sample_weight):
            calls.append(self.kwargs)
            n_iter, warning = self.specification
            if warning:
                warnings.warn("synthetic ceiling", ConvergenceWarning)
            self.n_iter_ = np.array([n_iter])
            self.coef_ = np.array([[0.25]])
            self.intercept_ = np.array([-0.5])
            return self

    monkeypatch.setattr(
        "dsdm_phase1.seawfb_modeling.LogisticRegression",
        lambda **kwargs: FakeLogistic(kwargs, next(queue)),
    )
    return calls


def test_q_numerical_primary_success_and_deterministic_digest(monkeypatch):
    calls = _script_q_fits(monkeypatch, [(25, False), (25, False)])
    first, first_receipt = fit_q_linear(_FitQStore(), 0, 0, "full", "seed-space", EXPECTED_Q_NUMERICAL_FIT)
    second, second_receipt = fit_q_linear(_FitQStore(), 0, 0, "full", "seed-space", EXPECTED_Q_NUMERICAL_FIT)
    assert first_receipt["accepted_attempt"] == "primary"
    assert first_receipt["attempts"] == [{"attempt": "primary", "max_iter": 5000, "tol": 1e-5, "n_iter": 25, "warning": False, "converged": True}]
    assert first_receipt["fit_seed"] == second_receipt["fit_seed"]
    assert first_receipt["parameter_digest"] == second_receipt["parameter_digest"]
    assert first_receipt["parameter_digest"] == q_parameter_digest(first.coefficient, first.intercept)
    assert calls[0]["random_state"] == calls[1]["random_state"]


def test_q_numerical_extended_attempt_is_from_scratch_same_seed(monkeypatch):
    calls = _script_q_fits(monkeypatch, [(5000, False), (8123, False)])
    _, receipt = fit_q_linear(_FitQStore(), 2, 3, "20", "seed-space", EXPECTED_Q_NUMERICAL_FIT)
    assert receipt["accepted_attempt"] == "extended"
    assert [item["max_iter"] for item in receipt["attempts"]] == [5000, 10000]
    assert [item["converged"] for item in receipt["attempts"]] == [False, True]
    assert calls[0]["random_state"] == calls[1]["random_state"]
    assert calls[0]["tol"] == calls[1]["tol"] == 1e-5


def test_q_numerical_extended_nonconvergence_fails_closed(monkeypatch):
    _script_q_fits(monkeypatch, [(5000, True), (10000, True)])
    with pytest.raises(SeawfbModelingError, match="q_linear_nonconverged_after_extended_attempt"):
        fit_q_linear(_FitQStore(), 2, 3, "80", "seed-space", EXPECTED_Q_NUMERICAL_FIT)


def test_q_numerical_config_drift_is_rejected():
    _validate_q_numerical_fit(EXPECTED_Q_NUMERICAL_FIT)
    changed = dict(EXPECTED_Q_NUMERICAL_FIT, tol=1e-6)
    with pytest.raises(SeawfbModelingError, match="q_numerical_fit_drift"):
        _validate_q_numerical_fit(changed)


def test_selection_is_auc_then_tss_then_stable_identity():
    def result(auc, tss):
        return {"metrics": {"mean_fold_roc_auc": auc, "pooled": {"tss": tss}}}

    choices = [("b", result(0.7, 0.4)), ("a", result(0.7, 0.4)), ("c", result(0.7, 0.5))]
    assert min(choices, key=lambda item: _selection_key(item[1], item[0]))[0] == "c"
    assert min(choices[:2], key=lambda item: _selection_key(item[1], item[0]))[0] == "a"


def test_primary_full_gate_requires_one_not_both_tree_families():
    families = {
        name: {"status": "available"}
        for name in ("intercept", "elastic_net", "random_forest", "shallow_ann")
    }
    families["hist_gradient_boosting"] = {"status": "unavailable"}
    _primary_full_family_gate(families)
    families["random_forest"] = {"status": "unavailable"}
    with pytest.raises(SeawfbModelingError, match="primary_full_tree_family_unavailable"):
        _primary_full_family_gate(families)


def test_fit_seed_namespaces_do_not_depend_on_removed_scope_seed():
    config = json.loads((ROOT / "config/goal051_seawfb_conventional.json").read_text())
    assert _seed_namespace(config, "target") == "goal051-target-model-v1"
    assert _seed_namespace(config, "q") == "goal051-q-linear-v1"
    fixture = {"goal_id": "fixture", "_test_fixture": True, "execution": {}, "community_control": {}}
    assert _seed_namespace(fixture, "target") == "fixture:target:test-v1"
    with pytest.raises(SeawfbModelingError, match="target_fit_seed_namespace_missing"):
        _seed_namespace({"execution": {}, "community_control": {}}, "target")
    paired = {
        "goal_id": "fixture",
        "_test_fixture": True,
        "execution": {},
        "community_control": {},
    }
    base = _fit_seed(paired, "bird", 100, 2, "random_forest", "rf02", "seed03")
    # Downstream q size is intentionally absent from the seed contract.
    assert base == _fit_seed(paired, "bird", 100, 2, "random_forest", "rf02", "seed03")
    assert "auxiliary" not in inspect.signature(_fit_seed).parameters


def test_non_null_family_can_be_explicitly_unavailable_but_intercept_cannot():
    assert _family_gate("random_forest", 1, 2) == "unavailable"
    assert _family_gate("random_forest", 2, 2) == "available"
    with pytest.raises(SeawfbModelingError, match="mandatory_intercept_unavailable"):
        _family_gate("intercept", 0, 1)
    assert _family_coverage(95, 100) == 0.95
    with pytest.raises(SeawfbModelingError, match="family_coverage_below_0.95"):
        _family_coverage(94, 100)


def test_canary_receipt_tags_are_collision_free_and_validated(tmp_path):
    config = {
        "execution": {
            "canary_receipt": "private/canary/receipt.json",
            "canary": {"serial_repeats": 2, "mixed_concurrency": {"mac": 3, "deep_server": 8}},
        }
    }
    first, tag = _canary_receipt_path(tmp_path, config, "mac-serial-1")
    second, _ = _canary_receipt_path(tmp_path, config, "mac-serial-2")
    assert tag == "mac-serial-1"
    assert first != second
    assert first.name == "receipt-mac-serial-1.json"
    assert len(_expected_canary_tags(config, "deep_server")) == 10
    with pytest.raises(SeawfbModelingError, match="canary_receipt_tag_invalid"):
        _canary_receipt_path(tmp_path, config, "bad tag")


def test_goal052_freeze_detects_consequential_mutations():
    frozen = json.loads((ROOT / "config/goal052_seawfb_dsdm.json").read_text())
    _validate_goal052(frozen)
    mutations = [
        (("architectures", "candidates", 0, "width"), 129, "goal052_architecture_drift"),
        (("architectures", "constants", "residual_shape"), "other", "goal052_training_constant_drift"),
        (("architectures", "selection_rank", "shared", 0), "mean_target_auc_desc", "goal052_selection_rule_drift"),
        (("scope", "crossed_grid", "q_conditions"), 448, "goal052_scope_drift"),
        (("scope", "response_row_plan_binding"), "other", "goal052_scope_drift"),
        (("pretraining", "auxiliary_effort_richness_rule"), "R_full", "goal052_pretraining_drift"),
        (("community_control", "surface_count"), 149, "goal052_community_control_drift"),
        (("replication", "seed_labels"), ["seed00"], "goal052_replication_drift"),
        (("replication", "primary_contrasts"), [], "goal052_replication_drift"),
        (("stability_audit", "cannot_change_winner"), False, "goal052_stability_policy_drift"),
        (("amendment_policy", "performance_driven_goalpost_change"), True, "goal052_amendment_policy_drift"),
        (("prospective_amendments", 0, "timing"), "after_scores", "goal052_amendment_record_drift"),
        (("stopping_boundary", 1), "outer_open", "goal052_stopping_boundary_drift"),
    ]
    for path, value, error in mutations:
        changed = copy.deepcopy(frozen)
        cursor = changed
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(SeawfbModelingError, match=error):
            _validate_goal052(changed)


def test_prevalence_extreme_quartiles_are_ranked_and_gated():
    families = ["elastic_net", "random_forest"]
    endpoints = []
    for index in range(8):
        endpoints.append(
            {
                "target": f"bird-{index}",
                "target_fraction": 100,
                "validation_support": {"constructed_prevalence": (index + 1) / 10},
                "families": {family: {"status": "available"} for family in families},
            }
        )
    diagnostic = _prevalence_diagnostic(endpoints, families, 0.9)
    assert diagnostic["quartile_size"] == 2
    assert diagnostic["quartiles"]["lowest"]["prevalence_range"] == [0.1, 0.2]
    endpoints[0]["families"]["elastic_net"]["status"] = "unavailable"
    with pytest.raises(SeawfbModelingError, match="prevalence_lowest_elastic_net_coverage_below_threshold"):
        _prevalence_diagnostic(endpoints, families, 0.9)


def test_canary_summary_requires_exact_metric_free_inventory(tmp_path, monkeypatch):
    config = {
        "community_control": {"numerical_fit": EXPECTED_Q_NUMERICAL_FIT},
        "execution": {
            "canary_receipt": "private/canary/receipt.json",
            "canary": {
                "target": "Target bird",
                "held_fold": "fold00",
                "focal_block": "block6",
                "candidate_ids": ["null00", "enet04", "rf02", "hgb04", "ann02"],
                "auxiliary_sizes": [20, "full"],
                "q_augmented_family": "hist_gradient_boosting",
                "serial_repeats": 2,
                "mixed_concurrency": {"mac": 3, "deep_server": 8},
                "host_expectations": {
                    "mac": {"hostname": "Barrys-Mac-mini.local", "system": "Darwin"},
                    "deep_server": {"hostname": "deep-server", "system": "Linux"},
                },
            },
        }
    }
    identity = {"fixture": "identity"}
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._config", lambda root: config)
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._identity", lambda root: identity)
    for sequence, tag in enumerate(_expected_canary_tags(config, "mac"), start=1):
        path, _ = _canary_receipt_path(tmp_path, config, tag)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "serial" if "-serial-" in tag else "mixed"
        index = int(tag.rsplit("-", 1)[1])
        if mode == "mixed":
            start_ns, end_ns = 10_000_000_000 + index * 1_000_000, 20_000_000_000
        else:
            start_ns, end_ns = sequence * 1_000_000_000, sequence * 1_000_000_000 + 500_000_000
        receipt = {
            "schema_version": "goal051-canary-v1",
            "identity": identity,
            "status": "metric_free_complete",
            "receipt_tag": tag,
            "receipt_path": str(path.relative_to(tmp_path)),
            "host_key": "mac",
            "run_mode": mode,
            "run_index": index,
            "target": "Target bird",
            "held_fold": 0,
            "focal_block": 6,
            "host": "Barrys-Mac-mini.local",
            "system": "Darwin",
            "platform": "macOS-test-platform",
            "start_epoch_ns": start_ns,
            "end_epoch_ns": end_ns,
            "total_wall_seconds": 0.5,
            "metrics_computed": False,
            "outer_response_rows_read": 0,
            "outer_predictor_rows_used": 0,
            "process_peak_rss_bytes": 1000 + sequence,
            "entries": [
                {
                    "candidate_id": candidate,
                    "family": {
                        "null00": "intercept",
                        "enet04": "elastic_net",
                        "rf02": "random_forest",
                        "hgb04": "hist_gradient_boosting",
                        "ann02": "shallow_ann",
                    }[candidate],
                    "finite": True,
                    "converged": True,
                    "prediction_count": 4,
                    "prediction_range": [0.1, 0.9],
                    "prediction_digest": f"digest-{candidate}",
                }
                for candidate in config["execution"]["canary"]["candidate_ids"]
            ],
            "q_linear": [
                {
                    "auxiliary_size": str(auxiliary),
                    "finite": True,
                    "converged": True,
                    "prediction_count": 4,
                    "expanded_rows": 20,
                    "collapsed_rows": 10,
                    "head_count": 2,
                    "prediction_range": [0.2, 0.8],
                    "prediction_digest": f"digest-q-{auxiliary}",
                    "parameter_digest": "a" * 64 if str(auxiliary) == "20" else "b" * 64,
                    "attempts": [
                        {"attempt": "primary", "max_iter": 5000, "tol": 1e-5, "n_iter": 25, "warning": False, "converged": True}
                    ],
                    "accepted_attempt": "primary",
                    "downstream_family": "hist_gradient_boosting",
                    "downstream_candidate_id": "hgb04",
                    "downstream_fit": {"converged": True},
                }
                for auxiliary in (20, "full")
            ],
        }
        path.write_text(json.dumps(receipt))
    summary = canary_summary(tmp_path, "mac")
    assert summary["receipt_count"] == 5
    assert summary["mixed_batch"]["runs"] == 3
    assert summary["mixed_batch"]["interval_peak_concurrency"] == 3
    assert summary["prediction_digest_stable"] is True
    assert summary["q_parameter_digest_stable"] is True
    missing, _ = _canary_receipt_path(tmp_path, config, "mac-mixed-3")
    nonoverlap = json.loads(missing.read_text())
    nonoverlap["q_linear"][0]["parameter_digest"] = "c" * 64
    missing.write_text(json.dumps(nonoverlap))
    with pytest.raises(SeawfbModelingError, match="canary_q_parameter_digest_instability"):
        canary_summary(tmp_path, "mac")
    nonoverlap["q_linear"][0]["parameter_digest"] = "a" * 64
    nonoverlap["start_epoch_ns"] = 21_000_000_000
    nonoverlap["end_epoch_ns"] = 22_000_000_000
    missing.write_text(json.dumps(nonoverlap))
    with pytest.raises(SeawfbModelingError, match="canary_mixed_concurrency_not_proven"):
        canary_summary(tmp_path, "mac")
    missing.unlink()
    with pytest.raises(SeawfbModelingError, match="canary_receipt_missing:mac-mixed-3"):
        canary_summary(tmp_path, "mac")


def test_interval_peak_uses_half_open_intervals():
    assert _interval_peak([(0, 10), (2, 8), (4, 6)]) == 3
    assert _interval_peak([(0, 1), (1, 2)]) == 1


def test_canary_batch_uses_exact_serial_then_concurrent_schedule(tmp_path, monkeypatch):
    config = {
        "execution": {
            "canary": {
                "serial_repeats": 2,
                "mixed_concurrency": {"mac": 3, "deep_server": 8},
                "host_expectations": {
                    "mac": {"hostname": platform.node(), "system": platform.system()},
                    "deep_server": {"hostname": "deep-server", "system": "Linux"},
                },
            }
        }
    }
    calls = []
    pools = []

    class FakePool:
        def __init__(self, max_workers):
            self.max_workers = max_workers
            pools.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future

    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._config", lambda root: config)
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional.validate_inputs", lambda root: {})
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._require_canary_host", lambda config, host: {})
    monkeypatch.setattr(
        "dsdm_phase1.goal051_seawfb_conventional.canary",
        lambda root, tag: calls.append(tag) or {"receipt_tag": tag},
    )
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional.ProcessPoolExecutor", FakePool)
    monkeypatch.setattr(
        "dsdm_phase1.goal051_seawfb_conventional.canary_summary",
        lambda root, host: {"status": "complete", "host_key": host},
    )
    result = canary_batch(tmp_path, "mac")
    assert calls == ["mac-serial-1", "mac-serial-2", "mac-mixed-1", "mac-mixed-2", "mac-mixed-3"]
    assert pools[0].max_workers == 3
    assert result == {"status": "complete", "host_key": "mac"}


def test_canary_route_binds_both_host_summaries_and_worker_limit(tmp_path, monkeypatch):
    identity = {"fixture": "identity"}
    config = {
        "execution": {
            "canary_receipt": "private/canary/receipt.json",
            "tracked_canary_summary": "metadata/goal051_canary.json",
            "canary": {
                "serial_repeats": 2,
                "mixed_concurrency": {"mac": 3, "deep_server": 8},
                "host_expectations": {
                    "mac": {"hostname": "Barrys-Mac-mini.local", "system": "Darwin"},
                    "deep_server": {"hostname": "deep-server", "system": "Linux"},
                },
            },
        }
    }
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._config", lambda root: config)
    monkeypatch.setattr("dsdm_phase1.goal051_seawfb_conventional._identity", lambda root: identity)
    for host_key, concurrency in config["execution"]["canary"]["mixed_concurrency"].items():
        expected = config["execution"]["canary"]["host_expectations"][host_key]
        path = tmp_path / "private/canary" / f"summary-{host_key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "goal051-canary-host-summary-v1",
                    "status": "metric_free_host_inventory_complete",
                    "identity": identity,
                    "host_key": host_key,
                    "actual_hostname": expected["hostname"],
                    "actual_system": expected["system"],
                    "actual_platform": f"{expected['system']}-test",
                    "serial_latency_seconds": {"values": [1.0, 1.1], "mean": 1.05},
                    "mixed_batch": {
                        "runs": concurrency,
                        "configured_concurrency": concurrency,
                        "interval_peak_concurrency": concurrency,
                        "elapsed_seconds": 2.0,
                        "throughput_runs_per_second": concurrency / 2,
                    },
                    "peak_rss_bytes": 1234,
                    "prediction_digest_stable": True,
                    "prediction_digests": {"candidate:null00": "abc"},
                    "q_parameter_digest_stable": True,
                    "q_parameter_digests": {"20": "a" * 64, "full": "b" * 64},
                    "metrics_computed": False,
                    "outer_response_rows_read": 0,
                    "outer_predictor_rows_used": 0,
                }
            )
        )
    route = canary_route(tmp_path, "deep_server", 8)
    assert route["selected_host"] == "deep_server"
    assert route["selected_workers"] == 8
    assert set(route["host_summaries"]) == {"mac", "deep_server"}
    assert (tmp_path / "metadata/goal051_canary.json").is_file()
    with pytest.raises(SeawfbModelingError, match="canary_route_workers_invalid"):
        canary_route(tmp_path, "mac", 4)


def test_live_protocol_contract_validates_without_fitting_models():
    result = validate_inputs(ROOT)
    assert result["target_endpoints"] == 303
    assert result["q_conditions"] == 449
    assert result["q_surfaces"] == 150
    assert result["outer_response_rows_read"] == 0
