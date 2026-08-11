from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from dsdm_phase1.goal040_acquisition import (
    MANIFEST_PATH,
    PACKAGE,
    REQUEST_FIELDS,
    Goal040AcquisitionError,
    _canonical,
    _load_plan,
    _paths,
    run_acquisition,
    validate_acquisition,
)


ROOT = Path(__file__).resolve().parents[1]


class Frame:
    def __init__(self, rows: list[dict[str, str]], columns: list[str]):
        self.rows = rows
        self.columns = columns

    def to_csv(self, path, *, index, lineterminator):
        assert index is False and lineterminator == "\n"
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)


class FakeGalah:
    __version__ = PACKAGE["version"]

    def __init__(self, plan, bad=None):
        self.plan = plan
        self.bad = bad
        self.calls = []
        self.config_paths = []

    def galah_config(self, **kwargs):
        self.config_paths.append(Path(kwargs["config_file"]))
        assert Path(kwargs["config_file"]).is_file()
        Path(kwargs["config_file"]).write_text("[galahSettings]\n", encoding="utf-8")
        assert kwargs["authenticate"] is False

    def atlas_occurrences(self, **kwargs):
        self.calls.append(kwargs)
        query_index = next(
            index for index, query in enumerate(self.plan["queries"])
            if query["selector_value"] == kwargs["identifiers"]
        )
        expected = self.plan["queries"][query_index]["expected_rows"]
        if self.bad == "wrong_count" and query_index == 0:
            expected += 1
        header = ["dcterms:license" if item == "license" else item for item in REQUEST_FIELDS]
        header.extend(["COORDINATE_INVALID", "temporalIssue", "taxonomicIssue"])
        rows = []
        for row_index in range(expected):
            row = {field: "" for field in header}
            row.update({
                "recordID": "shared-record" if row_index == 0 else f"record-{query_index}-{row_index}",
                "occurrenceID": "" if query_index % 2 else f"occurrence-{query_index}-{row_index}",
                "eventDate": "2001-01-01", "year": "2001",
                "decimalLatitude": "-42", "decimalLongitude": "147",
                "scientificName": self.plan["queries"][query_index]["taxon"],
                "taxonConceptID": "synthetic-concept", "basisOfRecord": "HUMAN_OBSERVATION",
                "occurrenceStatus": "present", "dcterms:license": "CC-BY",
                "COORDINATE_INVALID": "false",
                "temporalIssue": "false", "taxonomicIssue": "false",
            })
            if self.bad == "blank_recordID" and query_index == 0:
                row["recordID"] = ""
            rows.append(row)
        return Frame(rows, header)


def synthetic_plan(_root: Path) -> dict:
    queries = []
    for index in range(21):
        query = {
            "branch_id": f"taxon_{index:02d}__taxon_union",
            "taxon": f"Taxon {index:02d}",
            "selector_value": [f"concept-{index:02d}"],
            "query_identity_sha256": hashlib.sha256(f"query-{index}".encode()).hexdigest(),
            "expected_rows": 1,
        }
        queries.append(query)
    return {
        "queries": queries,
        "bindings": {
            name: {"path": f"metadata/{name}.json", "sha256": hashlib.sha256(name.encode()).hexdigest()}
            for name in ("contract", "taxon_ledger", "domain_manifest", "count_manifest")
        } | {"ordered_taxon_union_matrix_sha256": hashlib.sha256(b"matrix").hexdigest()},
        "total": 21,
    }


def run_fake(tmp_path: Path, *, bad=None):
    plan = synthetic_plan(tmp_path)
    fake = FakeGalah(plan, bad=bad)
    result = run_acquisition(
        tmp_path, galah_module=fake, environ={"ALA_DOWNLOAD_EMAIL": "runtime-contact-secret"},
        alarm_fn=lambda call, _seconds: call(), _plan_loader=synthetic_plan,
    )
    return result, fake


