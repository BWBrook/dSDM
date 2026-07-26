import copy
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import dsdm_phase1.pseudoabsence_derivation as derivation


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/pseudoabsence_derivation_plan.json"
EVIDENCE = ROOT / "evidence/pseudoabsence_derivation/2026-07-26"
OUTPUT = (
    ROOT
    / "data/processed/response/goal021-pseudoabsence-derivation/2026-07-26"
)
EXPECTED_RESPONSE_FIELDS = (
    "species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pa", "pa_type",
    "survey_supported_absence_rule_id", "source_combination", "cross_source_conflict",
    "ala_presence", "ala_source_row_count", "ala_unique_provider_record_count", "ala_resource_count",
    "ala_dataset_count", "ala_unknown_uncertainty_count", "ala_qa_flag_count",
    "ala_low_cell_certainty_only", "camera_evidence", "camera_pa", "camera_pa_type",
    "camera_survey_supported_absence_rule_id", "camera_site_count", "camera_presence_site_count",
    "camera_survey_supported_absence_site_count", "camera_positive_source_row_count", "camera_internal_conflict",
    "response_origin", "pseudoabsence_rule_id", "pseudoabsence_support_species_count", "pseudoabsence_support_species_ids",
    "nearest_target_presence_grid_cell_id", "nearest_target_presence_source_combination",
    "nearest_target_presence_distance_m", "distance_crs",
)
EXPECTED_AUDIT_FIELDS = (
    "species_id", "grid_cell_id", "centroid_lon", "centroid_lat", "pseudoabsence_support_species_count",
    "pseudoabsence_support_species_ids", "target_pa_type", "target_source_combination", "target_camera_pa_type",
    "island_code", "island_exclusion_rule_id", "nearest_target_presence_grid_cell_id",
    "nearest_target_presence_source_combination", "nearest_target_presence_distance_m", "distance_crs",
    "distance_eligible", "disposition",
)


def goal020_row(
    species_id,
    grid_cell_id,
    *,
    lon="147.005",
    lat="-42.005",
    pa_type="presence",
    ala_presence="1",
    source_combination="ala_only_presence",
):
    row = {field: "" for field in derivation.GOAL020_FIELDS}
    presence = pa_type == "presence"
    row.update(
        {
            "species_id": species_id,
            "grid_cell_id": grid_cell_id,
            "centroid_lon": lon,
            "centroid_lat": lat,
            "pa": "1" if presence else "0",
            "pa_type": pa_type,
            "survey_supported_absence_rule_id": (
                "" if presence else derivation.SURVEY_ABSENCE_RULE_ID
            ),
            "source_combination": source_combination,
            "cross_source_conflict": "false",
            "ala_presence": ala_presence,
        }
    )
    if ala_presence == "1":
        row.update(
            {
                "ala_source_row_count": "1",
                "ala_unique_provider_record_count": "1",
                "ala_resource_count": "1",
                "ala_dataset_count": "1",
                "ala_unknown_uncertainty_count": "0",
                "ala_qa_flag_count": "0",
                "ala_low_cell_certainty_only": "false",
            }
        )
    if source_combination in {
        "camera_only_presence",
        "both_presence",
        "ala_overrides_camera_absence",
        "camera_absence_retained",
    }:
        camera_presence = source_combination in {
            "camera_only_presence",
            "both_presence",
        }
        row.update(
            {
                "camera_evidence": (
                    "presence" if camera_presence else "survey_supported_absence"
                ),
                "camera_pa": "1" if camera_presence else "0",
                "camera_pa_type": (
                    "presence" if camera_presence else "survey_supported_absence"
                ),
                "camera_survey_supported_absence_rule_id": (
                    "" if camera_presence else derivation.SURVEY_ABSENCE_RULE_ID
                ),
                "camera_site_count": "1",
                "camera_presence_site_count": "1" if camera_presence else "0",
                "camera_survey_supported_absence_site_count": (
                    "0" if camera_presence else "1"
                ),
                "camera_positive_source_row_count": "1" if camera_presence else "0",
                "camera_internal_conflict": "false",
            }
        )
    return row


