import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dsdm_phase1 import model_ready_features as mf  # noqa: E402


def synthetic(n=12):
    rows = []
    assignments = []
    for i in range(n):
        row = {name: float(i + j + 1) for j, name in enumerate(mf.CONTINUOUS)}
        row.update({"grid_cell_id": f"g{i:02d}", "soil_class": str(i % 2 + 1), "veg_mvg": str(i % 3 + 1), "landuse_secondary": str(i % 4 + 1)})
        rows.append(row)
        assignments.append({"grid_cell_id": row["grid_cell_id"], "outer_role": "outer_train" if i < 10 else "test", "cv_fold": f"fold{i % 5:02d}" if i < 10 else ""})
    return rows, assignments


def test_fit_membership_and_population_standardisation():
    rows, assignments = synthetic()
    par = mf.fit_transform(rows, assignments, "outer")
    assert par.training_count == 10
    z, nominal = par.apply_blocks(rows[:10])
    assert np.allclose(np.mean(z[:, [0, 1]], axis=0), 0.0)
    assert np.allclose(np.std(z[:, [0, 1]], axis=0, ddof=0), 1.0)
    restored = par.inverse_continuous(z)
    expected = np.asarray([[float(i + j + 1) for j, _ in enumerate(mf.CONTINUOUS)] for i in range(10)])
    assert np.allclose(restored, expected, atol=1e-10)


def test_held_out_perturbation_does_not_change_fit_but_training_does():
    rows, assignments = synthetic()
    first = mf.fit_transform(rows, assignments, "outer")
    held = [dict(x) for x in rows]; held[-1][mf.CONTINUOUS[0]] = 999999
    assert mf.fit_transform(held, assignments, "outer").to_dict() == first.to_dict()
    changed = [dict(x) for x in rows]; changed[0][mf.CONTINUOUS[0]] = 999999
    assert mf.fit_transform(changed, assignments, "outer").means[mf.CONTINUOUS[0]] != first.means[mf.CONTINUOUS[0]]


def test_order_and_response_values_do_not_influence_fit():
    rows, assignments = synthetic()
    first = mf.fit_transform(rows, assignments, "outer")
    shuffled = list(reversed(rows))
    assert mf.fit_transform(shuffled, assignments, "outer").to_dict() == first.to_dict()


def test_duplicate_keys_and_unknown_transform_fail():
    rows, assignments = synthetic()
    with pytest.raises(mf.ModelReadyFeatureError, match="duplicate"):
        mf.fit_transform(rows + [rows[0]], assignments + [assignments[0]], "outer")
    with pytest.raises(mf.ModelReadyFeatureError, match="unknown"):
        mf.fit_transform(rows, assignments, "bad")


def test_categorical_vocabulary_is_nominal_and_lazy_materialisation():
    rows, assignments = synthetic()
    params = mf.fit_all_transforms(rows, assignments)
    vocab = mf.categorical_vocabulary(rows)
    assert vocab["soil_class"]["levels"] == ["1", "2"]
    assert vocab["soil_class"]["semantics"] == "nominal_raw_code"
    substrate = mf.LazyFeatureSubstrate(rows, params)
    chunks = list(substrate.iter_materialized("outer", chunk_size=5))
    assert sum(x.grid_cell_ids.size for x in chunks) == len(rows)
    assert all(x.continuous.dtype == np.float64 for x in chunks)
    assert all(x.categorical.dtype.kind in "OUS" for x in chunks)
    unknown = dict(rows[0]); unknown["soil_class"] = "999"
    with pytest.raises(mf.ModelReadyFeatureError, match="unknown_category"):
        params["outer"].apply_blocks([unknown])


def test_identity_bearing_selection_and_no_numeric_category_matrix():
    rows, assignments = synthetic()
    substrate = mf.LazyFeatureSubstrate(rows, mf.fit_all_transforms(rows, assignments))
    result = substrate.materialize("outer", grid_cell_ids=["g09", "g01"])
    assert result.grid_cell_ids.tolist() == ["g09", "g01"]
    assert result.continuous_names == mf.CONTINUOUS
    assert result.categorical_names == mf.CATEGORICAL
    assert result.categorical.dtype.kind in "OUS"
    with pytest.raises(mf.ModelReadyFeatureError, match="unknown_requested_id"):
        substrate.materialize("outer", grid_cell_ids=["g99"])
    with pytest.raises(mf.ModelReadyFeatureError, match="duplicate_requested_id"):
        substrate.materialize("outer", grid_cell_ids=["g01", "g01"])


def test_transform_id_literal_and_injective_tokens():
    rows, assignments = synthetic()
    with pytest.raises(mf.ModelReadyFeatureError, match="unknown_transform_id"):
        mf.fit_transform(rows, assignments, "cv_fold11")
    values = ["a b", "a_b", "", "é"]
    tokens = [mf.safe_level_token(x) for x in values]
    assert len(set(tokens)) == len(tokens)


def test_hard_failure_missing_nonfinite_and_zero_sd():
    rows, assignments = synthetic()
    missing = [dict(x) for x in rows]; del missing[0][mf.CONTINUOUS[0]]
    with pytest.raises(mf.ModelReadyFeatureError): mf.fit_transform(missing, assignments, "outer")
    nonfinite = [dict(x) for x in rows]; nonfinite[0][mf.CONTINUOUS[0]] = "nan"
    with pytest.raises(mf.ModelReadyFeatureError): mf.fit_transform(nonfinite, assignments, "outer")
    zero = [dict(x) for x in rows]
    for row in zero: row[mf.CONTINUOUS[0]] = 1.0
    with pytest.raises(mf.ModelReadyFeatureError, match="zero_or_nonfinite_sd"): mf.fit_transform(zero, assignments, "outer")


