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
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dsdm_phase1.ala_field_contract import (  # noqa: E402
    ALAFieldContractError,
    TRACKED_FILENAMES,
    TRACKED_ONLY,
    _profile,
    _read_bound_csv,
    _scan_tracked,
    validate_contract,
    validate_evidence_package,
    validate_plan,
)


PLAN_PATH = ROOT / "config" / "ala_field_contract_calibration_plan.json"
CONTRACT_PATH = ROOT / "config" / "ala_field_contract.json"
EVIDENCE_DIR = ROOT / "evidence" / "ala_field_contract" / "2026-07-24"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rechecksum(evidence_dir: Path) -> None:
    manifest = load_json(evidence_dir / "manifest.json")
    for entry in manifest["files"]:
        path = evidence_dir / entry["path"]
        entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        entry["bytes"] = path.stat().st_size
    (evidence_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def synthetic_rows(
    core: list[str],
    *,
    record_ids: tuple[str, str] | None = None,
    unknown_extra_value: str | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    qa = ["QA_ALWAYS", "QA_MIXED"]
    if unknown_extra_value is not None:
        qa.append("UNEXPECTED_EXTRA")
    fields = [*core, *qa]
    rows: list[dict[str, str]] = []
    for index in range(2):
        row = {field: f"synthetic-{field}" for field in core}
        row.update(
            {
                "occurrenceID": "",
                "dataResourceUid": "synthetic-resource",
                "dataResourceName": "synthetic-resource-name",
                "datasetID": "",
                "datasetName": "",
                "eventDate": f"2020-01-0{index + 1}",
                "year": "2020",
                "decimalLatitude": str(-40 - index),
                "decimalLongitude": str(145 + index),
                "coordinateUncertaintyInMeters": "100",
                "coordinatePrecision": "",
                "raw_scientificName": "Synthetic species",
                "raw_taxonConceptID": "",
                "scientificName": "Synthetic species",
                "taxonConceptID": "https://example.test/taxon",
                "acceptedNameUsage": "",
                "acceptedNameUsageID": "",
                "taxonRank": "species",
                "assertions": "synthetic-assertion-summary",
                "dcterms:license": "synthetic-licence",
                "QA_ALWAYS": "true",
                "QA_MIXED": "true" if index else "false",
            }
        )
        if "recordID" in core:
            row["recordID"] = record_ids[index] if record_ids else ""
        if unknown_extra_value is not None:
            row["UNEXPECTED_EXTRA"] = unknown_extra_value
        rows.append(row)
    return fields, rows


class ALAFieldContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_json(PLAN_PATH)
        self.contract = load_json(CONTRACT_PATH)

    def test_committed_evidence_is_tracked_only_without_raw(self) -> None:
        result = validate_evidence_package(PLAN_PATH, EVIDENCE_DIR)
        self.assertEqual(result["readiness"], TRACKED_ONLY)
        self.assertTrue(result["raw_replay_required"])
        self.assertEqual(
            {path.name for path in EVIDENCE_DIR.iterdir()},
            {*TRACKED_FILENAMES, "manifest.json"},
        )

    def test_plan_and_generic_contract_fail_closed_on_material_mutation(self) -> None:
        plan_mutations = [
            lambda value: value.update(network_calls_allowed=1),
            lambda value: value["source"]["occurrence_csv"].update(
                sha256="0" * 64
            ),
            lambda value: value["source"]["request_profile"].update(
                sha256="0" * 64
            ),
            lambda value: value["calibration"].update(
                content_fingerprint_role="record_identity"
            ),
            lambda value: value["calibration"]["expanded_qa_fields"].append(
                "UNEXPECTED_BOOLEAN"
            ),
            lambda value: value["evidence"].update(
                raw_replay_required_for_decision=False
            ),
        ]
        for mutate in plan_mutations:
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(self.plan)
                mutate(candidate)
                with self.assertRaises(ALAFieldContractError):
                    validate_plan(candidate, ROOT)

        contract_mutations = [
            lambda value: value["record_identity"].update(
                content_fallback_allowed=True
            ),
            lambda value: value["provenance"].update(
                dataset_resource_fallback_allowed=True
            ),
            lambda value: value["spatial"].update(
                decimal_place_precision_inference="allowed"
            ),
            lambda value: value["quality_assertions"].update(
                any_flag_rejects=True
            ),
            lambda value: value["readiness_gates"].update(
                branch_count_union_without_provider_identity="allowed"
            ),
        ]
        for mutate in contract_mutations:
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(self.contract)
                mutate(candidate)
                with self.assertRaises(ALAFieldContractError):
                    validate_contract(candidate)

    def test_synthetic_profile_separates_provider_and_diagnostic_identity(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["calibration"]["expanded_qa_fields"] = [
            "QA_ALWAYS",
            "QA_MIXED",
        ]
        fields, rows = synthetic_rows(
            plan["calibration"]["returned_core_fields"]
        )
        profile = _profile(plan, fields, rows)
        self.assertIsNone(profile["provider_identity"]["selected_field"])
        self.assertFalse(
            profile["provider_identity"]["complete_unique_provider_identity"]
        )
        self.assertFalse(
            profile["duplicate_diagnostics"][
                "content_fingerprint_used_as_identity"
            ]
        )
        self.assertEqual(
            profile["duplicate_diagnostics"][
                "distinct_complete_content_fingerprint_count"
            ],
            2,
        )

    def test_synthetic_provider_candidate_must_be_complete_and_unique(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["calibration"]["returned_core_fields"].insert(0, "recordID")
        plan["calibration"]["expanded_qa_fields"] = [
            "QA_ALWAYS",
            "QA_MIXED",
        ]
        fields, unique_rows = synthetic_rows(
            plan["calibration"]["returned_core_fields"],
            record_ids=("synthetic-id-a", "synthetic-id-b"),
        )
        unique_profile = _profile(plan, fields, unique_rows)
        self.assertEqual(
            unique_profile["provider_identity"]["selected_field"], "recordID"
        )

        fields, duplicate_rows = synthetic_rows(
            plan["calibration"]["returned_core_fields"],
            record_ids=("synthetic-id-a", "synthetic-id-a"),
        )
        duplicate_profile = _profile(plan, fields, duplicate_rows)
        self.assertIsNone(
            duplicate_profile["provider_identity"]["selected_field"]
        )

    def test_unknown_boolean_extra_and_non_boolean_qa_fail_schema_review(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["calibration"]["expanded_qa_fields"] = [
            "QA_ALWAYS",
            "QA_MIXED",
        ]
        fields, rows = synthetic_rows(
            plan["calibration"]["returned_core_fields"],
            unknown_extra_value="true",
        )
        with self.assertRaisesRegex(
            ALAFieldContractError, "allowlist drifted"
        ):
            _profile(plan, fields, rows)

        fields, rows = synthetic_rows(
            plan["calibration"]["returned_core_fields"]
        )
        rows[0]["QA_MIXED"] = "not-a-boolean"
        with self.assertRaisesRegex(
            ALAFieldContractError, "not Boolean-compatible"
        ):
            _profile(plan, fields, rows)

    def test_tracked_tampering_fails_even_after_manifest_rechecksum(self) -> None:
        mutations = [
            lambda profile: profile["provider_identity"].update(
                selected_field="occurrenceID",
                complete_unique_provider_identity=True,
            ),
            lambda profile: profile["csv_semantics"].update(
                population_measure="row_values"
            ),
            lambda profile: profile["field_population"][0].update(
                samples=["synthetic-id", "2020-01-01", "-40.0"]
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                with tempfile.TemporaryDirectory() as temporary:
                    candidate = Path(temporary) / "evidence"
                    shutil.copytree(EVIDENCE_DIR, candidate)
                    profile_path = candidate / "profile.json"
                    profile = load_json(profile_path)
                    mutate(profile)
                    profile_path.write_text(
                        json.dumps(profile, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    rechecksum(candidate)
                    with self.assertRaises(ALAFieldContractError):
                        validate_evidence_package(PLAN_PATH, candidate)

    def test_privacy_scanner_rejects_private_or_row_level_payloads(self) -> None:
        payloads = [
            {"contact": "private"},
            {"note": "person" + "@" + "example.test"},
            {"row_values": ["synthetic-secret"]},
            {"identifier_values": ["synthetic-id"]},
            {"coordinate_values": [-40.0, 145.0]},
            {"snapshot_row_ids": ["synthetic-key"]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ALAFieldContractError):
                    _scan_tracked(payload)

    def test_raw_binding_rejects_missing_altered_and_symlink_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.csv"
            raw.write_text("field\nvalue\n", encoding="utf-8")
            binding = {
                "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "bytes": raw.stat().st_size,
                "rows": 1,
                "columns": 1,
            }
            fields, rows = _read_bound_csv(raw, binding)
            self.assertEqual(fields, ["field"])
            self.assertEqual(len(rows), 1)

            altered = root / "altered.csv"
            altered.write_text("field\nchanged\n", encoding="utf-8")
            with self.assertRaises(ALAFieldContractError):
                _read_bound_csv(altered, binding)

            missing = root / "missing.csv"
            with self.assertRaises(ALAFieldContractError):
                _read_bound_csv(missing, binding)

            link = root / "link.csv"
            link.symlink_to(raw)
            with self.assertRaises(ALAFieldContractError):
                _read_bound_csv(link, binding)

    def test_module_has_no_network_or_acquisition_runtime_imports(self) -> None:
        source = ROOT / "src" / "dsdm_phase1" / "ala_field_contract.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint({"requests", "httpx", "galah", "pandas"})
        )


if __name__ == "__main__":
    unittest.main()
