import copy
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import dsdm_phase1.camera_spatial_normalization as camera


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/camera_spatial_normalization_plan.json"


class CameraSpatialNormalizationTests(unittest.TestCase):
    def test_source_datetime_uses_day_month_year_with_single_digit_hour(self):
        self.assertEqual(camera._observation_year("31/12/2001 1:02:03"), 2001)

    def test_island_codes_are_read_from_kml_placemark_names(self):
        islands = camera._load_islands(
            ROOT / "temp/data/spatial/offshore_islands.kml"
        )
        self.assertEqual(set(islands), set(camera.ISLAND_CODES))

    def test_plan_freezes_eight_species_without_mutating_goal018(self):
        plan = json.loads(PLAN.read_text())
        result = camera.validate_plan(plan)

        self.assertEqual(result["species_count"], 8)
        self.assertNotIn(
            "macropus_giganteus",
            plan["species_contract"]["active_species_ids"],
        )
        self.assertTrue(
            plan["species_contract"]["excluded_downstream"][
                "prior_goal017_goal018_provenance_retained"
            ]
        )
        self.assertEqual(
            plan["bindings"]["goal018_plan"]["sha256"],
            "516b0bbb089cfcbc6558677ea0f0b4ac2662acb2c79e33308485ae6ff605d75b",
        )

    def test_repeated_coordinates_require_one_cell_and_island_class(self):
        coast = gpd.GeoSeries(
            [Polygon([(146, -43), (149, -43), (149, -40), (146, -40)])],
            crs="EPSG:4326",
        )
        islands = {
            "KI": Polygon(
                [(147.0, -42.02), (147.02, -42.02), (147.02, -42.0), (147.0, -42.0)]
            )
        }
        first = camera.candidate_centroid(147.001, -42.001)
        second = camera.candidate_centroid(147.002, -42.002)
        other = camera.candidate_centroid(147.021, -42.001)
        grid = {
            camera.grid_cell_id(*first): first,
            camera.grid_cell_id(*other): other,
        }

        same = camera.classify_location_rows(
            [(147.001, -42.001), (147.002, -42.002)],
            grid,
            coast,
            islands,
        )
        different = camera.classify_location_rows(
            [(147.001, -42.001), (147.021, -42.001)],
            grid,
            coast,
            islands,
        )

        self.assertEqual(same["state"], "eligible")
        self.assertEqual(different["state"], "ambiguous_site_location")

    def test_island_class_is_retained_when_spatial_gate_excludes_site(self):
        coast = gpd.GeoSeries(
            [Polygon([(146, -43), (146.5, -43), (146.5, -42.5), (146, -42.5)])],
            crs="EPSG:4326",
        )
        islands = {
            "KI": Polygon(
                [(147.0, -42.02), (147.02, -42.02), (147.02, -42.0), (147.0, -42.0)]
            )
        }
        centroid = camera.candidate_centroid(147.001, -42.001)
        result = camera.classify_location_rows(
            [(147.001, -42.001)],
            {camera.grid_cell_id(*centroid): centroid},
            coast,
            islands,
        )

        self.assertEqual(result["state"], "invalid_site_location")
        self.assertEqual(result["island_code"], "KI")

    def test_island_suppression_presence_retention_and_cell_dominance(self):
        sites = {
            "one": {"grid_cell_id": "g_1", "island_code": "KI"},
            "two": {"grid_cell_id": "g_1", "island_code": ""},
        }
        detections = {("one", "a"), ("two", "b")}
        rows, blockers = camera.build_site_species_rows(
            sites,
            detections,
            ("a", "b", "c"),
            {"a": ["KI"], "b": [], "c": ["KI"]},
        )

        self.assertEqual(len(rows), 6)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(
            next(row for row in rows if row["site_id"] == "one" and row["species_id"] == "a")[
                "classification"
            ],
            "presence",
        )
        self.assertEqual(
            next(row for row in rows if row["site_id"] == "one" and row["species_id"] == "c")[
                "classification"
            ],
            "species_island_absence_exclusion",
        )
        collapsed = camera.collapse_grid_evidence(rows)
        self.assertEqual(
            {row["species_id"]: row["pa_type"] for row in collapsed},
            {"a": "presence", "b": "presence", "c": "survey_supported_absence"},
        )

    def test_tracked_evidence_privacy_fails_closed(self):
        safe = {
            "normalization_summary.json": {
                "input_rows": 1,
                "by_species": {"thylogale_billardierii": {"presence_sites": 1}},
            }
        }
        camera.assert_evidence_privacy(safe)
        for key in (
            "site_id",
            "survey",
            "longitude",
            "grid_cell_id",
            "datetime",
            "filename",
            "source_code",
        ):
            with self.subTest(key=key):
                broken = copy.deepcopy(safe)
                broken["normalization_summary.json"][key] = "private"
                with self.assertRaises(camera.CameraNormalizationError):
                    camera.assert_evidence_privacy(broken)

    def test_private_manifest_rejects_path_escape_and_hash_drift(self):
        plan = json.loads(PLAN.read_text())
        with self.assertRaises(camera.CameraNormalizationError):
            camera.validate_private_manifest(
                plan,
                Path("/tmp/private"),
                {
                    "schema_version": "1.0",
                    "files": [
                        {
                            "role": "site_locations",
                            "path": "../private.csv",
                            "bytes": 42687,
                            "data_rows": 1388,
                            "sha256": plan["private_inputs"]["roles"]["site_locations"][
                                "sha256"
                            ],
                            "columns": ["site", "lat", "lon"],
                        }
                    ],
                },
            )

        drift = copy.deepcopy(plan)
        drift["private_inputs"]["roles"]["site_locations"]["sha256"] = "0" * 64
        with patch.object(camera, "sha256", return_value="f" * 64):
            with self.assertRaises(camera.CameraNormalizationError):
                camera.validate_private_manifest(
                    drift,
                    Path("/tmp/private"),
                    {
                        "schema_version": "1.0",
                        "files": [
                            {
                                "role": "site_locations",
                                "path": "private.csv",
                                "bytes": 42687,
                                "data_rows": 1388,
                                "sha256": "f" * 64,
                                "columns": ["site", "lat", "lon"],
                            }
                        ],
                    },
                )

    def test_focal_lookup_ambiguity_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lookup.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["species", "code"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"species": "synthetic one", "code": "focal"},
                        {"species": "synthetic two", "code": "focal"},
                    ]
                )
            with self.assertRaises(camera.CameraNormalizationError):
                camera._load_lookup(path, {"focal"})

    def test_unreferenced_site_is_excluded_before_spatial_acceptance(self):
        self.assertEqual(
            camera.site_disposition(
                {"state": "eligible", "reason": ""},
                has_observations=False,
                in_window_rows=0,
            ),
            ("unreferenced_site", "unreferenced_site"),
        )

    def test_private_output_replay_detects_byte_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            expected = root / "expected"
            actual.mkdir()
            expected.mkdir()
            for name in camera.OUTPUT_FILES:
                (actual / name).write_text("same\n")
                (expected / name).write_text("same\n")
            camera._validate_output_replay(actual, expected)
            (actual / "grid_evidence.csv").write_text("tampered\n")
            with self.assertRaises(camera.CameraNormalizationError):
                camera._validate_output_replay(actual, expected)

    def test_second_directory_publication_failure_rolls_back_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage_output = root / "staged-output"
            stage_evidence = root / "staged-evidence"
            output = root / "output"
            evidence = root / "evidence"
            stage_output.mkdir()
            stage_evidence.mkdir()
            original_rename = Path.rename

            def fail_evidence_rename(path, target):
                if path.name == "staged-evidence":
                    raise OSError("synthetic")
                return original_rename(path, target)

            with patch.object(Path, "rename", new=fail_evidence_rename):
                with self.assertRaises(camera.CameraNormalizationError):
                    camera._publish_staged(
                        stage_output, stage_evidence, output, evidence
                    )
            self.assertFalse(output.exists())
            self.assertFalse(evidence.exists())

    def test_nested_evidence_entry_fails_tracked_and_full_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence"
            shutil.copytree(
                ROOT / "evidence/camera_spatial_normalization/2026-07-24",
                evidence,
            )
            nested = evidence / "private_rows"
            nested.mkdir()
            (nested / "rows.json").write_text('{"site_ids":["synthetic"]}\n')

            with self.assertRaisesRegex(
                camera.CameraNormalizationError, "evidence_footprint_drift"
            ):
                camera.validate_evidence(PLAN, evidence)
            with self.assertRaisesRegex(
                camera.CameraNormalizationError, "evidence_footprint_drift"
            ):
                camera.validate_evidence(
                    PLAN,
                    evidence,
                    private_dir=Path(directory) / "private",
                    output_dir=Path(directory) / "output",
                )

    def test_nested_private_and_output_entries_fail_exact_footprints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private"
            private.mkdir()
            private_names = {
                "locations.csv",
                "lookup.csv",
                "observations.csv",
                "crosswalk.json",
                "source_manifest.json",
            }
            for name in private_names:
                (private / name).write_text("synthetic\n")
            (private / "nested").mkdir()
            with self.assertRaisesRegex(
                camera.CameraNormalizationError,
                "private_manifest_footprint_drift",
            ):
                camera._validate_exact_directory_files(
                    private,
                    private_names,
                    directory_error="private_directory_invalid",
                    footprint_error="private_manifest_footprint_drift",
                )

            actual = root / "actual"
            expected = root / "expected"
            actual.mkdir()
            expected.mkdir()
            for name in camera.OUTPUT_FILES:
                (actual / name).write_text("same\n")
                (expected / name).write_text("same\n")
            (actual / "nested").mkdir()
            with self.assertRaisesRegex(
                camera.CameraNormalizationError, "output_footprint_drift"
            ):
                camera._validate_output_replay(actual, expected)

    def test_tracked_payload_unknown_private_alias_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence"
            shutil.copytree(
                ROOT / "evidence/camera_spatial_normalization/2026-07-24",
                evidence,
            )
            summary_path = evidence / "normalization_summary.json"
            summary = json.loads(summary_path.read_text())
            summary["site_ids"] = ["synthetic"]
            summary_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n"
            )
            manifest_path = evidence / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            entry = next(
                item
                for item in manifest["files"]
                if item["path"] == "normalization_summary.json"
            )
            entry["bytes"] = summary_path.stat().st_size
            entry["sha256"] = camera.sha256(summary_path)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )

            with self.assertRaisesRegex(
                camera.CameraNormalizationError,
                "normalization_summary_schema_failure",
            ):
                camera.validate_evidence(PLAN, evidence)

    def test_spatial_evidence_reports_site_exclusion_reason_split(self):
        spatial = json.loads(
            (
                ROOT
                / "evidence/camera_spatial_normalization/2026-07-24"
                / "spatial_summary.json"
            ).read_text()
        )
        self.assertEqual(
            spatial["site_exclusion_reason_counts"],
            {
                "outside_land_boundary": 13,
                "ineligible_grid_cell": 54,
                "unreferenced_site": 1,
            },
        )

    def test_plan_rejects_directory_and_privacy_shape_drift(self):
        plan = json.loads(PLAN.read_text())
        mutations = []
        drift = copy.deepcopy(plan)
        drift["outputs"]["directory"] = "trackable/output"
        mutations.append(drift)
        drift = copy.deepcopy(plan)
        drift["evidence"]["directory"] = "elsewhere/evidence"
        mutations.append(drift)
        drift = copy.deepcopy(plan)
        drift["privacy"]["site_ids"] = False
        mutations.append(drift)
        drift = copy.deepcopy(plan)
        del drift["privacy"]["tracked_row_values"]
        mutations.append(drift)
        drift = copy.deepcopy(plan)
        drift["privacy"]["tracked_row_values"] = True
        mutations.append(drift)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(
                    camera.CameraNormalizationError,
                    "publication_or_privacy_contract_drift",
                ):
                    camera.validate_plan(mutation)

    def test_run_rejects_noncanonical_or_nonignored_destination(self):
        canonical_output = (
            ROOT
            / "data/processed/camera/goal019-spatial-normalization/2026-07-24"
        )
        canonical_evidence = (
            ROOT / "evidence/camera_spatial_normalization/2026-07-24"
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                camera.CameraNormalizationError,
                "publication_destination_not_canonical",
            ):
                camera.run(
                    PLAN,
                    private_dir=Path(directory) / "private",
                    output_dir=Path(directory) / "trackable-output",
                    evidence_dir=canonical_evidence,
                )
            with self.assertRaisesRegex(
                camera.CameraNormalizationError,
                "publication_destination_not_canonical",
            ):
                camera.run(
                    PLAN,
                    private_dir=Path(directory) / "private",
                    output_dir=canonical_output,
                    evidence_dir=Path(directory) / "evidence",
                )
            with patch.object(
                camera, "_git_path_is_ignored", return_value=False
            ):
                with self.assertRaisesRegex(
                    camera.CameraNormalizationError,
                    "private_output_not_ignored",
                ):
                    camera.run(
                        PLAN,
                        private_dir=Path(directory) / "private",
                        output_dir=canonical_output,
                        evidence_dir=canonical_evidence,
                    )


if __name__ == "__main__":
    unittest.main()
