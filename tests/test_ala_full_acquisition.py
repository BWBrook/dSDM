"""Offline contract tests for Goal 017 (no network calls)."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1.ala_full_acquisition import (  # noqa: E402
    AcquisitionValidationError,
    CORE_FIELDS,
    GALAH_VERSION,
    PASS,
    TRACKED_ONLY,
    run,
    validate_evidence,
    validate_plan,
)


PLAN = ROOT / "config" / "ala_full_acquisition_plan.json"


class Frame:
    def __init__(self, rows, columns=None):
        self.rows = rows
        self.columns = columns or list(rows[0])

    def __len__(self):
        return len(self.rows)

    def to_dict(self, orient="records"):
        assert orient == "records"
        return [dict(row) for row in self.rows]

    def to_csv(self, path, *, index, lineterminator):
        assert index is False and lineterminator == "\n"
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)


class Pandas:
    DataFrame = Frame


def _qa():
    return json.loads((ROOT / "config" / "ala_field_contract_calibration_plan.json").read_text())["calibration"]["expanded_qa_fields"]


def occurrence_frame(species, n, *, duplicate=False, duplicate_header=False, control_id=False, missing=None, leaked_account=None):
    fields = list(CORE_FIELDS) + _qa()
    if duplicate_header:
        fields.insert(0, "recordID")
    rows = []
    for i in range(n):
        row = {f: "" for f in fields}
        row.update({"recordID": f"same-id" if duplicate else f"{species}-{i}", "occurrenceID": f"o-{species}-{i}", "dataResourceUid": "dr", "eventDate": "2001-01-01", "year": "2001", "decimalLatitude": "-42", "decimalLongitude": "147", "scientificName": "Species", "taxonConceptID": "concept", "taxonRank": "species", "dcterms:license": "CC-BY", "assertions": ""})
        if control_id:
            row["recordID"] += "\u0085"
        if leaked_account:
            row["dataResourceName"] = leaked_account
        for f in _qa():
            row[f] = "false"
        if missing:
            row.pop(missing, None)
        rows.append(row)
    return Frame(rows, fields)


class Galah:
    __version__ = GALAH_VERSION

    def __init__(self, count=1, bad=None):
        self.count = count
        self.bad = bad
        self.count_calls = []
        self.occurrence_calls = []
        self.config_paths = []
        self.runtime_account = None

    def galah_config(self, **kwargs):
        self.config_paths.append(Path(kwargs["config_file"]))
        self.runtime_account = kwargs["email"]
        Path(kwargs["config_file"]).write_text("[galahSettings]\n", encoding="utf-8")

    def atlas_counts(self, **kwargs):
        self.count_calls.append(kwargs)
        value = self.count
        if kwargs["filters"][-1] == "year=2001":
            value = 1
        return Frame([{"totalRecords": value}], ["totalRecords"])

    def atlas_occurrences(self, **kwargs):
        self.occurrence_calls.append(kwargs)
        ident = kwargs["identifiers"].split("/")[-1]
        n = 1 if kwargs["filters"][-1] == "year=2001" else self.count
        missing = self.bad if self.bad not in (None, "duplicate", "duplicate_header", "unicode_control", "email") else None
        return occurrence_frame(
            ident,
            n,
            duplicate=self.bad == "duplicate",
            duplicate_header=self.bad == "duplicate_header",
            control_id=self.bad == "unicode_control",
            missing=missing,
            leaked_account=self.runtime_account if self.bad == "email" else None,
        )


def rehash_evidence(evidence, filename):
    path = evidence / filename
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest["files"] if item["path"] == filename)
    entry["bytes"] = path.stat().st_size
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


class Goal017Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="goal017-test-")
        self.root = Path(self.temp)
        self.raw = self.root / "raw"
        self.evidence = self.root / "evidence"

    def tearDown(self):
        shutil.rmtree(self.temp)

    def test_plan_and_lazy_import(self):
        plan = json.loads(PLAN.read_text())
        self.assertEqual(validate_plan(plan, root=ROOT)["species_count"], 9)
        tree = ast.parse((ROOT / "src/dsdm_phase1/ala_full_acquisition.py").read_text())
        imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
        self.assertNotIn("galah", imports)
        self.assertNotIn("pandas", imports)

    def test_complete_synthetic_run_and_replay(self):
        fake = Galah(count=2)
        result = run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertEqual(result["readiness"], PASS)
        self.assertEqual(len(fake.count_calls), 10)
        self.assertEqual(len(fake.occurrence_calls), 10)
        self.assertEqual(validate_evidence(PLAN, self.evidence)["readiness"], TRACKED_ONLY)
        self.assertEqual(validate_evidence(PLAN, self.evidence, self.raw)["readiness"], PASS)
        self.assertTrue(all(not path.exists() for path in fake.config_paths))

    def test_duplicate_record_ids_block_without_retry(self):
        fake = Galah(count=1, bad="duplicate")
        with self.assertRaises(AcquisitionValidationError):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertEqual(len(fake.occurrence_calls), 3)
        self.assertEqual(json.loads((self.evidence / "review.json").read_text())["readiness"], "goal017_acquisition_blocked")

    def test_missing_email_fails_before_live_import(self):
        with self.assertRaises(AcquisitionValidationError):
            run(PLAN, self.raw, self.evidence, environ={})

    def test_missing_canary_record_id_stops_before_full_acquisition(self):
        fake = Galah(count=2, bad="recordID")
        with self.assertRaisesRegex(AcquisitionValidationError, "record_id_blank_or_control"):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertEqual(len(fake.occurrence_calls), 1)
        self.assertEqual(validate_evidence(PLAN, self.evidence)["readiness"], "goal017_acquisition_blocked")

    def test_disk_gate_stops_before_canary(self):
        fake = Galah(count=1)
        with self.assertRaisesRegex(AcquisitionValidationError, "disk_capacity_failure"):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 0, alarm_fn=lambda call, _: call())
        self.assertEqual(len(fake.count_calls), 9)
        self.assertEqual(len(fake.occurrence_calls), 0)

    def test_rechecksummed_false_pass_is_rejected(self):
        fake = Galah(count=1)
        run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        acquisition_path = self.evidence / "acquisition.json"
        acquisition = json.loads(acquisition_path.read_text())
        acquisition["species"].pop()
        acquisition_path.write_text(json.dumps(acquisition, indent=2, sort_keys=True) + "\n")
        rehash_evidence(self.evidence, "acquisition.json")
        with self.assertRaisesRegex(AcquisitionValidationError, "acquisition_evidence_failure"):
            validate_evidence(PLAN, self.evidence)

    def test_runtime_account_is_removed_from_raw_and_never_evidenced(self):
        fake = Galah(count=1, bad="email")
        account = "test@example.org"
        with self.assertRaisesRegex(AcquisitionValidationError, "runtime_account_in_raw"):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": account}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertTrue(all(account.encode() not in path.read_bytes() for path in self.raw.rglob("*") if path.is_file()))
        self.assertNotIn(account, "\n".join(path.read_text() for path in self.evidence.glob("*.json")))

    def test_duplicate_core_header_is_rejected(self):
        fake = Galah(count=1, bad="duplicate_header")
        with self.assertRaisesRegex(AcquisitionValidationError, "occurrence_header_failure"):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertEqual(len(fake.occurrence_calls), 1)

    def test_unicode_control_in_record_id_is_rejected(self):
        fake = Galah(count=1, bad="unicode_control")
        with self.assertRaisesRegex(AcquisitionValidationError, "record_id_blank_or_control"):
            run(PLAN, self.raw, self.evidence, galah_module=fake, pandas_module=Pandas, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"}, disk_free_fn=lambda _: 10**15, alarm_fn=lambda call, _: call())
        self.assertEqual(len(fake.occurrence_calls), 1)

    def test_dependency_failure_is_sanitised_before_raw_directories(self):
        with patch("dsdm_phase1.ala_full_acquisition.importlib.import_module", side_effect=ModuleNotFoundError):
            with self.assertRaisesRegex(AcquisitionValidationError, "dependency_unavailable"):
                run(PLAN, self.raw, self.evidence, environ={"ALA_DOWNLOAD_EMAIL": "test@example.org"})
        self.assertFalse(self.raw.exists())
        self.assertFalse(self.evidence.exists())


if __name__ == "__main__":
    unittest.main()
