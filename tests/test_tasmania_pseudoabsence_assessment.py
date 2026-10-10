"""Response-access gate and closed-prediction integrity, using synthetic data."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
spec_math = importlib.util.spec_from_file_location("tasmania_pseudoabsence_metrics", SCRIPTS / "tasmania_pseudoabsence_metrics.py")
math = importlib.util.module_from_spec(spec_math)
sys.modules[spec_math.name] = math
spec_math.loader.exec_module(math)
spec = importlib.util.spec_from_file_location("sensitivity_assessment", SCRIPTS / "tasmania_pseudoabsence_assessment.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_receipt_tamper_refused(tmp_path):
    path = tmp_path / "receipt.json"
    m.write_new_json(path, {"count": 3})
    assert m.verified_receipt(path)["count"] == 3
    value = json.loads(path.read_text())
    value["count"] = 2
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="digest mismatch"):
        m.verified_receipt(path)


def test_incomplete_closure_never_opens_responses(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "EVIDENCE", tmp_path / "evidence")
    m.write_new_json(tmp_path / "prediction-closure.json", {
        "status": "accepted", "outer_held_response_labels_read": 0,
        "target_physical_fits": 8124, "smoke_physical_fits": 14, "recovery_physical_fits": 200})
    def prohibited(*args, **kwargs):
        raise AssertionError("response access happened before closure")
    monkeypatch.setattr(m, "open_held_response_once", prohibited)
    with pytest.raises(ValueError, match="fit inventory incomplete"):
        m.score(tmp_path)


def test_literal_fit_counts_without_source_closures_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "EVIDENCE", tmp_path / "evidence")
    m.write_new_json(tmp_path / "prediction-closure.json", {
        "status": "accepted", "outer_held_response_labels_read": 0,
        "target_physical_fits": 8125, "smoke_physical_fits": 14, "recovery_physical_fits": 200,
        "assessment_source_sha256": m.sha(m.__file__),
        "metrics_source_sha256": m.sha(SCRIPTS / "tasmania_pseudoabsence_metrics.py"),
        "baseline_receipt_digest": m.BASE_RECEIPT_DIGEST, "source_closures": []})
    def prohibited(*args, **kwargs):
        raise AssertionError("response access happened before source qualification")
    monkeypatch.setattr(m, "open_held_response_once", prohibited)
    with pytest.raises(ValueError, match="source-closure role inventory"):
        m.score(tmp_path)


def test_partial_outputs_refuse_before_closure_or_response_access(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(m, "EVIDENCE", evidence)
    (evidence / "paired-performance.csv").write_text("partial\n")
    def prohibited(*args, **kwargs):
        raise AssertionError("validation or response access occurred after stale output")
    monkeypatch.setattr(m, "validate_closure", prohibited)
    monkeypatch.setattr(m, "open_held_response_once", prohibited)
    with pytest.raises(ValueError, match="prior assessment output"):
        m.score(tmp_path)


def test_response_intent_precedes_hashes_and_snapshot_excludes_training(tmp_path, monkeypatch):
    response = tmp_path / "synthetic-source.csv"
    response.write_text("species_id,grid_cell_id,outer_role,microcluster,pa,pa_type\n"
                        "sp,a,test,mc08,1,presence\n"
                        "sp,training,deliberately malformed unparsed trailing fields\n"
                        "sp,b,test,mc08,0,survey_supported_absence\n")
    monkeypatch.setattr(m, "RESPONSE", response)
    original_sha = m.sha
    monkeypatch.setattr(m, "RESPONSE_SHA", original_sha(response))
    integrity_passes = []
    def checked_sha(path):
        assert (tmp_path / "response-access-intent.json").is_file()
        integrity_passes.append(path)
        return original_sha(path)
    monkeypatch.setattr(m, "sha", checked_sha)
    rows, access = m.open_held_response_once({"receipt_digest": "a" * 64},
        {"sp": {"grid_cell_id": np.array(["a", "b"])}}, tmp_path)
    assert set(rows) == {("sp", "a"), ("sp", "b")}
    assert len(integrity_passes) == access["integrity_hash_passes"] == 2
    assert access["canonical_file_opens"] == 3 and access["response_parses"] == 1
    snapshot = m.verified_receipt(tmp_path / "held-response-snapshot.json")
    assert snapshot["receipt_digest"] == access["private_snapshot_receipt_digest"]
    assert [row["grid_cell_id"] for row in snapshot["rows"]] == ["a", "b"]
    assert all(set(row) == {"species_id", "grid_cell_id", "microcluster", "pa", "pa_type"} for row in snapshot["rows"])


def fixture_arrays():
    return {"grid_cell_id": np.array(["a", "b"]), "patch": np.array(["mc08", "mc08"]),
            "primary_scores": np.full((7, 3, 2), 0.5), "sensitivity_scores": np.full((7, 3, 2), 0.5),
            "primary_thresholds": np.full((7, 3), 0.5), "sensitivity_thresholds": np.full((7, 3), 0.5),
            "map_grid_cell_id": np.array([f"cell{i:05}" for i in range(71023)]),
            "primary_map_scores": np.full((3, 71023), 0.5), "sensitivity_map_scores": np.full((3, 71023), 0.5)}


def test_closed_predictions_and_negative_control(tmp_path):
    path = tmp_path / "synthetic.npz"
    arrays = fixture_arrays()
    np.savez_compressed(path, **arrays)
    expected = m.sha(path)
    m.validate_prediction_file(path, expected, "thylogale_billardierii")
    arrays["sensitivity_scores"][0, 0, 0] = 0.6
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="file changed"):
        m.validate_prediction_file(path, expected, "thylogale_billardierii")
    with pytest.raises(ValueError, match="negative control failed"):
        m.validate_prediction_file(path, m.sha(path), "thylogale_billardierii")


def test_map_identity_duplicates_refused(tmp_path):
    path = tmp_path / "synthetic.npz"
    arrays = fixture_arrays()
    arrays["map_grid_cell_id"][0] = arrays["map_grid_cell_id"][1]
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="map domain invalid"):
        m.validate_prediction_file(path, m.sha(path), "dasyurus_viverrinus")


def test_primary_probabilities_checked_even_if_ranks_and_classifications_match(tmp_path, monkeypatch):
    species = "dasyurus_viverrinus"
    monkeypatch.setattr(m, "BASELINE", tmp_path)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "predictions/averaged").mkdir(parents=True)
    np.savez(tmp_path / "inputs" / f"{species}.npz", grid_cell_id=np.array(["a", "b"]), patch=np.array(["mc08", "mc08"]))
    neural = np.broadcast_to([0.2, 0.8], (7, 6, 2)).copy()
    conventional = np.broadcast_to([0.2, 0.8], (7, 5, 2)).copy()
    np.savez(tmp_path / "predictions/averaged" / f"{species}.npz", neural_mean=neural, conventional_mean=conventional)
    a = {"grid_cell_id": np.array(["a", "b"]), "patch": np.array(["mc08", "mc08"]),
         "primary_scores": np.broadcast_to([0.2, 0.8], (7, 3, 2)).copy(), "primary_thresholds": np.full((7, 3), 0.5)}
    thresholds = {(species, endpoint, method): 0.5 for endpoint in m.ENDPOINTS
                  for method in ("target_only_resmlp", "multihead_full_finetune", "conventional/random_forest")}
    selected = {(species, endpoint): "random_forest" for endpoint in m.ENDPOINTS}
    m.validate_normalized_primary({species: a}, thresholds, selected)
    a["primary_scores"][0, 0] = [0.3, 0.7]
    with pytest.raises(ValueError, match="probabilities changed"):
        m.validate_normalized_primary({species: a}, thresholds, selected)
