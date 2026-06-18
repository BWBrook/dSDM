"""Tests for the Phase 1 synthetic contract scaffold."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "phase1_synthetic"
sys.path.insert(0, str(ROOT / "src"))

import dsdm_phase1  # noqa: E402
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


class AcquisitionDryRunTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, dict]:
        return {
            "species_decision_manifest": load_fixture("decision_manifest_resolved.json"),
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_decision_manifest": load_fixture(
                "decision_manifest_source_resolved.json"
            ),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }

    def test_unresolved_source_decisions_block_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_decision_manifest"] = load_fixture(
            "decision_manifest_source_unresolved.json"
        )

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_acquisition_dry_run_summary(
                run_id="syn_run_goal_005",
                **inputs,
            )

        message = str(caught.exception)
        self.assertIn("P1-D007", message)
        self.assertIn("P1-D008", message)
        self.assertIn("P1-D009", message)

    def test_unresolved_species_contract_blocks_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        inputs["species_contract"] = load_fixture("species_contract_unresolved.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_acquisition_dry_run_summary(
                run_id="syn_run_goal_005",
                **inputs,
            )

        self.assertIn("unresolved decision status", str(caught.exception))

    def test_invalid_source_contracts_block_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_acquisition_dry_run_summary(
                run_id="syn_run_goal_005",
                **inputs,
            )

        self.assertIn("safe relative path", str(caught.exception))

    def test_valid_synthetic_inputs_produce_deterministic_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        missing_source_path = FIXTURE_DIR / "synthetic_sources" / "syn_ala_snapshot.json"
        self.assertFalse(missing_source_path.exists())

        first = dsdm_phase1.build_acquisition_dry_run_summary(
            run_id="syn_run_goal_005",
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_acquisition_dry_run_summary(
            run_id="syn_run_goal_005",
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_005",
            "stage": "synthetic_acquisition_manifest_dry_run",
            "status": "ready_for_mocked_acquisition",
            "decision_manifest_ids": {
                "species_contract": "syn_decisions_resolved",
                "source_contracts": "syn_source_decisions_resolved",
            },
            "required_decisions": [
                "P1-D001",
                "P1-D002",
                "P1-D007",
                "P1-D008",
                "P1-D009",
            ],
            "species_count": 2,
            "included_species_ids": ["syn_species_001", "syn_species_002"],
            "source_ids": ["syn_ala_contract", "syn_camera_contract"],
            "source_types": ["ala_occurrence", "camera_trap"],
            "source_checksums": {
                "syn_ala_contract": "1111111111111111111111111111111111111111111111111111111111111111",
                "syn_camera_contract": "2222222222222222222222222222222222222222222222222222222222222222",
            },
            "licenses": {
                "syn_ala_contract": "synthetic-license-placeholder",
                "syn_camera_contract": "synthetic-license-placeholder",
            },
            "sensitivities": {
                "syn_ala_contract": "synthetic-not-sensitive",
                "syn_camera_contract": "synthetic-not-sensitive",
            },
            "sources": [
                {
                    "source_id": "syn_ala_contract",
                    "source_type": "ala_occurrence",
                    "decision_references": ["P1-D007"],
                    "checksum": {
                        "algorithm": "sha256",
                        "value": "1111111111111111111111111111111111111111111111111111111111111111",
                    },
                    "license": "synthetic-license-placeholder",
                    "sensitivity": "synthetic-not-sensitive",
                    "local_path": "synthetic_sources/syn_ala_snapshot.json",
                },
                {
                    "source_id": "syn_camera_contract",
                    "source_type": "camera_trap",
                    "decision_references": ["P1-D008", "P1-D009"],
                    "checksum": {
                        "algorithm": "sha256",
                        "value": "2222222222222222222222222222222222222222222222222222222222222222",
                    },
                    "license": "synthetic-license-placeholder",
                    "sensitivity": "synthetic-not-sensitive",
                    "local_path": "synthetic_sources/syn_camera_source.json",
                },
            ],
        }
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)


class MockedAcquisitionRequestTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, dict]:
        return {
            "species_decision_manifest": load_fixture("decision_manifest_resolved.json"),
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_decision_manifest": load_fixture(
                "decision_manifest_source_resolved.json"
            ),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
            "request_decision_manifest": load_fixture(
                "decision_manifest_request_resolved.json"
            ),
        }

    def test_unresolved_ala_request_decisions_block_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        inputs["request_decision_manifest"] = load_fixture(
            "decision_manifest_request_ala_unresolved.json"
        )

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                **inputs,
            )

        message = str(caught.exception)
        self.assertIn("P1-D003", message)
        self.assertIn("P1-D004", message)
        self.assertIn("P1-D005", message)
        self.assertIn("P1-D006", message)

    def test_missing_ala_request_decision_blocks_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        decisions = inputs["request_decision_manifest"]["decisions"]
        inputs["request_decision_manifest"]["decisions"] = [
            decision for decision in decisions if decision["id"] != "P1-D004"
        ]

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                **inputs,
            )

        self.assertIn("P1-D004", str(caught.exception))

    def test_unresolved_camera_request_decisions_block_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        inputs["request_decision_manifest"] = load_fixture(
            "decision_manifest_request_camera_unresolved.json"
        )

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                **inputs,
            )

        message = str(caught.exception)
        self.assertIn("P1-D008", message)
        self.assertIn("P1-D009", message)
        self.assertIn("P1-D010", message)

    def test_missing_camera_request_decision_blocks_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        decisions = inputs["request_decision_manifest"]["decisions"]
        inputs["request_decision_manifest"]["decisions"] = [
            decision for decision in decisions if decision["id"] != "P1-D010"
        ]

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                **inputs,
            )

        self.assertIn("P1-D010", str(caught.exception))

    def test_invalid_source_contracts_block_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                **inputs,
            )

        self.assertIn("safe relative path", str(caught.exception))

    def test_valid_synthetic_inputs_produce_deterministic_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        missing_ala_path = FIXTURE_DIR / "synthetic_sources" / "syn_ala_snapshot.json"
        missing_camera_path = (
            FIXTURE_DIR / "synthetic_sources" / "syn_camera_source.json"
        )
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())

        first = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_run_goal_006",
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_run_goal_006",
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_006",
            "stage": "mocked_acquisition_request_dry_run",
            "status": "ready_for_mocked_request_review",
            "dry_run_status": "ready_for_mocked_acquisition",
            "decision_manifest_ids": {
                "species_contract": "syn_decisions_resolved",
                "source_contracts": "syn_source_decisions_resolved",
                "request_manifest": "syn_request_decisions_resolved",
            },
            "required_decisions": [
                "P1-D001",
                "P1-D002",
                "P1-D003",
                "P1-D004",
                "P1-D005",
                "P1-D006",
                "P1-D007",
                "P1-D008",
                "P1-D009",
                "P1-D010",
            ],
            "source_ids": ["syn_ala_contract", "syn_camera_contract"],
            "source_types": ["ala_occurrence", "camera_trap"],
            "request_count": 2,
            "requests": [
                {
                    "request_id": "syn_run_goal_006:syn_ala_contract",
                    "source_contract_id": "syn_ala_contract",
                    "source_id": "syn_ala_contract",
                    "source_type": "ala_occurrence",
                    "execution_status": "not_executed",
                    "mocked": True,
                    "decision_references": [
                        "P1-D003",
                        "P1-D004",
                        "P1-D005",
                        "P1-D006",
                        "P1-D007",
                    ],
                    "checksum": {
                        "algorithm": "sha256",
                        "value": "1111111111111111111111111111111111111111111111111111111111111111",
                    },
                    "license": "synthetic-license-placeholder",
                    "sensitivity": "synthetic-not-sensitive",
                    "intent": {
                        "kind": "synthetic_ala_request",
                        "query_names": [
                            "synthetic_fictomys_contracta",
                            "synthetic_imagomeles_absentia",
                        ],
                        "alias_policy_id": "SYN_ALA_ALIAS_POLICY",
                        "date_filter_policy_id": "SYN_ALA_DATE_POLICY",
                        "data_resource_filter_policy_id": "SYN_ALA_RESOURCE_POLICY",
                        "quality_filter_policy_id": "SYN_ALA_QUALITY_POLICY",
                        "versioning_policy_id": "SYN_ALA_VERSIONING_POLICY",
                    },
                },
                {
                    "request_id": "syn_run_goal_006:syn_camera_contract",
                    "source_contract_id": "syn_camera_contract",
                    "source_id": "syn_camera_contract",
                    "source_type": "camera_trap",
                    "execution_status": "not_executed",
                    "mocked": True,
                    "decision_references": ["P1-D008", "P1-D009", "P1-D010"],
                    "checksum": {
                        "algorithm": "sha256",
                        "value": "2222222222222222222222222222222222222222222222222222222222222222",
                    },
                    "license": "synthetic-license-placeholder",
                    "sensitivity": "synthetic-not-sensitive",
                    "intent": {
                        "kind": "synthetic_camera_ingest_request",
                        "camera_authority_id": "SYN_CAMERA_AUTHORITY",
                        "true_absence_rule_id": "SYN_TRUE_ABSENCE_RULE",
                        "effort_policy_id": "SYN_CAMERA_EFFORT_POLICY",
                    },
                },
            ],
        }
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())


if __name__ == "__main__":
    unittest.main()
