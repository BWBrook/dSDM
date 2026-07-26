import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import dsdm_phase1.predictor_support_diagnostics as d

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/predictor_support_diagnostic_plan.json"
EVIDENCE = ROOT / "evidence/predictor_support_diagnostics/2026-07-26"

class PredictorSupportDiagnosticsTests(unittest.TestCase):
    def test_missing_patterns_and_rook_components(self):
        rows=[{"grid_cell_id":"g_0_0","x":""},{"grid_cell_id":"g_100_0","x":""},{"grid_cell_id":"g_0_100","x":"1"},{"grid_cell_id":"g_900_900","x":""}]
        p=d.missing_pattern(rows,("x",)); self.assertEqual(p["missing_count_distribution"],{"0":1,"1":3})
        r=d.rook_components(rows,{r["grid_cell_id"] for r in rows if r["x"]==""}); self.assertEqual(r["rook_missing_missing_edges"],1); self.assertEqual(r["connected_component_count"],2)

    def test_quantile_and_workbook_fixture(self):
        self.assertEqual(d._percentile([1,2,3,4,5],.5),3.0)
        wb=d.parse_workbook_reference(ROOT/"temp/data/spatial/se_stack_metadata.xlsx")
        self.assertIn("climate", wb["sheets"]); self.assertEqual(wb["workbook_sha256"],"ec460f9a41913f3288ca7dd38b6150b575f9c00b73581b892468cd0577127edd")

    def test_tracked_validation_and_refreshed_manifest_tamper(self):
        self.assertEqual(d.validate_evidence(PLAN,EVIDENCE),{"tracked_valid":True,"full_replay":False})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=root/"config/predictor_support_diagnostic_plan.json"; e=root/"evidence/predictor_support_diagnostics/2026-07-26"; p.parent.mkdir(parents=True); e.mkdir(parents=True)
            shutil.copy2(PLAN,p)
            for f in EVIDENCE.iterdir(): shutil.copy2(f,e/f.name)
            target=e/"response_impact.json"; x=json.loads(target.read_text()); x["rows"]=1; target.write_text(json.dumps(x,sort_keys=True,indent=2)+"\n")
            m=json.loads((e/"manifest.json").read_text());
            for ent in m["files"]:
                if ent["path"]==target.name: ent.update(bytes=target.stat().st_size,sha256=d.sha256(target))
            (e/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
            with self.assertRaisesRegex(d.PredictorSupportError,"response_impact_semantic_drift"):
                d.validate_evidence(p,e)

    def test_privacy_and_stop_contract(self):
        with self.assertRaises(d.PredictorSupportError): d.assert_evidence_privacy({"grid_cell_id":"g_1_2"})
        self.assertEqual(d.validate_plan(json.loads(PLAN.read_text()))["goal_id"],d.GOAL_ID)

    def test_edge_distance_order_invariant_and_diagonal_disconnect(self):
        rows=[{"grid_cell_id":"g_0_0"},{"grid_cell_id":"g_100_0"},{"grid_cell_id":"g_200_0"},{"grid_cell_id":"g_0_100"}]
        a=d.edge_distance_summary(rows,{"g_100_0"}); b=d.edge_distance_summary(list(reversed(rows)),{"g_100_0"})
        self.assertEqual(a,b); self.assertEqual(a["incomplete_distance_bands"]["edge"],1)
        self.assertEqual(d.rook_components(rows,{"g_0_0","g_200_0"})["connected_component_count"],2)

    def test_plan_binding_drift_rejected(self):
        p=json.loads(PLAN.read_text()); p["bindings"]["predictor_outputs"]["sha256"]="0"*64
        with self.assertRaisesRegex(d.PredictorSupportError,"plan_binding_drift"): d.validate_plan(p)

    def test_review_and_ranking_tamper_rejected_after_manifest_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=root/"config/predictor_support_diagnostic_plan.json"; e=root/"evidence/predictor_support_diagnostics/2026-07-26"; p.parent.mkdir(parents=True); e.mkdir(parents=True); shutil.copy2(PLAN,p)
            for f in EVIDENCE.iterdir(): shutil.copy2(f,e/f.name)
            target=e/"review.json"; x=json.loads(target.read_text()); x["decision_readiness"]="ready"; target.write_text(json.dumps(x,sort_keys=True,indent=2)+"\n")
            m=json.loads((e/"manifest.json").read_text());
            for ent in m["files"]:
                if ent["path"]==target.name: ent.update(bytes=target.stat().st_size,sha256=d.sha256(target))
            (e/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
            with self.assertRaisesRegex(d.PredictorSupportError,"review_semantic_drift"): d.validate_evidence(p,e)

    def test_five_rehashed_semantic_tamper_cases_rejected(self):
        cases=[
            ("environmental_support.json",lambda x: x["per_species"]["dasyurus_viverrinus"].__setitem__("complete_map_cells_outside_any_marginal_envelope",1),"environmental_species_arithmetic_drift"),
            ("categorical_support.json",lambda x: x["per_species"]["dasyurus_viverrinus"].__setitem__("affected_complete_map_cells_any_unseen_level",1),"categorical_species_arithmetic_drift"),
            ("missingness_patterns.json",lambda x: x["rook_adjacency"].__setitem__("connected_component_count",1),"component_arithmetic_drift"),
            ("response_impact.json",lambda x: x["by_source_combination"]["ala_only_presence"].__setitem__("incomplete",1),"response_group_arithmetic_drift"),
            ("policy_options.json",lambda x: x["options"]["human_footprint"]["if_drop_predictor"].__setitem__("canonical_cells_retained",1),"policy_retained_bounds_drift"),
            ("environmental_support.json",lambda x: x.__setitem__("pooled_complete_map_cells_outside_any_response_envelope",1),"environmental_pooled_bounds_drift"),
            ("categorical_support.json",lambda x: x.__setitem__("pooled_unseen_codes_in_fully_complete_map_cells",1),"categorical_pooled_arithmetic_drift"),
        ]
        for filename, mutate, error in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                root=Path(td); p=root/"config/predictor_support_diagnostic_plan.json"; e=root/"evidence/predictor_support_diagnostics/2026-07-26"; p.parent.mkdir(parents=True); e.mkdir(parents=True); shutil.copy2(PLAN,p)
                for f in EVIDENCE.iterdir(): shutil.copy2(f,e/f.name)
                target=e/filename; payload=json.loads(target.read_text()); mutate(payload); target.write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n")
                manifest=json.loads((e/"manifest.json").read_text());
                for ent in manifest["files"]:
                    if ent["path"]==filename: ent.update(bytes=target.stat().st_size,sha256=d.sha256(target))
                (e/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
                with self.assertRaisesRegex(d.PredictorSupportError,error): d.validate_evidence(p,e)

    def test_existing_destination_guard(self):
        with self.assertRaisesRegex(d.PredictorSupportError, "publication_destination_exists"):
            d.run_production(ROOT)

    def test_full_validation_replays_upstream_and_goal023(self):
        self.assertEqual(
            d.validate_evidence(PLAN, EVIDENCE, full=True, root=ROOT),
            {"tracked_valid": True, "full_replay": True},
        )

    def test_production_validates_payloads_before_publication(self):
        payloads = {n[:-5]: json.loads((EVIDENCE / n).read_text()) for n in d.EVIDENCE_FILES}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir()
            shutil.copy2(PLAN, root / "config/predictor_support_diagnostic_plan.json")
            calls = mock.Mock(wraps=d._validate_semantics)
            with mock.patch.object(d, "compute_diagnostics", return_value=payloads), mock.patch.object(d, "_validate_semantics", calls), mock.patch.object(d, "_publish"):
                d.run_production(root)
            self.assertEqual(calls.call_count, 1)

if __name__ == "__main__": unittest.main()
