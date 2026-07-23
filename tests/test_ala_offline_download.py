"""Focused fail-closed tests for the Goal 014 blocked gate."""

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

from dsdm_phase1.ala_offline_download import (  # noqa: E402
    BLOCKED,
    TRACKED_ONLY,
    OfflineDownloadValidationError,
    validate_archive_path,
    validate_evidence_package,
    validate_plan,
)

PLAN_PATH = ROOT / "config" / "ala_offline_download_plan.json"
PACKAGE = ROOT / "evidence" / "ala_offline_download" / "2026-07-24"
RAW = ROOT / "data" / "raw" / "ala" / "goal014-offline-download" / "2026-07-24"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rechecksum(target: Path) -> None:
    manifest = load(target / "manifest.json")
    for entry in manifest["files"]:
        artifact = target / entry["path"]
        entry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        entry["bytes"] = artifact.stat().st_size
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


class OfflineDownloadGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load(PLAN_PATH)

    def test_tracked_only_and_exact_raw_replay_states(self) -> None:
        tracked = validate_evidence_package(PACKAGE, self.plan)
        self.assertEqual(tracked["readiness"], TRACKED_ONLY)
        replay = validate_evidence_package(PACKAGE, self.plan, raw_dir=RAW)
        self.assertEqual(replay["readiness"], BLOCKED)
        self.assertFalse(replay["raw_replay_required"])
        self.assertEqual(replay["selected_count"], 17)

    def test_plan_mutations_fail_closed(self) -> None:
        mutations = [
            lambda p: p.update(max_selector_calls=4),
            lambda p: p.update(max_jobs=2),
            lambda p: p["selector"].update(max_calls=2),
            lambda p: p["selector"].update(pageSize=1),
            lambda p: p["submission"].update(allow_post=True),
            lambda p: p["submission"].update(fileType="tsv"),
            lambda p: p["submission"].update(emailNotify=True),
            lambda p: p["projection"].update(fl="occurrenceID"),
            lambda p: p["quality"].update(qa="all"),
            lambda p: p["lifecycle"].update(max_polls=61),
            lambda p: p["archive"].update(max_bytes=1),
            lambda p: p["route_cap_evidence"].update(offline_source_default_maximum=5000),
            lambda p: p["route_cap_evidence"].update(production_operability="validated"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(self.plan)
                mutate(candidate)
                with self.assertRaises(OfflineDownloadValidationError):
                    validate_plan(candidate)

    def test_evidence_mutations_fail_after_rechecksum(self) -> None:
        mutations = [
            ("count_selection.json", lambda d: d.update(selected_count=101)),
            ("count_selection.json", lambda d: d.update(http_status=201)),
            ("count_selection.json", lambda d: d.update(accepted_concept_query="*:*")),
            ("count_selection.json", lambda d: d.update(pageSize=1)),
            ("count_selection.json", lambda d: d.update(facet_basis="raw_echoed")),
            ("count_selection.json", lambda d: d.update(raw_bytes=1)),
            ("submission.json", lambda d: d.update(attempted_get_requests=2)),
            ("submission.json", lambda d: d["request_ledger"].update(method="POST")),
            ("submission.json", lambda d: d.update(post_requests=1)),
            ("submission.json", lambda d: d.update(retry_requests=1)),
            ("submission.json", lambda d: d.update(alternate_host_requests=1)),
            ("submission.json", lambda d: d.update(auth_or_jwt_used=True)),
            ("submission.json", lambda d: d.update(status_polls=1)),
            ("submission.json", lambda d: d.update(jobs_created=1)),
            ("submission.json", lambda d: d.update(raw_response_body_retained=True)),
            ("submission.json", lambda d: d.update(runtime_email_placeholder="runtime-email-placeholder")),
            ("review.json", lambda d: d.update(readiness="offline_download_route_validated_for_full_acquisition_design")),
            ("review.json", lambda d: d["lifecycle"].update(polls=1)),
            ("contract.json", lambda d: d.update(openapi_sha256="tampered")),
            ("contract.json", lambda d: d["route_cap_evidence"].update(offline_source_default_maximum=1)),
            ("contract.json", lambda d: d["route_cap_evidence"].update(source_anchors=["wrong-anchor"])),
            ("contract.json", lambda d: d["projection_decision"].update(unsafe={"occurrence_id": "private"})),
            ("contract.json", lambda d: d["status_schema_fields"].append("https://api.ala.org.au/occurrences/offline/status/private")),
            ("contract.json", lambda d: d["projection_decision"].update(audit={"event_time": "2026-07-24T00:00:00Z"})),
        ]
        for filename, mutate in mutations:
            with self.subTest(filename=filename):
                temp = tempfile.TemporaryDirectory()
                target = Path(temp.name) / "evidence"
                shutil.copytree(PACKAGE, target)
                path = target / filename
                value = load(path)
                mutate(value)
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
                rechecksum(target)
                try:
                    with self.assertRaises(OfflineDownloadValidationError):
                        validate_evidence_package(target, self.plan)
                finally:
                    temp.cleanup()

    def test_raw_directory_footprint_and_schema_guards(self) -> None:
        for raw_mutation in ("empty", "wrong-name", "symlink"):
            temp = tempfile.TemporaryDirectory()
            target = Path(temp.name) / "raw"
            target.mkdir()
            if raw_mutation == "wrong-name":
                shutil.copy2(RAW / "count-pseudocheirus-2001.json", target / "wrong.json")
            elif raw_mutation == "symlink":
                (target / "count-pseudocheirus-2001.json").symlink_to(RAW / "count-pseudocheirus-2001.json")
            with self.subTest(raw_mutation=raw_mutation):
                with self.assertRaises(OfflineDownloadValidationError):
                    validate_evidence_package(PACKAGE, self.plan, raw_dir=target)
            temp.cleanup()

    def test_manifest_entry_tampering_fails_closed(self) -> None:
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name) / "evidence"
        shutil.copytree(PACKAGE, target)
        manifest = load(target / "manifest.json")
        manifest["files"][0]["unexpected"] = "tamper"
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(OfflineDownloadValidationError):
            validate_evidence_package(target, self.plan)
        temp.cleanup()

    def test_archive_safety_rejects_symlink_oversize_and_unofficial_host(self) -> None:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        archive = root / "archive.zip"
        archive.write_bytes(b"zip")
        validate_archive_path(archive)
        link = root / "link.zip"
        link.symlink_to(archive)
        with self.assertRaises(OfflineDownloadValidationError):
            validate_archive_path(link)
        archive.write_bytes(b"x" * (20 * 1024 * 1024 + 1))
        with self.assertRaises(OfflineDownloadValidationError):
            validate_archive_path(archive)
        archive.write_bytes(b"zip")
        with self.assertRaises(OfflineDownloadValidationError):
            validate_archive_path(archive, expected_host="evil.example")
        temp.cleanup()


if __name__ == "__main__":
    unittest.main()
