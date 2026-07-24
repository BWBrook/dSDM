import csv
from contextlib import contextmanager
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch
import geopandas as gpd
from shapely.geometry import Polygon
import dsdm_phase1.ala_spatial_normalization as spatial

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dsdm_phase1.ala_spatial_normalization import (
    AUDIT_FIELDS, PRESENCE_FIELDS, SPECIES, _taxon, _temporal, _uncertainty,
    candidate_centroid, collapse_presence, grid_cell_id, snapshot_row_id,
    _coast_covers,
    NormalizationError, validate_evidence,
    validate_plan, normalize_rows,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/ala_spatial_normalization_plan.json"


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _rehash_evidence_entry(evidence_dir, name):
    manifest_path = evidence_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest["files"] if item["path"] == name)
    path = evidence_dir / name
    entry["bytes"] = path.stat().st_size
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(manifest_path, manifest)


def _bind_output_hash(evidence_dir, key, output_path):
    outputs_path = evidence_dir / "outputs.json"
    outputs = json.loads(outputs_path.read_text())
    outputs[key] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    _write_json(outputs_path, outputs)
    _rehash_evidence_entry(evidence_dir, "outputs.json")


def _rewrite_csv(path, fields, mutate):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    mutate(rows)
    spatial._write_csv(path, fields, rows)


