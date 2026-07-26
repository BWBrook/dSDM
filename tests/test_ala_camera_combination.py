import copy
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import dsdm_phase1.ala_camera_combination as combination
from dsdm_phase1 import camera_spatial_normalization as camera


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/ala_camera_combination_plan.json"
EVIDENCE = ROOT / "evidence/ala_camera_combination/2026-07-26"
OUTPUT = (
    ROOT
    / "data/processed/combined/goal020-ala-camera-combination/2026-07-26"
)


def ala_row(cell: str, lon: str = "147.005", lat: str = "-42.005"):
    return {
        "species_id": "species_a",
        "grid_cell_id": cell,
        "centroid_lon": lon,
        "centroid_lat": lat,
        "presence": "1",
        "source_row_count": "2",
        "unique_provider_record_count": "2",
        "resource_count": "1",
        "dataset_count": "1",
        "unknown_uncertainty_count": "0",
        "qa_flag_count": "0",
        "low_cell_certainty_only": "false",
    }


def camera_row(
    cell: str,
    pa_type: str,
    *,
    lon: str = "147.005",
    lat: str = "-42.005",
    internal_conflict: str = "false",
):
    presence = pa_type == "presence"
    return {
        "species_id": "species_a",
        "grid_cell_id": cell,
        "centroid_lon": lon,
        "centroid_lat": lat,
        "pa": "1" if presence else "0",
        "pa_type": pa_type,
        "survey_supported_absence_rule_id": "" if presence else "P1-D009",
        "site_count": "1",
        "presence_site_count": "1" if presence else "0",
        "survey_supported_absence_site_count": "0" if presence else "1",
        "positive_source_row_count": "1" if presence else "0",
        "source_conflict": internal_conflict,
    }


