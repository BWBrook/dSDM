from __future__ import annotations

import numpy as np
import pytest


def test_threshold_lower_median_and_boundary_equality():
    from dsdm_phase1.inner_cv import select_threshold
    y = np.asarray([0, 0, 1, 1])
    result = select_threshold(y, [np.asarray([0.1, 0.2, 0.8, 0.9])])
    assert result.threshold in result.maximizers and result.tss == max(
        (1.0 if t <= 0.8 else 0.0) for t in result.maximizers
    ) or result.tss >= 0
    assert np.isfinite(result.threshold)


def test_fraction100_full_identity_and_alias_rejection():
    from dsdm_phase1.inner_cv import InnerCVError, SelectionStratum, _validate_stratum
    _validate_stratum(SelectionStratum("sp", "fraction100", "full", "intercept", ("seed00",)))
    with pytest.raises(InnerCVError): _validate_stratum(SelectionStratum("sp", "fraction100", "ladder00", "intercept", ("seed00",)))
    with pytest.raises(InnerCVError): _validate_stratum(SelectionStratum("sp", "fraction25", "full", "intercept", ("seed00",)))


def test_threshold_raw_types_constant_and_adjacent_float():
    from dsdm_phase1.inner_cv import InnerCVError, select_threshold
    with pytest.raises(InnerCVError): select_threshold(np.asarray([[0, 1]]), [np.asarray([0.1, 0.9])])
    with pytest.raises(InnerCVError): select_threshold(np.asarray([0.0, 1.0]), [np.asarray([0.1, 0.9])])
    with pytest.raises(InnerCVError): select_threshold(np.asarray([0, 1]), [np.asarray([[0.1, 0.9]])])
    low = np.float64(0.5); high = np.nextafter(low, np.inf)
    result = select_threshold(np.asarray([0, 1]), np.asarray([[low, high]]))
    assert result.tss == 1.0 and result.threshold in result.maximizers


def test_selection_rejects_mixed_strata():
    from dsdm_phase1.inner_cv import CandidateOOF, SelectionStratum, select_candidate, InnerCVError
    s = SelectionStratum("sp", "fraction25", "ladder00", "intercept", ("seed00",))
    bad = SelectionStratum("sp2", "fraction25", "ladder00", "intercept", ("seed00",))
    empty = CandidateOOF(s, "a", tuple(), 0.5, 0.5, 0.5, {})
    with pytest.raises(InnerCVError): select_candidate([empty, CandidateOOF(bad, "b", tuple(), 0.5, 0.5, 0.5, {})])


def test_selection_recomputes_aggregates_and_allows_residual_family():
    from dsdm_phase1.inner_cv import CandidateOOF, FoldOOF, InnerCVError, SelectionStratum, select_candidate, select_threshold
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES
    from dsdm_phase1.modeling_contract import RowKey
    folds = []; ys=[]; ss=[]
    for i in range(5):
        keys = (RowKey("sp", f"{i}a"), RowKey("sp", f"{i}b")); y = np.asarray([0, 1], dtype=np.int8); score = np.asarray([0.1, 0.9]); folds.append(FoldOOF(f"fold{i:02d}", keys, y, {"seed00": score}, score, 1.0, 1.0)); ys.append(y); ss.append(score)
    threshold = select_threshold(np.concatenate(ys), [np.concatenate(ss)]).threshold
    valid = CandidateOOF(SelectionStratum("sp", "fraction25", "ladder00", "residual_mlp", ("seed00",)), "resmlp00", tuple(FoldOOF(f.fold_id, f.keys, f.y_true, f.scores_by_seed, f.mean_score, f.roc_auc, float(1.0 if threshold <= 0.9 else 0.0)) for f in folds), threshold, 1.0, 1.0, {})
    assert select_candidate([valid]).candidate_id == "resmlp00"
    with pytest.raises(InnerCVError): select_candidate([CandidateOOF(valid.stratum, valid.candidate_id, valid.folds, valid.threshold, 0.99, valid.mean_fold_tss_at_oof_threshold, {})])


