from __future__ import annotations

import numpy as np
import pytest

from dsdm.real_data import (
    CATEGORICAL_LEVELS,
    FEATURE_NAMES,
    RealDataError,
    CaseSpec,
    build_bundle_from_records,
    bundle_digest,
    load_bundle,
    save_bundle,
    validate_bundle,
    validate_auxiliary_records,
    export_content_addressed_bundle,
)


def _records(n_species=8, n_cells=25):
    species = tuple(f"species_{i:02d}" for i in range(n_species))
    records = []
    for si, name in enumerate(species):
        for cell in range(n_cells):
            fold = f"fold{cell % 5:02d}"
            src = "presence" if cell % 3 == 0 else "survey_supported_absence"
            records.append({"species": name, "cell": f"c{cell:03d}", "fold": fold,
                            "y": 1.0 if src == "presence" else 0.0, "source": src,
                            "x": np.arange(25, dtype=np.float32) + cell / 100,
                            "soil_class": 2 + (cell % 13), "veg_mvg": (1, 2, 3, 4, 5, 7, 9, 10, 11, 15, 16, 17, 18, 19, 21, 22, 24, 25, 26, 27, 29, 31)[cell % 22],
                            "landuse_secondary": (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18)[cell % 17],})
    return records


def test_feature_schema_is_full_nominal_one_hot_contract():
    assert len(FEATURE_NAMES) == 77
    assert len(CATEGORICAL_LEVELS["soil_class"]) == 13
    assert len(CATEGORICAL_LEVELS["veg_mvg"]) == 22
    assert len(CATEGORICAL_LEVELS["landuse_secondary"]) == 17


def test_bundle_roles_are_nested_and_exclude_pseudoabsence():
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    assert bundle.x_discovery.shape[1] == 77
    assert len(bundle.x_discovery) < len(bundle.x_replay)
    assert len(bundle.x_replay) + len(bundle.x_inner_assessment) == 25
    assert bundle.metadata["auxiliary_species_count"] == 7
    assert bundle.metadata["auxiliary_pseudoabsence_rows"] == 0
    assert np.isfinite(bundle.x_discovery).all()


def test_target_pseudoabsence_is_a_primary_zero_but_auxiliary_is_excluded():
    rows = _records()
    rows[2]["source"] = "pseudoabsence"
    rows[2].pop("y", None)
    rows[27]["source"] = "pseudoabsence"
    rows[27].pop("y", None)
    bundle = build_bundle_from_records(rows, CaseSpec("light", "species_00", "fold03", "resmlp00", 31032), strict_scope=False)
    assert bundle.metadata["target_pseudoabsence_rows"] == 1
    assert bundle.metadata["auxiliary_pseudoabsence_rows"] == 1
    assert sum(bundle.y_replay == 0.0) >= 2


def test_foundation_serializer_reuses_case_held_transform(monkeypatch, tmp_path):
    import json
    import dsdm_phase1.goal029_production as production
    from dsdm_phase1.modeling_contract import RowKey
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/dsdm_real_compute_calibration.json").read_text())

    key = RowKey("species_00", "cell000")
    class Rows:
        keys = (key,); pa = np.asarray([1], dtype=np.int8); response_source = ("presence",)
    class Broker:
        _rows = Rows(); _fold_by_key = {key: "fold00"}
    class Provider:
        def _value(self, _key, transform):
            assert transform == "cv_fold03"
            return {"continuous": [0.0] * 25, "categorical": {"soil_class": "2", "veg_mvg": "1", "landuse_secondary": "1"}}
    class Vault:
        attempted_open_count = 0; open_count = 0
    monkeypatch.setattr(production, "ingest_production_foundation", lambda root, config: (Broker(), Provider(), Vault()))
    records, _ = __import__("dsdm.real_data", fromlist=["records_from_foundation"]).records_from_foundation(root, config, CaseSpec("light", "species_00", "fold03", "resmlp00", 31032))
    assert records[0]["x"] == [0.0] * 25


