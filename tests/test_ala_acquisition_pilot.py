"""Goal 013 direct-ALA row-pilot contract and evidence tests."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1.ala_acquisition_pilot import (  # noqa: E402
    PilotValidationError,
    build_request_plan,
    collect_pilot,
    rebuild_evidence_from_raw,
    validate_evidence_package,
    validate_pilot_config,
)


PROFILE_PATH = ROOT / "config" / "ala_acquisition_request_profile.json"
PLAN_PATH = ROOT / "config" / "ala_acquisition_pilot_plan.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def field_row(occurrence_id: str, concept_id: str, index: int) -> dict:
    year = 2001 + index % 25
    return {
        "occurrenceID": occurrence_id,
        "dataResourceUid": "dr-test",
        "dataResourceName": "Synthetic resource",
        "datasetID": None,
        "datasetName": None,
        "eventDate": int(
            datetime(year, 1, 2, tzinfo=timezone.utc).timestamp() * 1000
        ),
        "year": year,
        "decimalLatitude": -42.0 - index / 1000,
        "decimalLongitude": 147.0 + index / 1000,
        "coordinateUncertaintyInMeters": None,
        "coordinatePrecision": 0.001,
        "raw_scientificName": None,
        "raw_taxonConceptID": None,
        "scientificName": "Synthetic taxon",
        "taxonConceptID": concept_id,
        "acceptedNameUsage": None,
        "acceptedNameUsageID": None,
        "taxonRank": "species",
        "assertions": [],
        "license": "CC BY 4.0",
    }


def synthetic_payloads(plan: list[dict]) -> dict[str, bytes]:
    parent_ids: dict[str, list[str]] = {}
    payloads: dict[str, bytes] = {}
    for spec in plan:
        if spec["branch"] == "parent":
            ids = [
                f"synthetic:{spec['focal_species_id']}:{i:03d}"
                for i in range(spec["start"], spec["start"] + 25)
            ]
            parent_ids.setdefault(spec["focal_species_id"], []).extend(ids)
        elif spec["key"] == "fallback__macropus_synonym_id__start_000":
            ids = []
        elif spec["key"] == "fallback__macropus_synonym_name__start_000":
            ids = parent_ids["macropus_giganteus"][:25]
        elif spec["key"] == "fallback__vombatus_ursinus_hirsutus__start_000":
            ids = []
        elif spec["key"] == "fallback__vombatus_ursinus_tasmaniensis__start_000":
            ids = parent_ids["vombatus_ursinus"][:25]
        else:
            ids = parent_ids["vombatus_ursinus"][25:50]
        rows = [
            field_row(occurrence_id, spec["concept_id"], index)
            for index, occurrence_id in enumerate(ids)
        ]
        if rows:
            rows[0]["otherProperties"] = {
                "rawOnlyMarker": "must-stay-in-ignored-raw"
            }
        echo = "?" + urllib.parse.urlencode(
            [
                ("q", spec["query"]),
                ("disableAllQualityFilters", "true"),
                ("fq", "stateProvince:Tasmania"),
                ("fq", "year:[2001 TO 2025]"),
            ]
        )
        if spec["branch"] == "parent":
            total_records = 50
        else:
            total_records = len(rows)
        payload = {
            "status": "OK",
            "pageSize": 25,
            "startIndex": spec["start"],
            "totalRecords": total_records,
            "sort": "occurrenceID",
            "dir": "asc",
            "query": echo,
            "urlParameters": echo,
            "occurrences": rows,
            "facetResults": [],
        }
        payloads[spec["canonical_url"]] = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
    return payloads


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class ALAExpansionPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_json(PROFILE_PATH)
        self.config = load_json(PLAN_PATH)

    def _collect_synthetic(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        raw = root / "raw"
        evidence = root / "evidence"
        plan = build_request_plan(self.profile, self.config)
        payloads = synthetic_payloads(plan)

        def fetch(url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
            return 200, payloads[url]

        result = collect_pilot(
            PROFILE_PATH,
            PLAN_PATH,
            raw,
            evidence,
            fetcher=fetch,
            sleep_fn=lambda _seconds: None,
            now_fn=Clock(),
        )
        return temp, raw, evidence, result

    def _rechecksum_manifest(self, evidence: Path) -> None:
        manifest_path = evidence / "manifest.json"
        manifest = load_json(manifest_path)
        for entry in manifest["files"]:
            artifact = evidence / entry["path"]
            entry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            entry["bytes"] = artifact.stat().st_size
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def _rewrite_raw(
        self,
        raw: Path,
        evidence: Path,
        plan: list[dict],
        index: int,
        mutate,
    ) -> None:
        raw_path = raw / plan[index]["raw_file"]
        payload = load_json(raw_path)
        mutate(payload)
        raw_path.write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
        requests_path = evidence / "requests.json"
        requests = load_json(requests_path)
        request = requests["requests"][index]
        request["raw_sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        request["raw_bytes"] = raw_path.stat().st_size
        requests_path.write_text(
            json.dumps(requests, indent=2) + "\n", encoding="utf-8"
        )
        self._rechecksum_manifest(evidence)

    def test_plan_is_exactly_23_requests_and_575_planned_rows(self) -> None:
        validation = validate_pilot_config(self.config, self.profile)
        plan = build_request_plan(self.profile, self.config)
        self.assertEqual(validation["planned_request_count"], 23)
        self.assertEqual(validation["planned_row_ceiling"], 575)
        self.assertEqual(len(plan), 23)
        self.assertEqual(sum(item["page_size"] for item in plan), 575)
        self.assertEqual(
            [(item["start"], item["page_size"]) for item in plan[:2]],
            [(0, 25), (25, 25)],
        )
        self.assertEqual(
            {item["branch"] for item in plan[18:]},
            {
                "fallback_macropus_synonym_id",
                "fallback_macropus_synonym_name",
                "fallback_vombatus_child",
            },
        )
        for spec in plan:
            parameters = spec["ordered_parameters"]
            self.assertEqual(
                [value for key, value in parameters if key == "fq"],
                ["stateProvince:Tasmania", "year:[2001 TO 2025]"],
            )
            self.assertEqual(
                [value for key, value in parameters if key == "fl"],
                [",".join(self.profile["future_fl"])],
            )
            self.assertIn(["facet", "false"], parameters)
            self.assertIn(["disableAllQualityFilters", "true"], parameters)
            self.assertIn(["sort", "occurrenceID"], parameters)
            self.assertIn(["dir", "asc"], parameters)

    def test_config_and_profile_drift_fail_before_request_planning(self) -> None:
        mutations = [
            lambda c, _p: c.update({"max_record_requests": 24}),
            lambda c, _p: c.update({"max_returned_rows": 576}),
            lambda c, _p: c.update({"page_size": 50}),
            lambda c, _p: c.update({"parent_starts": [0, 25, 50]}),
            lambda c, _p: c.update({"sort": "eventDate"}),
            lambda c, _p: c.update({"facet": True}),
            lambda c, _p: c.update({"disable_all_quality_filters": False}),
            lambda c, _p: c["future_fl"].remove("license"),
            lambda _c, p: p["future_fl"].remove("license"),
            lambda _c, p: p["scope"]["temporal"].update({"end": 2024}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                config = copy.deepcopy(self.config)
                profile = copy.deepcopy(self.profile)
                mutate(config, profile)
                with self.assertRaises(PilotValidationError):
                    validate_pilot_config(config, profile)

    def test_synthetic_collection_replays_from_raw_without_payload_leakage(self) -> None:
        temp, raw, evidence, result = self._collect_synthetic()
        try:
            self.assertEqual(
                result["readiness"],
                "pilot_pass_ready_for_bounded_full_acquisition_design",
            )
            self.assertEqual(result["successful_record_requests"], 23)
            self.assertEqual(result["returned_rows"], 525)
            replay = validate_evidence_package(
                evidence, self.profile, self.config, raw_dir=raw
            )
            self.assertTrue(replay["raw_reconstruction"])
            self.assertEqual(replay["successful_record_requests"], 23)
            tracked_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(evidence.glob("*.json"))
            )
            self.assertNotIn("synthetic:", tracked_text)
            self.assertNotIn("-42.", tracked_text)
            self.assertNotIn("147.", tracked_text)
            self.assertNotIn("must-stay-in-ignored-raw", tracked_text)
            requests = load_json(evidence / "requests.json")
            self.assertEqual(
                requests["requests"][0]["unrequested_field_stats"],
                {
                    "otherProperties": {
                        "presence_count": 1,
                        "non_null_count": 1,
                        "types": ["object"],
                    }
                },
            )
            self.assertEqual(
                sum(
                    request["validation"]["event_date_unparseable_count"]
                    for request in requests["requests"]
                ),
                0,
            )
            self.assertEqual(
                requests["requests"][0]["query_binding"],
                {
                    "echoes_checked": 2,
                    "matched_echoes": 2,
                    "q_values_per_echo": 1,
                    "fq_values_per_echo": 2,
                    "quality_values_per_echo": 1,
                },
            )
            self.assertTrue(
                requests["requests"][0]["response_controls"][
                    "occurrence_ids_strictly_ascending"
                ]
            )
            self.assertTrue(
                requests["requests"][0]["response_controls"][
                    "returned_rows_match_expected"
                ]
            )
        finally:
            temp.cleanup()

    def test_raw_query_and_url_parameter_tampering_is_rejected(self) -> None:
        for echo_key in ("query", "urlParameters"):
            with self.subTest(echo_key=echo_key):
                temp, raw, evidence, _result = self._collect_synthetic()
                try:
                    plan = build_request_plan(self.profile, self.config)

                    def mutate(payload: dict) -> None:
                        payload[echo_key] = (
                            "?q=%2A%3A%2A&disableAllQualityFilters=true"
                            "&fq=stateProvince%3ATasmania"
                            "&fq=year%3A%5B2001+TO+2025%5D"
                        )

                    self._rewrite_raw(raw, evidence, plan, 0, mutate)
                    with self.assertRaisesRegex(
                        PilotValidationError, "query binding"
                    ):
                        validate_evidence_package(
                            evidence,
                            self.profile,
                            self.config,
                            raw_dir=raw,
                        )
                finally:
                    temp.cleanup()

    def test_swapped_rows_and_missing_expected_row_are_rejected(self) -> None:
        mutations = [
            lambda payload: payload["occurrences"].__setitem__(
                slice(0, 2),
                [
                    payload["occurrences"][1],
                    payload["occurrences"][0],
                ],
            ),
            lambda payload: payload["occurrences"].pop(),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                temp, raw, evidence, _result = self._collect_synthetic()
                try:
                    plan = build_request_plan(self.profile, self.config)
                    self._rewrite_raw(raw, evidence, plan, 0, mutate)
                    with self.assertRaises(PilotValidationError):
                        validate_evidence_package(
                            evidence,
                            self.profile,
                            self.config,
                            raw_dir=raw,
                        )
                finally:
                    temp.cleanup()

    def test_parent_total_disagreement_and_boundary_order_are_rejected(
        self,
    ) -> None:
        temp, raw, evidence, _result = self._collect_synthetic()
        try:
            plan = build_request_plan(self.profile, self.config)
            self._rewrite_raw(
                raw,
                evidence,
                plan,
                1,
                lambda payload: payload.update({"totalRecords": 51}),
            )
            requests_path = evidence / "requests.json"
            requests = load_json(requests_path)
            requests["requests"][1]["response_controls"][
                "total_records"
            ] = 51
            requests_path.write_text(
                json.dumps(requests, indent=2) + "\n", encoding="utf-8"
            )
            self._rechecksum_manifest(evidence)
            with self.assertRaisesRegex(
                PilotValidationError, "totalRecords"
            ):
                validate_evidence_package(
                    evidence, self.profile, self.config, raw_dir=raw
                )
        finally:
            temp.cleanup()

        temp, raw, evidence, _result = self._collect_synthetic()
        try:
            plan = build_request_plan(self.profile, self.config)
            first_path = raw / plan[0]["raw_file"]
            second_path = raw / plan[1]["raw_file"]
            first = load_json(first_path)
            second = load_json(second_path)
            first["occurrences"], second["occurrences"] = (
                second["occurrences"],
                first["occurrences"],
            )
            for index, payload in ((0, first), (1, second)):
                self._rewrite_raw(
                    raw,
                    evidence,
                    plan,
                    index,
                    lambda target, payload=payload: (
                        target.clear(),
                        target.update(payload),
                    ),
                )
            with self.assertRaisesRegex(
                PilotValidationError, "boundary"
            ):
                validate_evidence_package(
                    evidence, self.profile, self.config, raw_dir=raw
                )
        finally:
            temp.cleanup()

    def test_tracked_only_validation_never_returns_pass_readiness(self) -> None:
        temp, _raw, evidence, _result = self._collect_synthetic()
        try:
            result = validate_evidence_package(
                evidence, self.profile, self.config
            )
            self.assertFalse(result["raw_reconstruction"])
            self.assertEqual(
                result["readiness"],
                "tracked_package_structurally_valid_raw_replay_required",
            )
        finally:
            temp.cleanup()

        mutations = [
            lambda d: d["pagination"]["pairs"][0].update(
                {"overlap_count": 1}
            ),
            lambda d: d["fallback_behavior"]["macropus_synonym"].update(
                {"normalized_name_rows": 24}
            ),
            lambda d: d["deduplication"].update(
                {"unique_rows_after_deduplication": 467}
            ),
            lambda d: d.update({"observations": "ecological totals"}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                temp, _raw, evidence, _result = self._collect_synthetic()
                try:
                    review_path = evidence / "review.json"
                    review = load_json(review_path)
                    mutate(review)
                    review_path.write_text(
                        json.dumps(review, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    self._rechecksum_manifest(evidence)
                    try:
                        result = validate_evidence_package(
                            evidence, self.profile, self.config
                        )
                    except PilotValidationError:
                        continue
                    self.assertNotEqual(
                        result["readiness"],
                        "pilot_pass_ready_for_bounded_full_acquisition_design",
                    )
                finally:
                    temp.cleanup()

    def test_evidence_only_rebuild_recomputes_epoch_milliseconds_without_fetch(
        self,
    ) -> None:
        temp, raw, evidence, _result = self._collect_synthetic()
        try:
            before = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in raw.iterdir()
            }
            requests_path = evidence / "requests.json"
            requests = load_json(requests_path)
            requests["requests"][0]["validation"][
                "event_date_unparseable_count"
            ] = 25
            requests_path.write_text(
                json.dumps(requests, indent=2) + "\n", encoding="utf-8"
            )
            self._rechecksum_manifest(evidence)
            result = rebuild_evidence_from_raw(
                PROFILE_PATH,
                PLAN_PATH,
                raw,
                evidence,
                now_fn=Clock(),
            )
            self.assertEqual(result["http_requests_made"], 0)
            rebuilt = load_json(requests_path)
            self.assertEqual(
                sum(
                    request["validation"]["event_date_unparseable_count"]
                    for request in rebuilt["requests"]
                ),
                0,
            )
            after = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in raw.iterdir()
            }
            self.assertEqual(after, before)
        finally:
            temp.cleanup()

    def test_resume_reuses_first_raw_response_without_repeating_request(self) -> None:
        plan = build_request_plan(self.profile, self.config)
        payloads = synthetic_payloads(plan)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()
            first_path = raw / plan[0]["raw_file"]
            first_path.write_bytes(payloads[plan[0]["canonical_url"]])
            recovered_time = datetime(
                2026, 7, 23, 12, 59, tzinfo=timezone.utc
            ).timestamp()
            os.utime(first_path, (recovered_time, recovered_time))
            fetched: list[str] = []

            def fetch(url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
                fetched.append(url)
                return 200, payloads[url]

            result = collect_pilot(
                PROFILE_PATH,
                PLAN_PATH,
                raw,
                root / "evidence",
                fetcher=fetch,
                sleep_fn=lambda _seconds: None,
                now_fn=Clock(),
            )
            self.assertEqual(len(fetched), 22)
            self.assertNotIn(plan[0]["canonical_url"], fetched)
            self.assertEqual(result["successful_record_requests"], 23)
            self.assertEqual(result["http_attempts"], 23)
            requests = load_json(root / "evidence" / "requests.json")
            self.assertEqual(
                requests["requests"][0]["retrieval_timestamp_basis"],
                "recovered_raw_file_write_mtime",
            )
            self.assertEqual(
                requests["requests"][0]["retrieved_at_utc"],
                "2026-07-23T12:59:00Z",
            )
            self.assertEqual(
                requests["requests"][0]["raw_sha256"],
                hashlib.sha256(first_path.read_bytes()).hexdigest(),
            )

    def test_response_guards_reject_over_ceiling_duplicate_null_and_date_drift(self) -> None:
        plan = build_request_plan(self.profile, self.config)
        base_payloads = synthetic_payloads(plan)
        target = plan[0]["canonical_url"]
        mutations = [
            lambda p: p["occurrences"].append(copy.deepcopy(p["occurrences"][0])),
            lambda p: p["occurrences"][1].update(
                {"occurrenceID": p["occurrences"][0]["occurrenceID"]}
            ),
            lambda p: p["occurrences"][0].update({"occurrenceID": None}),
            lambda p: p["occurrences"][0].update({"scientificName": None}),
            lambda p: p["occurrences"][0].update({"taxonConceptID": ""}),
            lambda p: p["occurrences"][0].update({"taxonRank": None}),
            lambda p: p["occurrences"][0].update({"year": 2000}),
            lambda p: p["occurrences"][0].update(
                {
                    "eventDate": int(
                        datetime(
                            2000, 1, 1, tzinfo=timezone.utc
                        ).timestamp()
                        * 1000
                    )
                }
            ),
            lambda p: p["occurrences"][0].update({"unexpectedField": "leak"}),
            lambda p: p["occurrences"][0].update(
                {"otherProperties": "not-an-object"}
            ),
            lambda p: p.update({"sort": "score"}),
            lambda p: p.update({"dir": "desc"}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                payloads = dict(base_payloads)
                payload = json.loads(payloads[target])
                mutate(payload)
                payloads[target] = json.dumps(payload).encode("utf-8")

                def fetch(url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
                    return 200, payloads[url]

                with tempfile.TemporaryDirectory() as temp:
                    with self.assertRaises(PilotValidationError):
                        collect_pilot(
                            PROFILE_PATH,
                            PLAN_PATH,
                            Path(temp) / "raw",
                            Path(temp) / "evidence",
                            fetcher=fetch,
                            sleep_fn=lambda _seconds: None,
                            now_fn=Clock(),
                        )

    def test_pagination_overlap_is_rejected(self) -> None:
        plan = build_request_plan(self.profile, self.config)
        payloads = synthetic_payloads(plan)
        first = json.loads(payloads[plan[0]["canonical_url"]])
        second = json.loads(payloads[plan[1]["canonical_url"]])
        second["occurrences"][0]["occurrenceID"] = first["occurrences"][0][
            "occurrenceID"
        ]
        payloads[plan[1]["canonical_url"]] = json.dumps(second).encode("utf-8")

        def fetch(url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
            return 200, payloads[url]

        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(PilotValidationError, "pagination"):
                collect_pilot(
                    PROFILE_PATH,
                    PLAN_PATH,
                    Path(temp) / "raw",
                    Path(temp) / "evidence",
                    fetcher=fetch,
                    sleep_fn=lambda _seconds: None,
                    now_fn=Clock(),
                )

    def test_transient_retry_is_bounded_and_recorded(self) -> None:
        plan = build_request_plan(self.profile, self.config)
        payloads = synthetic_payloads(plan)
        attempts: dict[str, int] = {}

        def fetch(url: str, _headers: dict[str, str]) -> tuple[int, bytes]:
            attempts[url] = attempts.get(url, 0) + 1
            if url == plan[0]["canonical_url"] and attempts[url] == 1:
                raise urllib.error.URLError("synthetic transient")
            return 200, payloads[url]

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = collect_pilot(
                PROFILE_PATH,
                PLAN_PATH,
                root / "raw",
                root / "evidence",
                fetcher=fetch,
                sleep_fn=lambda _seconds: None,
                now_fn=Clock(),
            )
            requests = load_json(root / "evidence" / "requests.json")
            self.assertEqual(result["http_attempts"], 24)
            self.assertEqual(requests["requests"][0]["attempt_count"], 2)
            self.assertEqual(
                requests["requests"][0]["retry_events"],
                [{"attempt": 1, "reason": "transport_error"}],
            )

    def test_evidence_rejects_missing_checksums_leakage_and_rechecksummed_tampering(self) -> None:
        mutators = [
            ("requests.json", lambda d: d["requests"][0].pop("raw_sha256")),
            (
                "requests.json",
                lambda d: d["requests"][0].update(
                    {"occurrences": [{"occurrenceID": "synthetic:leak"}]}
                ),
            ),
            (
                "requests.json",
                lambda d: d["requests"][0].update(
                    {"coordinate_values": [-42.1, 147.1]}
                ),
            ),
            (
                "requests.json",
                lambda d: d["requests"][0].update({"returned_rows": 24}),
            ),
            (
                "review.json",
                lambda d: d["pagination"]["pairs"][0].update(
                    {"overlap_count": 1}
                ),
            ),
            (
                "review.json",
                lambda d: d.update(
                    {
                        "readiness": (
                            "pilot_pass_ready_for_bounded_full_acquisition_design"
                        ),
                        "unresolved_assertions": [],
                    }
                ),
            ),
        ]
        for filename, mutate in mutators:
            with self.subTest(filename=filename, mutate=mutate):
                temp, raw, evidence, _result = self._collect_synthetic()
                try:
                    path = evidence / filename
                    payload = load_json(path)
                    mutate(payload)
                    path.write_text(
                        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
                    )
                    self._rechecksum_manifest(evidence)
                    with self.assertRaises(PilotValidationError):
                        validate_evidence_package(
                            evidence, self.profile, self.config, raw_dir=raw
                        )
                finally:
                    temp.cleanup()

        temp, raw, evidence, _result = self._collect_synthetic()
        try:
            manifest = load_json(evidence / "manifest.json")
            manifest["files"][0].pop("sha256")
            (evidence / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaises(PilotValidationError):
                validate_evidence_package(
                    evidence, self.profile, self.config, raw_dir=raw
                )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
