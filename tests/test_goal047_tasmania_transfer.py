import inspect
import json
from decimal import Decimal
from pathlib import Path
import subprocess

import numpy as np
import pyarrow as pa
import pytest

from dsdm_phase1 import goal042_transfer_response as goal042
from dsdm_phase1 import goal047_tasmania_transfer as goal047
from dsdm_phase1.mainland_modeling import (
    CONTINUOUS,
    EncodedFeatures,
    MainlandStore,
    ResponseRows,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET = "Dasyurus maculatus"


def _rows(response_values=(1, 0, 1, 0)):
    evidence = (
        (True, False, True),
        (False, False, True),
        (False, True, False),
        (False, False, True),
    )
    return [
        {
            "target": TARGET,
            "cell_id": cell,
            "response": response,
            "ala_presence": ala,
            "camera_presence": camera,
            "camera_survey_supported_absence": absence,
        }
        for cell, response, (ala, camera, absence) in zip(
            ("a", "b", "c", "d"), response_values, evidence, strict=True
        )
    ]


def _seed_table(seeds=("seed00",)):
    return {TARGET: {method: list(seeds) for method in goal047.METHODS}}


def _predictions(seeds=("seed00",)):
    output = {}
    for method_index, method in enumerate(goal047.METHODS):
        rows = []
        for seed_index, seed in enumerate(seeds):
            for cell, score in zip(("a", "b", "c", "d"), (0.85, 0.15, 0.75, 0.10), strict=True):
                rows.append(
                    {
                        "target": TARGET,
                        "cell_id": cell,
                        "seed_label": seed,
                        "score": score - method_index / 100 + seed_index / 1000,
                        "predictor_complete": True,
                    }
                )
        output[method] = rows
    return output


def _thresholds(value=0.5):
    return {method: {TARGET: value} for method in goal047.METHODS}


def test_response_precedence_and_surfaces_are_exact():
    primary = goal047.source_surface_rows(_rows(), "primary")
    secondary = goal047.source_surface_rows(_rows(), "secondary")
    assert [row["cell_id"] for row in primary] == ["a", "b", "c", "d"]
    assert len(secondary) == 4

    wrong = _rows(response_values=(0, 0, 1, 0))
    with pytest.raises(goal047.Goal047Error, match="response_precedence_invalid"):
        goal047.validate_response_precedence(wrong)

    unsupported = _rows()
    unsupported[1]["camera_survey_supported_absence"] = False
    with pytest.raises(goal047.Goal047Error, match="response_zero_without_camera_support"):
        goal047.validate_response_precedence(unsupported)


def test_prediction_scores_and_exact_seed_coverage_fail_closed():
    predictions = _predictions(("seed00", "seed01"))
    result = goal047.evaluate_transfer(
        _rows(),
        predictions,
        _thresholds(),
        targets=[TARGET],
        expected_seed_table=_seed_table(("seed00", "seed01")),
    )
    assert result["common_complete_cells"] == 4
    assert result["results"][0]["methods"][goal047.ARMS[0]]["seed_count"] == 2

    missing = _predictions(("seed00", "seed01"))
    missing[goal047.ARMS[0]] = [
        row for row in missing[goal047.ARMS[0]] if row["seed_label"] == "seed00"
    ]
    with pytest.raises(goal047.Goal047Error, match="prediction_seed_coverage_invalid"):
        goal047.evaluate_transfer(
            _rows(),
            missing,
            _thresholds(),
            targets=[TARGET],
            expected_seed_table=_seed_table(("seed00", "seed01")),
        )

    out_of_bounds = _predictions()
    out_of_bounds[goal047.ARMS[0]][0]["score"] = 1.01
    with pytest.raises(goal047.Goal047Error, match="prediction_score_invalid"):
        goal047.evaluate_transfer(
            _rows(), out_of_bounds, _thresholds(), targets=[TARGET]
        )


def test_single_class_surface_emits_explicit_nulls():
    rows = [_rows()[0], _rows()[2]]
    predictions = {
        method: [row for row in values if row["cell_id"] in {"a", "c"}]
        for method, values in _predictions().items()
    }
    result = goal047.evaluate_transfer(
        rows, predictions, _thresholds(), targets=[TARGET]
    )
    metrics = result["results"][0]["methods"][goal047.ARMS[0]]["metrics"]
    assert metrics["roc_auc"] is None
    assert metrics["null_reason"] == "single_class_surface"
    contrast = result["contrasts"][
        "multihead_full_finetune_minus_target_only_random_init_resmlp"
    ]
    assert contrast["equal_species_mean"] is None
    assert contrast["null_species_count"] == 1
    summary = result["equal_species_summaries"][goal047.ARMS[0]]["roc_auc"]
    assert summary["mean"] is None
    assert summary["nonnull_species_count"] == 0
    assert summary["null_species_count"] == 1


def test_zero_complete_target_skips_models_and_emits_null_surface(monkeypatch):
    config = json.loads((ROOT / goal047.CONFIG_PATH).read_text())
    monkeypatch.setattr(goal047, "TARGETS", (TARGET,))
    monkeypatch.setattr(goal047, "_config", lambda root: config)
    predictor = pa.table(
        {"cell_id": ["a"], **{name: [np.nan] for name in CONTINUOUS}}
    )
    seed_table = {TARGET: {method: ["seed00"] for method in goal047.METHODS}}
    opening = {"expected_coverage": {"method_seed_table": seed_table}}
    predictions, used = goal047._predict_private_models(
        ROOT, [_rows()[0]], predictor, opening
    )
    assert used == 0
    assert all(
        rows == [
            {
                "target": TARGET,
                "cell_id": "a",
                "seed_label": "seed00",
                "score": 0.5,
                "predictor_complete": False,
            }
        ]
        for rows in predictions.values()
    )
    result = goal047.evaluate_transfer(
        [_rows()[0]],
        predictions,
        _thresholds(),
        targets=[TARGET],
        expected_seed_table=seed_table,
    )
    target_result = result["results"][0]
    assert target_result["counts"]["predictor_incomplete"] == 1
    assert target_result["counts"]["common_complete_cells"] == 0
    assert target_result["methods"][goal047.ARMS[0]]["metrics"] == goal047._null_metrics(
        "no_common_complete_cells"
    )


def test_strict_focal_subtraction_is_independent_of_auxiliary_label():
    rows = ResponseRows(
        ("presence_overlap", "background_overlap", "background_keep", "presence_plain"),
        np.asarray([1, 0, 0, 1], dtype=np.int8),
        np.asarray([0, 1, 2, 3], dtype=np.int8),
    )
    selected, diagnostics = goal047.apply_strict_focal_subtraction(
        rows,
        [1, 3, 3, 0],
        {"presence_overlap", "background_overlap"},
    )
    assert selected.cell_ids == (
        "presence_overlap",
        "background_keep",
        "presence_plain",
    )
    assert diagnostics["focal_overlap_auxiliary_presences"] == 1
    assert diagnostics["focal_overlap_auxiliary_backgrounds"] == 1
    assert diagnostics["retained_presences"] == diagnostics["original_presences"]


def test_goal042_materialiser_synthetic_rows_are_unique_and_full_data():
    coordinates = {
        "presence": (Decimal("145.0"), Decimal("-40.0")),
        "background": (Decimal("145.1"), Decimal("-40.0")),
        "insufficient": (Decimal("145.2"), Decimal("-40.0")),
    }
    donors = {
        "presence": {TARGET},
        "background": {"head-a", "head-b", "head-c"},
        "insufficient": {"head-a"},
    }
    rows = goal042.materialise_mainland_rows(
        TARGET, coordinates, donors, {"presence"}
    )
    assert [(row["cell_id"], row["is_presence"]) for row in rows] == [
        ("background", False),
        ("presence", True),
    ]
    assert len({(row["target"], row["cell_id"]) for row in rows}) == len(rows)
    assert rows[0]["eligible_x3"] is True


def test_live_mainland_replay_summary_exactly_matches_goal042_manifest():
    cells, species_cells, diagnostics = goal047._load_mainland_authorities(ROOT)
    config = json.loads((ROOT / goal047.CONFIG_PATH).read_text())
    manifest = json.loads(
        (ROOT / config["bindings"]["goal042_response_manifest"]["path"]).read_text()
    )
    donor_members = {}
    for species in manifest["summary"]["cohort"]["support_taxa"]:
        for cell in species_cells[species]:
            donor_members.setdefault(cell, set()).add(species)
    rows = goal042.materialise_mainland_rows(
        TARGET,
        cells,
        donor_members,
        species_cells[TARGET],
    )
    observed = goal047._mainland_response_summary(rows)
    expected = manifest["summary"]["mainland_reference"][TARGET]
    assert set(observed) == {
        "reference_rows",
        "presence_cells",
        "support_cells_before_distance",
        "distance_rejected_under_5000m",
        "reference_background_cells",
        "primary_x3_response_cells",
        "primary_x3_presence_fraction",
    }
    assert observed == expected
    assert diagnostics["tasmania_rows_retained"] == 0


def test_lower_median_and_goal046_receipt_provenance_reject_fabrication():
    assert goal047.lower_median([9, 2, 8, 4, 6]) == 6
    with pytest.raises(goal047.Goal047Error, match="epoch_value_invalid"):
        goal047.lower_median([1, 2, 3, 4, 999])

    pre_path, _ = goal047.goal046._pretrain_paths(
        ROOT, TARGET, 0, "bridge_control", "seed00"
    )
    final_path = (
        ROOT
        / "data/processed/dsdm/goal046-strict-mainland-dsdm/final"
        / "dasyurus_maculatus_fraction100_full_fold00_seed00.json"
    )
    pre = json.loads(pre_path.read_text())
    final = json.loads(final_path.read_text())
    goal047._validate_goal046_epoch_receipts(
        ROOT, TARGET, "seed00", 0, pre, final, verify_files=True
    )
    fabricated = json.loads(json.dumps(final))
    fabricated["key"]["target"] = "wrong target"
    with pytest.raises(goal047.Goal047Error, match="epoch_target_provenance_invalid"):
        goal047._validate_goal046_epoch_receipts(
            ROOT, TARGET, "seed00", 0, pre, fabricated, verify_files=False
        )


def test_freeze_and_method_specific_inventory_keys_are_exact():
    freeze = json.loads((ROOT / goal047.FREEZE_PATH).read_text())
    assert goal047.validate_freeze(ROOT)["status"] == "goal047_freeze_valid"
    keys = goal047._expected_model_keys(freeze)
    assert len(keys) == 142
    for method in ("selected_conventional", "strict_q_conventional"):
        assert {
            seed
            for target, observed_method, seed in keys
            if target == "Pseudocheirus peregrinus" and observed_method == method
        } == {"seed00"}
    assert goal047._valid_digest("0" * 64) is False


def test_validate_freeze_rejects_bound_upstream_source_drift(monkeypatch):
    config = json.loads((ROOT / goal047.CONFIG_PATH).read_text())
    binding_name = "models_source"
    bound_path = (ROOT / config["bindings"][binding_name]["path"]).resolve()
    real_sha256_file = goal047.sha256_file

    def drifted_sha256(path):
        if Path(path).resolve() == bound_path:
            return "f" * 64
        return real_sha256_file(path)

    monkeypatch.setattr(goal047, "sha256_file", drifted_sha256)
    with pytest.raises(
        goal047.Goal047Error,
        match=f"binding_digest_mismatch:{binding_name}",
    ):
        goal047.validate_freeze(ROOT)


def test_goal047_local_mainland_full_encoder_matches_frozen_schema():
    store = MainlandStore(ROOT)
    complete = np.ones(len(store.cell_ids), dtype=bool)
    for name in CONTINUOUS:
        complete &= np.isfinite(store.continuous[name])
    cell = store.cell_ids[int(np.flatnonzero(complete)[0])]
    base = goal047._encode_mainland_full(store, [cell])
    with_q = goal047._encode_mainland_full(store, [cell], [0.25])
    assert goal047._feature_schema(base) == goal047._frozen_feature_schema(
        ROOT, with_q=False
    )
    assert goal047._feature_schema(with_q) == goal047._frozen_feature_schema(
        ROOT, with_q=True
    )
    assert with_q.names[21] == "q_linear"


def test_q_model_artifact_roundtrip_and_rehash(tmp_path):
    features = EncodedFeatures(
        np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64),
        ("a", "b"),
        ("continuous", "categorical"),
        1,
        "mainland_full",
        "transform",
        "encoder",
    )
    artifact = {
        "schema_version": goal047.Q_MODEL_SCHEMA,
        "candidate": {"id": "enet04"},
        "fit_seed": 1,
        "feature_schema": goal047._feature_schema(features),
        "coefficient": [1.0, -1.0],
        "intercept": 0.0,
    }
    path = tmp_path / "q.json"
    goal047._atomic_json(path, artifact)
    digest = sha256_file(path)
    loaded = goal047._load_q_model(path, digest)
    assert np.allclose(goal047._predict_q(loaded, features), [0.26894142, 0.73105858])
    path.write_text(path.read_text() + " ")
    with pytest.raises(goal047.Goal047Error, match="q_artifact_digest_invalid"):
        goal047._load_q_model(path, digest)