@contextmanager
def _synthetic_run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        raw = root / "raw"
        (raw / "occurrences").mkdir(parents=True)
        cols = [
            "recordID",
            "occurrenceID",
            "dataResourceUid",
            "datasetID",
            "eventDate",
            "year",
            "decimalLatitude",
            "decimalLongitude",
            "coordinateUncertaintyInMeters",
            "scientificName",
            "taxonConceptID",
            "taxonRank",
        ] + [f"x{i}" for i in range(133)]
        source_rows = []
        for index, species_id in enumerate(SPECIES):
            path = raw / "occurrences" / f"{species_id}.csv"
            row = dict.fromkeys(cols, "")
            row.update(
                recordID=f"r{index}",
                occurrenceID=f"o{index}",
                dataResourceUid="dr",
                datasetID="ds",
                eventDate="2001-01-01",
                year="2001",
                decimalLatitude="0.5",
                decimalLongitude="0.5",
                coordinateUncertaintyInMeters="",
                scientificName=SPECIES[species_id][0],
                taxonConceptID=SPECIES[species_id][1],
                taxonRank="species",
            )
            source_rows.append((path, row))
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=cols)
                writer.writeheader()
                writer.writerow(row)
        manifest_entries = [
            {
                "path": f"occurrences/{path.name}",
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path, _ in source_rows
        ]
        raw_manifest = root / "manifest.json"
        _write_json(raw_manifest, {"raw_files": manifest_entries})
        grid = root / "grid.csv"
        grid.write_text("lon,lat\n0.5,0.5\n")
        coast = root / "coast.shp"
        coast.write_bytes(b"synthetic")

        plan = json.loads(PLAN.read_text())
        plan["expected_input_rows"] = 9
        plan["bindings"]["raw_directory"]["path"] = "raw"
        plan["bindings"]["raw_manifest"].update(
            path="manifest.json",
            sha256=hashlib.sha256(raw_manifest.read_bytes()).hexdigest(),
        )
        plan["bindings"]["grid"].update(
            path="grid.csv", sha256=hashlib.sha256(grid.read_bytes()).hexdigest()
        )
        plan["bindings"]["coast_shp"].update(
            path="coast.shp", sha256=hashlib.sha256(coast.read_bytes()).hexdigest()
        )
        plan["outputs"]["directory"] = "out"
        plan["evidence"]["directory"] = "ev"
        for key in (
            "coast_shx",
            "coast_dbf",
            "coast_prj",
            "ala_plan",
            "field_contract",
            "decision_bundle",
        ):
            plan["bindings"][key].update(
                path="grid.csv", sha256=hashlib.sha256(grid.read_bytes()).hexdigest()
            )
        plan_path = root / "config/plan.json"
        _write_json(plan_path, plan)
        polygon = gpd.GeoSeries(
            [Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
            crs="EPSG:4326",
        )
        goal017_validator = lambda *args: {
            "readiness": "goal017_nine_species_acquisition_complete"
        }
        with (
            patch.object(
                spatial, "validate_plan", return_value={"goal_id": spatial.GOAL_ID}
            ),
            patch.object(
                spatial, "_read_grid", return_value={"g_5000_5000": (0.5, 0.5)}
            ),
            patch.object(spatial, "_shapefile_polygons", return_value=polygon),
            patch.object(spatial, "candidate_centroid", return_value=(0.5, 0.5)),
        ):
            result = spatial.run(
                plan_path, goal017_validator=goal017_validator
            )
            yield {
                "root": root,
                "plan": plan_path,
                "raw": raw,
                "output": root / "out",
                "evidence": root / "ev",
                "goal017_validator": goal017_validator,
                "result": result,
            }


class SpatialNormalizationTests(unittest.TestCase):
    def test_plan_pins_source_and_spatial_contracts(self):
        plan = json.loads((Path(__file__).resolve().parents[1] / "config/ala_spatial_normalization_plan.json").read_text())
        self.assertEqual(validate_plan(plan)["goal_id"], "goal018-ala-spatial-normalization-2026-07-24")
        self.assertEqual(plan["spatial_bindings"]["grid"]["row_count"], 74073)

    def test_full_validate_requires_plan_raw_and_output(self):
        with self.assertRaises(NormalizationError):
            validate_evidence(Path("config/ala_spatial_normalization_plan.json"), Path("evidence"))

    def test_event_date_strict_fallback(self):
        self.assertEqual(_temporal({"year": "", "eventDate": "2001-xx"})[2], "temporal_missing_or_invalid")
        self.assertEqual(_temporal({"year": "2001", "eventDate": "not-a-date"})[2], "event_date_invalid_flag")

    def test_audit_row_state_contract(self):
        self.assertIn("accepted_presence", {"accepted_presence", "excluded"})
        self.assertNotEqual("accepted", "accepted_presence")

    def test_raw_hash_cached_once_per_source_file(self):
        row = {"recordID":"r", "scientificName":"Vombatus ursinus", "taxonConceptID":SPECIES["vombatus_ursinus"][1], "taxonRank":"species", "year":"2001", "decimalLongitude":"0", "decimalLatitude":"0"}
        with tempfile.NamedTemporaryFile() as f, patch("dsdm_phase1.ala_spatial_normalization.sha256", return_value="abc") as h:
            normalize_rows([("vombatus_ursinus", Path(f.name), 1, row), ("vombatus_ursinus", Path(f.name), 2, dict(row, recordID="r2"))], {}, [])
            self.assertEqual(h.call_count, 1)

    def test_synthetic_run_and_full_validate(self):
        with _synthetic_run() as fixture:
            self.assertEqual(
                fixture["result"]["readiness"],
                "goal018_spatial_normalization_complete",
            )
            self.assertEqual(
                spatial.validate_evidence(
                    fixture["plan"],
                    fixture["evidence"],
                    raw_root=fixture["raw"],
                    output_dir=fixture["output"],
                    goal017_validator=fixture["goal017_validator"],
                )["readiness"],
                "goal018_spatial_normalization_complete",
            )

    def test_rehashed_audit_decision_mutation_fails_full_replay(self):
        with _synthetic_run() as fixture:
            audit_path = fixture["output"] / "row_audit.csv"
            _rewrite_csv(
                audit_path,
                AUDIT_FIELDS,
                lambda rows: rows[0].update(taxon_basis="mutated"),
            )
            _bind_output_hash(
                fixture["evidence"], "row_audit_sha256", audit_path
            )
            with self.assertRaises(NormalizationError):
                spatial.validate_evidence(
                    fixture["plan"],
                    fixture["evidence"],
                    raw_root=fixture["raw"],
                    output_dir=fixture["output"],
                    goal017_validator=fixture["goal017_validator"],
                )

    def test_rehashed_presence_aggregate_mutation_fails_full_replay(self):
        with _synthetic_run() as fixture:
            presence_path = fixture["output"] / "presence.csv"
            _rewrite_csv(
                presence_path,
                PRESENCE_FIELDS,
                lambda rows: rows[0].update(
                    source_row_count=str(int(rows[0]["source_row_count"]) + 1)
                ),
            )
            _bind_output_hash(
                fixture["evidence"], "presence_sha256", presence_path
            )
            with self.assertRaises(NormalizationError):
                spatial.validate_evidence(
                    fixture["plan"],
                    fixture["evidence"],
                    raw_root=fixture["raw"],
                    output_dir=fixture["output"],
                    goal017_validator=fixture["goal017_validator"],
                )

    def test_rehashed_aggregate_evidence_mutation_fails_full_replay(self):
        with _synthetic_run() as fixture:
            summary_path = fixture["evidence"] / "normalization_summary.json"
            summary = json.loads(summary_path.read_text())
            basis = summary["by_taxon_basis"]
            name, count = next(iter(basis.items()))
            del basis[name]
            basis["mutated_basis"] = count
            _write_json(summary_path, summary)
            _rehash_evidence_entry(
                fixture["evidence"], "normalization_summary.json"
            )
            with self.assertRaises(NormalizationError):
                spatial.validate_evidence(
                    fixture["plan"],
                    fixture["evidence"],
                    raw_root=fixture["raw"],
                    output_dir=fixture["output"],
                    goal017_validator=fixture["goal017_validator"],
                )

    def test_accepted_cell_invariant(self):
        row = {"recordID":"r", "scientificName":"Vombatus ursinus", "taxonConceptID":SPECIES["vombatus_ursinus"][1], "taxonRank":"species", "year":"2001", "decimalLongitude":"0", "decimalLatitude":"0"}
        with tempfile.NamedTemporaryFile() as f:
            audit, accepted = normalize_rows([("vombatus_ursinus", Path(f.name), 1, row)], {}, [])
        self.assertEqual(accepted, [])
        self.assertEqual(audit[0]["row_state"], "excluded")

    def test_audit_has_gate_states_and_source_ordinal(self):
        self.assertIn("row_state", AUDIT_FIELDS)
        self.assertIn("source_file", AUDIT_FIELDS)
        self.assertIn("source_row_ordinal", AUDIT_FIELDS)
    def test_deterministic_ids_and_negative_coordinates(self):
        self.assertEqual(snapshot_row_id("abc", 1), snapshot_row_id("abc", 1))
        self.assertNotEqual(snapshot_row_id("abc", 1), snapshot_row_id("abc", 2))
        self.assertEqual(grid_cell_id(143.845, -43.6375), "g_1438450_-436375")

    def test_lattice_edges_and_no_nearest_rescue(self):
        self.assertEqual(candidate_centroid(143.84, -43.6425), (143.845, -43.6375))
        self.assertEqual(candidate_centroid(143.85, -43.6325), (143.855, -43.6275))
        self.assertIsNone(candidate_centroid(float("nan"), -42))

    def test_coast_covers_boundary_and_hole(self):
        geom = gpd.GeoSeries([Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)], holes=[[(.5, .5), (1.5, .5), (1.5, 1.5), (.5, 1.5), (.5, .5)]])], crs="EPSG:4326")
        self.assertTrue(_coast_covers(0, 1, geom))
        self.assertFalse(_coast_covers(1, 1, geom))

    def test_taxon_parent_child_subspecies_and_mismatch(self):
        sid = "vombatus_ursinus"
        parent = {
            "scientificName": SPECIES[sid][0],
            "taxonConceptID": SPECIES[sid][1],
            "taxonRank": "species",
        }
        self.assertEqual(_taxon(parent, sid)[0], sid)
        child = {
            "acceptedNameUsage": "Vombatus ursinus hirsutus",
            "acceptedNameUsageID": "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7",
            "taxonRank": "subspecies",
        }
        self.assertTrue(_taxon(child, sid)[2])
        sub = {"acceptedNameUsage": "Vombatus ursinus hirsutus", "taxonRank": "subspecies"}
        self.assertTrue(_taxon(sub, sid)[2])
        self.assertIsNone(_taxon({"scientificName": "Other species", "taxonRank": "species"}, sid)[0])
        self.assertIsNone(_taxon({"taxonConceptID": SPECIES["sarcophilus_harrisii"][1], "scientificName": "Vombatus ursinus", "taxonRank": "species"}, sid)[0])
        self.assertIsNone(_taxon({"taxonConceptID": SPECIES[sid][1], "acceptedNameUsage": "Other species", "taxonRank": "species"}, sid)[0])

    def test_taxon_unlisted_subspecies_concept_passes_bound_source(self):
        sid = "vombatus_ursinus"
        row = {
            "scientificName": "Vombatus ursinus example",
            "taxonConceptID": "https://example.invalid/unlisted-child",
            "taxonRank": "subspecies",
        }
        accepted, basis, descendant, rank = _taxon(row, sid)
        self.assertEqual(accepted, sid)
        self.assertEqual(basis, "accepted_subspecies_name")
        self.assertTrue(descendant)
        self.assertEqual(rank, "subspecies")

    def test_taxon_known_concepts_and_controlling_names_fail_on_conflict(self):
        sid = "vombatus_ursinus"
        child = "https://biodiversity.org.au/afd/taxa/e4b74750-7541-4c67-89d1-5b5718b30ea7"
        cases = [
            {
                "scientificName": "Sarcophilus harrisii",
                "taxonConceptID": SPECIES[sid][1],
                "taxonRank": "species",
            },
            {
                "acceptedNameUsage": "Vombatus ursinus",
                "acceptedNameUsageID": SPECIES["sarcophilus_harrisii"][1],
                "taxonRank": "species",
            },
            {
                "acceptedNameUsage": "Sarcophilus harrisii",
                "acceptedNameUsageID": child,
                "taxonRank": "subspecies",
            },
            {
                "acceptedNameUsage": "Sarcophilus harrisii",
                "scientificName": "Vombatus ursinus",
                "taxonConceptID": SPECIES[sid][1],
                "taxonRank": "species",
            },
            {
                "acceptedNameUsage": "Vombatus ursinus example",
                "acceptedNameUsageID": "https://example.invalid/unknown-accepted",
                "taxonConceptID": "https://example.invalid/unlisted-child",
                "taxonRank": "subspecies",
            },
        ]
        for row in cases:
            with self.subTest(row=row):
                self.assertIsNone(_taxon(row, sid)[0])

    def test_taxon_species_parent_accepts_parenthesized_authorship(self):
        canonical = "vombatus_ursinus"
        alias = "notamacropus_rufogriseus"
        cases = [
            (
                canonical,
                {
                    "scientificName": "Vombatus ursinus (Shaw, 1800)",
                    "taxonConceptID": SPECIES[canonical][1],
                    "taxonRank": "species",
                },
            ),
            (
                alias,
                {
                    "acceptedNameUsage": "Macropus rufogriseus (Desmarest, 1817)",
                    "acceptedNameUsageID": SPECIES[alias][1],
                    "taxonRank": "species",
                },
            ),
        ]
        for species_id, row in cases:
            with self.subTest(species_id=species_id):
                self.assertEqual(_taxon(row, species_id)[0], species_id)
        self.assertIsNone(
            _taxon(
                {
                    "scientificName": "Vombatus ursinus (Shaw, 1800)",
                    "taxonRank": "species",
                },
                canonical,
            )[0]
        )
        self.assertIsNone(
            _taxon(
                {
                    "scientificName": "Vombatus ursinus Shaw, 1800",
                    "taxonConceptID": SPECIES[canonical][1],
                    "taxonRank": "species",
                },
                canonical,
            )[0]
        )

    def test_temporal_fallback_conflict_and_endpoints(self):
        self.assertEqual(_temporal({"year": "", "eventDate": "2001-xx"})[2], "temporal_missing_or_invalid")
        self.assertEqual(_temporal({"year": "2001", "eventDate": "2002-01-01"})[2], "temporal_conflict")
        self.assertEqual(_temporal({"year": "2025", "eventDate": ""})[0], 2025)
        self.assertEqual(_temporal({"year": "x", "eventDate": ""})[2], "temporal_missing_or_invalid")

    def test_uncertainty_bands(self):
        self.assertEqual(_uncertainty({})[:2], (None, "unknown"))
        self.assertIsNone(_uncertainty({"coordinateUncertaintyInMeters": "1000"})[2])
        self.assertEqual(_uncertainty({"coordinateUncertaintyInMeters": "1000.1"})[2], "coordinate_uncertainty_over_1000_m")
        self.assertEqual(_uncertainty({"coordinateUncertaintyInMeters": "oops"})[2], "coordinate_uncertainty_invalid")

    def test_deterministic_collapse_and_aggregate_fields(self):
        a = {"accepted_species_id": "vombatus_ursinus", "grid_cell_id": "g_1_2", "candidate_centroid_lon": 1, "candidate_centroid_lat": 2, "uncertainty_band": "unknown", "coordinate_uncertainty_m": "", "cell_half_diagonal_m": 1, "qa_flag_count": 1}
        rows = [{"audit": a, "row": {"recordID": "r1", "dataResourceUid": "dr", "datasetID": "ds"}}, {"audit": dict(a), "row": {"recordID": "r2", "dataResourceUid": "dr", "datasetID": "ds"}}]
        out = collapse_presence(rows)
        self.assertEqual(out[0]["source_row_count"], 2)
        self.assertEqual(out[0]["unique_provider_record_count"], 2)
        self.assertEqual(out[0]["presence"], 1)

    def test_spatial_summary_uses_accepted_low_certainty_population(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name in ("raw_manifest", "grid", "coast_shp"):
                path = root / name
                path.write_text(name)
                paths[name] = path
            output = root / "output"
            output.mkdir()
            (output / "row_audit.csv").write_text("audit\n")
            (output / "presence.csv").write_text("presence\n")
            accepted_unknown = {
                "source_species_id": "vombatus_ursinus",
                "row_state": "accepted_presence",
                "grid_cell_id": "g_1",
                "primary_reason": "",
                "taxon_basis": "pinned_parent_concept",
                "uncertainty_band": "unknown",
                "centroid_distance_m": 1.0,
                "ordered_flags": "boundary_covers;low_cell_certainty",
            }
            accepted_reported = {
                **accepted_unknown,
                "grid_cell_id": "g_2",
                "uncertainty_band": "0-1000m",
                "centroid_distance_m": 2.0,
            }
            excluded_outlier = {
                **accepted_unknown,
                "row_state": "excluded",
                "grid_cell_id": "",
                "primary_reason": "ineligible_grid_cell",
                "centroid_distance_m": 999.0,
            }
            audit = [accepted_unknown, accepted_reported, excluded_outlier]
            payloads = spatial._build_evidence_payloads(
                {},
                paths,
                [None] * len(audit),
                audit,
                [{}, {}],
                [{"species_id": "vombatus_ursinus", "grid_cell_id": "g_1"}],
                output,
            )
            summary = payloads["spatial_summary.json"]
            self.assertEqual(summary["low_cell_certainty_rows"], 2)
            self.assertEqual(summary["centroid_distance_m"], {"max": 2.0, "n": 2})

    def test_tracked_semantically_empty_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            names = ["source_inventory.json", "normalization_summary.json", "spatial_summary.json", "outputs.json", "review.json"]
            for n in names:
                (root / n).write_text(json.dumps({"aggregate": 1}) + "\n")
            entries = [{"path": n, "bytes": (root / n).stat().st_size, "sha256": hashlib.sha256((root / n).read_bytes()).hexdigest()} for n in names]
            (root / "manifest.json").write_text(json.dumps({"schema_version": "1.0", "files": entries}) + "\n")
            with self.assertRaises(NormalizationError):
                validate_evidence(PLAN, root)


if __name__ == "__main__":
    unittest.main()