def test_goal032_binding_loads_bound_goal029_config(monkeypatch):
    import json
    import dsdm_phase1.goal029_production as production
    from dsdm.real_data import records_from_foundation
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/dsdm_real_compute_calibration.json").read_text())
    captured = {}
    key = __import__("dsdm_phase1.modeling_contract", fromlist=["RowKey"]).RowKey("species_00", "cell000")
    class Rows:
        keys = (key,); pa = np.asarray([1], dtype=np.int8); response_source = ("presence",)
    class Broker:
        _rows = Rows(); _fold_by_key = {key: "fold00"}
    class Provider:
        def _value(self, _key, _transform):
            return {"continuous": [0.0] * 25, "categorical": {"soil_class": "2", "veg_mvg": "1", "landuse_secondary": "1"}}
    class Vault:
        attempted_open_count = 0; open_count = 0
    def fake_ingest(_root, supplied):
        captured.update(supplied); return Broker(), Provider(), Vault()
    monkeypatch.setattr(production, "ingest_production_foundation", fake_ingest)
    records_from_foundation(root, config, CaseSpec("light", "species_00", "fold03", "resmlp00", 31032))
    assert captured.get("identity", {}).get("goal_id", "").startswith("goal029-")


def test_goal032_binding_verifies_feature_authorities_before_ingest():
    import copy
    import json
    from dsdm.real_data import records_from_foundation
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/dsdm_real_compute_calibration.json").read_text())
    config = copy.deepcopy(config)
    config["bindings"]["goal026_feature_contract"]["sha256"] = "0" * 64
    with pytest.raises(RealDataError, match="goal026_feature_contract binding digest mismatch"):
        records_from_foundation(root, config, CaseSpec("light", "species_00", "fold03", "resmlp00", 31032))


