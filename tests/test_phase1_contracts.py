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


class NormalizedSourceRowGateTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, object]:
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
            "source_rows": load_fixture("source_rows.json")["rows"],
        }

    def test_unresolved_request_decisions_block_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        inputs["request_decision_manifest"] = load_fixture(
            "decision_manifest_request_ala_unresolved.json"
        )

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        message = str(caught.exception)
        self.assertIn("P1-D003", message)
        self.assertIn("P1-D004", message)

    def test_missing_request_decisions_block_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        decisions = inputs["request_decision_manifest"]["decisions"]
        inputs["request_decision_manifest"]["decisions"] = [
            decision for decision in decisions if decision["id"] != "P1-D010"
        ]

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("P1-D010", str(caught.exception))

    def test_invalid_source_contracts_block_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("safe relative path", str(caught.exception))

    def test_missing_row_provenance_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        del broken_rows[0]["source_record_id"]
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("source_record_id", str(caught.exception))

    def test_invalid_pa_type_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        broken_rows[0]["pa_type"] = "synthetic_absence"
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("invalid pa_type", str(caught.exception))

    def test_missing_true_absence_rule_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        true_absence = next(row for row in broken_rows if row["pa_type"] == "true_absence")
        del true_absence["true_absence_rule_id"]
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("true_absence_rule_id", str(caught.exception))

    def test_missing_pseudoabsence_rule_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        pseudoabsence = next(row for row in broken_rows if row["pa_type"] == "pseudoabsence")
        del pseudoabsence["pseudoabsence_rule_id"]
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                **inputs,
            )

        self.assertIn("pseudoabsence_rule_id", str(caught.exception))

    def test_valid_synthetic_rows_produce_deterministic_row_summary(self) -> None:
        inputs = self.valid_inputs()
        missing_ala_path = FIXTURE_DIR / "synthetic_sources" / "syn_ala_snapshot.json"
        missing_camera_path = (
            FIXTURE_DIR / "synthetic_sources" / "syn_camera_source.json"
        )
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())

        first = dsdm_phase1.build_normalized_source_row_gate_summary(
            run_id="syn_run_goal_007",
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_normalized_source_row_gate_summary(
            run_id="syn_run_goal_007",
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_007",
            "stage": "synthetic_normalized_source_row_gate",
            "status": "ready_for_synthetic_normalized_row_review",
            "mocked_request_status": "ready_for_mocked_request_review",
            "decision_manifest_ids": {
                "species_contract": "syn_decisions_resolved",
                "source_contracts": "syn_source_decisions_resolved",
                "request_manifest": "syn_request_decisions_resolved",
            },
            "row_count": 3,
            "row_ids": [
                "syn_row_presence_001",
                "syn_row_pseudoabsence_001",
                "syn_row_true_absence_001",
            ],
            "species_ids": ["syn_species_001", "syn_species_002"],
            "sources": [
                "synthetic_ala",
                "synthetic_background",
                "synthetic_camera",
            ],
            "source_dataset_ids": ["SYN_ALA", "SYN_BACKGROUND", "SYN_CAMERA"],
            "source_dataset_names": [
                "Synthetic ALA-like fixture",
                "Synthetic background fixture",
                "Synthetic camera fixture",
            ],
            "pa_types": ["presence", "pseudoabsence", "true_absence"],
            "sources_by_pa_type": {
                "presence": ["synthetic_ala"],
                "pseudoabsence": ["synthetic_background"],
                "true_absence": ["synthetic_camera"],
            },
            "required_provenance_fields": [
                "run_id",
                "row_id",
                "species_id",
                "scientific_name",
                "source",
                "source_record_id",
                "source_dataset_id",
                "source_dataset_name",
                "pa",
                "pa_type",
                "decision_manifest_id",
                "input_manifest_id",
            ],
            "true_absence_rule_ids": ["SYN_TRUE_ABSENCE_RULE"],
            "pseudoabsence_rule_ids": ["SYN_PSEUDOABSENCE_RULE"],
            "rows": [
                {
                    "row_id": "syn_row_presence_001",
                    "species_id": "syn_species_001",
                    "scientific_name": "Fictomys contracta",
                    "source": "synthetic_ala",
                    "source_record_id": "SYN_ALA_001",
                    "source_dataset_id": "SYN_ALA",
                    "source_dataset_name": "Synthetic ALA-like fixture",
                    "pa": 1,
                    "pa_type": "presence",
                    "grid_cell_id": "SYN_GRID_001",
                },
                {
                    "row_id": "syn_row_pseudoabsence_001",
                    "species_id": "syn_species_002",
                    "scientific_name": "Imagomeles absentia",
                    "source": "synthetic_background",
                    "source_record_id": "SYN_BG_001",
                    "source_dataset_id": "SYN_BACKGROUND",
                    "source_dataset_name": "Synthetic background fixture",
                    "pa": 0,
                    "pa_type": "pseudoabsence",
                    "grid_cell_id": "SYN_GRID_003",
                    "pseudoabsence_rule_id": "SYN_PSEUDOABSENCE_RULE",
                },
                {
                    "row_id": "syn_row_true_absence_001",
                    "species_id": "syn_species_001",
                    "scientific_name": "Fictomys contracta",
                    "source": "synthetic_camera",
                    "source_record_id": "SYN_CAM_001",
                    "source_dataset_id": "SYN_CAMERA",
                    "source_dataset_name": "Synthetic camera fixture",
                    "pa": 0,
                    "pa_type": "true_absence",
                    "grid_cell_id": "SYN_GRID_002",
                    "true_absence_rule_id": "SYN_TRUE_ABSENCE_RULE",
                },
            ],
        }
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertNotEqual(
            first["sources_by_pa_type"]["true_absence"],
            first["sources_by_pa_type"]["pseudoabsence"],
        )
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())