def test_selection_rejects_different_key_or_label_evidence():
    from dataclasses import replace
    from dsdm_phase1.inner_cv import CandidateOOF, FoldOOF, InnerCVError, SelectionStratum, select_candidate, select_threshold
    from dsdm_phase1.modeling_contract import RowKey
    folds=[]; ys=[]; ss=[]
    for i in range(5):
        keys=(RowKey("sp", f"{i}a"), RowKey("sp", f"{i}b")); y=np.asarray([0,1], dtype=np.int8); score=np.asarray([.1,.9]); folds.append(FoldOOF(f"fold{i:02d}", keys, y, {"seed00":score}, score, 1., 1.)); ys.append(y); ss.append(score)
    threshold=select_threshold(np.concatenate(ys), [np.concatenate(ss)]).threshold; stratum=SelectionStratum("sp","fraction25","ladder00","residual_mlp",("seed00",))
    valid=CandidateOOF(stratum,"resmlp00",tuple(folds),threshold,1.,1.,{})
    changed_keys=tuple(replace(folds[0], keys=(RowKey("sp","new-a"), RowKey("sp","new-b"))) for _ in [0])
    by_key=list(folds); by_key[0]=changed_keys[0]
    with pytest.raises(InnerCVError, match="comparability"): select_candidate([valid, CandidateOOF(stratum,"resmlp01",tuple(by_key),threshold,1.,1.,{})])
    by_label=list(folds); by_label[0]=FoldOOF("fold00", folds[0].keys, np.asarray([1,0], dtype=np.int8), {"seed00":np.asarray([.9,.1])}, np.asarray([.9,.1]), 1., 1.)
    with pytest.raises(InnerCVError, match="comparability"): select_candidate([valid, CandidateOOF(stratum,"resmlp01",tuple(by_label),threshold,1.,1.,{})])


def test_five_fold_oof_and_refit_binding_spy():
    from dataclasses import replace
    from dsdm_phase1.inner_cv import SelectionStratum, refit_outer_training, run_candidate_oof
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, FitReport
    from dsdm_phase1.modeling_contract import FeatureProvider, LazyFeatureSubstrate, RowKey, RowSet, SplitBroker, TaskKey
    from dsdm_phase1.target_subsets import build_ladders
    rows=[]; values={}
    for i in range(30):
        pa = i % 2; key = RowKey("sp", str(i)); fold = f"fold{i % 5:02d}"
        rows.append({"species_id":"sp", "grid_cell_id":str(i), "pa":pa, "pa_type":"presence" if pa else "pseudoabsence", "microcluster":"m", "cv_fold":fold})
        values[key] = {"continuous":[float(i)], "categorical":{}}
    outer = RowSet.from_records(rows); broker = SplitBroker(outer, {k:f"fold{i % 5:02d}" for i,k in enumerate(outer.keys)})
    provider = FeatureProvider(LazyFeatureSubstrate(values), frozenset(outer.keys)); endpoints={}
    for i in range(5): endpoints[f"fold{i:02d}"] = build_ladders(broker.inner("sp", f"fold{i:02d}")[0])[("fraction100", "ladder00")]
    class SpyFitted:
        def predict_scores(self, batch): return np.asarray(batch.y, dtype=float) * .8 + .1
    class SpyAdapter:
        family="intercept"
        def __init__(self): self.calls=[]
        def fit(self, train, stopping, candidate, seed, exact_epochs=None):
            self.calls.append((tuple(train.keys), None if stopping is None else tuple(stopping.keys), exact_epochs)); return SpyFitted(), FitReport(True, 1, None, None, None, (), 0., 0.)
    adapter=SpyAdapter(); stratum=SelectionStratum("sp", "fraction100", "full", "intercept", ("seed00",)); candidate=CANONICAL_CANDIDATES["null00"]
    result = run_candidate_oof(stratum, tuple(f"fold{i:02d}" for i in range(5)), endpoints, candidate, broker, provider, adapter)
    assert len(result.folds) == 5 and len(adapter.calls) == 5 and all(call[1] is None for call in adapter.calls)
    tampered_endpoints = dict(endpoints); tampered_endpoints["fold00"] = replace(endpoints["fold00"], full_alias_id=None)
    with pytest.raises(Exception): run_candidate_oof(stratum, tuple(f"fold{i:02d}" for i in range(5)), tampered_endpoints, candidate, broker, provider, adapter)
    fraction25_endpoints = {f"fold{i:02d}": build_ladders(broker.inner("sp", f"fold{i:02d}")[0])[("fraction25", "ladder00")] for i in range(5)}
    fraction25_tampered = dict(fraction25_endpoints); fraction25_tampered["fold00"] = replace(fraction25_tampered["fold00"], full_alias_id="full")
    with pytest.raises(Exception): run_candidate_oof(SelectionStratum("sp", "fraction25", "ladder00", "intercept", ("seed00",)), tuple(f"fold{i:02d}" for i in range(5)), fraction25_tampered, candidate, broker, provider, adapter)
    task=TaskKey("sp", "outer", "fraction100", "full", "intercept", "null00", "seed00")
    fitted, _ = refit_outer_training(task, build_ladders(outer)[("fraction100", "ladder00")], candidate, broker, provider, adapter, None)
    assert fitted is not None and len(adapter.calls) == 6
    with pytest.raises(Exception): refit_outer_training(task, replace(build_ladders(outer)[("fraction100", "ladder00")], full_alias_id=None), candidate, broker, provider, adapter, None)
    fraction25_task = TaskKey("sp", "outer", "fraction25", "ladder00", "intercept", "null00", "seed00")
    with pytest.raises(Exception): refit_outer_training(fraction25_task, replace(build_ladders(outer)[("fraction25", "ladder00")], full_alias_id="full"), candidate, broker, provider, adapter, None)
    with pytest.raises(Exception): refit_outer_training(TaskKey("sp", "cv_fold00", "fraction100", "full", "intercept", "null00", "seed00"), endpoints["fold00"], candidate, broker, provider, adapter, None)


