from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal049_aggregate_census as census
import goal049_taxonomy_freeze as taxonomy


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _config() -> dict:
    return {
        "schema_version": "1.0",
        "occurrence_contract": {
            "time_start": "2001-01-01", "time_end": "2025-12-31",
            "occurrence_status": "PRESENT", "spatially_valid": True,
            "snap_immediately_to_resolution_degree": 0.01,
            "transport_ceiling": {"lat_long_groups_per_species": 750000, "lat_long_groups_total": 50000000, "private_disk_gib": 4, "peak_ram_gib": 8},
        },
    }


def _tree(tmp_path: Path) -> Path:
    root = tmp_path
    _write(root / "config/goal049_seawfb_canonical_response.json", _config())
    _write(root / "config/goal048_seawfb_bioregional_freeze.json", {"species_universes": {"ecological_candidate_names": ["Species alpha"]}})
    private = root / taxonomy.PRIVATE_RELATIVE
    _write(private / "registry.json", {"rows": [{"source_name": "Species alpha", "active": True, "effort": True, "goal048_seed": True, "seed_names": ["Species alpha"]}]})
    domain = private / "domain_cells.csv"
    domain.parent.mkdir(parents=True, exist_ok=True)
    domain.write_text("cell_id,row,column,longitude,latitude\nr0000c0000,0,0,1.005,2.005\n")
    _write(private / "domain_freeze.json", {"status": "frozen_count_free", "cell_count": 1, "bbox": {"xmin": 1.005, "xmax": 1.005, "ymin": 2.005, "ymax": 2.005}})
    registry_path = private / "registry.json"
    _write(root / "metadata/goal049_registry_receipt.json", {"status": "complete_count_free", "private_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest()})
    _write(root / "metadata/goal049_authority_receipt.json", {"status": "complete_count_free"})
    _write(root / "metadata/goal048_prerequisite_freeze.json", {"status": "validated_count_free"})
    return root


def test_taxonomy_is_count_free_and_accepts_only_attributable_aliases(tmp_path, monkeypatch):
    root = _tree(tmp_path)

    monkeypatch.setattr(taxonomy.galah, "search_taxa", lambda **_: pd.DataFrame([{
        "taxonConceptID": "p1", "scientificName": "Species alpha", "taxonomicStatus": "accepted", "rank": "species",
    }]))

    def fake_get(url: str):
        if "/childConcepts/" in url:
            return [{"guid": "d1", "name": "Species alpha subspecies", "taxonomicStatus": "accepted", "rank": "subspecies", "parentGuid": "p1"}]
        if url.endswith("/p1"):
            return {"taxonConcept": {"taxonConceptID": "p1", "scientificName": "Species alpha", "taxonomicStatus": "accepted", "rank": "species"}, "synonyms": [
                {"guid": "a1", "nameString": "Old alpha", "taxonomicStatus": "synonym", "acceptedConceptID": "p1"},
                {"guid": "a2", "nameString": "alpha/beta", "taxonomicStatus": "synonym", "acceptedConceptID": "p1"},
                {"guid": "a3", "nameString": "Wrong target", "taxonomicStatus": "synonym", "acceptedConceptID": "other"},
            ]}
        if url.endswith("/d1"):
            return {"taxonConcept": {"taxonConceptID": "d1", "scientificName": "Species alpha subspecies", "taxonomicStatus": "accepted", "rankString": "subspecies", "parentGuid": "p1"}}
        if url.endswith("/a1"):
            return {"taxonConcept": {"taxonConceptID": "a1", "taxonomicStatus": "synonym", "acceptedConceptID": "p1"}}
        if url.endswith("/a3"):
            return {"taxonConcept": {"taxonConceptID": "a3", "taxonomicStatus": "synonym", "acceptedConceptID": "other"}}
        raise AssertionError(url)

    monkeypatch.setattr(taxonomy, "_get_json", fake_get)
    receipt = taxonomy.freeze_taxonomy(root)
    assert receipt["status"] == "passed"
    frozen = json.loads((root / taxonomy.PRIVATE_RELATIVE / "taxonomy_freeze.json").read_text())
    row = frozen["rows"][0]
    assert row["ordered_identifiers"] == ["p1", "d1", "a1"]
    assert row["excluded_composite_alias_count"] == 1
    assert taxonomy.validate_taxonomy_freeze(root)["status"] == "passed"
    assert receipt["occurrence_support_queried"] is False


def test_taxonomy_fails_on_ambiguous_parent(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setattr(taxonomy.galah, "search_taxa", lambda **_: pd.DataFrame([
        {"taxonConceptID": "p1", "taxonomicStatus": "accepted", "rank": "species"},
        {"taxonConceptID": "p2", "taxonomicStatus": "accepted", "rank": "species"},
    ]))
    with pytest.raises(taxonomy.Goal049TaxonomyError, match="ambiguous"):
        taxonomy.freeze_taxonomy(root)


def test_taxonomy_ascends_accepted_subspecies_and_retains_match(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setattr(taxonomy.galah, "search_taxa", lambda **_: pd.DataFrame([{
        "taxonConceptID": "d1", "scientificName": "Species alpha minor", "taxonomicStatus": "accepted",
        "rank": "subspecies", "matchType": "exactMatch",
    }]))

    def fake_get(url: str):
        if url.endswith("/d1"):
            return {"taxonConcept": {
                "taxonConceptID": "d1", "scientificName": "Species alpha minor",
                "taxonomicStatus": "accepted", "rankString": "subspecies", "parentGuid": "p1",
            }, "classification": {"speciesGuid": "p1"}}
        if url.endswith("/p1"):
            return {"taxonConcept": {
                "taxonConceptID": "p1", "scientificName": "Species alpha",
                "taxonomicStatus": "accepted", "rank": "species",
            }, "synonyms": []}
        if "/childConcepts/" in url:
            return []
        raise AssertionError(url)

    monkeypatch.setattr(taxonomy, "_get_json", fake_get)
    taxonomy.freeze_taxonomy(root)
    frozen = json.loads((root / taxonomy.PRIVATE_RELATIVE / "taxonomy_freeze.json").read_text())
    row = frozen["rows"][0]
    assert row["parent"] == "p1"
    assert row["ordered_identifiers"] == ["p1", "d1"]
    assert row["name_resolution"] == {"input_name": "Species alpha", "lookup_name": "Species alpha", "basis": "registry_name+classification.speciesGuid"}
    assert taxonomy.validate_taxonomy_freeze(root)["status"] == "passed"


def test_taxonomy_records_exact_config_name_mapping(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    config = json.loads((root / "config/goal049_seawfb_canonical_response.json").read_text())
    config["taxonomy"] = {"explicit_name_resolutions": {"Species alpha": "Mapped alpha"}}
    _write(root / "config/goal049_seawfb_canonical_response.json", config)
    seen: list[str] = []

    def fake_search(**kwargs):
        seen.append(kwargs["taxa"])
        return pd.DataFrame([{"taxonConceptID": "p1", "scientificName": "Mapped alpha", "taxonomicStatus": "accepted", "rank": "species", "matchType": "exactMatch"}])

    monkeypatch.setattr(taxonomy.galah, "search_taxa", fake_search)
    monkeypatch.setattr(taxonomy, "_get_json", lambda url: {"taxonConcept": {"taxonConceptID": "p1", "scientificName": "Mapped alpha", "taxonomicStatus": "accepted", "rank": "species"}, "synonyms": []} if url.endswith("/p1") else [])
    taxonomy.freeze_taxonomy(root)
    frozen = json.loads((root / taxonomy.PRIVATE_RELATIVE / "taxonomy_freeze.json").read_text())
    receipt = json.loads((root / taxonomy.FREEZE_RELATIVE).read_text())
    expected = {"input_name": "Species alpha", "lookup_name": "Mapped alpha", "basis": "explicit_name_resolution"}
    assert seen == ["Mapped alpha"]
    assert frozen["rows"][0]["name_resolution"] == expected
    assert frozen["explicit_name_resolutions"] == {"Species alpha": "Mapped alpha"}
    assert receipt["explicit_name_resolutions"] == {"Species alpha": "Mapped alpha"}


def test_taxonomy_rejects_inconsistent_subspecies_parent_evidence(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setattr(taxonomy.galah, "search_taxa", lambda **_: pd.DataFrame([{
        "taxonConceptID": "d1", "scientificName": "Species alpha minor", "taxonomicStatus": "accepted",
        "rank": "subspecies", "matchType": "exactMatch",
    }]))
    monkeypatch.setattr(taxonomy, "_get_json", lambda url: {"taxonConcept": {
        "taxonConceptID": "d1", "scientificName": "Species alpha minor", "taxonomicStatus": "accepted",
        "rankString": "subspecies", "parentGuid": "p1",
    }, "classification": {"speciesGuid": "p2"}} if url.endswith("/d1") else [])
    with pytest.raises(taxonomy.Goal049TaxonomyError, match="inconsistent species parent"):
        taxonomy.freeze_taxonomy(root)


def test_taxonomy_selection_skips_inactive_nonseed_and_requires_unique_seed(tmp_path):
    root = _tree(tmp_path)
    rows = [
        {"name": "Seed", "source_name": "Seed", "effort": False, "auxiliary": False, "target": False, "goal048_seed": True},
        {"name": "Inactive", "source_name": "Inactive", "effort": False, "auxiliary": False, "target": False, "goal048_seed": False},
        {"name": "Active", "source_name": "Active", "effort": True, "auxiliary": False, "target": False, "goal048_seed": False},
    ]
    (root / "config/goal048_seawfb_bioregional_freeze.json").write_text(json.dumps({"species_universes": {"ecological_candidate_names": ["Seed"]}}))
    selected, seeds = taxonomy._selected_registry_rows(root, rows)
    assert [row["name"] for row in selected] == ["Seed", "Active"]
    assert seeds == ["Seed"]
    with pytest.raises(taxonomy.Goal049TaxonomyError, match="not unique"):
        taxonomy._selected_registry_rows(root, rows + [{"name": "Seed copy", "source_name": "Seed copy", "goal048_seed": True, "seed_names": ["Seed"]}])


def _stage_a(root: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(taxonomy.galah, "search_taxa", lambda **_: pd.DataFrame([{"taxonConceptID": "p1", "scientificName": "Species alpha", "taxonomicStatus": "accepted", "rank": "species"}]))
    monkeypatch.setattr(taxonomy, "_get_json", lambda url: ({"taxonConcept": {"taxonConceptID": "p1", "scientificName": "Species alpha", "taxonomicStatus": "accepted", "rank": "species"}, "synonyms": []} if url.endswith("/p1") else []))
    taxonomy.freeze_taxonomy(root)
    monkeypatch.undo()


def test_goal048_promotion_uses_identifier_union_when_display_name_changed(tmp_path):
    root = _tree(tmp_path)
    old_private = root / census.GOAL048_PRIVATE_RELATIVE
    old_private.mkdir(parents=True, exist_ok=True)
    old_domain = old_private / "domain_cells.csv"
    old_domain.write_text("cell_id,row,column,longitude,latitude\nr0000c0000,0,0,1.005,2.005\n")
    _write(old_private / "domain_freeze.json", {"cell_count": 1, "bbox": {"xmin": 1.005, "xmax": 1.005, "ymin": 2.005, "ymax": 2.005}})
    _write(old_private / "taxonomy_freeze.json", {"rows": [{"seed_name": "Old alpha", "ordered_identifiers": ["p1"]}]})
    old_cells = old_private / "census/cells/000.json"
    _write(old_cells, {"species": "Old alpha", "cells": ["r0000c0000"]})
    filters = ["year>=2001", "year<=2025", "occurrenceStatus=PRESENT", "spatiallyValid=true", "decimalLongitude>=1.005", "decimalLongitude<=1.005", "decimalLatitude>=2.005", "decimalLatitude<=2.005"]
    fingerprint = census._digest({"identifiers": ["p1"], "filters": filters})
    counts = {"total_count": 3, "facet_count_sum": 3, "facet_group_count": 1}
    checkpoint = {"species": "Old alpha", "query_fingerprint": fingerprint, **counts, "count_conservation_sha256": census._digest(counts), "private_cell_receipt": str(old_cells.relative_to(root)), "private_cell_receipt_sha256": hashlib.sha256(old_cells.read_bytes()).hexdigest()}
    _write(old_private / "census/checkpoints/00000.json", checkpoint)
    _write(root / "config/goal048_seawfb_bioregional_freeze.json", {"aggregate_feasibility": {"filters": {"years_inclusive": [2001, 2025], "occurrence_status": "present", "spatial_validity": "valid_coordinate_required"}}})
    frame = census._domain_frame(root)
    item = {"index": 0, "species": "Current alpha", "identifiers": ["p1"], "query_fingerprint": fingerprint, "total_query": {"identifiers": ["p1"], "filters": filters}, "domain_cells_sha256": hashlib.sha256(old_domain.read_bytes()).hexdigest(), "domain_cell_count": 1, "domain_freeze_sha256": hashlib.sha256((old_private / "domain_freeze.json").read_bytes()).hexdigest(), "normalisation": census._normalisation(frame), "stage_a_freeze_sha256": "stage-a"}
    promoted = census.audit_goal048_receipt(root, item, frame, {"r0000c0000"})
    assert promoted is not None
    assert promoted["source"] == "promoted_goal048_receipt"
    assert promoted["species"] == "Current alpha"


def test_live_canary_skips_promotable_prefix_without_noncontiguous_checkpoint(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    plan = [
        {"index": 0, "species": "Old display", "identifiers": ["old"], "query_fingerprint": "old"},
        {"index": 1, "species": "New display", "identifiers": ["new"], "query_fingerprint": "new"},
    ]
    monkeypatch.setattr(census, "_stage_a", lambda _: {"status": "passed"})
    monkeypatch.setattr(census, "build_census_plan", lambda _: plan)
    monkeypatch.setattr(census, "load_resume_state", lambda *args: [])
    monkeypatch.setattr(census, "_goal048_identifier_unions", lambda _: {("old",)})
    monkeypatch.setattr(census.galah, "galah_config", lambda **_: None)
    seen = {}

    def fake_run(*args, **kwargs):
        seen["item"] = args[1]
        seen["receipt_path"] = kwargs.get("receipt_path") or args[4]
        return {"status": "passed", "species": "New display", "source": "live_galah_aggregate"}

    monkeypatch.setattr(census, "_run_species", fake_run)
    monkeypatch.setattr(census, "_write_canary_receipt", lambda *args: {})
    monkeypatch.setattr(census, "_commit_checkpoint", lambda *args, **kwargs: pytest.fail("later canary must not create a checkpoint"))
    result = census.run_canary(root)
    assert result["species"] == "New display"
    assert seen["item"]["index"] == 1
    assert seen["receipt_path"].name == "canary_species_cells.json"


def test_census_canary_resume_is_atomic_and_conserves_counts(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    _stage_a(root)
    calls: list[dict] = []

    def fake_counts(**query):
        calls.append(query)
        if query.get("group_by") == "lat_long":
            return pd.DataFrame({"lat_long": ["[2.005, 1.005]"], "count": [3]})
        return pd.DataFrame({"totalRecords": [3]})

    monkeypatch.setattr(census.galah, "atlas_counts", fake_counts)
    first = census.run_canary(root)
    assert first["source"] == "live_galah_aggregate"
    assert first["total_count"] == first["facet_count_sum"] == 3
    species_receipt = root / census.PRIVATE_RELATIVE / "species_cells/00000.json"
    assert json.loads(species_receipt.read_text())["cells"] == ["r0000c0000"]
    assert len(calls) == 2
    canary = json.loads((root / census.CANARY_RELATIVE).read_text())
    assert census.validate_canary(root)["status"] == "passed"
    assert "cells" not in canary and "coordinates" not in json.dumps(canary).lower()
    second = census.run_census(root)
    assert second["status"] == "complete"
    assert len(calls) == 2
    progress = json.loads((root / census.PROGRESS_RELATIVE).read_text())
    assert progress["occurrence_rows_downloaded"] == 0
    assert progress["model_outcome_counter"] == 0


def test_census_rejects_total_facet_mismatch(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    _stage_a(root)
    monkeypatch.setattr(census.galah, "atlas_counts", lambda **query: pd.DataFrame({"totalRecords": [2]}) if "group_by" not in query else pd.DataFrame({"lat_long": ["[2.005, 1.005]"], "count": [1]}))
    with pytest.raises(census.Goal049CensusError, match="conserve"):
        census.run_canary(root)