class Phase1DecisionBundleTests(unittest.TestCase):
    def load_bundle(self) -> dict:
        return dsdm_phase1.load_phase1_decision_bundle(
            ROOT / "config" / "phase1_decision_bundle.json"
        )

    def test_tracked_bundle_validates_deterministically(self) -> None:
        bundle = self.load_bundle()

        first = dsdm_phase1.validate_phase1_decision_bundle(bundle)
        second = dsdm_phase1.validate_phase1_decision_bundle(copy.deepcopy(bundle))

        self.assertEqual(first, second)
        self.assertEqual(first["decision_consolidation_status"], "complete")
        self.assertEqual(first["live_acquisition_status"], "blocked")
        self.assertEqual(
            first["blocked_prerequisites"],
            ["P1-D003:ala_taxon_resolution", "P1-D008:camera_source_staging"],
        )

    def test_all_decisions_are_represented_once(self) -> None:
        bundle = self.load_bundle()
        decision_ids = [decision["id"] for decision in bundle["decisions"]]

        self.assertEqual(len(decision_ids), 30)
        self.assertEqual(set(decision_ids), {f"P1-D{index:03d}" for index in range(1, 31)})
        self.assertEqual(
            dsdm_phase1.validate_phase1_decision_bundle(bundle)["decision_count"],
            30,
        )

    def test_species_and_thylogale_special_handling_are_preserved(self) -> None:
        bundle = self.load_bundle()
        species = bundle["species"]

        self.assertEqual(len(species), 9)
        thylogale = next(row for row in species if row["scientific_name"] == "Thylogale billardierii")
        self.assertTrue(thylogale["include_phase1"])
        self.assertEqual(thylogale["historical_aliases"], [])
        self.assertEqual(
            bundle["policies"]["thylogale_edge_case"]["pseudoabsence_generation"],
            "disabled",
        )
        self.assertTrue(
            bundle["policies"]["thylogale_edge_case"]["prevalence_aware_evaluation"]
        )

    def test_temporal_uncertainty_and_absence_policies_are_explicit(self) -> None:
        bundle = self.load_bundle()

        self.assertEqual(
            bundle["policies"]["temporal"]["primary_window"],
            {"start": "2001-01-01", "end": "2025-12-31", "inclusive": True},
        )
        quality = bundle["policies"]["ala_quality"]
        self.assertEqual(quality["max_coordinate_uncertainty_m"], 1000)
        self.assertFalse(quality["missing_uncertainty_excluded"])
        self.assertEqual(quality["precision_basis"], ["reported", "inferred", "unknown"])
        self.assertEqual(
            bundle["policies"]["source_combination"]["absence_label"],
            "survey_supported_absence",
        )
        self.assertNotEqual(
            bundle["policies"]["source_combination"]["absence_label"],
            bundle["policies"]["pseudoabsence"]["label"],
        )

    def test_presence_dominance_and_camera_privacy_are_explicit(self) -> None:
        bundle = self.load_bundle()

        self.assertEqual(
            bundle["policies"]["source_combination"]["accepted_presence_dominates"],
            True,
        )
        self.assertEqual(
            bundle["privacy"]["camera"]["maximum_public_resolution_degree"],
            0.01,
        )
        self.assertIsNone(bundle["operational_prerequisites"][1]["exact_local_source_path"])

    def test_pseudoabsence_and_no_thinning_rules_are_explicit(self) -> None:
        bundle = self.load_bundle()
        pseudo = bundle["policies"]["pseudoabsence"]
        thinning = bundle["policies"]["thinning"]

        self.assertEqual(pseudo["minimum_distinct_non_target_species"], 3)
        self.assertEqual(pseudo["minimum_distance_km"], 5)
        self.assertEqual(pseudo["distance_metric"], "projected_metric_crs")
        self.assertFalse(thinning["human_footprint_thinning"])
        self.assertFalse(thinning["random_or_kmeans_thinning"])

    def test_spatial_partition_and_predictor_policies_are_explicit(self) -> None:
        bundle = self.load_bundle()
        partition = bundle["policies"]["spatial_partition"]
        predictors = bundle["policies"]["predictors"]

        self.assertEqual(
            (partition["microcluster_count"], partition["outer_test_cluster_count"],
             partition["cv_fold_count"], partition["clusters_in_cv"]),
            (50, 5, 5, 45),
        )
        self.assertEqual(predictors["active_predictor_count"], 28)
        self.assertEqual(
            predictors["active_predictors"],
            [
                "annmeantemp", "meandiurnrange", "isothermality", "tempseason",
                "maxtempwarmmonth", "mintempcoldmonth", "tempannrange", "meantempwetq",
                "meantempdryq", "meantempwarmq", "meantempcoldq", "annprecip",
                "precipwetmonth", "precipdrymonth", "precipseason", "precipwetq",
                "precipdryq", "precipwarmq", "precipcoldq", "elevation", "top_roughness",
                "soil_class", "dist_fw", "dist_road", "fpar", "veg_mvg",
                "landuse_secondary", "human_footprint",
            ],
        )
        self.assertEqual(
            predictors["excluded_predictors"],
            ["landuse_primary", "landuse_tertiary", "veg_mvs", "fire_freq"],
        )
        self.assertEqual(
            bundle["policies"]["scaling"]["continuous_scaling_fit"],
            "training_data_only",
        )

    def test_approved_offshore_island_matrix_is_exact(self) -> None:
        matrix = self.load_bundle()["policies"]["island_exclusions"]

        self.assertEqual(
            matrix["island_codes"],
            {"KI": "King Island", "FI": "Flinders Island", "CBI": "Cape Barren Island", "CI": "Clarke Island", "THI": "Three Hummock Island", "HI": "Hunter Island", "MI": "Maria Island", "BI": "Bruny Island"},
        )
        self.assertEqual(
            matrix["species_exclusions"],
            {"thylogale_billardierii": ["KI", "CBI"], "notamacropus_rufogriseus": ["THI", "HI"], "macropus_giganteus": ["KI", "FI", "CBI", "CI", "HI", "BI"], "trichosurus_vulpecula": ["CBI", "CI", "HI"], "pseudocheirus_peregrinus": ["CBI", "CI", "THI", "HI", "BI"], "vombatus_ursinus": ["THI", "HI", "BI"], "sarcophilus_harrisii": ["KI", "FI", "CBI", "CI", "THI", "HI", "BI"], "dasyurus_maculatus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI", "BI"], "dasyurus_viverrinus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI"]},
        )

    def test_live_acquisition_remains_blocked_by_two_prerequisites(self) -> None:
        bundle = self.load_bundle()
        summary = dsdm_phase1.build_phase1_decision_readiness_summary(bundle)

        self.assertEqual(summary["decision_consolidation_status"], "complete")
        self.assertEqual(summary["live_acquisition_status"], "blocked")
        self.assertEqual(len(summary["blocked_prerequisites"]), 2)
        self.assertEqual(
            {item["decision_id"] for item in bundle["operational_prerequisites"]},
            {"P1-D003", "P1-D008"},
        )

    def test_missing_or_duplicate_decisions_fail_closed(self) -> None:
        missing = self.load_bundle()
        missing["decisions"] = missing["decisions"][:-1]
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(missing)

        duplicate = self.load_bundle()
        duplicate["decisions"].append(copy.deepcopy(duplicate["decisions"][0]))
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(duplicate)

    def test_material_contradiction_fails_closed(self) -> None:
        bundle = self.load_bundle()
        bundle["policies"]["pseudoabsence"]["minimum_distance_km"] = 0

        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bundle)

    def test_required_policy_and_reference_mutations_fail_closed(self) -> None:
        missing_grid = self.load_bundle()
        del missing_grid["policies"]["grid"]
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(missing_grid)

        missing_qa = self.load_bundle()
        del missing_qa["policies"]["qa"]
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(missing_qa)

        bad_ref = self.load_bundle()
        bad_ref["decisions"][0]["policy_ref"] = "does_not_exist"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bad_ref)

    def test_status_effort_predictor_and_island_mutations_fail_closed(self) -> None:
        wrong_status = self.load_bundle()
        wrong_status["decisions"][2]["status"] = "resolved"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(wrong_status)

        wrong_camera_status = self.load_bundle()
        wrong_camera_status["decisions"][7]["status"] = "resolved"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(wrong_camera_status)

        effort = self.load_bundle()
        effort["policies"]["camera"]["effort"]["thresholding"] = "detailed_effort_study"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(effort)

        duplicate_predictor = self.load_bundle()
        duplicate_predictor["policies"]["predictors"]["active_predictors"][1] = "annmeantemp"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(duplicate_predictor)

        malformed_island = self.load_bundle()
        del malformed_island["policies"]["island_exclusions"]["species_exclusions"]["dasyurus_viverrinus"]
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(malformed_island)

    def test_privacy_mutations_fail_closed(self) -> None:
        public = self.load_bundle()
        public["privacy"]["camera"]["release"] = "public_site_coordinates"
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(public)

        sensitive_field = self.load_bundle()
        sensitive_field["privacy"]["camera"]["exact_camera_coordinates"] = []
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(sensitive_field)

    def test_bundle_validator_does_not_open_source_payload_paths(self) -> None:
        bundle = self.load_bundle()
        bundle["operational_prerequisites"][1]["exact_local_source_path"] = "data/private-camera.csv"

        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