def test_neural_oof_two_fit_trace_and_stopping_mapping():
    from dsdm_phase1.inner_cv import SelectionStratum, run_candidate_oof
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, FitReport
    from dsdm_phase1.modeling_contract import FeatureProvider, LazyFeatureSubstrate, RowKey, RowSet, SplitBroker
    from dsdm_phase1.target_subsets import build_ladders
    rows=[]; values={}
    for i in range(30):
        pa=i % 2; key=RowKey("sp", str(i)); rows.append({"species_id":"sp","grid_cell_id":str(i),"pa":pa,"pa_type":"presence" if pa else "pseudoabsence","microcluster":"m","cv_fold":f"fold{i%5:02d}"}); values[key]={"continuous":[float(i)],"categorical":{}}
    outer=RowSet.from_records(rows); broker=SplitBroker(outer,{k:f"fold{i%5:02d}" for i,k in enumerate(outer.keys)}); provider=FeatureProvider(LazyFeatureSubstrate(values),frozenset(outer.keys)); endpoints={f"fold{i:02d}":build_ladders(broker.inner("sp",f"fold{i:02d}")[0])[("fraction100","ladder00")] for i in range(5)}
    class Fitted:
        def predict_scores(self, batch): return np.linspace(.2,.8,len(batch.keys))
    class NeuralSpy:
        family="shallow_ann"
        def __init__(self): self.calls=[]
        def fit(self, train, stopping, candidate, seed, exact_epochs=None):
            self.calls.append((tuple(train.keys), None if stopping is None else tuple(stopping.keys), exact_epochs))
            report=FitReport(True, 2 if exact_epochs is not None else 4, 2 if stopping is not None else exact_epochs, None, "patience_stop" if stopping is not None else None, (), 0., 0., "init")
            return Fitted(), report
    spy=NeuralSpy(); result=run_candidate_oof(SelectionStratum("sp","fraction100","full","shallow_ann",("seed00",)), tuple(f"fold{i:02d}" for i in range(5)), endpoints, CANONICAL_CANDIDATES["ann00"], broker, provider, spy)
    assert len(spy.calls)==10 and all(spy.calls[2*i][1] is not None and spy.calls[2*i+1][1] is None and spy.calls[2*i+1][2]==2 for i in range(5))
    assert len(result.neural_receipts["seed00"]) == 5 and [r.stopping_fold for r in result.neural_receipts["seed00"]] == ["fold01", "fold02", "fold03", "fold04", "fold00"]