def test_neural_checkpoint_must_strictly_match_bridge_control():
    width = len(goal047._frozen_feature_schema(ROOT, with_q=False)["feature_names"])
    model = goal047.ResidualMLP(goal047._bridge_control_spec(ROOT), width)
    state = dict(model.state_dict())
    goal047._validate_neural_checkpoint(
        ROOT, state, width, shared_only=False
    )
    broken = dict(state)
    broken.pop(next(iter(broken)))
    with pytest.raises(goal047.Goal047Error, match="model_architecture_state_invalid"):
        goal047._validate_neural_checkpoint(
            ROOT, broken, width, shared_only=False
        )


def test_git_receipt_predicate_requires_tracked_identity_cleanliness_and_ancestry(
    tmp_path,
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Goal047 test"], cwd=tmp_path, check=True)
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n")
    subprocess.run(["git", "add", "receipt.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "receipt"], cwd=tmp_path, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert goal047._validate_git_predicate(tmp_path, receipt, commit) == (commit, True)

    (tmp_path / "dirty.txt").write_text("dirty")
    with pytest.raises(goal047.Goal047Error, match="opening_worktree_not_clean"):
        goal047._validate_git_predicate(tmp_path, receipt, commit)


def test_exclusive_marker_refuses_double_open(tmp_path):
    marker = tmp_path / "private" / "opening_started.json"
    goal047._create_opening_marker(marker, {"status": "started"})
    assert json.loads(marker.read_text()) == {"status": "started"}
    with pytest.raises(goal047.Goal047Error, match="opening_already_started"):
        goal047._create_opening_marker(marker, {"status": "started-again"})


def _surface_result(surface):
    results = [
        {
            "target": target,
            "counts": {
                "surface_rows": 1,
                "common_complete_cells": 0,
                "presence_n": 0,
                "background_n": 0,
                "missing_method_prediction": 0,
                "predictor_incomplete": 1,
            },
            "methods": {
                method: {
                    "threshold": 0.5,
                    "seed_count": len(goal047.SEEDS) if method in goal047.ARMS else 1,
                    "metrics": goal047._null_metrics("no_common_complete_cells"),
                }
                for method in goal047.METHODS
            },
        }
        for target in goal047.TARGETS
    ]
    contrasts = {
        f"multihead_full_finetune_minus_{method}": {
            "per_species": {target: None for target in goal047.TARGETS},
            "equal_species_mean": None,
            "equal_species_median": None,
            "nonnull_species_count": 0,
            "null_species_count": len(goal047.TARGETS),
            "nulls_ignored_in_equal_species_summary": True,
        }
        for method in goal047.METHODS
        if method != "multihead_full_finetune"
    }
    return {
        "schema_version": "goal047-surface-result-v2",
        "surface": surface,
        "targets": list(goal047.TARGETS),
        "common_complete_cells": 0,
        "results": results,
        "equal_species_summaries": {
            method: {
                metric: {
                    "mean": None,
                    "median": None,
                    "nonnull_species_count": 0,
                    "null_species_count": 5,
                    "nulls_ignored": True,
                }
                for metric in goal047.METRIC_NAMES
            }
            for method in goal047.METHODS
        },
        "contrasts": contrasts,
        "privacy": {
            "cell_level_outputs_tracked": False,
            "coordinates_tracked": False,
            "camera_identifiers_tracked": False,
            "row_payload_tracked": False,
        },
    }


def _postopening_diagnostics():
    return {
        "continuous_out_of_mainland_range": {
            name: {
                "below_mainland_minimum": 0,
                "above_mainland_maximum": 0,
                "missing": 0,
            }
            for name in goal047.CONTINUOUS
        },
        "categorical_unseen": {
            name: {"unseen_nonmissing": 0, "missing": 0}
            for name in goal047.CATEGORICAL
        },
        "descriptive_only_no_model_changes": True,
    }


def test_result_validation_is_private_schema_safe_and_never_reopens_payload(
    tmp_path, monkeypatch
):
    result = {
        "schema_version": "goal047-transfer-result-v2",
        "status": "production_complete",
        "surfaces": {
            "primary": _surface_result("primary"),
            "secondary": _surface_result("secondary"),
        },
        "postopening_predictor_diagnostics": _postopening_diagnostics(),
        "preopening_access_counters": {
            "response_rows_read": 0,
            "predictor_rows_read": 0,
        },
        "postopening_access_counters": {
            "response_file_opens": 1,
            "predictor_file_opens": 1,
            "response_rows_read": 5,
            "predictor_rows_read": 10,
            "predictor_rows_used": 0,
        },
        "privacy": {
            "cell_level_outputs_tracked": False,
            "coordinates_tracked": False,
            "camera_identifiers_tracked": False,
            "row_payload_tracked": False,
        },
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result))
    opening_path = tmp_path / "opening.json"
    opening_path.write_text(
        json.dumps(
            {
                "schema_version": "goal047-opening-v2",
                "status": "sealed_ready_for_opening",
                "production_authorized": True,
                "threshold_table": {
                    method: {target: 0.5 for target in goal047.TARGETS}
                    for method in goal047.METHODS
                },
                "expected_coverage": {
                    "targets": list(goal047.TARGETS),
                    "methods": list(goal047.METHODS),
                    "neural_seed_labels": list(goal047.SEEDS),
                    "method_seed_table": {
                        target: {
                            method: (
                                list(goal047.SEEDS)
                                if method in goal047.ARMS
                                else ["seed00"]
                            )
                            for method in goal047.METHODS
                        }
                        for target in goal047.TARGETS
                    },
                },
            }
        )
    )
    completed = tmp_path / "private" / "opening_completed.json"
    completed.parent.mkdir()
    completed.write_text(
        json.dumps(
            {
                "schema_version": "goal047-opening-completed-v2",
                "status": "complete",
                "access_counters": result["postopening_access_counters"],
                "result_sha256": sha256_file(path),
            }
        )
    )
    monkeypatch.setattr(
        goal047,
        "_config",
        lambda root: {
            "execution": {
                "tracked_summary": "unused.json",
                "private_root": "private",
                "opening_receipt": "opening.json",
            }
        },
    )
    monkeypatch.setattr(
        goal047,
        "_tracked_identical",
        lambda root, path: Path(path).resolve() == opening_path.resolve(),
    )
    assert goal047.validate_result(tmp_path, path)["targets"] == 5

    wrong_threshold = json.loads(json.dumps(result))
    wrong_threshold["surfaces"]["primary"]["results"][0]["methods"][goal047.ARMS[0]]["threshold"] = 0.4
    path.write_text(json.dumps(wrong_threshold))
    with pytest.raises(goal047.Goal047Error, match="result_method_authority_invalid"):
        goal047.validate_result(tmp_path, path)

    wrong_seed_count = json.loads(json.dumps(result))
    wrong_seed_count["surfaces"]["secondary"]["results"][0]["methods"][goal047.ARMS[0]]["seed_count"] = 4
    path.write_text(json.dumps(wrong_seed_count))
    with pytest.raises(goal047.Goal047Error, match="result_method_authority_invalid"):
        goal047.validate_result(tmp_path, path)

    malformed = json.loads(json.dumps(result))
    del malformed["surfaces"]["primary"]["results"][0]["methods"][goal047.ARMS[0]]["metrics"]
    path.write_text(json.dumps(malformed))
    with pytest.raises(goal047.Goal047Error, match="result_method_schema_invalid"):
        goal047.validate_result(tmp_path, path)

    result["private_cell_id"] = "forbidden"
    path.write_text(json.dumps(result))
    with pytest.raises(goal047.Goal047Error, match="result_contains_private_material"):
        goal047.validate_result(tmp_path, path)


def test_production_api_and_cli_have_no_injected_prediction_bypass():
    assert list(inspect.signature(goal047.one_shot_evaluate).parameters) == ["root"]
    with pytest.raises(SystemExit):
        goal047.main(
            ["evaluate", "--root", str(ROOT), "--predictions", "external.json"]
        )


def test_opening_gate_fails_closed_without_receipt():
    with pytest.raises(goal047.Goal047Error, match="opening_receipt_missing"):
        goal047.validate_opening_gate(ROOT)


def test_live_input_gate_is_zero_zero():
    result = goal047.validate_inputs(ROOT)
    assert result["status"] == "goal047_inputs_ready"
    assert result["preopening_tasmania_response_rows_read"] == 0
    assert result["preopening_tasmania_predictor_rows_read"] == 0
