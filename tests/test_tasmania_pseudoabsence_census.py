from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from dsdm_phase1.modeling_contract import RowSet


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tasmania_pseudoabsence_census", ROOT / "scripts/tasmania_pseudoabsence_census.py")
assert SPEC and SPEC.loader
census = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(census)


def _rows(*sources: str):
    records = []
    for index, source in enumerate(sources):
        pa = 1 if source == "presence" else 0
        records.append({
            "species_id": "synthetic_species",
            "grid_cell_id": f"cell_{index:02d}",
            "pa": pa,
            "pa_type": source,
            "microcluster": "mc00",
        })
    return RowSet.from_records(records)


def test_pseudoabsence_subtraction_is_exact_and_source_specific():
    rows = _rows("presence", "survey_supported_absence", "pseudoabsence", "presence")
    retained, excluded = census.filter_rowset_without_pseudoabsence(rows)

    assert len(retained.keys) == 3
    assert len(excluded) == 1
    assert {key.grid_cell_id for key in excluded} == {"cell_02"}
    assert "pseudoabsence" not in retained.response_source
    assert set(retained.keys) | set(excluded) == set(rows.keys)
    assert set(retained.keys).isdisjoint(excluded)
    assert census._id_digest(excluded) != census._id_digest(retained.keys)


def test_classloss_refuses_filter_without_pooling_or_dropping():
    rows = _rows("presence", "pseudoabsence")

    with pytest.raises(census.CensusError, match="missing_class_after_pseudoabsence_removal"):
        census.filter_rowset_without_pseudoabsence(rows)


def test_membership_digest_mismatch_fails_closed():
    with pytest.raises(census.CensusError, match="membership_digest_mismatch:synthetic"):
        census.verify_membership_digest("a" * 64, "b" * 64, "synthetic")


def test_held_label_and_source_payload_is_not_parsed(tmp_path: Path):
    path = tmp_path / "response.csv"
    path.write_text(
        "species_id,grid_cell_id,pa,pa_type\n"
        "synthetic_species,train_cell,1,presence\n"
        'synthetic_species,held_cell,"POISON\n',
        encoding="utf-8",
    )
    parsed = census._read_allowlisted_response_rows(
        path,
        {("synthetic_species", "train_cell")},
        {"train_cell": {"microcluster": "mc00", "cv_fold": "fold00"}},
    )

    assert parsed == [{
        "species_id": "synthetic_species",
        "grid_cell_id": "train_cell",
        "pa": 1,
        "pa_type": "presence",
        "microcluster": "mc00",
        "cv_fold": "fold00",
    }]


def test_response_free_binding_fails_before_source_parser(monkeypatch: pytest.MonkeyPatch):
    original = census.sha256_file

    def altered(path: Path) -> str:
        if path.name == "response_support.csv":
            return "0" * 64
        return original(path)

    monkeypatch.setattr(census, "sha256_file", altered)
    monkeypatch.setattr(census, "_read_csv", lambda *_args, **_kwargs: pytest.fail("source parser reached"))
    with pytest.raises(census.CensusError, match="response_support_binding_mismatch"):
        census._load_bindings(ROOT)


def test_saved_bundle_metadata_tamper_is_rejected(monkeypatch: pytest.MonkeyPatch):
    original = census._bundle_inventory
    changed = False

    def tampered(path: Path):
        nonlocal changed
        metadata, inventory = original(path)
        if not changed:
            changed = True
            metadata = dict(metadata)
            metadata["target"] = "tampered_species"
        return metadata, inventory

    monkeypatch.setattr(census, "_bundle_inventory", tampered)
    with pytest.raises(census.CensusError, match="bundle_target_mismatch"):
        census.run_census(ROOT)


def test_metadata_commitment_checked_without_reading_response_arrays(tmp_path: Path):
    import numpy as np

    metadata = {"target": "synthetic_species", "array_digests": {"y_held": "a" * 64}}
    metadata["bundle_digest"] = census.digest_value({"metadata": metadata, "arrays": metadata["array_digests"]})
    path = tmp_path / "bundle.npz"

    def save():
        np.savez(path, metadata_json=np.frombuffer(census._canonical(metadata), dtype=np.uint8),
                 y_held=np.array([{"poison": "requires forbidden pickle access"}], dtype=object))

    save()
    actual, _ = census._bundle_inventory(path)
    assert actual == metadata
    metadata["target"] = "altered_species"
    save()
    with pytest.raises(census.CensusError, match="bundle_digest_mismatch"):
        census._bundle_inventory(path)


@pytest.mark.skipif(not (ROOT / census.INNER_BUNDLE_REL).is_dir(), reason="private accepted bundles unavailable")
def test_real_census_matches_all_saved_endpoint_digests():
    report = census.run_census(ROOT)

    assert report["success"] is True
    assert report["training_response_rows_read"] == 11039
    assert report["held_response_labels_read"] is False
    assert report["held_response_source_fields_read"] is False
    assert report["membership_verification"] == {
        "inner": {"expected": 280, "matched": 280},
        "outer": {"expected": 56, "matched": 56},
    }
    assert report["role_summary"]["discovery"]["minimum_retained_class_counts"]["0"] > 0
    assert report["role_summary"]["discovery"]["minimum_retained_class_counts"]["1"] > 0
    assert report["role_summary"]["stopping"]["minimum_retained_class_counts"]["0"] > 0
    assert report["role_summary"]["stopping"]["minimum_retained_class_counts"]["1"] > 0
    assert report["role_summary"]["replay"]["minimum_retained_class_counts"]["0"] > 0
    assert report["role_summary"]["replay"]["minimum_retained_class_counts"]["1"] > 0
    assert report["role_summary"]["outer_fit"]["minimum_retained_class_counts"]["0"] > 0
    assert report["role_summary"]["outer_fit"]["minimum_retained_class_counts"]["1"] > 0
    assert all("grid_cell_id" not in json.dumps(record) for record in report["records"])
