import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import dsdm_phase1.predictor_stack_extraction as extraction

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/predictor_stack_extraction_plan.json"
EVIDENCE = ROOT / "evidence/predictor_stack_extraction/2026-07-26"
OUTPUT = ROOT / "data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26"


def _copy_tracked_package(destination: Path) -> tuple[Path, Path]:
    plan = destination / "config/predictor_stack_extraction_plan.json"
    evidence = destination / "evidence/predictor_stack_extraction/2026-07-26"
    plan.parent.mkdir(parents=True)
    evidence.mkdir(parents=True)
    shutil.copy2(PLAN, plan)
    for source in EVIDENCE.iterdir():
        shutil.copy2(source, evidence / source.name)
    return plan, evidence


class PredictorStackExtractionTests(unittest.TestCase):
    def test_band_contract_and_schema(self):
        self.assertEqual(extraction.ACTIVE_BAND_INDICES, tuple(list(range(1, 25)) + [26, 28, 30, 32]))
        self.assertEqual(extraction.EXCLUDED_PREDICTORS, ("fire_freq", "veg_mvs", "landuse_primary", "landuse_tertiary"))
        self.assertEqual(len(extraction.OUTPUT_FIELDS), 34)

    def test_float32_serialization_round_trip(self):
        value = 123.456789
        rendered = extraction.serialize_float32(value)
        self.assertEqual(extraction.np.float32(float(rendered)), extraction.np.float32(value))

    def test_exact_indexing_rejects_non_centres(self):
        class Dummy:
            bounds = type("B", (), {"left": 0.0, "top": 1.0})()
            transform = type("T", (), {"a": 0.1, "e": -0.1})()
            width = height = 10
        self.assertEqual(extraction._cell_indices(Dummy(), 0.05, 0.95), (0, 0))
        with self.assertRaises(extraction.PredictorExtractionError):
            extraction._cell_indices(Dummy(), 0.051, 0.95)

    def test_missing_values_are_retained_and_categorical_values_are_integer(self):
        self.assertTrue(extraction._is_missing(-3.4e38, -3.4e38))
        self.assertFalse(extraction._is_missing(2.0, -3.4e38))
        with self.assertRaises(extraction.PredictorExtractionError):
            raise extraction.PredictorExtractionError("categorical_value_not_integer")

    def test_plan_is_frozen(self):
        plan = json.loads(PLAN.read_text())
        self.assertEqual(extraction.validate_plan(plan)["active_predictor_count"], 28)

    def test_runtime_contract_covers_locked_numpy_branches_without_live_version(self):
        runtime = extraction.RUNTIME_CONTRACT
        self.assertEqual(runtime["python_requires"], ">=3.11")
        self.assertEqual(runtime["rasterio"], "1.4.4")
        self.assertEqual(runtime["numpy_by_python"]["python_full_version < '3.12'"], "2.4.6")
        self.assertEqual(runtime["numpy_by_python"]["python_full_version >= '3.12'"], "2.5.1")
        self.assertNotIn("numpy", extraction._build_payloads.__code__.co_consts)

    def test_production_artefacts_hash_footprint_ignore_and_full_replay(self):
        self.assertEqual({p.name for p in OUTPUT.iterdir()}, set(extraction.OUTPUT_FILES))
        self.assertTrue(all(p.is_file() and not p.is_symlink() for p in OUTPUT.iterdir()))
        ignored = __import__("subprocess").run(["git", "check-ignore", "--quiet", "--no-index", "--", str(OUTPUT)], cwd=ROOT)
        self.assertEqual(ignored.returncode, 0)
        result = extraction.validate_evidence(PLAN, EVIDENCE, full=True, output_dir=OUTPUT)
        self.assertEqual(result, {"tracked_valid": True, "full_replay": True})
        self.assertEqual(hashlib.sha256((OUTPUT / extraction.OUTPUT_FILES[0]).read_bytes()).hexdigest(), extraction.EXPECTED_OUTPUTS["roles"][extraction.OUTPUT_FILES[0]]["sha256"])

    def test_tracked_validation_works_without_private_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, evidence = _copy_tracked_package(Path(tmp))
            self.assertEqual(extraction.validate_evidence(plan, evidence), {"tracked_valid": True, "full_replay": False})

    def test_manifest_refreshed_semantic_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, evidence = _copy_tracked_package(Path(tmp))
            target = evidence / "missingness_summary.json"
            payload = json.loads(target.read_text()); payload["canonical"]["complete"] = 1; target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            manifest = json.loads((evidence / "manifest.json").read_text())
            for entry in manifest["files"]:
                if entry["path"] == target.name:
                    entry["bytes"] = target.stat().st_size; entry["sha256"] = extraction.sha256(target)
            (evidence / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            with self.assertRaisesRegex(extraction.PredictorExtractionError, "missingness_semantic_drift"):
                extraction.validate_evidence(plan, evidence)

    def test_privacy_and_footprint_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, evidence = _copy_tracked_package(Path(tmp))
            (evidence / "unexpected.json").write_text("{}")
            with self.assertRaisesRegex(extraction.PredictorExtractionError, "evidence_footprint_drift"):
                extraction.validate_evidence(plan, evidence)
        payload = {"centroid_lon": "private"}
        with self.assertRaisesRegex(extraction.PredictorExtractionError, "tracked_evidence_privacy_failure"):
            extraction.assert_evidence_privacy(payload)

    def test_plan_drift_and_private_output_tamper_rejected_by_full_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, evidence = _copy_tracked_package(root)
            for role, (relative, _) in extraction.EXPECTED_BINDINGS.items():
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            output = root / "data/processed/predictors/goal022-predictor-stack-extraction/2026-07-26"
            output.mkdir(parents=True)
            for name in extraction.OUTPUT_FILES:
                shutil.copy2(OUTPUT / name, output / name)
            (output / extraction.OUTPUT_FILES[0]).write_bytes((output / extraction.OUTPUT_FILES[0]).read_bytes() + b"tamper")
            with self.assertRaisesRegex(extraction.PredictorExtractionError, "output_replay_failure"):
                extraction.validate_evidence(plan, evidence, full=True, output_dir=output)
            plan_payload = json.loads(plan.read_text()); plan_payload["expected_oracle"]["canonical_rows"] = 1; plan.write_text(json.dumps(plan_payload))
            with self.assertRaisesRegex(extraction.PredictorExtractionError, "oracle_contract_drift"):
                extraction.validate_evidence(plan, evidence)

    def test_existing_destination_guard_and_atomic_second_rename_rollback(self):
        with self.assertRaisesRegex(extraction.PredictorExtractionError, "publication_destination_exists"):
            extraction.run_production(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); stage = root / "stage"; stage_output = stage / "output"; stage_evidence = stage / "evidence"; stage_output.mkdir(parents=True); stage_evidence.mkdir()
            output = root / "output"; evidence = root / "evidence"
            original = Path.rename; calls = []
            def fail_second(self, target):
                calls.append((self, target))
                if len(calls) == 2:
                    raise OSError("injected second rename failure")
                return original(self, target)
            with mock.patch.object(Path, "rename", fail_second):
                with self.assertRaises(OSError):
                    extraction._publish_staged(stage_output, stage_evidence, output, evidence)
            self.assertFalse(output.exists()); self.assertFalse(evidence.exists()); self.assertTrue(stage_output.exists()); self.assertTrue(stage_evidence.exists())


if __name__ == "__main__":
    unittest.main()
