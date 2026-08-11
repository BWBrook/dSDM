from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from dsdm_phase1.goal040_freeze import ABS_SHA256, validate
from dsdm_phase1.goal040_taxonomy import validate_taxon_freeze


ROOT = Path(__file__).resolve().parents[1]
ANCHORS = {
    "Notamacropus rufogriseus",
    "Trichosurus vulpecula",
    "Pseudocheirus peregrinus",
    "Vombatus ursinus",
    "Dasyurus maculatus",
}


def _ledger() -> list[dict[str, str]]:
    with (ROOT / "metadata/goal040_taxon_query_ledger.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def test_amtc_frame_and_decisions_are_count_free_and_conservative():
    rows = _ledger()
    assert len(rows) == 416
    assert len({row["scientific_name"] for row in rows}) == len(rows)
    assert {row["primary_cohort_decision"] for row in rows} == {
        "include", "exclude", "nonquery"
    }
    assert sum(row["global_extant_status"] == "no" for row in rows) == 40

    by_name = {row["scientific_name"]: row for row in rows}
    for extinct in {"Conilurus albipes", "Lagorchestes leporides", "Perameles fasciata"}:
        assert by_name[extinct]["primary_cohort_decision"] == "exclude"
        assert by_name[extinct]["query_roles"] == ""

    query_rows = [row for row in rows if row["query_roles"]]
    assert len(query_rows) == 21
    assert sum(row["shared_evaluation_eligible"] == "true" for row in rows) == 5
    assert {row["scientific_name"] for row in query_rows
            if row["shared_evaluation_eligible"] == "true"} == ANCHORS
    assert sum("mainland_donor_pretraining" in row["query_roles"] for row in rows) >= 15

    for name in {"Dasyurus viverrinus", "Thylogale billardierii", "Sarcophilus harrisii",
                 "Petaurus breviceps", "Petaurus notatus"}:
        assert by_name[name]["shared_evaluation_eligible"] == "false"
    assert by_name["Macropus giganteus"]["shared_evaluation_eligible"] == "false"
    assert "mainland_donor_pretraining" in by_name["Macropus giganteus"]["query_roles"]

    for row in query_rows:
        roles = set(row["query_roles"].split("|"))
        if "mainland_donor_pretraining" in roles:
            assert row["current_native_extant_mainland_status"] == "yes"
        if roles & {"tasmania_support", "shared_evaluation_candidate"}:
            assert row["current_native_extant_tasmania_status"] == "yes"
        if row["shared_evaluation_eligible"] == "true":
            assert "shared_evaluation_candidate" in roles
            assert row["current_native_extant_mainland_status"] == "yes"
            assert row["current_native_extant_tasmania_status"] == "yes"
        assert row["review_status"].startswith("resolved")
        assert row["ala_accepted_concept_id"].startswith("https://biodiversity.org.au/afd/taxa/")
        assert row["query_strategy"] == "explicit_reviewed_parent_plus_domain_relevant_accepted_descendants_union"
        assert json.loads(row["query_concepts"])
        assert row["provider_record_deduplication"].startswith("occurrenceID required")

    for row in rows:
        if row["current_native_extant_tasmania_status"] == "not_assessed_nonquery":
            assert row["tasmania_status_basis"] == "not assessed because no Tasmania query/support role"
            assert "bie_current_vic_act" not in row["tasmania_status_basis"]

    serialized = (ROOT / "metadata/goal040_taxon_query_ledger.csv").read_text(encoding="utf-8").lower()
    assert "latitude" not in serialized and "longitude" not in serialized
    assert "@utas.edu.au" not in serialized and "camera" not in serialized


@pytest.mark.parametrize(
    ("name", "field", "value", "message"),
    [
        ("Macropus giganteus", "current_native_extant_mainland_status", "no", "mainland donor role"),
        ("Notamacropus rufogriseus", "current_native_extant_tasmania_status", "no", "Tasmania/shared role"),
        ("Phascolarctos cinereus", "shared_evaluation_eligible", "true", "shared eligibility"),
    ],
)
def test_regional_role_validation_fails_closed(tmp_path, name, field, value, message):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    source_ledger = ROOT / "metadata/goal040_taxon_query_ledger.csv"
    rows = _ledger()
    for row in rows:
        if row["scientific_name"] == name:
            row[field] = value
            break
    with (metadata / source_ledger.name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    evidence = ROOT / "metadata/goal040_taxon_evidence_manifest.json"
    (metadata / evidence.name).write_bytes(evidence.read_bytes())

    with pytest.raises(ValueError, match=message):
        validate_taxon_freeze(tmp_path)


def test_authority_manifests_freeze_candidate_frame_and_query_limits():
    evidence = json.loads(
        (ROOT / "metadata/goal040_taxon_evidence_manifest.json").read_text(encoding="utf-8")
    )
    frame = evidence["candidate_frame"]
    assert frame["version"] == "5.0 (February 2026)"
    assert frame["species_rows"] == 416 and frame["globally_extinct_rows"] == 40
    assert frame["download_sha256"] == "c2d0ffe8e12901655017a238fd8593cea3bd9c5641871906d961b5ab16b513a6"
    assert evidence["ala_discovery_crosscheck"]["role"] == "cross-check_only_not_completeness_or_eligibility"
    assert evidence["query_policy"]["parent_expansion_assumed"] is False
    assert evidence["query_policy"]["provider_record_deduplication"].startswith("occurrenceID required")
    assert evidence["summary"]["query_cohort_scope"] == "conservative_nonrepresentative_feasibility_subset"
    assert evidence["summary"]["broad_cohort_representativeness"] == "unproven"
    assert "subset only" in evidence["summary"]["permitted_future_claim"]


def test_exact_ibra_domain_and_grid_are_frozen():
    manifest = json.loads(
        (ROOT / "metadata/goal040_domain_boundary_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "frozen_before_counts"
    assert manifest["products"]["land_and_state"]["sha256"] == ABS_SHA256

    exact = manifest["exact_study_domain"]
    authority = exact["authority"]
    assert authority["product_version"] == "7.1"
    assert authority["source_url"].endswith("IBRA7_Subregions/FeatureServer/0")
    assert "419 unique subregion codes" in authority["source_identity"]
    assert authority["licence"] == "CC BY 3.0 AU"
    assert len(authority["sha256"]) == 64 and authority["retrieved_at"].endswith("Z")

    reconciliation = exact["reconciliation"]
    assert len(exact["ibra_subregion_allowlist"]) == 163
    assert reconciliation["sorted_allowlist_sha256"] == "00e6b954b657e1ad09c10bbf088dacd5ae72b7dfaa1d8d507da5bfc55243f81e"
    assert "MDD01" not in exact["ibra_subregion_allowlist"]
    assert reconciliation["excluded_partial_subregion"] == {
        "code": "MDD01",
        "archived_overlap_fraction": 0.02148877423,
        "archived_overlap_km2": 1168.822567,
        "rationale": "whole-subregion allowlist cannot preserve the 2.15-percent sliver without widening to all MDD01",
    }

    grid = exact["grid"]
    assert grid["eligible_cell_count"] == 1125325
    assert grid["eligible_cell_id_sha256"] == "022a83b2762b886f455406a96cb48a91d612e1b08d6d1cad00eb5db7070a2b06"
    assert grid["state_counts"] == {
        "Australian Capital Territory": 2332,
        "New South Wales": 460725,
        "Queensland": 242636,
        "South Australia": 121710,
        "Tasmania": 72293,
        "Victoria": 225629,
    }
    assert grid["absent_jurisdictions"] == ["Northern Territory", "Other Territories"]
    assert grid["jurisdiction_exclusions_before_final_eligibility"] == {
        "Northern Territory": 0, "Other Territories": 61
    }


def test_count_free_freeze_validation_summary():
    result = validate(ROOT)
    assert result["status"] == "validated_count_free"
    assert result["eligible_cells"] == 1125325
    assert result["taxonomy"]["rows"] == 416
    assert result["taxonomy"]["query_role_taxa"] == 21
    assert result["taxonomy"]["shared_evaluation_taxa"] == 5