def test_bundle_round_trip_is_digest_stable(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    path = tmp_path / "bundle.npz"
    save_bundle(bundle, path)
    assert validate_bundle(path, {"case_id": "light", "architecture": {"id": "resmlp00"}}).metadata["bundle_digest"]
    restored = load_bundle(path)
    assert bundle_digest(bundle) == bundle_digest(restored)
    assert np.array_equal(bundle.x_replay, restored.x_replay)


def test_bundle_rejects_nan_and_pickle(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    rows = _records()
    rows[0]["x"] = np.full(25, np.nan, dtype=np.float32)
    with pytest.raises(RealDataError):
        build_bundle_from_records(rows, case, strict_scope=False)
    bad = tmp_path / "bad.npz"
    np.savez(bad, payload=np.asarray([{"x": 1}], dtype=object))
    with pytest.raises(RealDataError):
        load_bundle(bad)


def test_bundle_manifest_rejects_array_tamper(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    path = tmp_path / "bundle.npz"
    save_bundle(bundle, path)
    with np.load(path, allow_pickle=False) as source:
        values = {name: source[name] for name in source.files}
    values["x_discovery"] = values["x_discovery"].copy()
    values["x_discovery"][0, 0] += 1.0
    tampered = tmp_path / "tampered.npz"
    np.savez_compressed(tampered, **values)
    with pytest.raises(RealDataError):
        validate_bundle(tampered, {"case_id": "light", "architecture": {"id": "resmlp00"}})


def test_portable_manifest_binds_identity_authorities_and_all_arrays(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    path = tmp_path / "bundle.npz"
    save_bundle(bundle, path)
    with np.load(path, allow_pickle=False) as payload:
        envelope = __import__("json").loads(bytes(payload["metadata_json"].tolist()).decode())
        manifest = envelope["metadata"]
        assert manifest["target"] == "species_00"
        assert manifest["held_fold"] == "fold03"
        assert manifest["stopping_fold"] == "fold04"
        assert manifest["transform"] == "cv_fold03"
        assert manifest["outer_attempted"] == manifest["outer_opened"] == 0
        assert set(manifest["array_digests"]) == {"x_discovery", "y_discovery", "x_stopping", "y_stopping", "x_replay", "y_replay", "x_held"}
        assert "source_membership" not in __import__("json").dumps(manifest)
    expected = {"case_id": "light", "target": "species_00", "held_fold": "fold03", "stopping_fold": "fold04", "architecture": {"id": "resmlp00"}, "seed": 31032}
    validate_bundle(path, expected)


def test_manifest_distinguishes_global_base_seed_from_derived_case_seed(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 987654321)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    metadata = dict(bundle.metadata)
    metadata["base_seed"] = 31032
    bound = type(bundle)(
        bundle.case,
        bundle.x_discovery,
        bundle.y_discovery,
        bundle.x_stopping,
        bundle.y_stopping,
        bundle.x_replay,
        bundle.y_replay,
        bundle.x_inner_assessment,
        bundle.y_inner_assessment,
        metadata,
    )
    path = tmp_path / "bundle.npz"
    save_bundle(bound, path)
    restored = validate_bundle(
        path,
        {
            "case_id": "light",
            "target": "species_00",
            "held_fold": "fold03",
            "stopping_fold": "fold04",
            "architecture": {"id": "resmlp00"},
            "seed": 987654321,
            "base_seed": 31032,
        },
    )
    assert restored.metadata["seed"] == 987654321
    assert restored.metadata["base_seed"] == 31032


def test_bundle_validation_uses_exact_goal032_source_digest(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    metadata = dict(bundle.metadata)
    metadata["goal032_config_digest"] = "a" * 64
    bound = type(bundle)(
        bundle.case,
        bundle.x_discovery,
        bundle.y_discovery,
        bundle.x_stopping,
        bundle.y_stopping,
        bundle.x_replay,
        bundle.y_replay,
        bundle.x_inner_assessment,
        bundle.y_inner_assessment,
        metadata,
    )
    path = tmp_path / "bundle.npz"
    save_bundle(bound, path)
    validate_bundle(
        path,
        {"case_id": "light", "architecture": {"id": "resmlp00"}},
        {"_source_sha256": "a" * 64},
    )
    with pytest.raises(RealDataError, match="config binding"):
        validate_bundle(
            path,
            {"case_id": "light", "architecture": {"id": "resmlp00"}},
            {"_source_sha256": "b" * 64},
        )


@pytest.mark.parametrize("field,value", [("target", "species_01"), ("held_fold", "fold02"), ("transform", "cv_fold02"), ("outer_opened", 1)])
def test_validate_bundle_rejects_manifest_identity_mutation(tmp_path, field, value):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    path = tmp_path / "bundle.npz"
    save_bundle(build_bundle_from_records(_records(), case, strict_scope=False), path)
    with np.load(path, allow_pickle=False) as payload:
        values = {name: payload[name] for name in payload.files}
    envelope = __import__("json").loads(bytes(values["metadata_json"].tolist()).decode())
    envelope["metadata"][field] = value
    values["metadata_json"] = np.frombuffer(__import__("json").dumps(envelope, sort_keys=True).encode(), dtype=np.uint8)
    tampered = tmp_path / "tampered.npz"
    np.savez_compressed(tampered, **values)
    with pytest.raises(RealDataError):
        validate_bundle(tampered, {"case_id": "light", "target": "species_00", "held_fold": "fold03", "stopping_fold": "fold04", "architecture": {"id": "resmlp00"}, "seed": 31032})


def test_auxiliary_validation_is_four_fold_equal_weight_and_counts_unseen():
    rows = _records()
    rows[26]["soil_class"] = 999
    summary = validate_auxiliary_records(rows, "species_00", "fold03")
    assert summary["species_count"] == 7
    assert summary["fold_count"] == 4
    assert summary["equal_species_weight"] == pytest.approx(1 / 7)
    assert summary["unseen_category_counts"]["soil_class"] == 1


def test_content_addressed_export_updates_local_index(tmp_path):
    case = CaseSpec("light", "species_00", "fold03", "resmlp00", 31032)
    bundle = build_bundle_from_records(_records(), case, strict_scope=False)
    path, index = export_content_addressed_bundle(bundle, tmp_path)
    assert path.name == f"light-{bundle_digest(bundle)}.npz"
    assert index["light"]["bundle_digest"] == bundle_digest(bundle)
    assert (tmp_path / "index.json").is_file()
