import csv
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import dsdm_phase1.predictor_source_repair_domain_freeze as d

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/predictor_source_repair_domain_freeze_plan.json"
EVIDENCE = ROOT / "evidence/predictor_source_repair_domain_freeze/2026-07-26"


class Goal024Tests(unittest.TestCase):
    def _copy_evidence(self, td):
        root = Path(td); p = root / "config/plan.json"; e = root / "evidence"; p.parent.mkdir(); e.mkdir(); shutil.copy2(PLAN, p)
        for f in EVIDENCE.iterdir(): shutil.copy2(f, e / f.name)
        return root, p, e

    def _refresh_manifest(self, e, changed):
        m = json.loads((e / "manifest.json").read_text())
        for ent in m["files"]:
            if ent["path"] == changed:
                path = e / changed; ent.update(bytes=path.stat().st_size, sha256=d.sha256(path))
        (e / "manifest.json").write_text(json.dumps(m, sort_keys=True, indent=2) + "\n")

    def test_structural_inclusion_and_zero_repair_synthetic(self):
        a = {"grid_cell_id": "g_1_1", "predictor_complete": "true", **{p: "1" for p in d.ACTIVE}}
        b = dict(a, grid_cell_id="g_1_2", elevation="", predictor_complete="false", missing_predictor_count="1", missing_predictor_ids="elevation")
        cells = [dict(a), dict(b)]
        response_cells = [dict(a), dict(b)]
        response = [{"species_id": "dasyurus_maculatus", "grid_cell_id": "g_1_1", "pa": "1", "pa_type": "presence", "response_origin": "goal020", "source_combination": ""}]
        out = d._domain_rows(cells, response_cells, response)
        self.assertEqual(out["complete_keys"], {"g_1_1"})
        audits, _ = d._audit(cells, response, out["complete_keys"])
        self.assertEqual(sum(x["included"] == "true" for x in audits), 1)
        self.assertEqual({x["repair_status"] for x in audits}, {"not_authorized"})

    def test_tracked_validation_and_refreshed_manifest_tamper(self):
        self.assertEqual(d.validate_evidence(PLAN, EVIDENCE), {"tracked_valid": True, "full_replay": False})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); p = root / "config/plan.json"; e = root / "evidence"; p.parent.mkdir(); e.mkdir()
            shutil.copy2(PLAN, p)
            for f in EVIDENCE.iterdir(): shutil.copy2(f, e / f.name)
            target = e / "domain_summary.json"; x = json.loads(target.read_text()); x["map_cells"]["included"] = 1; target.write_text(json.dumps(x, sort_keys=True, indent=2) + "\n")
            m = json.loads((e / "manifest.json").read_text())
            for ent in m["files"]:
                if ent["path"] == target.name: ent.update(bytes=target.stat().st_size, sha256=d.sha256(target))
            (e / "manifest.json").write_text(json.dumps(m, sort_keys=True, indent=2) + "\n")
            with self.assertRaisesRegex(d.PredictorDomainError, "domain_summary_semantic_drift"):
                d.validate_evidence(p, e)

    def test_table_driven_cross_payload_tamper_cases(self):
        cases = [
            ("source_inventory.json", lambda x: x["local_candidate_inventory"]["human_footprint_tas.tif"]["oracle"].__setitem__("shared_raster_nodata_pixels", 1), "hfp_inventory_semantic_drift"),
            ("response_impact.json", lambda x: x["by_species"]["dasyurus_viverrinus"].__setitem__("excluded", 99), "response_group_semantic_drift"),
            ("support_contract.json", lambda x: x["goal023_diagnostics"].__setitem__("structural_filter", True), "support_contract_semantic_drift"),
            ("support_contract.json", lambda x: x["pseudoabsence_post_domain"].__setitem__("retained_rows", 497), "pseudoabsence_post_domain_semantic_drift"),
        ]
        for filename, mutate, error in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                _, p, e = self._copy_evidence(td); target=e/filename; value=json.loads(target.read_text()); mutate(value); target.write_text(json.dumps(value, sort_keys=True, indent=2)+"\n"); self._refresh_manifest(e, filename)
                with self.assertRaisesRegex(d.PredictorDomainError, error): d.validate_evidence(p, e)

    def test_privacy_and_schema_closure_injections(self):
        cases = [
            ("source_inventory.json", lambda x: x.__setitem__("centroid_lon", -42.1), "tracked_evidence_privacy_failure"),
            ("source_inventory.json", lambda x: x.__setitem__("extra_payload", ["g_1_2"]), "tracked_evidence_privacy_failure"),
            ("source_comparison.json", lambda x: x.__setitem__("extra_payload", 1), "source_comparison_schema_drift"),
            ("outputs.json", lambda x: x["roles"]["predictor_cell_map_canonical.csv"].__setitem__("extra", 1), "outputs_semantic_drift"),
        ]
        for filename, mutate, error in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                _, p, e = self._copy_evidence(td); target=e/filename; value=json.loads(target.read_text()); mutate(value); target.write_text(json.dumps(value, sort_keys=True, indent=2)+"\n"); self._refresh_manifest(e, filename)
                with self.assertRaisesRegex(d.PredictorDomainError, error): d.validate_evidence(p, e)

    def test_full_replay_and_footprint(self):
        self.assertEqual(d.validate_evidence(PLAN, EVIDENCE, full=True, root=ROOT), {"tracked_valid": True, "full_replay": True})
        with self.assertRaisesRegex(d.PredictorDomainError, "evidence_footprint_drift"):
            with tempfile.TemporaryDirectory() as td:
                x = Path(td); shutil.copytree(EVIDENCE, x / "e"); (x / "e" / "extra.json").write_text("{}")
                d.validate_evidence(PLAN, x / "e")

    def test_private_outputs_have_expected_grain_and_values(self):
        out = ROOT / "data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26"
        with (out / "predictor_cell_map_canonical.csv").open(newline="") as f: rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), d.MAP_INCLUDED)
        self.assertTrue(all(all(r[p] != "" for p in d.ACTIVE) for r in rows))
        with (out / "cell_domain_audit.csv").open(newline="") as f: audits = list(csv.DictReader(f))
        self.assertEqual(len(audits), d.MAP_ROWS)
        self.assertEqual(sum(x["included"] == "true" for x in audits), d.MAP_INCLUDED)

    def test_private_footprint_and_byte_guard(self):
        computed=d.compute_outputs(ROOT, json.loads(PLAN.read_text())); expected=d._private_expected(computed); out=ROOT/"data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26"
        self.assertEqual(d._private_metadata(out, expected)["roles"]["predictor_cell_map_canonical.csv"]["rows"], d.MAP_INCLUDED)
        with tempfile.TemporaryDirectory() as td:
            x=Path(td)/"private"; shutil.copytree(out,x); (x/"extra.csv").write_text("x\n")
            with self.assertRaisesRegex(d.PredictorDomainError,"private_output_footprint_drift"): d._private_metadata(x, expected)
            (x/"extra.csv").unlink(); (x/"predictor_cell_map_canonical.csv").write_bytes((x/"predictor_cell_map_canonical.csv").read_bytes()+b"\n")
            with self.assertRaisesRegex(d.PredictorDomainError,"private_output_byte_drift"): d._private_metadata(x, expected)
            (x/"predictor_cell_map_canonical.csv").unlink(); (x/"predictor_cell_map_canonical.csv").symlink_to(out/"predictor_cell_map_canonical.csv")
            with self.assertRaisesRegex(d.PredictorDomainError,"private_output_footprint_drift"): d._private_metadata(x, expected)

    def test_plan_binding_and_existing_destination_guards(self):
        plan=json.loads(PLAN.read_text()); plan["bindings"]["goal023_plan"]["sha256"]="0"*64
        with self.assertRaisesRegex(d.PredictorDomainError,"plan_binding_drift"): d.validate_plan(plan)
        with self.assertRaisesRegex(d.PredictorDomainError,"publication_destination_exists"): d.run_production(ROOT)

    def test_second_rename_rolls_back_first(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); stage=root/"stage"; stage.mkdir(); (stage/"x").write_text("x"); target=root/"private"; evidence_stage=root/"e-stage"; evidence_stage.mkdir(); (evidence_stage/"x").write_text("x"); evidence=root/"evidence"
            original=Path.rename; calls=[]
            def rename(path, destination):
                calls.append(path)
                if len(calls)==2: raise OSError("injected second rename")
                return original(path, destination)
            with mock.patch.object(Path, "rename", new=rename), self.assertRaisesRegex(d.PredictorDomainError,"publication_rollback"):
                d._publish_pair(stage, evidence_stage, target, evidence)
            self.assertTrue(stage.exists()); self.assertFalse(target.exists()); self.assertFalse(evidence.exists())


if __name__ == "__main__":
    unittest.main()