class AlaCameraCombinationTests(unittest.TestCase):
    def test_plan_freezes_exact_bindings_oracle_and_stop_boundary(self):
        plan = json.loads(PLAN.read_text())
        result = combination.validate_plan(plan)

        self.assertEqual(result["species_count"], 8)
        self.assertEqual(
            {role: value["sha256"] for role, value in plan["bindings"].items()},
            combination.EXPECTED_BINDING_HASHES,
        )
        self.assertEqual(plan["expected_oracle"]["overall"], combination.EXPECTED_OVERALL)
        self.assertEqual(
            plan["stopped_before"],
            ["pseudoabsence", "predictors", "partitions", "mapping", "modelling"],
        )

    def test_synthetic_truth_table_preserves_null_and_conflict_provenance(self):
        ala_rows = [ala_row("g_1"), ala_row("g_3"), ala_row("g_4")]
        camera_rows = [
            camera_row("g_2", "presence", lon="147.015"),
            camera_row("g_3", "presence", internal_conflict="true"),
            camera_row("g_4", "survey_supported_absence"),
            camera_row("g_5", "survey_supported_absence", lon="147.025"),
        ]

        rows = combination.combine_rows(
            ala_rows, camera_rows, active_species=("species_a",)
        )

        self.assertEqual(
            [row["source_combination"] for row in rows],
            [
                "ala_only_presence",
                "camera_only_presence",
                "both_presence",
                "ala_overrides_camera_absence",
                "camera_absence_retained",
            ],
        )
        self.assertEqual(rows[0]["camera_pa"], "")
        self.assertEqual(rows[1]["ala_presence"], "")
        self.assertEqual(rows[2]["camera_internal_conflict"], "true")
        self.assertEqual(rows[2]["cross_source_conflict"], "false")
        self.assertEqual(rows[3]["cross_source_conflict"], "true")
        self.assertEqual(rows[3]["survey_supported_absence_rule_id"], "")
        self.assertEqual(rows[4]["survey_supported_absence_rule_id"], "P1-D009")

    def test_overlap_centroid_mismatch_and_duplicate_keys_fail_closed(self):
        with self.assertRaisesRegex(
            combination.CombinationError, "overlap_centroid_mismatch"
        ):
            combination.combine_rows(
                [ala_row("g_1")],
                [camera_row("g_1", "presence", lon="147.015")],
                active_species=("species_a",),
            )
        with self.assertRaisesRegex(
            combination.CombinationError, "duplicate_species_grid_key"
        ):
            combination.combine_rows(
                [ala_row("g_1"), ala_row("g_1")],
                [],
                active_species=("species_a",),
            )

    def test_production_tracked_and_full_replay_match_frozen_oracle(self):
        tracked = combination.validate_evidence(PLAN, EVIDENCE)
        full = combination.validate_evidence(PLAN, EVIDENCE, full=True)

        self.assertTrue(tracked["private_replay_required"])
        self.assertFalse(full["private_replay_required"])
        self.assertEqual(full["output_rows"], 12868)
        summary = json.loads((EVIDENCE / "combination_summary.json").read_text())
        self.assertEqual(summary["overall"], combination.EXPECTED_OVERALL)
        self.assertEqual(summary["by_species"], combination.EXPECTED_BY_SPECIES)
        with (OUTPUT / combination.OUTPUT_FILE).open(
            newline="", encoding="utf-8"
        ) as stream:
            observed_species = {
                row["species_id"] for row in csv.DictReader(stream)
            }
        self.assertNotIn(
            combination.EXCLUDED_SPECIES,
            observed_species,
        )

    def test_private_output_has_exact_footprint_and_is_ignored(self):
        self.assertEqual(
            {path.name for path in OUTPUT.iterdir()},
            {combination.OUTPUT_FILE},
        )
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", OUTPUT],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_full_replay_detects_private_output_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "output"
            shutil.copytree(OUTPUT, copied)
            path = copied / combination.OUTPUT_FILE
            path.write_bytes(path.read_bytes() + b"tamper\n")
            with self.assertRaisesRegex(
                combination.CombinationError, "output_semantic_replay_failure"
            ):
                combination.validate_evidence(
                    PLAN, EVIDENCE, full=True, output_dir=copied
                )

    def test_nested_tracked_evidence_and_private_payloads_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "evidence"
            shutil.copytree(EVIDENCE, copied)
            (copied / "nested").mkdir()
            with self.assertRaisesRegex(
                combination.CombinationError, "evidence_footprint_drift"
            ):
                combination.validate_evidence(PLAN, copied)
        for payload in (
            {"private_value": "g_1470050_-420050"},
            {"private_value": "/Users/private/camera.csv"},
            {"private_value": "147.005, -42.005"},
            {"site_id": "private"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(
                    combination.CombinationError,
                    "tracked_evidence_privacy_failure",
                ):
                    combination.assert_evidence_privacy(
                        {"payload.json": payload}
                    )

    def test_island_gate_detects_excluded_presence_without_deleting_it(self):
        plan = json.loads(PLAN.read_text())
        root = PLAN.resolve().parents[1]
        decision = json.loads(
            (root / plan["bindings"]["decision_bundle"]["path"]).read_text()
        )
        islands_path = root / plan["bindings"]["offshore_islands"]["path"]
        king = camera._load_islands(islands_path)["KI"].representative_point()
        row = {
            "species_id": "vombatus_ursinus",
            "centroid_lon": str(king.x),
            "centroid_lat": str(king.y),
            "pa_type": "presence",
        }

        self.assertEqual(
            combination._matrix_conflicts([row], decision, islands_path), 1
        )

    def test_tracked_validation_rejects_full_inputs_without_full_flag(self):
        with self.assertRaisesRegex(
            combination.CombinationError, "full_replay_flag_required"
        ):
            combination.validate_evidence(PLAN, EVIDENCE, output_dir=OUTPUT)

    def test_plan_and_evidence_shape_drift_fail_closed(self):
        plan = json.loads(PLAN.read_text())
        drift = copy.deepcopy(plan)
        drift["combination_contract"]["accepted_presence_dominates"] = False
        with self.assertRaisesRegex(
            combination.CombinationError, "combination_contract_drift"
        ):
            combination.validate_plan(drift)

        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "evidence"
            shutil.copytree(EVIDENCE, copied)
            summary_path = copied / "combination_summary.json"
            summary = json.loads(summary_path.read_text())
            summary["overall"]["output_rows"] -= 1
            summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
            manifest = json.loads((copied / "manifest.json").read_text())
            entry = next(
                item
                for item in manifest["files"]
                if item["path"] == "combination_summary.json"
            )
            entry["bytes"] = summary_path.stat().st_size
            entry["sha256"] = combination.sha256(summary_path)
            (copied / "manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
            with self.assertRaisesRegex(
                combination.CombinationError, "combination_summary_shape_drift"
            ):
                combination.validate_evidence(PLAN, copied)


if __name__ == "__main__":
    unittest.main()