def test_published_plan_is_exact_count_bound_and_ascending():
    plan = _load_plan(ROOT)
    assert len(plan["queries"]) == 21 and plan["total"] == 1_258_883
    assert [item["expected_rows"] for item in plan["queries"]] == sorted(
        item["expected_rows"] for item in plan["queries"]
    )
    assert all(item["selector_type"] == "identifier_union" for item in plan["queries"])


def test_happy_completion_manifest_and_raw_replay(tmp_path):
    result, fake = run_fake(tmp_path)
    assert result["status"] == "acquisition_complete_raw_replay_validated"
    assert len(fake.calls) == 21
    assert all(call["filters"] == ["year>=2001", "year<=2025"] for call in fake.calls)
    assert all(call["use_data_profile"] is False and call["mint_doi"] is False for call in fake.calls)
    assert all(call["fields"] == REQUEST_FIELDS for call in fake.calls)
    assert all(not path.exists() for path in fake.config_paths)
    tracked = validate_acquisition(tmp_path, _plan_loader=synthetic_plan)
    assert tracked == {
        "status": "tracked_acquisition_manifest_valid_raw_replay_required",
        "raw_replay_required": True,
    }
    manifest = json.loads((tmp_path / MANIFEST_PATH).read_text())
    assert manifest["summary"]["cross_union_duplicate_recordID_distinct"] == 1
    assert manifest["scope"]["sampling_or_additional_taxon_screen"] is False
    text = json.dumps(manifest)
    assert "runtime-contact-secret" not in text and "http://" not in text and "https://" not in text


def test_completed_resume_skips_all_calls_without_runtime_contact(tmp_path):
    run_fake(tmp_path)
    plan = synthetic_plan(tmp_path)
    fake = FakeGalah(plan)
    result = run_acquisition(
        tmp_path, galah_module=fake, environ={}, _plan_loader=synthetic_plan,
    )
    assert result["status"] == "acquisition_complete_raw_replay_validated"
    assert fake.calls == []


def test_lone_partial_is_discarded_then_downloaded_once(tmp_path):
    first = synthetic_plan(tmp_path)["queries"][0]
    partial, _, _ = _paths(tmp_path, first["branch_id"])
    partial.parent.mkdir(parents=True)
    partial.write_text("interrupted", encoding="utf-8")
    _, fake = run_fake(tmp_path)
    assert len(fake.calls) == 21 and not partial.exists()


@pytest.mark.parametrize("bad,reason", [
    ("blank_recordID", "recordID_blank_or_control"),
    ("wrong_count", "raw_row_count_mismatch"),
])
def test_invalid_record_identity_or_count_fails_without_retry(tmp_path, bad, reason):
    plan = synthetic_plan(tmp_path)
    fake = FakeGalah(plan, bad=bad)
    with pytest.raises(Goal040AcquisitionError, match=reason):
        run_acquisition(
            tmp_path, galah_module=fake, environ={"ALA_DOWNLOAD_EMAIL": "runtime-contact-secret"},
            alarm_fn=lambda call, _seconds: call(), _plan_loader=synthetic_plan,
        )
    assert len(fake.calls) == 1 and not (tmp_path / MANIFEST_PATH).exists()


def test_tracked_privacy_and_raw_tamper_fail_closed(tmp_path):
    run_fake(tmp_path)
    manifest_path = tmp_path / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["scope"]["sampling_or_additional_taxon_screen"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(Goal040AcquisitionError, match="acquisition_scope_drift"):
        validate_acquisition(tmp_path, _plan_loader=synthetic_plan)

    run_path = _paths(tmp_path, synthetic_plan(tmp_path)["queries"][0]["branch_id"])[1]
    manifest["scope"]["sampling_or_additional_taxon_screen"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run_path.write_text(run_path.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(Goal040AcquisitionError):
        validate_acquisition(tmp_path, require_raw=True, _plan_loader=synthetic_plan)