def test_plan_and_refreshed_manifest_tamper_are_rejected(tmp_path):
    plan = json.loads((ROOT / "config/model_ready_feature_plan.json").read_text())
    broken = dict(plan); broken["stopped_before"] = []
    with pytest.raises(mf.ModelReadyFeatureError, match="contract|plan"):
        mf.validate_plan(broken)
    evidence = tmp_path / "evidence"; evidence.mkdir()
    for source in (ROOT / "evidence/model_ready_features/2026-07-27").iterdir():
        (evidence / source.name).write_bytes(source.read_bytes())
    fit = json.loads((evidence / "fit_parameters.json").read_text()); fit["fits"]["outer"]["training_count"] += 1
    (evidence / "fit_parameters.json").write_text(mf.json_text(fit))
    manifest = mf._manifest(evidence); (evidence / "manifest.json").write_text(mf.json_text(manifest))
    with pytest.raises(mf.ModelReadyFeatureError, match="fit_evidence_drift"):
        mf.validate_evidence(ROOT, evidence)


def test_atomic_pair_publication_rolls_back_second_failure(tmp_path, monkeypatch):
    stage = tmp_path / "stage"; stage.mkdir(); staged_e = stage / "e"; staged_p = stage / "p"; staged_e.mkdir(); staged_p.mkdir()
    destination_e = tmp_path / "evidence"; destination_p = tmp_path / "private"
    original = mf.os.replace; calls = []
    def fail_second(src, dst):
        calls.append(dst)
        if len(calls) == 2: raise OSError("injected")
        return original(src, dst)
    monkeypatch.setattr(mf.os, "replace", fail_second)
    with pytest.raises(mf.ModelReadyFeatureError, match="rollback"):
        mf._publish_pair(staged_e, staged_p, destination_e, destination_p)
    assert not destination_e.exists() and not destination_p.exists()


@pytest.mark.parametrize("name", ["bindings.json", "review.json"])
def test_required_tracked_role_missing_or_refreshed_binding_tamper_fails(tmp_path, name):
    evidence = tmp_path / "evidence"; evidence.mkdir()
    source = ROOT / "evidence/model_ready_features/2026-07-27"
    for item in source.iterdir(): (evidence / item.name).write_bytes(item.read_bytes())
    if name == "bindings.json":
        payload = json.loads((evidence / name).read_text()); payload["bindings"]["goal024_map"]["sha256"] = "0" * 64; (evidence / name).write_text(mf.json_text(payload))
    else:
        (evidence / name).unlink()
    (evidence / "manifest.json").write_text(mf.json_text(mf._manifest(evidence)))
    with pytest.raises(mf.ModelReadyFeatureError): mf.validate_evidence(ROOT, evidence)


def test_feature_block_shape_and_private_semantic_drift_fail(tmp_path):
    evidence = tmp_path / "evidence"; private = tmp_path / "private"
    import shutil
    shutil.copytree(ROOT / "evidence/model_ready_features/2026-07-27", evidence)
    shutil.copytree(ROOT / "data/processed/features/goal026-model-ready-feature-substrate/2026-07-27", private)
    contract = json.loads((evidence / "feature_contract.json").read_text()); contract["continuous_shape"] = ["n_rows", 28]; (evidence / "feature_contract.json").write_text(mf.json_text(contract)); (evidence / "manifest.json").write_text(mf.json_text(mf._manifest(evidence)))
    with pytest.raises(mf.ModelReadyFeatureError, match="contract"):
        mf.validate_evidence(ROOT, evidence, private)
    shutil.copytree(ROOT / "evidence/model_ready_features/2026-07-27", evidence, dirs_exist_ok=True)
    rows = list(csv.DictReader((private / "response_support.csv").open(newline=""))); rows[0]["marginal_envelope_supported"] = "false"
    with (private / "response_support.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    meta = json.loads((evidence / "output_metadata.json").read_text()); meta["private_roles"]["response_support.csv"]["bytes"] = (private / "response_support.csv").stat().st_size; meta["private_roles"]["response_support.csv"]["sha256"] = mf.sha256(private / "response_support.csv"); (evidence / "output_metadata.json").write_text(mf.json_text(meta)); (evidence / "manifest.json").write_text(mf.json_text(mf._manifest(evidence)))
    with pytest.raises(mf.ModelReadyFeatureError, match="private|output"):
        mf.validate_evidence(ROOT, evidence, private)


def test_real_frozen_counts_and_six_fit_sets():
    maps, cells, response, assignments = mf.load_frozen_inputs(ROOT)
    assert (len(maps), len(cells), len(response), len(assignments)) == (mf.MAP_ROWS, mf.RESPONSE_CELLS, mf.RESPONSE_ROWS, mf.MAP_ROWS)
    params = mf.fit_all_transforms(maps, assignments)
    assert tuple(params) == mf.TRANSFORMS
    assert [params[x].training_count for x in mf.TRANSFORMS] == [64270, 52016, 53231, 52497, 50449, 48887]
    assert all(all(x > 0 and np.isfinite(x) for x in p.population_sd.values()) for p in params.values())


def test_evidence_manifest_and_private_receipt():
    evidence = ROOT / "evidence/model_ready_features/2026-07-27"
    manifest = json.loads((evidence / "manifest.json").read_text())
    assert manifest["goal_id"] == mf.GOAL_ID
    assert set(manifest["files"]) == {"bindings.json", "feature_contract.json", "fit_parameters.json", "output_metadata.json", "review.json", "summary.json", "support_summary.json"}
    private = ROOT / "data/processed/features/goal026-model-ready-feature-substrate/2026-07-27"
    with (private / "response_support.csv").open(newline="") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == 76266
