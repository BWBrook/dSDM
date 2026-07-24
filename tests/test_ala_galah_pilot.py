"""Goal 015 route-correct Galah pilot contract and replay tests."""

from __future__ import annotations

import ast
import copy
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1.ala_galah_pilot import (  # noqa: E402
    CORRECT_DOWNLOAD_ENDPOINT,
    EXPECTED_COUNT,
    GALAH_VERSION,
    OCCURRENCE_RAW_FILENAME,
    PASS,
    PROJECTION_FIELDS,
    TRACKED_ONLY,
    GalahPilotValidationError,
    run_pilot,
    validate_evidence_package,
    validate_plan,
)


PLAN_PATH = ROOT / "config" / "ala_galah_pilot_plan.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rechecksum(package: Path) -> None:
    manifest_path = package / "manifest.json"
    manifest = load_json(manifest_path)
    for entry in manifest["files"]:
        artifact = package / entry["path"]
        entry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        entry["bytes"] = artifact.stat().st_size
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 24, 1, 2, 3, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class FakeFrame:
    def __init__(self, records: list[dict], columns: list[str] | None = None):
        self._records = records
        self.columns = columns or list(records[0])
        self.dtypes = {
            name: (
                "int64"
                if name in {"totalRecords", "year"}
                else "float64"
                if name
                in {
                    "decimalLatitude",
                    "decimalLongitude",
                    "coordinateUncertaintyInMeters",
                    "coordinatePrecision",
                }
                else "object"
            )
            for name in self.columns
        }

    def __len__(self) -> int:
        return len(self._records)

    def to_dict(self, orient: str) -> list[dict]:
        if orient != "records":
            raise AssertionError("unexpected orientation")
        return [dict(record) for record in self._records]

    def to_csv(
        self, path: str | Path, *, index: bool, lineterminator: str
    ) -> None:
        if index or lineterminator != "\n":
            raise AssertionError("raw serialization controls drifted")
        with Path(path).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=self.columns, lineterminator=lineterminator
            )
            writer.writeheader()
            writer.writerows(self._records)


class FakePandas:
    DataFrame = FakeFrame


def occurrence_frame(rows: int = EXPECTED_COUNT) -> FakeFrame:
    core = [field for field in PROJECTION_FIELDS if field != "assertions"]
    core[core.index("license")] = "dcterms:license"
    columns = [*core, "assertions", "missingCoordinatePrecision"]
    records = []
    for index in range(rows):
        record = {name: "" for name in columns}
        record.update(
            {
                "occurrenceID": f"opaque-row-{index}",
                "dataResourceUid": "opaque-resource",
                "eventDate": "2001-01-01",
                "year": 2001,
                "decimalLatitude": -42.0,
                "decimalLongitude": 147.0,
                "scientificName": "Pseudocheirus peregrinus",
                "taxonConceptID": "opaque-concept",
                "taxonRank": "species",
                "missingCoordinatePrecision": False,
            }
        )
        records.append(record)
    return FakeFrame(records, columns)


class FakeGalah:
    __version__ = GALAH_VERSION

    def __init__(
        self,
        *,
        count: int = EXPECTED_COUNT,
        occurrences: object | None = None,
        fail_occurrences: bool = False,
    ) -> None:
        self.count = count
        self.occurrences = (
            occurrence_frame() if occurrences is None else occurrences
        )
        self.fail_occurrences = fail_occurrences
        self.config_calls: list[dict] = []
        self.count_calls: list[dict] = []
        self.occurrence_calls: list[dict] = []
        self.config_paths: list[Path] = []

    def galah_config(self, **kwargs) -> None:
        path = Path(kwargs["config_file"])
        if not path.is_file():
            raise AssertionError("custom config file must exist before setup")
        self.config_calls.append(dict(kwargs))
        self.config_paths.append(path)
        path.write_text(
            f"[galahSettings]\nemail={kwargs['email']}\n", encoding="utf-8"
        )

    def atlas_counts(self, **kwargs) -> FakeFrame:
        self.count_calls.append(dict(kwargs))
        if not Path(kwargs["config_file"]).is_file():
            raise AssertionError("count call lost ephemeral config")
        return FakeFrame([{"totalRecords": self.count}])

    def atlas_occurrences(self, **kwargs):
        self.occurrence_calls.append(dict(kwargs))
        if not Path(kwargs["config_file"]).is_file():
            raise AssertionError("occurrence call lost ephemeral config")
        if self.fail_occurrences:
            raise RuntimeError("synthetic package failure")
        return self.occurrences


class GalahPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_json(PLAN_PATH)

    def _run(self, fake: FakeGalah | None = None):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        raw = root / "raw"
        evidence = root / "evidence"
        fake = fake or FakeGalah()
        bounds: list[int] = []

        def bounded(call, seconds: int):
            bounds.append(seconds)
            return call()

        result = run_pilot(
            PLAN_PATH,
            raw,
            evidence,
            galah_module=fake,
            pandas_module=FakePandas,
            environ={"ALA_DOWNLOAD_EMAIL": "runtime-account-secret"},
            now_fn=Clock(),
            occurrence_call_runner=bounded,
        )
        return temp, raw, evidence, fake, bounds, result

    def test_validator_module_keeps_runtime_dependencies_lazy(self) -> None:
        source = ROOT / "src" / "dsdm_phase1" / "ala_galah_pilot.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("galah", imported)
        self.assertNotIn("pandas", imported)

    def test_exact_plan_and_security_mutations_fail_closed(self) -> None:
        self.assertEqual(validate_plan(self.plan)["expected_count"], EXPECTED_COUNT)
        mutations = [
            lambda p: p["package"].update(
                download_endpoint="https://api.ala.org.au/occurrences/offline/download"
            ),
            lambda p: p["package"].update(version="0.13.2"),
            lambda p: p["configuration"].update(authenticate=True),
            lambda p: p["configuration"].update(verbose=True),
            lambda p: p["configuration"].update(
                config_storage="package_default_config"
            ),
            lambda p: p["configuration"].update(email_env="PRIVATE_CONTACT"),
            lambda p: p["configuration"].update(token="forbidden"),
            lambda p: p["configuration"].update(jwt="forbidden"),
            lambda p: p["query"].update(species_id="wrong_species"),
            lambda p: p["query"].update(accepted_concept="wrong-concept"),
            lambda p: p["query"].update(
                filters=["stateProvince=Victoria", "year=2001"]
            ),
            lambda p: p["query"].update(
                filters=["stateProvince=Tasmania", "year=2002"]
            ),
            lambda p: p["query"].update(use_data_profile=True),
            lambda p: p["caps"].update(expected_count=18),
            lambda p: p["caps"].update(max_count_calls=2),
            lambda p: p["caps"].update(max_occurrence_calls=2),
            lambda p: p["caps"].update(max_records=101),
            lambda p: p["caps"].update(occurrence_timeout_seconds=901),
            lambda p: p["projection"]["fields"].remove("assertions"),
            lambda p: p["projection"].update(mint_doi=True),
            lambda p: p["projection"].update(dwc_headers=False),
            lambda p: p["projection"].update(qa="none"),
            lambda p: p["projection"].update(
                returned_field_aliases={"license": "license"}
            ),
            lambda p: p["raw"].update(
                files=["count.csv", OCCURRENCE_RAW_FILENAME]
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(self.plan)
                mutate(candidate)
                with self.assertRaises(GalahPilotValidationError):
                    validate_plan(candidate)

    def test_runner_uses_one_call_each_and_destroys_ephemeral_config(self) -> None:
        temp, raw, evidence, fake, bounds, result = self._run()
        try:
            self.assertEqual(result["readiness"], PASS)
            self.assertEqual(len(fake.config_calls), 1)
            self.assertEqual(len(fake.count_calls), 1)
            self.assertEqual(len(fake.occurrence_calls), 1)
            self.assertEqual(bounds, [900])
            config = fake.config_calls[0]
            self.assertEqual(
                {
                    key: config[key]
                    for key in (
                        "atlas",
                        "email_notify",
                        "reason",
                        "authenticate",
                        "data_profile",
                        "verbose",
                        "timeout",
                    )
                },
                {
                    "atlas": "Australia",
                    "email_notify": False,
                    "reason": 4,
                    "authenticate": False,
                    "data_profile": None,
                    "verbose": False,
                    "timeout": 600,
                },
            )
            config_path = str(fake.config_paths[0])
            self.assertEqual(fake.count_calls[0]["config_file"], config_path)
            self.assertEqual(
                fake.occurrence_calls[0]["config_file"], config_path
            )
            self.assertTrue(
                all(call["use_data_profile"] is False for call in [
                    fake.count_calls[0],
                    fake.occurrence_calls[0],
                ])
            )
            self.assertEqual(
                fake.occurrence_calls[0]["fields"], PROJECTION_FIELDS
            )
            self.assertFalse(fake.occurrence_calls[0]["mint_doi"])
            self.assertFalse(fake.config_paths[0].exists())
            self.assertEqual(
                sorted(path.name for path in raw.iterdir()),
                ["galah-count.csv", "galah-occurrences.csv"],
            )
            tracked = validate_evidence_package(evidence, self.plan)
            self.assertEqual(tracked["readiness"], TRACKED_ONLY)
            replay = validate_evidence_package(
                evidence, self.plan, raw_dir=raw
            )
            self.assertEqual(replay["readiness"], PASS)
            self.assertEqual(replay["count"], EXPECTED_COUNT)
            self.assertEqual(replay["returned_rows"], EXPECTED_COUNT)
        finally:
            temp.cleanup()

    def test_count_drift_stops_before_occurrence_call_and_cleans_config(self) -> None:
        fake = FakeGalah(count=18)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(
                GalahPilotValidationError, "count_drift"
            ):
                run_pilot(
                    PLAN_PATH,
                    root / "raw",
                    root / "evidence",
                    galah_module=fake,
                    pandas_module=FakePandas,
                    environ={"ALA_DOWNLOAD_EMAIL": "runtime-account-secret"},
                    now_fn=Clock(),
                    occurrence_call_runner=lambda call, _seconds: call(),
                )
            self.assertEqual(len(fake.count_calls), 1)
            self.assertEqual(len(fake.occurrence_calls), 0)
            self.assertFalse(fake.config_paths[0].exists())
            combined = b"".join(
                path.read_bytes()
                for path in (root / "evidence").iterdir()
                if path.is_file()
            )
            self.assertNotIn(b"runtime-account-secret", combined)

    def test_occurrence_failure_is_not_retried_and_cleans_config(self) -> None:
        fake = FakeGalah(fail_occurrences=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(
                GalahPilotValidationError, "runtime_or_access_error"
            ):
                run_pilot(
                    PLAN_PATH,
                    root / "raw",
                    root / "evidence",
                    galah_module=fake,
                    pandas_module=FakePandas,
                    environ={"ALA_DOWNLOAD_EMAIL": "runtime-account-secret"},
                    now_fn=Clock(),
                    occurrence_call_runner=lambda call, _seconds: call(),
                )
            self.assertEqual(len(fake.count_calls), 1)
            self.assertEqual(len(fake.occurrence_calls), 1)
            self.assertFalse(fake.config_paths[0].exists())

    def test_wrong_return_type_and_row_count_fail_closed(self) -> None:
        cases = [
            (object(), "wrong_return_type"),
            (occurrence_frame(rows=16), "row_count_mismatch"),
        ]
        for returned, stop_reason in cases:
            with self.subTest(stop_reason=stop_reason):
                fake = FakeGalah(occurrences=returned)
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    with self.assertRaisesRegex(
                        GalahPilotValidationError, stop_reason
                    ):
                        run_pilot(
                            PLAN_PATH,
                            root / "raw",
                            root / "evidence",
                            galah_module=fake,
                            pandas_module=FakePandas,
                            environ={
                                "ALA_DOWNLOAD_EMAIL": "runtime-account-secret"
                            },
                            now_fn=Clock(),
                            occurrence_call_runner=lambda call, _seconds: call(),
                        )
                    self.assertEqual(len(fake.occurrence_calls), 1)
                    self.assertFalse(fake.config_paths[0].exists())

    def test_raw_footprint_symlink_and_checksum_mutations_fail(self) -> None:
        temp, raw, evidence, _fake, _bounds, _result = self._run()
        try:
            mutations = ("missing", "altered", "symlink", "extra")
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    with tempfile.TemporaryDirectory() as work:
                        candidate = Path(work) / "raw"
                        shutil.copytree(raw, candidate)
                        occurrence = candidate / OCCURRENCE_RAW_FILENAME
                        if mutation == "missing":
                            occurrence.unlink()
                        elif mutation == "altered":
                            occurrence.write_bytes(
                                occurrence.read_bytes() + b"\n"
                            )
                        elif mutation == "symlink":
                            occurrence.unlink()
                            occurrence.symlink_to(
                                raw / OCCURRENCE_RAW_FILENAME
                            )
                        else:
                            (candidate / "unexpected.csv").write_text(
                                "unexpected\n", encoding="utf-8"
                            )
                        with self.assertRaises(GalahPilotValidationError):
                            validate_evidence_package(
                                evidence, self.plan, raw_dir=candidate
                            )
        finally:
            temp.cleanup()

    def test_tracked_tampering_and_payload_leakage_fail_after_rechecksum(self) -> None:
        temp, _raw, evidence, _fake, _bounds, _result = self._run()
        try:
            mutations = [
                (
                    "run_summary.json",
                    lambda d: d["route"].update(
                        endpoint="https://api.ala.org.au/occurrences/offline/download"
                    ),
                ),
                (
                    "run_summary.json",
                    lambda d: d["settings"].update(authenticate=True),
                ),
                (
                    "run_summary.json",
                    lambda d: d["query"].update(expected_count=18),
                ),
                (
                    "run_summary.json",
                    lambda d: d["query"].update(species_id="wrong_species"),
                ),
                (
                    "run_summary.json",
                    lambda d: d.update(
                        row_payload=[{"occurrenceID": "private-row"}]
                    ),
                ),
                (
                    "run_summary.json",
                    lambda d: d.update(coordinate_values=[-42.0, 147.0]),
                ),
                (
                    "support_resolution.json",
                    lambda d: d.update(contact="private-contact"),
                ),
                (
                    "review.json",
                    lambda d: d.update(readiness=PASS),
                ),
            ]
            for filename, mutate in mutations:
                with self.subTest(filename=filename, mutate=mutate):
                    with tempfile.TemporaryDirectory() as work:
                        candidate = Path(work) / "evidence"
                        shutil.copytree(evidence, candidate)
                        target = candidate / filename
                        payload = load_json(target)
                        mutate(payload)
                        target.write_text(
                            json.dumps(payload, indent=2) + "\n",
                            encoding="utf-8",
                        )
                        rechecksum(candidate)
                        with self.assertRaises(GalahPilotValidationError):
                            validate_evidence_package(candidate, self.plan)
        finally:
            temp.cleanup()

    def test_manifest_and_tracked_only_state_cannot_claim_pass(self) -> None:
        temp, _raw, evidence, _fake, _bounds, _result = self._run()
        try:
            tracked = validate_evidence_package(evidence, self.plan)
            self.assertEqual(tracked["readiness"], TRACKED_ONLY)
            manifest = load_json(evidence / "manifest.json")
            self.assertEqual(
                {entry["path"] for entry in manifest["files"]},
                {
                    "support_resolution.json",
                    "run_summary.json",
                    "review.json",
                },
            )
            self.assertNotEqual(
                load_json(evidence / "review.json")["readiness"], PASS
            )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