def support_rows(cell, *, lon="147.005", lat="-42.005"):
    return [
        goal020_row(
            "thylogale_billardierii", cell, lon=lon, lat=lat
        ),
        goal020_row(
            "trichosurus_vulpecula", cell, lon=lon, lat=lat
        ),
        goal020_row(
            "pseudocheirus_peregrinus", cell, lon=lon, lat=lat
        ),
    ]


def sorted_rows(rows):
    return sorted(rows, key=lambda row: (row["species_id"], row["grid_cell_id"]))


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


class PseudoabsenceDerivationTests(unittest.TestCase):
    def test_plan_freezes_bindings_semantics_oracles_privacy_and_stop_boundary(self):
        plan = json.loads(PLAN.read_text())
        result = derivation.validate_plan(plan)

        self.assertEqual(result["eligible_target_count"], 7)
        self.assertEqual(
            {role: value["sha256"] for role, value in plan["bindings"].items()},
            derivation.EXPECTED_BINDING_HASHES,
        )
        self.assertEqual(plan["derivation_contract"], derivation.DERIVATION_CONTRACT)
        self.assertEqual(plan["expected_oracle"], derivation.EXPECTED_ORACLE)
        self.assertEqual(plan["outputs"]["response_layer_schema"], list(EXPECTED_RESPONSE_FIELDS))
        self.assertEqual(plan["outputs"]["candidate_audit_schema"], list(EXPECTED_AUDIT_FIELDS))
        self.assertEqual(list(derivation.RESPONSE_FIELDS), list(EXPECTED_RESPONSE_FIELDS))
        self.assertEqual(list(derivation.AUDIT_FIELDS), list(EXPECTED_AUDIT_FIELDS))
        self.assertEqual(plan["privacy"], derivation.PLAN_PRIVACY)
        self.assertEqual(
            plan["stopped_before"],
            [
                "thinning",
                "weights",
                "balancing",
                "predictors",
                "partitions",
                "mapping",
                "modelling",
            ],
        )

    def test_thylogale_supports_other_targets_but_is_never_a_target(self):
        target = "notamacropus_rufogriseus"
        candidate = "g_1470050_-420050"
        reference = "g_1471050_-420050"
        rows = support_rows(candidate)
        rows.append(
            goal020_row(
                target,
                reference,
                lon="147.105",
                source_combination="camera_only_presence",
                ala_presence="",
            )
        )

        result = derivation.derive_response_layer(
            sorted_rows(rows),
            eligible_targets=(target,),
            island_exclusions={target: set()},
            cell_island_codes={},
            projected_xy={candidate: (0.0, 0.0), reference: (6000.0, 0.0)},
        )

        self.assertEqual(len(result["audit_rows"]), 1)
        audit = result["audit_rows"][0]
        self.assertEqual(audit["disposition"], "pseudoabsence")
        self.assertEqual(audit["pseudoabsence_support_species_count"], "3")
        self.assertIn(
            "thylogale_billardierii",
            audit["pseudoabsence_support_species_ids"].split("|"),
        )
        self.assertNotIn(
            "thylogale_billardierii",
            {row["species_id"] for row in result["audit_rows"]},
        )

    def test_camera_precedence_and_island_suppression_are_mutually_exclusive(self):
        target = "notamacropus_rufogriseus"
        camera_cell = "g_1470050_-420050"
        island_cell = "g_1470150_-420050"
        reference = "g_1471050_-420050"
        rows = support_rows(camera_cell)
        rows.extend(support_rows(island_cell, lon="147.015"))
        rows.extend(
            [
                goal020_row(
                    target,
                    camera_cell,
                    pa_type="survey_supported_absence",
                    ala_presence="",
                    source_combination="camera_absence_retained",
                ),
                goal020_row(
                    target,
                    reference,
                    lon="147.105",
                    source_combination="camera_only_presence",
                    ala_presence="",
                ),
            ]
        )

        result = derivation.derive_response_layer(
            sorted_rows(rows),
            eligible_targets=(target,),
            island_exclusions={target: {"BI"}},
            cell_island_codes={island_cell: "BI"},
            projected_xy={
                camera_cell: (0.0, 0.0),
                island_cell: (1000.0, 0.0),
                reference: (10000.0, 0.0),
            },
        )

        dispositions = {
            row["grid_cell_id"]: row["disposition"]
            for row in result["audit_rows"]
        }
        self.assertEqual(
            dispositions,
            {
                camera_cell: "camera_survey_supported_absence",
                island_cell: "island_suppressed",
            },
        )
        self.assertEqual(result["derivation_summary"]["overall"]["pseudoabsence"], 0)

    def test_exact_5000_m_is_inclusive_and_nearest_ties_break_lexically(self):
        target = "notamacropus_rufogriseus"
        candidate = "g_1470050_-420050"
        lexical_first = "g_1469050_-420050"
        lexical_second = "g_1471050_-420050"
        rows = support_rows(candidate)
        rows.extend(
            [
                goal020_row(target, lexical_first, lon="146.905"),
                goal020_row(target, lexical_second, lon="147.105"),
            ]
        )

        result = derivation.derive_response_layer(
            sorted_rows(rows),
            eligible_targets=(target,),
            island_exclusions={target: set()},
            cell_island_codes={},
            projected_xy={
                candidate: (0.0, 0.0),
                lexical_first: (-3000.0, 4000.0),
                lexical_second: (3000.0, 4000.0),
            },
        )

        audit = result["audit_rows"][0]
        self.assertEqual(audit["disposition"], "pseudoabsence")
        self.assertEqual(
            audit["nearest_target_presence_grid_cell_id"], lexical_first
        )
        self.assertEqual(audit["nearest_target_presence_distance_m"], "5000.000000")

    def test_pseudoabsence_provenance_blanks_and_goal020_byte_projection(self):
        target = "notamacropus_rufogriseus"
        candidate = "g_1470050_-420050"
        reference = "g_1471050_-420050"
        rows = sorted_rows(
            support_rows(candidate)
            + [goal020_row(target, reference, lon="147.105")]
        )
        result = derivation.derive_response_layer(
            rows,
            eligible_targets=(target,),
            island_exclusions={target: set()},
            cell_island_codes={},
            projected_xy={candidate: (0.0, 0.0), reference: (6000.0, 0.0)},
        )

        pseudo = next(
            row
            for row in result["response_rows"]
            if row["response_origin"] == "derived_pseudoabsence"
        )
        self.assertEqual(pseudo["pa"], "0")
        self.assertEqual(pseudo["pa_type"], "pseudoabsence")
        self.assertEqual(pseudo["cross_source_conflict"], "false")
        self.assertEqual(
            pseudo["pseudoabsence_rule_id"], derivation.PSEUDOABSENCE_RULE_ID
        )
        for field in derivation.PSEUDOABSENCE_BLANK_GOAL020_FIELDS:
            self.assertEqual(pseudo[field], "", field)
        self.assertEqual(
            derivation.project_goal020_bytes(result["response_rows"]),
            csv_bytes(rows, derivation.GOAL020_FIELDS),
        )

    def test_duplicates_schema_drift_privacy_and_publication_fail_closed(self):
        row = goal020_row(
            "notamacropus_rufogriseus", "g_1470050_-420050"
        )
        with self.assertRaisesRegex(
            derivation.PseudoabsenceError, "duplicate_species_grid_key"
        ):
            derivation.validate_goal020_rows(
                [row, copy.deepcopy(row)],
                expected_rows=None,
                require_all_species=False,
                require_canonical_grid=False,
            )
        drift = dict(row)
        drift.pop("camera_internal_conflict")
        with self.assertRaisesRegex(
            derivation.PseudoabsenceError, "goal020_row_shape_drift"
        ):
            derivation.validate_goal020_rows(
                [drift],
                expected_rows=None,
                require_all_species=False,
                require_canonical_grid=False,
            )
        for payload in (
            {"grid_cell_id": "redacted"},
            {"private_value": "g_1470050_-420050"},
            {"private_value": "/Users/private/response_layer.csv"},
            {"private_value": "147.005, -42.005"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(
                    derivation.PseudoabsenceError,
                    "tracked_evidence_privacy_failure",
                ):
                    derivation.assert_evidence_privacy({"test.json": payload})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage_output = root / "stage-output"
            stage_output.mkdir()
            (stage_output / "marker").write_text("stage")
            missing_stage_evidence = root / "missing-stage-evidence"
            output = root / "output"
            evidence = root / "evidence"
            with self.assertRaisesRegex(
                derivation.PseudoabsenceError, "evidence_publication_failure"
            ):
                derivation._publish_staged(
                    stage_output, missing_stage_evidence, output, evidence
                )
            self.assertFalse(output.exists())
            self.assertFalse(evidence.exists())

            output.mkdir()
            marker = output / "preserve"
            marker.write_text("existing")
            with self.assertRaisesRegex(
                derivation.PseudoabsenceError, "publication_destination_exists"
            ):
                derivation._publish_staged(
                    root / "unused-output",
                    root / "unused-evidence",
                    output,
                    evidence,
                )
            self.assertEqual(marker.read_text(), "existing")

    def test_production_replay_matches_frozen_oracle_and_private_hashes(self):
        tracked = derivation.validate_evidence(PLAN, EVIDENCE)
        full = derivation.validate_evidence(PLAN, EVIDENCE, full=True)

        self.assertTrue(tracked["private_replay_required"])
        self.assertFalse(full["private_replay_required"])
        self.assertEqual(full["candidate_rows"], 2316)
        self.assertEqual(full["pseudoabsence_rows"], 587)
        summary = json.loads((EVIDENCE / "derivation_summary.json").read_text())
        self.assertEqual(summary["funnel"], derivation.EXPECTED_FUNNEL)
        self.assertEqual(
            summary["final_response_by_species"],
            derivation.EXPECTED_FINAL_RESPONSE_BY_SPECIES,
        )
        self.assertEqual(
            summary["support_distribution"], {"3": 385, "4": 128, "5": 54, "6": 20}
        )

        with (OUTPUT / derivation.AUDIT_FILE).open(
            newline="", encoding="utf-8"
        ) as stream:
            audit = list(csv.DictReader(stream))
        self.assertEqual(len(audit), 2316)
        self.assertEqual(
            Counter(row["disposition"] for row in audit),
            Counter(
                {
                    "target_presence": 733,
                    "camera_survey_supported_absence": 17,
                    "island_suppressed": 79,
                    "distance_rejected": 900,
                    "pseudoabsence": 587,
                }
            ),
        )
        accepted = [
            row for row in audit if row["disposition"] == "pseudoabsence"
        ]
        key_payload = "".join(
            f"{row['species_id']},{row['grid_cell_id']}\n"
            for row in accepted
        ).encode()
        self.assertEqual(
            hashlib.sha256(key_payload).hexdigest(),
            derivation.PORTABLE_ACCEPTED_KEY_SHA256,
        )

    def test_private_and_tracked_footprints_tamper_and_shape_drift(self):
        self.assertEqual(
            {path.name for path in OUTPUT.iterdir()},
            {derivation.AUDIT_FILE, derivation.RESPONSE_FILE},
        )
        self.assertEqual(
            {path.name for path in EVIDENCE.iterdir()},
            set(derivation.EVIDENCE_FILES),
        )
        self.assertTrue(
            all(path.is_file() and not path.is_symlink() for path in OUTPUT.iterdir())
        )
        self.assertTrue(
            all(path.is_file() and not path.is_symlink() for path in EVIDENCE.iterdir())
        )
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", OUTPUT],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)

        with tempfile.TemporaryDirectory() as directory:
            copied_output = Path(directory) / "output"
            shutil.copytree(OUTPUT, copied_output)
            response = copied_output / derivation.RESPONSE_FILE
            response.write_bytes(response.read_bytes() + b"tamper\n")
            with self.assertRaisesRegex(
                derivation.PseudoabsenceError, "output_semantic_replay_failure"
            ):
                derivation.validate_evidence(
                    PLAN, EVIDENCE, full=True, output_dir=copied_output
                )

        with tempfile.TemporaryDirectory() as directory:
            copied_evidence = Path(directory) / "evidence"
            shutil.copytree(EVIDENCE, copied_evidence)
            (copied_evidence / "nested").mkdir()
            with self.assertRaisesRegex(
                derivation.PseudoabsenceError, "evidence_footprint_drift"
            ):
                derivation.validate_evidence(PLAN, copied_evidence)

        plan = json.loads(PLAN.read_text())
        plan["derivation_contract"]["minimum_distance_m"] = 4999
        with self.assertRaisesRegex(
            derivation.PseudoabsenceError, "derivation_contract_drift"
        ):
            derivation.validate_plan(plan)

    def test_provenance_and_evidence_payloads_are_explicit(self):
        with (OUTPUT / derivation.AUDIT_FILE).open(newline="", encoding="utf-8") as stream:
            audit = list(csv.DictReader(stream))
        self.assertTrue(all(row["centroid_lon"] and row["centroid_lat"] for row in audit))
        self.assertTrue(all(row["distance_crs"] == "EPSG:7855" for row in audit))
        with (OUTPUT / derivation.RESPONSE_FILE).open(newline="", encoding="utf-8") as stream:
            response = list(csv.DictReader(stream))
        pseudo = [row for row in response if row["response_origin"] == "derived_pseudoabsence"]
        self.assertEqual(len(pseudo), 587)
        self.assertTrue(all(row["pseudoabsence_support_species_count"] in {"3", "4", "5", "6"} for row in pseudo))
        self.assertTrue(all(row["distance_crs"] == "EPSG:7855" and row["nearest_target_presence_source_combination"] for row in pseudo))
        summary = json.loads((EVIDENCE / "derivation_summary.json").read_text())
        self.assertEqual(summary["per_species"]["thylogale_billardierii"]["pseudoabsence"], 0)
        spatial = json.loads((EVIDENCE / "spatial_summary.json").read_text())
        self.assertEqual(spatial["full_distance_preimage_sha256"], derivation.FULL_DISTANCE_PREIMAGE_SHA256)

    def test_tracked_validation_does_not_require_private_output_and_island_hits_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            moved = Path(directory) / "private"
            OUTPUT.rename(moved)
            try:
                result = derivation.validate_evidence(PLAN, EVIDENCE)
                self.assertTrue(result["private_replay_required"])
            finally:
                moved.rename(OUTPUT)
        from shapely.geometry import Polygon, Point
        with self.assertRaisesRegex(derivation.PseudoabsenceError, "multiple_island_hits"):
            derivation._island_code(Point(0, 0), {"A": Polygon([(-1,-1),(1,-1),(1,1),(-1,1)]), "B": Polygon([(-1,-1),(1,-1),(1,1),(-1,1)])})

    def test_refreshed_manifest_semantic_tamper_and_private_ignore_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "evidence"
            shutil.copytree(EVIDENCE, copied)
            summary = copied / "derivation_summary.json"
            payload = json.loads(summary.read_text()); payload["funnel"]["pseudoabsence"] = 586; summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            manifest = json.loads((copied / "manifest.json").read_text())
            entry = next(e for e in manifest["files"] if e["path"] == "derivation_summary.json")
            entry["bytes"] = summary.stat().st_size; entry["sha256"] = hashlib.sha256(summary.read_bytes()).hexdigest()
            (copied / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(derivation.PseudoabsenceError, "output_semantic_replay_failure"):
                derivation.validate_evidence(PLAN, copied, full=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "config").mkdir(); shutil.copy2(PLAN, root / "config/pseudoabsence_derivation_plan.json")
            with self.assertRaisesRegex(derivation.PseudoabsenceError, "private_output_not_ignored"):
                derivation.run_production(root)


if __name__ == "__main__":
    unittest.main()
