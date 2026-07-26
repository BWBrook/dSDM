"""Tests for the Phase 1 synthetic contract scaffold."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "phase1_synthetic"
DECISION_BUNDLE_PATH = ROOT / "config" / "phase1_decision_bundle.json"
GOAL010_CANDIDATES_PATH = ROOT / "evidence" / "ala_taxon_resolution" / "2026-07-23" / "candidates.json"
GOAL010_PACKAGE_PATH = ROOT / "evidence" / "ala_taxon_resolution" / "2026-07-23"
sys.path.insert(0, str(ROOT / "src"))

import dsdm_phase1  # noqa: E402
from dsdm_phase1.contracts import (  # noqa: E402
    ValidationError,
    validate_decision_manifest,
    validate_manifest_checksums,
    validate_source_contracts,
    validate_source_rows,
    validate_species_contract,
    validate_ala_resolution_candidates,
)
from dsdm_phase1.manifests import _validate_ala_request_intent  # noqa: E402


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_decision_bundle() -> dict:
    return dsdm_phase1.load_phase1_decision_bundle(DECISION_BUNDLE_PATH)


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
            {"presence", "survey_supported_absence", "pseudoabsence"},
        )
        self.assertEqual(
            result["sources_by_pa_type"]["survey_supported_absence"],
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
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }

    def test_unresolved_species_contract_blocks_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        inputs["species_contract"] = load_fixture("species_contract_unresolved.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_acquisition_dry_run_summary(
                run_id="syn_run_goal_005",
                decision_bundle=load_decision_bundle(),
                **inputs,
            )

        self.assertIn("unresolved decision status", str(caught.exception))

    def test_invalid_source_contracts_block_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_acquisition_dry_run_summary(
                run_id="syn_run_goal_005",
                decision_bundle=load_decision_bundle(),
                **inputs,
            )

        self.assertIn("safe relative path", str(caught.exception))

    def test_valid_synthetic_inputs_produce_deterministic_dry_run_summary(self) -> None:
        inputs = self.valid_inputs()
        missing_source_path = FIXTURE_DIR / "synthetic_sources" / "syn_ala_snapshot.json"
        self.assertFalse(missing_source_path.exists())

        first = dsdm_phase1.build_acquisition_dry_run_summary(
            run_id="syn_run_goal_005",
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_acquisition_dry_run_summary(
            run_id="syn_run_goal_005",
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_005",
            "stage": "synthetic_acquisition_manifest_dry_run",
            "status": "ready_for_mocked_acquisition",
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
        self.assertEqual(first, second)
        for key, value in expected.items():
            self.assertEqual(first[key], value)


class MockedAcquisitionRequestTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, dict]:
        return {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }

    def test_invalid_source_contracts_block_mocked_requests(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_run_goal_006",
                decision_bundle=load_decision_bundle(),
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
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_run_goal_006",
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_006",
            "stage": "mocked_acquisition_request_dry_run",
            "status": "ready_for_mocked_request_review",
            "dry_run_status": "ready_for_mocked_acquisition",
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
                        "query_resolution_status": "blocked_pending_P1-D003",
                        "policy_references": ["P1-D003", "P1-D004", "P1-D005", "P1-D006", "P1-D007"],
                        "primary_window": {"start": "2001-01-01", "end": "2025-12-31", "inclusive": True},
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
                        "authority_status": "blocked_pending_P1-D008",
                        "survey_supported_absence_rule_id": "P1-D009",
                        "policy_references": ["P1-D008", "P1-D009", "P1-D010"],
                        "absence_label": "survey_supported_absence",
                    },
                },
            ],
        }
        bundle = load_decision_bundle()
        resolution = bundle["policies"]["species"]["ala_resolution"]
        expected["requests"][0]["intent"].update(
            {
                "query_resolution_status": "resolved",
                "species_queries": [
                    {
                        "species_id": species["species_id"],
                        "accepted_name": species["accepted_name"],
                        "ala_taxon_concept_id": species["ala_taxon_concept_id"],
                        "historical_aliases": list(species["historical_aliases"]),
                    }
                    for species in bundle["species"]
                ],
                "synonym_normalization": resolution["synonym_normalization"],
                "accepted_descendants": resolution["accepted_descendants"],
                "pre_acquisition_scope_assertion_required": resolution["pre_acquisition_scope_assertion_required"],
                "taxon_identity_retention": dict(resolution["taxon_identity_retention"]),
                "expansion_failure_fallback": resolution["expansion_failure_fallback"],
                "subtaxon_policy": copy.deepcopy(resolution["subtaxon_policy"]),
            }
        )
        self.assertEqual(first, second)
        for key, value in expected.items():
            self.assertEqual(first[key], value)
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())


class NormalizedSourceRowGateTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, object]:
        return {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
            "source_rows": load_fixture("source_rows.json")["rows"],
        }

    def test_invalid_source_contracts_block_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        inputs["source_contracts"] = load_fixture("source_contracts_unsafe_path.json")

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                decision_bundle=load_decision_bundle(),
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
                decision_bundle=load_decision_bundle(),
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
                decision_bundle=load_decision_bundle(),
                **inputs,
            )

        self.assertIn("invalid pa_type", str(caught.exception))

    def test_missing_survey_supported_absence_rule_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        survey_absence = next(row for row in broken_rows if row["pa_type"] == "survey_supported_absence")
        del survey_absence["survey_supported_absence_rule_id"]
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                decision_bundle=load_decision_bundle(),
                **inputs,
            )

        self.assertIn("survey_supported_absence_rule_id", str(caught.exception))

    def test_missing_pseudoabsence_rule_blocks_row_summaries(self) -> None:
        inputs = self.valid_inputs()
        broken_rows = copy.deepcopy(inputs["source_rows"])
        pseudoabsence = next(row for row in broken_rows if row["pa_type"] == "pseudoabsence")
        del pseudoabsence["pseudoabsence_rule_id"]
        inputs["source_rows"] = broken_rows

        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_007",
                decision_bundle=load_decision_bundle(),
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
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )
        second = dsdm_phase1.build_normalized_source_row_gate_summary(
            run_id="syn_run_goal_007",
            decision_bundle=load_decision_bundle(),
            **copy.deepcopy(inputs),
        )

        expected = {
            "run_id": "syn_run_goal_007",
            "stage": "synthetic_normalized_source_row_gate",
            "status": "ready_for_synthetic_normalized_row_review",
            "mocked_request_status": "ready_for_mocked_request_review",
            "row_count": 3,
            "row_ids": [
                "syn_row_presence_001",
                "syn_row_pseudoabsence_001",
                "syn_row_survey_supported_absence_001",
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
            "pa_types": ["presence", "pseudoabsence", "survey_supported_absence"],
            "sources_by_pa_type": {
                "presence": ["synthetic_ala"],
                "pseudoabsence": ["synthetic_background"],
                "survey_supported_absence": ["synthetic_camera"],
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
                "source_type",
                "source_contract_id",
                "pa",
                "pa_type",
                "decision_manifest_id",
                "input_manifest_id",
            ],
            "survey_supported_absence_rule_ids": ["P1-D009"],
            "pseudoabsence_rule_ids": ["SYN_PSEUDOABSENCE_RULE"],
            "rows": [
                {
                    "row_id": "syn_row_presence_001",
                    "species_id": "syn_species_001",
                    "scientific_name": "Fictomys contracta",
                    "source": "synthetic_ala",
                    "source_type": "ala_occurrence",
                    "source_contract_id": "syn_ala_contract",
                    "source_record_id": "SYN_ALA_001",
                    "source_dataset_id": "SYN_ALA",
                    "source_dataset_name": "Synthetic ALA-like fixture",
                    "pa": 1,
                    "pa_type": "presence",
                    "grid_cell_id": "SYN_GRID_001",
                    "ala_taxon_identity": {
                        "submitted_name": "Fictomys contracta minor",
                        "matched_name": "Fictomys contracta minor",
                        "matched_concept_id": "SYN_AFD_MATCHED_SUBSPECIES_001",
                        "accepted_name": "Fictomys contracta minor",
                        "accepted_concept_id": "SYN_AFD_ACCEPTED_SUBSPECIES_001",
                        "accepted_rank": "subspecies",
                    },
                },
                {
                    "row_id": "syn_row_pseudoabsence_001",
                    "species_id": "syn_species_002",
                    "scientific_name": "Imagomeles absentia",
                    "source": "synthetic_background",
                    "source_type": "pseudoabsence_fixture",
                    "source_contract_id": None,
                    "source_record_id": "SYN_BG_001",
                    "source_dataset_id": "SYN_BACKGROUND",
                    "source_dataset_name": "Synthetic background fixture",
                    "pa": 0,
                    "pa_type": "pseudoabsence",
                    "grid_cell_id": "SYN_GRID_003",
                    "pseudoabsence_rule_id": "SYN_PSEUDOABSENCE_RULE",
                },
                {
                    "row_id": "syn_row_survey_supported_absence_001",
                    "species_id": "syn_species_001",
                    "scientific_name": "Fictomys contracta",
                    "source": "synthetic_camera",
                    "source_type": "camera_trap",
                    "source_contract_id": "syn_camera_contract",
                    "source_record_id": "SYN_CAM_001",
                    "source_dataset_id": "SYN_CAMERA",
                    "source_dataset_name": "Synthetic camera fixture",
                    "pa": 0,
                    "pa_type": "survey_supported_absence",
                    "grid_cell_id": "SYN_GRID_002",
                    "survey_supported_absence_rule_id": "P1-D009",
                    "camera_resolution_degree": 0.01,
                },
            ],
            "decision_bundle_id": "dsdm-phase1-decision-bundle",
            "decision_bundle_schema_version": "1.1",
            "decision_consolidation_status": "complete",
            "live_acquisition_status": "blocked",
            "blocked_prerequisites": ["P1-D008:camera_source_staging"],
            "policy_provenance": {
                "accepted_presence_dominates": True,
                "camera_absence_label": "survey_supported_absence",
                "coordinate_assignment": "containing_eligible_cell_only",
                "nearest_land_cell_rescue": False,
                "source_collapse_executed": False,
                "spatial_assignment_executed": False,
                "ala_resolution_status": "resolved",
                "ala_resolution_evidence_package": "evidence/ala_taxon_resolution/2026-07-23",
            },
        }
        self.assertEqual(first, second)
        for key, value in expected.items():
            self.assertEqual(first[key], value)
        self.assertNotEqual(
            first["sources_by_pa_type"]["survey_supported_absence"],
            first["sources_by_pa_type"]["pseudoabsence"],
        )
        self.assertFalse(missing_ala_path.exists())
        self.assertFalse(missing_camera_path.exists())


class Goal009CanonicalAlignmentTests(unittest.TestCase):
    def valid_inputs(self) -> dict[str, object]:
        return {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
            "source_rows": load_fixture("source_rows.json")["rows"],
        }

    def test_authoritative_bundle_is_required_and_provenance_is_exposed(self) -> None:
        inputs = self.valid_inputs()
        with self.assertRaises(TypeError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                **inputs,
            )

        summary = dsdm_phase1.build_normalized_source_row_gate_summary(
            run_id="syn_run_goal_009",
            decision_bundle=load_decision_bundle(),
            **inputs,
        )
        self.assertEqual(summary["decision_bundle_id"], "dsdm-phase1-decision-bundle")
        self.assertEqual(summary["decision_bundle_schema_version"], "1.1")
        self.assertEqual(summary["decision_consolidation_status"], "complete")
        self.assertEqual(summary["live_acquisition_status"], "blocked")
        self.assertEqual(summary["blocked_prerequisites"], ["P1-D008:camera_source_staging"])
        self.assertTrue(summary["policy_provenance"]["accepted_presence_dominates"])
        self.assertFalse(summary["policy_provenance"]["nearest_land_cell_rescue"])
        self.assertFalse(summary["policy_provenance"]["source_collapse_executed"])

        dry_run = dsdm_phase1.build_acquisition_dry_run_summary(
            run_id="syn_run_goal_009",
            decision_bundle=load_decision_bundle(),
            **{key: value for key, value in inputs.items() if key != "source_rows"},
        )
        request = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_run_goal_009",
            decision_bundle=load_decision_bundle(),
            **{key: value for key, value in inputs.items() if key != "source_rows"},
        )
        for result in (dry_run, request):
            self.assertEqual(result["decision_bundle_id"], "dsdm-phase1-decision-bundle")
            self.assertEqual(result["live_acquisition_status"], "blocked")

    def test_contradictory_presence_or_coordinate_policy_blocks(self) -> None:
        inputs = self.valid_inputs()
        bundle = load_decision_bundle()
        bundle["policies"]["source_combination"]["accepted_presence_dominates"] = False
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=bundle,
                **inputs,
            )

        bundle = load_decision_bundle()
        bundle["policies"]["coordinate_assignment"]["nearest_land_cell_rescue"] = True
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=bundle,
                **inputs,
            )

    def test_legacy_true_absence_fails_with_migration_error(self) -> None:
        inputs = self.valid_inputs()
        rows = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in rows if row["source"] == "synthetic_camera")
        camera["pa_type"] = "true_absence"
        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=rows,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )
        self.assertIn("legacy pa_type true_absence is retired", str(caught.exception))

    def test_survey_absence_rule_source_and_pseudoabsence_constraints_fail_closed(self) -> None:
        inputs = self.valid_inputs()
        contracts = copy.deepcopy(inputs["source_contracts"])
        camera_contract = next(item for item in contracts["contracts"] if item["source_type"] == "camera_trap")
        del camera_contract["survey_supported_absence"]
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_contracts=contracts,
                **{key: value for key, value in inputs.items() if key != "source_contracts"},
            )

        rows = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in rows if row["source"] == "synthetic_camera")
        del camera["survey_supported_absence_rule_id"]
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=rows,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

        bundle = load_decision_bundle()
        bundle["policies"]["pseudoabsence"]["thylogale_generation"] = "enabled"
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=bundle,
                **inputs,
            )

    def test_sensitive_camera_fields_and_finer_resolution_fail_closed(self) -> None:
        inputs = self.valid_inputs()
        for field, value in (("site_id", "SYN_SITE"), ("deployment_timing", "synthetic"), ("current_activity", "synthetic")):
            rows = copy.deepcopy(inputs["source_rows"])
            camera = next(row for row in rows if row["source"] == "synthetic_camera")
            camera[field] = value
            with self.assertRaises(ValidationError):
                dsdm_phase1.build_normalized_source_row_gate_summary(
                    run_id="syn_run_goal_009",
                    decision_bundle=load_decision_bundle(),
                    source_rows=rows,
                    **{key: value for key, value in inputs.items() if key != "source_rows"},
                )

        rows = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in rows if row["source"] == "synthetic_camera")
        camera["camera_resolution_degree"] = 0.001
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=rows,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

    def test_camera_presence_privacy_and_source_identity_fail_closed(self) -> None:
        inputs = self.valid_inputs()
        camera_template = next(row for row in inputs["source_rows"] if row["source_type"] == "camera_trap")
        presence = copy.deepcopy(camera_template)
        presence["pa"] = 1
        presence["pa_type"] = "presence"
        presence.pop("survey_supported_absence_rule_id", None)
        presence.pop("absence_basis", None)
        presence["site_id"] = "SYN_SITE"
        rows = [row for row in inputs["source_rows"] if row is not camera_template] + [presence]
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=rows,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

        ordinary_coords = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in ordinary_coords if row["source_type"] == "camera_trap")
        camera["longitude"] = 100.0
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=ordinary_coords,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

        wrong_type = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in wrong_type if row["source_type"] == "camera_trap")
        camera["source_type"] = "ala_occurrence"
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=wrong_type,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

        wrong_name = copy.deepcopy(inputs["source_rows"])
        camera = next(row for row in wrong_name if row["source_type"] == "camera_trap")
        camera["source"] = "synthetic_not_camera"
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=wrong_name,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )

    def test_actual_thylogale_pseudoabsence_row_is_rejected(self) -> None:
        inputs = self.valid_inputs()
        rows = copy.deepcopy(inputs["source_rows"])
        pseudo = next(row for row in rows if row["pa_type"] == "pseudoabsence")
        pseudo["species_id"] = "thylogale_billardierii"
        with self.assertRaises(ValidationError) as caught:
            dsdm_phase1.build_normalized_source_row_gate_summary(
                run_id="syn_run_goal_009",
                decision_bundle=load_decision_bundle(),
                source_rows=rows,
                **{key: value for key, value in inputs.items() if key != "source_rows"},
            )
        self.assertIn("Thylogale pseudoabsence", str(caught.exception))


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
            ["P1-D008:camera_source_staging"],
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
        self.assertIsNone(bundle["operational_prerequisites"][0]["exact_local_source_path"])

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
            {"thylogale_billardierii": ["CBI"], "notamacropus_rufogriseus": ["CI", "THI", "HI"], "macropus_giganteus": ["KI", "FI", "CBI", "CI", "HI", "BI"], "trichosurus_vulpecula": ["CBI", "CI", "HI"], "pseudocheirus_peregrinus": ["CBI", "CI"], "vombatus_ursinus": ["KI", "CI", "THI", "HI", "BI"], "sarcophilus_harrisii": ["KI", "FI", "CBI", "CI", "THI", "HI", "BI"], "dasyurus_maculatus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI", "BI"], "dasyurus_viverrinus": ["KI", "FI", "CBI", "CI", "THI", "HI", "MI"]},
        )
        self.assertEqual(
            matrix["provisional_exclusions"],
            {
                "policy": "suppress_absence_pending_contemporary_status_resolution",
                "species_islands": {
                    "thylogale_billardierii": ["CBI"],
                    "pseudocheirus_peregrinus": ["CBI"],
                },
            },
        )

    def test_live_acquisition_remains_blocked_by_two_prerequisites(self) -> None:
        bundle = self.load_bundle()
        summary = dsdm_phase1.build_phase1_decision_readiness_summary(bundle)

        self.assertEqual(summary["decision_consolidation_status"], "complete")
        self.assertEqual(summary["live_acquisition_status"], "blocked")
        self.assertEqual(len(summary["blocked_prerequisites"]), 1)
        self.assertEqual(
            {item["decision_id"] for item in bundle["operational_prerequisites"]},
            {"P1-D008"},
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
        wrong_status["decisions"][2]["status"] = "resolved_with_prerequisite"
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
        bundle["operational_prerequisites"][0]["exact_local_source_path"] = "data/private-camera.csv"

        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bundle)


class Goal011AuthoritativeResolutionTests(unittest.TestCase):
    def load_bundle(self) -> dict:
        return dsdm_phase1.load_phase1_decision_bundle(DECISION_BUNDLE_PATH)

    def load_candidates(self) -> dict:
        return json.loads(GOAL010_CANDIDATES_PATH.read_text(encoding="utf-8"))

    def test_goal010_candidates_reconcile_with_authoritative_rows(self) -> None:
        bundle = self.load_bundle()
        candidates = self.load_candidates()
        result = validate_ala_resolution_candidates(bundle, candidates)
        self.assertEqual(result["species_count"], 9)
        self.assertEqual(result["approved_aliases"], {"notamacropus_rufogriseus": ["Macropus rufogriseus"]})

    def test_schema_resolution_and_sole_camera_blocker(self) -> None:
        bundle = self.load_bundle()
        summary = dsdm_phase1.build_phase1_decision_readiness_summary(bundle)
        self.assertEqual(bundle["schema_version"], "1.1")
        self.assertEqual(summary["ala_resolution_status"], "resolved")
        self.assertEqual(summary["blocked_prerequisites"], ["P1-D008:camera_source_staging"])
        self.assertEqual(bundle["decisions"][2]["status"], "resolved")
        self.assertEqual([item["decision_id"] for item in bundle["operational_prerequisites"]], ["P1-D008"])

    def test_structured_subtaxon_policy_and_resolution_provenance(self) -> None:
        policy = self.load_bundle()["policies"]["species"]["ala_resolution"]
        self.assertEqual(policy["status"], "resolved")
        self.assertEqual(policy["approval_date"], "2026-07-23")
        self.assertEqual(policy["canonical_query_rank"], "species")
        self.assertEqual(policy["synonym_normalization"], "in_scope")
        self.assertEqual(policy["accepted_descendants"], "in_scope")
        self.assertTrue(policy["pre_acquisition_scope_assertion_required"])
        self.assertEqual(policy["expansion_failure_fallback"], "explicit_parent_plus_required_accepted_child_ids")
        self.assertEqual(policy["taxon_identity_retention"], {"submitted": True, "matched": True, "accepted": True, "rank": True})
        self.assertEqual(policy["subtaxon_policy"]["macropus_giganteus"]["accepted_parent_species_ref"], "macropus_giganteus")
        self.assertEqual(policy["subtaxon_policy"]["macropus_giganteus"]["name_concept_id"], "https://biodiversity.org.au/afd/taxa/6cfeb6de-600b-425e-9e8d-3cea25f8ef84")
        self.assertEqual(
            [child["concept_id"] for child in policy["subtaxon_policy"]["vombatus_ursinus"]["accepted_child_concepts"]],
            [
                "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7",
                "https://biodiversity.org.au/afd/taxa/3e53b354-2b48-4a2a-af29-acd8ecdfe1e6",
                "https://biodiversity.org.au/afd/taxa/76b2b77b-6092-47dd-8de1-00e504b1e383",
            ],
        )
        self.assertEqual(len(policy["subtaxon_policy"]["vombatus_ursinus"]["accepted_child_concepts"]), 3)

    def test_resolved_mocked_ala_intent_contains_nine_queries(self) -> None:
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        manifest = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_goal_011", decision_bundle=self.load_bundle(), **inputs
        )
        ala = next(item for item in manifest["requests"] if item["source_type"] == "ala_occurrence")
        self.assertEqual(ala["intent"]["query_resolution_status"], "resolved")
        self.assertEqual(len(ala["intent"]["species_queries"]), 9)
        self.assertEqual(ala["intent"]["subtaxon_policy"], self.load_bundle()["policies"]["species"]["ala_resolution"]["subtaxon_policy"])
        self.assertEqual(manifest["blocked_prerequisites"], ["P1-D008:camera_source_staging"])
        camera = next(item for item in manifest["requests"] if item["source_type"] == "camera_trap")
        self.assertEqual(camera["intent"]["authority_status"], "blocked_pending_P1-D008")

    def test_goal010_stored_evidence_validates_against_updated_bundle(self) -> None:
        from dsdm_phase1.ala_taxon_resolution import validate_evidence_package

        result = validate_evidence_package(GOAL010_PACKAGE_PATH, bundle=self.load_bundle())
        self.assertEqual(result["recommendable_count"], 9)

    def test_resolution_mutations_fail_closed(self) -> None:
        mutations = [
            ("missing_concept", lambda b: b["species"][0].update({"ala_taxon_concept_id": None})),
            ("duplicate_concept", lambda b: b["species"][1].update({"ala_taxon_concept_id": b["species"][0]["ala_taxon_concept_id"]})),
            ("malformed_concept", lambda b: b["species"][0].update({"ala_taxon_concept_id": "not-an-afd-id"})),
            ("swapped_concept", lambda b: b["species"][0].update({"ala_taxon_concept_id": b["species"][1]["ala_taxon_concept_id"]})),
            ("unique_forged_uuid", lambda b: b["species"][0].update({"ala_taxon_concept_id": "https://biodiversity.org.au/afd/taxa/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})),
            ("unapproved_alias", lambda b: b["species"][0]["historical_aliases"].append("Invented alias")),
            ("bad_pointer", lambda b: b["policies"]["species"]["ala_resolution"].update({"evidence_package": "wrong"})),
            ("bad_approval", lambda b: b["policies"]["species"]["ala_resolution"].update({"approval_date": "2026-07-22"})),
            ("synonym_scope_disabled", lambda b: b["policies"]["species"]["ala_resolution"].update({"synonym_normalization": "out_of_scope"})),
            ("scope_disabled", lambda b: b["policies"]["species"]["ala_resolution"].update({"accepted_descendants": "out_of_scope"})),
            ("missing_assertion", lambda b: b["policies"]["species"]["ala_resolution"].pop("pre_acquisition_scope_assertion_required")),
            ("missing_fallback", lambda b: b["policies"]["species"]["ala_resolution"].pop("expansion_failure_fallback")),
            ("missing_identity_retention", lambda b: b["policies"]["species"]["ala_resolution"].pop("taxon_identity_retention")),
            ("p1d003_reverted", lambda b: b["decisions"][2].update({"status": "resolved_with_prerequisite"})),
            ("extra_camera_prereq", lambda b: b["operational_prerequisites"].append({"decision_id": "P1-D009"})),
            ("wrong_macropus_name_id", lambda b: b["policies"]["species"]["ala_resolution"]["subtaxon_policy"]["macropus_giganteus"].update({"name_concept_id": "https://biodiversity.org.au/afd/taxa/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})),
            ("wrong_vombatus_child_id", lambda b: b["policies"]["species"]["ala_resolution"]["subtaxon_policy"]["vombatus_ursinus"]["accepted_child_concepts"][0].update({"concept_id": "https://biodiversity.org.au/afd/taxa/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                bundle = self.load_bundle()
                mutate(bundle)
                with self.assertRaises(ValidationError):
                    dsdm_phase1.validate_phase1_decision_bundle(bundle)

    def test_two_way_concept_swap_and_request_builder_fail_closed(self) -> None:
        bundle = self.load_bundle()
        first, second = bundle["species"][0], bundle["species"][1]
        first_id, second_id = first["ala_taxon_concept_id"], second["ala_taxon_concept_id"]
        first["ala_taxon_concept_id"], second["ala_taxon_concept_id"] = second_id, first_id
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bundle)
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_goal_011", decision_bundle=bundle, **inputs
            )

    def test_unique_forged_uuid_and_request_builder_fail_closed(self) -> None:
        bundle = self.load_bundle()
        bundle["species"][0]["ala_taxon_concept_id"] = (
            "https://biodiversity.org.au/afd/taxa/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )
        with self.assertRaises(ValidationError):
            dsdm_phase1.validate_phase1_decision_bundle(bundle)
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        with self.assertRaises(ValidationError):
            dsdm_phase1.build_mocked_acquisition_request_manifest(
                run_id="syn_goal_011", decision_bundle=bundle, **inputs
            )

    def test_scope_plan_omission_fails_closed(self) -> None:
        bundle = self.load_bundle()
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        manifest = dsdm_phase1.build_mocked_acquisition_request_manifest(
            run_id="syn_goal_011", decision_bundle=bundle, **inputs
        )
        intent = next(item for item in manifest["requests"] if item["source_type"] == "ala_occurrence")["intent"]
        del intent["subtaxon_policy"]
        with self.assertRaises(ValidationError):
            _validate_ala_request_intent(intent, bundle)

    def test_ala_identity_block_is_required_and_non_ala_rows_cannot_leak_it(self) -> None:
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        rows = load_fixture("source_rows.json")["rows"]
        for label, mutate in [
            ("missing", lambda broken: broken[0].pop("ala_taxon_identity")),
            ("invalid_rank", lambda broken: broken[0]["ala_taxon_identity"].update({"accepted_rank": "variety"})),
            ("camera_leak", lambda broken: broken[1].update({"ala_taxon_identity": copy.deepcopy(broken[0]["ala_taxon_identity"])})),
            ("pseudoabsence_leak", lambda broken: broken[2].update({"ala_taxon_identity": copy.deepcopy(broken[0]["ala_taxon_identity"])})),
        ]:
            with self.subTest(label=label):
                broken = copy.deepcopy(rows)
                mutate(broken)
                with self.assertRaises(ValidationError):
                    dsdm_phase1.build_normalized_source_row_gate_summary(
                        run_id="syn_goal_011", decision_bundle=self.load_bundle(), source_rows=broken, **inputs
                    )

    def test_distinct_ala_identity_survives_normalized_summary(self) -> None:
        inputs = {
            "species_contract": load_fixture("species_contract_resolved.json"),
            "source_contracts": load_fixture("source_contracts_resolved.json"),
        }
        summary = dsdm_phase1.build_normalized_source_row_gate_summary(
            run_id="syn_goal_011", decision_bundle=self.load_bundle(),
            source_rows=load_fixture("source_rows.json")["rows"], **inputs
        )
        identity = summary["rows"][0]["ala_taxon_identity"]
        self.assertEqual(identity["accepted_rank"], "subspecies")
        self.assertEqual(identity["accepted_name"], "Fictomys contracta minor")
        self.assertNotEqual(identity["accepted_name"], summary["rows"][0]["scientific_name"])


if __name__ == "__main__":
    unittest.main()
