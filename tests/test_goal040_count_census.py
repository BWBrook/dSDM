from __future__ import annotations

import json
from pathlib import Path

import pytest

from dsdm_phase1.goal040_count_census import (
    MANIFEST_PATH,
    RAW_ROOT,
    Goal040CountError,
    build_branch_matrix,
    validate_count_census,
)


ROOT = Path(__file__).resolve().parents[1]


def _manifest(root: Path = ROOT) -> dict:
    return json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))


def _copy_tracked_contract(tmp_path: Path) -> None:
    for relative in (
        "metadata/goal040_count_census_manifest.json",
        "metadata/goal040_taxon_query_ledger.csv",
        "metadata/goal040_domain_boundary_manifest.json",
        "config/goal040_se_mammal_feasibility.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())


def test_tracked_count_receipt_covers_exact_frozen_union_and_gate():
    branches = build_branch_matrix(ROOT)
    manifest = _manifest()
    assert len(branches) == 45
    assert len({branch["taxon"] for branch in branches}) == 21
    assert sum(branch["branch_kind"] == "parent" for branch in branches) == 21
    assert sum(branch["branch_kind"] == "reviewed_descendant" for branch in branches) == 23
    assert sum(branch["branch_kind"] == "evidence_backed_alias" for branch in branches) == 1

    result = validate_count_census(ROOT, require_raw=False)
    assert result["result"] == "pass_acquisition_authorised"
    assert result["conservative_bbox_prefilter_rows"] == 1_258_883
    assert result["maximum_single_taxon_rows"] == 323_666
    assert result["service_count_requests"] == 22
    assert manifest["request_accounting"] == {
        "canonical_retained_count_estimates": 22,
        "superseded_exploratory_branch_estimates": 44,
        "total_unique_live_metadata_only_count_requests": 66,
        "superseded_receipts_retained_ignored": True,
        "pageSize_for_every_request": 0,
        "occurrence_rows_returned_across_all_requests": 0,
        "accounting_note": "45 initial branch calls included the Macropus alias retained canonically; adding 21 taxon-union calls yields 22 canonical estimates, 44 superseded estimates, and 66 unique live requests",
    }
    assert all(item["pass"] for item in result["resource_criteria"].values())
    assert manifest["privacy"] == {
        "occurrence_rows_retained": 0,
        "coordinates_retained": 0,
        "record_ids_retained": 0,
        "facets_retained": 0,
        "email_retained": False,
        "raw_files_tracked": False,
    }
    assert manifest["record_identity_policy"] == {
        "canonical_deduplication_key": "recordID_required",
        "auxiliary_field": "occurrenceID_optional_not_a_deduplication_key",
        "cross_union_rule": "duplicate_recordID_values_across_materialised_parent_descendant_alias_queries_collapse_once",
        "evidence": "Goal017 public ALA snapshot had recordID complete and unique in 50,834/50,834 rows while occurrenceID was materially incomplete, including 10,240/33,442 populated devil rows",
    }
    assert "@" not in json.dumps(manifest)


def test_ignored_raw_count_receipts_replay_offline_when_present():
    if not (ROOT / RAW_ROOT).exists():
        pytest.skip("ignored raw count receipts are intentionally not cloned")
    assert validate_count_census(ROOT, require_raw=True)["result"] == "pass_acquisition_authorised"
    manifest = _manifest()
    referenced_ids = [item["query_id"] for item in manifest["taxon_queries"]]
    referenced_ids += [item["branch_id"] for item in manifest["alias_probes"]]
    response_files = [ROOT / RAW_ROOT / f"{identifier}.response.json" for identifier in referenced_ids]
    assert len(response_files) == 22
    for path in response_files:
        response = json.loads(path.read_text(encoding="utf-8"))
        assert response["occurrence_rows_retained"] == 0
        assert response["coordinate_fields_retained"] == 0
        assert response["record_id_fields_retained"] == 0
        assert response["facet_rows_retained"] == 0
        assert response["email_retained"] is False
        assert set(response) == {
            "schema_version", "source", "totalRecords", "http_status",
            "service_envelope_sha256", "occurrence_rows_retained",
            "coordinate_fields_retained", "record_id_fields_retained",
            "facet_rows_retained", "email_retained",
        }


@pytest.mark.parametrize("tamper", ["missing_branch", "arithmetic", "privacy", "request_accounting"])
def test_count_manifest_tampering_fails_closed(tmp_path, tamper):
    _copy_tracked_contract(tmp_path)
    path = tmp_path / MANIFEST_PATH
    manifest = _manifest(tmp_path)
    if tamper == "missing_branch":
        manifest["branch_coverage"].pop()
    elif tamper == "arithmetic":
        manifest["summary"]["conservative_bbox_prefilter_rows"] += 1
    elif tamper == "privacy":
        manifest["privacy"]["coordinates_retained"] = 1
    else:
        manifest["request_accounting"]["total_unique_live_metadata_only_count_requests"] = 65
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(Goal040CountError):
        validate_count_census(tmp_path, require_raw=False)


def test_count_manifest_ledger_binding_tamper_fails_closed(tmp_path):
    _copy_tracked_contract(tmp_path)
    ledger = tmp_path / "metadata/goal040_taxon_query_ledger.csv"
    ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(Goal040CountError, match="taxon_ledger binding"):
        validate_count_census(tmp_path, require_raw=False)
