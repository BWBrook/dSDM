"""Tests for the Phase 1 synthetic contract scaffold."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "phase1_synthetic"
sys.path.insert(0, str(ROOT / "src"))

from dsdm_phase1.contracts import (  # noqa: E402
    ValidationError,
    validate_decision_manifest,
    validate_manifest_checksums,
    validate_source_contracts,
    validate_source_rows,
    validate_species_contract,
)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class Phase1ContractTests(unittest.TestCase):
    def test_unresolved_decisions_block_species_contract_stage(self) -> None:
        manifest = load_fixture("decision_manifest_unresolved.json")

        with self.assertRaises(ValidationError) as caught:
            validate_decision_manifest(manifest, stage="species_contract")

        message = str(caught.exception)
        self.assertIn("P1-D001", message)
        self.assertIn("P1-D002", message)

    def test_resolved_synthetic_decisions_allow_species_contract_stage(self) -> None:
        manifest = load_fixture("decision_manifest_resolved.json")

        result = validate_decision_manifest(manifest, stage="species_contract")

        self.assertEqual(result["stage"], "species_contract")
        self.assertEqual(result["required_decisions"], ["P1-D001", "P1-D002"])

    def test_species_contract_rejects_unresolved_included_species(self) -> None:
        unresolved = load_fixture("species_contract_unresolved.json")
        resolved = load_fixture("species_contract_resolved.json")

        with self.assertRaises(ValidationError):
            validate_species_contract(unresolved)

        result = validate_species_contract(resolved)
        self.assertEqual(
            result["included_species_ids"],
            ["syn_species_001", "syn_species_002"],
        )

    def test_pa_type_categories_and_provenance_survive_validation(self) -> None:
        rows = load_fixture("source_rows.json")["rows"]

        result = validate_source_rows(rows)

        self.assertEqual(
            set(result["pa_types"]),
            {"presence", "true_absence", "pseudoabsence"},
        )
        self.assertEqual(
            result["sources_by_pa_type"]["true_absence"],
            ["synthetic_camera"],
        )
        self.assertIn("source_record_id", result["required_provenance_fields"])

    def test_missing_provenance_fails(self) -> None:
        rows = load_fixture("source_rows.json")["rows"]
        broken_row = dict(rows[0])
        del broken_row["source_record_id"]

        with self.assertRaises(ValidationError):
            validate_source_rows([broken_row])

    def test_source_manifest_checksums_match_fixture_files(self) -> None:
        manifest = load_fixture("source_manifest.json")

        result = validate_manifest_checksums(manifest, base_dir=FIXTURE_DIR)

        self.assertEqual(
            result["checked_files"],
            [
                "species_contract_resolved.json",
                "decision_manifest_resolved.json",
                "source_rows.json",
            ],
        )

    def test_source_contracts_stage_rejects_unresolved_source_decisions(self) -> None:
        manifest = load_fixture("decision_manifest_source_unresolved.json")

        with self.assertRaises(ValidationError) as caught:
            validate_decision_manifest(manifest, stage="source_contracts")

        message = str(caught.exception)
        self.assertIn("P1-D007", message)
        self.assertIn("P1-D008", message)
        self.assertIn("P1-D009", message)

    def test_source_contracts_stage_rejects_missing_source_decisions(self) -> None:
        manifest = load_fixture("decision_manifest_resolved.json")

        with self.assertRaises(ValidationError) as caught:
            validate_decision_manifest(manifest, stage="source_contracts")

        message = str(caught.exception)
        self.assertIn("P1-D008", message)
        self.assertIn("P1-D009", message)

    def test_source_contracts_stage_accepts_synthetic_resolved_decisions(self) -> None:
        manifest = load_fixture("decision_manifest_source_resolved.json")

        result = validate_decision_manifest(manifest, stage="source_contracts")

        self.assertEqual(result["stage"], "source_contracts")
        self.assertEqual(
            result["required_decisions"],
            ["P1-D007", "P1-D008", "P1-D009"],
        )

    def test_source_contract_metadata_preserves_audit_and_decision_links(self) -> None:
        contracts = load_fixture("source_contracts_resolved.json")

        result = validate_source_contracts(contracts)

        self.assertEqual(
            result["source_ids"],
            ["syn_ala_contract", "syn_camera_contract"],
        )
        self.assertEqual(
            result["decision_references"],
            ["P1-D007", "P1-D008", "P1-D009"],
        )
        self.assertEqual(
            result["source_types"],
            ["ala_occurrence", "camera_trap"],
        )

    def test_source_contract_metadata_rejects_unsafe_paths(self) -> None:
        contracts = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            validate_source_contracts(contracts)

        self.assertIn("safe relative path", str(caught.exception))

    def test_source_contract_metadata_rejects_missing_audit_metadata(self) -> None:
        contracts = load_fixture("source_contracts_missing_audit.json")

        with self.assertRaises(ValidationError) as caught:
            validate_source_contracts(contracts)

        self.assertIn("checksum", str(caught.exception))

    def test_source_contract_metadata_rejects_non_hex_checksum(self) -> None:
        contracts = load_fixture("source_contracts_resolved.json")
        contracts["contracts"][0]["checksum"]["value"] = "z" * 64

        with self.assertRaises(ValidationError) as caught:
            validate_source_contracts(contracts)

        self.assertIn("SHA-256 hex digest", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
