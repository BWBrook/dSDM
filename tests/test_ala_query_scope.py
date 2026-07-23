"""Offline validation tests for the Goal 012 count-only query-scope package."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1.ala_query_scope import (  # noqa: E402
    QueryScopeValidationError,
    _sanitize_response,
    validate_evidence_package,
    validate_request_profile,
)


PROFILE_PATH = ROOT / "config" / "ala_acquisition_request_profile.json"
PACKAGE_PATH = ROOT / "evidence" / "ala_query_scope" / "2026-07-23"


def load_profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


class ALAQueryScopeTests(unittest.TestCase):
    def test_profile_and_evidence_replay(self) -> None:
        profile = load_profile()
        self.assertEqual(validate_request_profile(profile)["query_mode"], "parent_species_expansion")
        result = validate_evidence_package(PACKAGE_PATH, profile)
        self.assertEqual(result["probe_count"], 24)
        self.assertEqual(result["national_relation_count"], 3)
        self.assertFalse(result["containment_unresolved"])

    def test_profile_requires_current_endpoint_quality_mode_fallback_identity_and_dedup(self) -> None:
        mutations = [
            lambda p: p.update({"profile_id": "other-profile"}),
            lambda p: p.update({"status": "ready"}),
            lambda p: p.update({"documented_gateway_endpoint": "https://api.ala.org.au/occurrences/search"}),
            lambda p: p.pop("query_template"),
            lambda p: p.update({"occurrence_search_endpoint": "https://api.ala.org.au/occurrences/search"}),
            lambda p: p.update({"disable_all_quality_filters": False}),
            lambda p: p["fallback"].update({"mode": "parent_only"}),
            lambda p: p["fallback"].update({"deduplication_key": "recordID"}),
            lambda p: p["record_field_mapping"].pop(),
            lambda p: p["future_fl"].remove("license"),
            lambda p: p["future_fl"].append("not_an_index_field"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                profile = load_profile()
                mutate(profile)
                with self.assertRaises(QueryScopeValidationError):
                    validate_request_profile(profile)

    def test_zero_row_and_coordinate_record_guards(self) -> None:
        response = {
            "status": "OK", "pageSize": 0, "startIndex": 0, "totalRecords": 1,
            "occurrences": [{"occurrenceID": "record-leak"}], "facetResults": [],
        }
        with self.assertRaises(QueryScopeValidationError):
            _sanitize_response(response)
        response["occurrences"] = []
        response["decimalLatitude"] = -42.0
        with self.assertRaises(QueryScopeValidationError):
            _sanitize_response(response)

    def _mutated_package(self, mutate):
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "package"
        shutil.copytree(PACKAGE_PATH, target)
        probes_path = target / "probes.json"
        probes = json.loads(probes_path.read_text(encoding="utf-8"))
        mutate(probes)
        probes_path.write_text(json.dumps(probes, indent=2) + "\n", encoding="utf-8")
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            path = target / entry["path"]
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return temp, target

    def _mutated_artifact(self, filename, mutate):
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "package"
        shutil.copytree(PACKAGE_PATH, target)
        path = target / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            entry["sha256"] = hashlib.sha256((target / entry["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return temp, target

    def test_evidence_fails_closed_on_incomplete_matrix_and_weak_intersection(self) -> None:
        profile = load_profile()
        mutations = [
            lambda p: p["probes"].pop(0),
            lambda p: p["probes"].__setitem__(10, {**p["probes"][10], "total_records": "398"}),
            lambda p: p["relations"][1].update({"direct_count": 1}),
            lambda p: p["national_relations"].pop(),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                temp, target = self._mutated_package(mutate)
                try:
                    with self.assertRaises(QueryScopeValidationError):
                        validate_evidence_package(target, profile)
                finally:
                    temp.cleanup()

    def test_evidence_manifest_timestamp_and_checksums_are_mandatory(self) -> None:
        profile = load_profile()
        temp, target = self._mutated_package(lambda p: p.update({"retrieved_at_utc": None}))
        try:
            with self.assertRaises(QueryScopeValidationError):
                validate_evidence_package(target, profile)
        finally:
            temp.cleanup()

    def test_semantic_bindings_fail_even_after_rechecksum(self) -> None:
        profile = load_profile()
        mutations = [
            lambda p: p["probes"][0].update({"query": "*:*"}),
            lambda p: p["probes"][0]["extra_fq"].append("foo:bar"),
            lambda p: p["probes"][0].update({"endpoint": "https://api.ala.org.au/occurrences/search"}),
            lambda p: p["probes"][0].update({"method": "POST"}),
            lambda p: p["probes"][0].update({"http_status": 201}),
            lambda p: p["probes"][0]["response"].update({"query": None}),
            lambda p: p["probes"][0]["response"].update({"query": "?q=*%3A*&disableAllQualityFilters=true"}),
            lambda p: p["probes"][0]["response"].update({"query": p["probes"][0]["response"]["query"] + "&facet=true"}),
            lambda p: p["probes"][0]["response"].update({"query": p["probes"][0]["response"]["query"] + "&pageSize=500"}),
            lambda p: p["probes"][0]["response"].update({"query": p["probes"][0]["response"]["query"] + "&start=10"}),
            lambda p: p["probes"][9].update({"total_records": 1, "response": {**p["probes"][9]["response"], "totalRecords": 1}}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                temp, target = self._mutated_package(mutate)
                try:
                    with self.assertRaises(QueryScopeValidationError):
                        validate_evidence_package(target, profile)
                finally:
                    temp.cleanup()

    def test_metadata_and_review_drift_fail_after_rechecksum(self) -> None:
        profile = load_profile()
        for filename, key, value in (("metadata.json", "official_sources", {}), ("review.json", "parent_counts", {"macropus_giganteus": 1})):
            temp = tempfile.TemporaryDirectory(); target = Path(temp.name) / "package"; shutil.copytree(PACKAGE_PATH, target)
            path = target / filename; payload = json.loads(path.read_text(encoding="utf-8")); payload[key] = value; path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                entry["sha256"] = hashlib.sha256((target / entry["path"]).read_bytes()).hexdigest()
            (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            try:
                with self.assertRaises(QueryScopeValidationError): validate_evidence_package(target, profile)
            finally: temp.cleanup()
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "package"
        shutil.copytree(PACKAGE_PATH, target)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"] = manifest["files"][:-1]
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            with self.assertRaises(QueryScopeValidationError):
                validate_evidence_package(target, profile)
        finally:
            temp.cleanup()

    def test_chronology_metadata_flags_and_fl_provenance_fail_after_rechecksum(self) -> None:
        profile = load_profile()
        mutations = [
            ("review.json", lambda d: d.update({"reviewed_at_utc": "2026-07-23T12:30:00Z"})),
            ("review.json", lambda d: d.update({"scope_snapshot": "2026-07-23T12:27:14Z"})),
            ("review.json", lambda d: d.update({"later_bulk_acquisition_ready_apart_from_P1_D008": True})),
            ("review.json", lambda d: d.update({"readiness_caveat": "bulk acquisition ready"})),
            ("metadata.json", lambda d: d.update({"occurrence_search_parameters": []})),
            ("metadata.json", lambda d: d["occurrence_search_parameters"][2].update({"schema": {"type": "array"}})),
            ("metadata.json", lambda d: d["fields_metadata"]["available_fields"]["occurrenceID"].update({"indexed": False})),
            ("metadata.json", lambda d: d["fields_metadata"]["available_fields"]["occurrenceID"].update({"stored": False})),
        ]
        for filename, mutate in mutations:
            with self.subTest(filename=filename, mutate=mutate):
                temp, target = self._mutated_artifact(filename, mutate)
                try:
                    with self.assertRaises(QueryScopeValidationError):
                        validate_evidence_package(target, profile)
                finally:
                    temp.cleanup()


if __name__ == "__main__":
    unittest.main()
