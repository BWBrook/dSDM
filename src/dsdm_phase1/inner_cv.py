"""Leakage-safe inner OOF assembly, thresholding, and full-training refits."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.metrics import roc_auc_score

from .model_adapters import CANONICAL_CANDIDATES, FitReport, FittedAdapter, ModelAdapter, ModelAdapterError, validate_candidate
from .modeling_contract import FeatureBatch, FeatureProvider, ModelingContractError, RowKey, RowSet, SplitBroker, TaskKey, derive_seed
from .target_subsets import SubsetEndpoint, build_ladders


class InnerCVError(ModelingContractError):
    pass


@dataclass(frozen=True)
class FoldOOF:
    fold_id: str
    keys: tuple[RowKey, ...]
    y_true: np.ndarray
    scores_by_seed: Mapping[str, np.ndarray]
    mean_score: np.ndarray
    roc_auc: float
    tss_at_oof_threshold: float | None


@dataclass(frozen=True)
class SelectionStratum:
    species_id: str
    fraction_id: str
    ladder_id: str
    model_family: str
    ordered_selection_seeds: tuple[str, ...]


@dataclass(frozen=True)
class NeuralFoldReceipt:
    task: TaskKey
    stopping_fold: str
    best_epoch: int
    discovery_report: FitReport
    replay_report: FitReport
    discovery_initial_state_digest: str
    replay_initial_state_digest: str


@dataclass(frozen=True)
class FoldEpochs:
    stratum: SelectionStratum
    candidate_id: str
    seed_label: str
    best_epochs_by_fold: tuple[int, int, int, int, int]
    receipts: tuple[NeuralFoldReceipt, ...] = ()


@dataclass(frozen=True)
class CandidateOOF:
    stratum: SelectionStratum
    candidate_id: str
    folds: tuple[FoldOOF, ...]
    threshold: float
    mean_fold_roc_auc: float
    mean_fold_tss_at_oof_threshold: float
    neural_epochs_by_seed: Mapping[str, FoldEpochs]
    neural_receipts: Mapping[str, tuple[NeuralFoldReceipt, ...]] = field(default_factory=dict)
    fit_reports_by_seed: Mapping[str, tuple[FitReport, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    maximizers: tuple[float, ...]
    tss: float
    balanced_accuracy: float


def _rowset_for_keys(rows: RowSet, keys: Sequence[RowKey]) -> RowSet:
    wanted = tuple(keys); lookup = {k: i for i, k in enumerate(rows.keys)}
    if len(set(wanted)) != len(wanted) or any(k not in lookup for k in wanted): raise InnerCVError("endpoint_key_not_in_training")
    return rows.take([lookup[k] for k in wanted])


def _validate_stratum(s: SelectionStratum) -> None:
    canonical_seeds = tuple(f"seed{i:02d}" for i in range(5))
    selected_seeds = tuple(s.ordered_selection_seeds) if isinstance(s, SelectionStratum) else ()
    if (
        not isinstance(s, SelectionStratum)
        or not s.species_id
        or not s.fraction_id
        or not s.ladder_id
        or not s.model_family
        or not selected_seeds
        or len(set(selected_seeds)) != len(selected_seeds)
        or any(seed not in canonical_seeds for seed in selected_seeds)
        or selected_seeds != tuple(seed for seed in canonical_seeds if seed in selected_seeds)
    ):
        raise InnerCVError("selection_stratum_invalid")
    if s.fraction_id in {"fraction25", "fraction50"} and s.ladder_id not in {"ladder00", "ladder01", "ladder02"}:
        raise InnerCVError("selection_stratum_endpoint_invalid")
    if s.fraction_id == "fraction100" and s.ladder_id != "full":
        raise InnerCVError("selection_stratum_endpoint_invalid")
    if s.fraction_id not in {"fraction25", "fraction50", "fraction100"}:
        raise InnerCVError("selection_stratum_endpoint_invalid")


def _canonical_endpoint(endpoints: Mapping[tuple[str, str], SubsetEndpoint], fraction_id: str, ladder_id: str) -> SubsetEndpoint:
    lookup_ladder = "ladder00" if fraction_id == "fraction100" else ladder_id
    expected = endpoints.get((fraction_id, lookup_ladder))
    if expected is None: raise InnerCVError("endpoint_semantics_mismatch")
    if fraction_id == "fraction100":
        if expected.fraction_id != "fraction100" or expected.ladder_id != "full" or expected.full_alias_id != "full": raise InnerCVError("endpoint_canonical_identity_invalid")
    elif expected.fraction_id != fraction_id or expected.ladder_id != ladder_id or expected.full_alias_id is not None:
        raise InnerCVError("endpoint_canonical_identity_invalid")
    return expected


def _validate_endpoints(folds: Sequence[str], endpoints: Mapping[str, SubsetEndpoint]) -> None:
    expected = tuple(f"fold{i:02d}" for i in range(5))
    if tuple(folds) != expected or set(endpoints) != set(expected): raise InnerCVError("fold_endpoint_keys_mismatch")
    for fold in expected:
        e = endpoints[fold]
        if not isinstance(e, SubsetEndpoint): raise InnerCVError("endpoint_invalid")


def _tss(y: np.ndarray, score: np.ndarray, threshold: float) -> float:
    positive = score >= threshold; y = np.asarray(y, dtype=np.int8)
    tp = np.sum(positive & (y == 1)); fn = np.sum(~positive & (y == 1)); tn = np.sum(~positive & (y == 0)); fp = np.sum(positive & (y == 0))
    if tp + fn == 0 or tn + fp == 0: raise InnerCVError("single_class_threshold_data")
    return float(tp / (tp + fn) + tn / (tn + fp) - 1.0)


def select_threshold(y_true: np.ndarray, seed_scores: Sequence[np.ndarray]) -> ThresholdResult:
    raw_y = np.asarray(y_true)
    if raw_y.ndim != 1 or raw_y.dtype.kind not in "iu" or raw_y.dtype.kind == "b" or len(raw_y) == 0 or not np.isin(raw_y, [0, 1]).all() or len(set(raw_y.tolist())) < 2: raise InnerCVError("threshold_class_invalid")
    y = raw_y.astype(np.int8)
    arrays = []
    for value in seed_scores:
        a = np.asarray(value)
        if a.ndim != 1 or a.dtype.kind not in "fiu" or a.dtype.kind == "b": raise InnerCVError("threshold_scores_invalid")
        a = a.astype(np.float64)
        if len(a) != len(y) or not np.isfinite(a).all() or np.any(a < 0) or np.any(a > 1): raise InnerCVError("threshold_scores_invalid")
        arrays.append(a)
    if not arrays: raise InnerCVError("threshold_scores_invalid")
    scores = np.mean(np.vstack(arrays), axis=0)
    unique = np.unique(scores)
    candidates: list[float] = [float(np.nextafter(unique[0], -np.inf)), float(np.nextafter(unique[-1], np.inf))]
    for low, high in zip(unique[:-1], unique[1:]):
        midpoint = float(low + (high - low) / 2.0)
        if not (low < midpoint < high): midpoint = float(high)
        if np.isfinite(midpoint): candidates.append(midpoint)
    candidates = sorted(set(candidates))
    values = np.asarray([_tss(y, scores, t) for t in candidates])
    max_tss = float(np.max(values)); maximizers = tuple(float(t) for t, v in zip(candidates, values) if v == max_tss)
    threshold = maximizers[(len(maximizers) - 1) // 2]
    tss = _tss(y, scores, threshold)
    if tss != max_tss: raise InnerCVError("threshold_replay_mismatch")
    pred = scores >= threshold; ba = float((np.mean(pred[y == 1]) + np.mean(~pred[y == 0])) / 2.0)
    return ThresholdResult(threshold, maximizers, tss, ba)


def run_candidate_oof(stratum: SelectionStratum, folds: Sequence[str], endpoints_by_fold: Mapping[str, SubsetEndpoint], candidate: Mapping[str, Any], broker: SplitBroker, provider: FeatureProvider, adapter: ModelAdapter) -> CandidateOOF:
    _validate_stratum(stratum); _validate_endpoints(folds, endpoints_by_fold)
    if candidate.get("family") != stratum.model_family or getattr(adapter, "family", None) != stratum.model_family: raise InnerCVError("candidate_family_stratum_mismatch")
    try: validate_candidate(stratum.model_family, candidate)
    except ModelAdapterError as exc: raise InnerCVError("candidate_not_canonical") from exc
    fold_results: list[FoldOOF] = []; epoch_records: dict[str, FoldEpochs] = {}; receipt_records: dict[str, list[NeuralFoldReceipt]] = {}; fit_reports: dict[str, list[FitReport]] = {}
    for fold in folds:
        cv_train, assessment = broker.inner(stratum.species_id, fold)
        endpoint = endpoints_by_fold[fold]
        if endpoint.fraction_id != stratum.fraction_id or endpoint.ladder_id != stratum.ladder_id: raise InnerCVError("endpoint_stratum_mismatch")
        endpoint_rows = _rowset_for_keys(cv_train, endpoint.keys)
        if len(set(endpoint_rows.pa.tolist())) < 2: raise InnerCVError("single_class_endpoint")
        # Fit one encoder on complete E_v, then reuse for every neural sub-batch.
        expected_endpoint = _canonical_endpoint(build_ladders(cv_train), stratum.fraction_id, stratum.ladder_id)
        if endpoint != expected_endpoint:
            raise InnerCVError("endpoint_semantics_mismatch")
        transform_id = f"cv_{fold}"
        encoder = provider.fit_encoder(endpoint_rows, stratum.model_family, transform_id)
        full_batch = provider.materialize(endpoint_rows, transform_id, encoder)
        assessment_batch = provider.materialize(assessment, transform_id, encoder)
        if len(set(assessment.pa.tolist())) < 2: raise InnerCVError("single_class_assessment")
        scores_by_seed: dict[str, np.ndarray] = {}; epochs_for_fold: dict[str, int] = {}
        for seed_label in stratum.ordered_selection_seeds:
            task = TaskKey(stratum.species_id, transform_id, stratum.fraction_id, stratum.ladder_id, stratum.model_family, str(candidate["id"]), seed_label)
            seed = derive_seed(task, "fit")
            if stratum.model_family in {"shallow_ann", "residual_mlp"}:
                stop_fold = f"fold{(int(fold[-2:]) + 1) % 5:02d}"
                stop_rows = _rowset_for_keys(endpoint_rows, [k for k in endpoint_rows.keys if broker._fold_by_key[k] == stop_fold])
                discovery_rows = _rowset_for_keys(endpoint_rows, [k for k in endpoint_rows.keys if broker._fold_by_key[k] not in {fold, stop_fold}])
                if not len(stop_rows.keys) or not len(discovery_rows.keys) or len(set(stop_rows.pa.tolist())) < 2 or len(set(discovery_rows.pa.tolist())) < 2: raise InnerCVError("neural_stopping_split_invalid")
                discovery = provider.materialize(discovery_rows, transform_id, encoder); stopping = provider.materialize(stop_rows, transform_id, encoder)
                discovered, report = adapter.fit(discovery, stopping, candidate, seed)
                report = replace(report, stopping_fold=stop_fold)
                if report.best_epoch is None: raise InnerCVError("neural_best_epoch_missing")
                epochs_for_fold[seed_label] = int(report.best_epoch)
                discovery_initial = report.initial_state_digest
                del discovered
                replay, replay_report = adapter.fit(full_batch, None, candidate, seed, exact_epochs=int(report.best_epoch))
                if replay_report.stopping_fold is not None or replay_report.iterations != int(report.best_epoch) or discovery_initial is None or replay_report.initial_state_digest is None or discovery_initial != replay_report.initial_state_digest:
                    raise InnerCVError("neural_replay_receipt_mismatch")
                receipt_records.setdefault(seed_label, []).append(NeuralFoldReceipt(task, stop_fold, int(report.best_epoch), report, replay_report, discovery_initial, replay_report.initial_state_digest))
                fit_reports.setdefault(seed_label, []).extend((report, replay_report))
                scores_by_seed[seed_label] = replay.predict_scores(assessment_batch)
            else:
                fitted, report = adapter.fit(full_batch, None, candidate, seed)
                fit_reports.setdefault(seed_label, []).append(report)
                scores_by_seed[seed_label] = fitted.predict_scores(assessment_batch)
        mean_score = np.mean(np.vstack([scores_by_seed[s] for s in stratum.ordered_selection_seeds]), axis=0)
        if not np.isfinite(mean_score).all() or len(mean_score) != len(assessment.keys): raise InnerCVError("oof_score_invalid")
        try: auc = float(roc_auc_score(assessment.pa, mean_score))
        except ValueError as exc: raise InnerCVError("single_class_assessment") from exc
        fold_results.append(FoldOOF(fold, tuple(assessment.keys), assessment.pa.copy(), scores_by_seed, mean_score, auc, None))
        if epochs_for_fold:
            for seed_label in epochs_for_fold:
                prev = epoch_records.get(seed_label)
                values = list(prev.best_epochs_by_fold) if prev else [0] * 5
                values[int(fold[-2:])] = epochs_for_fold[seed_label]
                epoch_records[seed_label] = FoldEpochs(stratum, str(candidate["id"]), seed_label, tuple(values), tuple(receipt_records.get(seed_label, ())))
    expected_keys = set(broker.outer_training(stratum.species_id).keys); observed_keys: set[RowKey] = set()
    for result in fold_results:
        if set(result.keys) & observed_keys or len(result.keys) != len(set(result.keys)): raise InnerCVError("oof_duplicate_or_fold_overlap")
        if not np.isin(result.y_true, [0, 1]).all() or len(result.y_true) != len(result.keys): raise InnerCVError("oof_label_invalid")
        if set(result.scores_by_seed) != set(stratum.ordered_selection_seeds): raise InnerCVError("oof_seed_keys_mismatch")
        for values in result.scores_by_seed.values():
            if len(values) != len(result.keys) or not np.isfinite(values).all() or np.any(values < 0) or np.any(values > 1): raise InnerCVError("oof_scores_invalid")
        observed_keys.update(result.keys)
    if observed_keys != expected_keys: raise InnerCVError("oof_coverage_mismatch")
    all_y = np.concatenate([f.y_true for f in fold_results]); all_scores = [np.concatenate([f.scores_by_seed[s] for f in fold_results]) for s in stratum.ordered_selection_seeds]
    threshold_result = select_threshold(all_y, all_scores)
    final_folds = tuple(FoldOOF(f.fold_id, f.keys, f.y_true, f.scores_by_seed, f.mean_score, f.roc_auc, _tss(f.y_true, f.mean_score, threshold_result.threshold)) for f in fold_results)
    return CandidateOOF(
        stratum,
        str(candidate["id"]),
        final_folds,
        threshold_result.threshold,
        float(np.mean([f.roc_auc for f in final_folds])),
        float(np.mean([f.tss_at_oof_threshold for f in final_folds])),
        epoch_records,
        {k: tuple(v) for k, v in receipt_records.items()},
        {k: tuple(v) for k, v in fit_reports.items()},
    )


def select_candidate(results: Sequence[CandidateOOF]) -> CandidateOOF:
    if not results: raise InnerCVError("no_candidate_results")
    comparison_reference = None
    for result in results:
        _validate_stratum(result.stratum)
        canonical = CANONICAL_CANDIDATES.get(result.candidate_id)
        if canonical is None or canonical.get("family") != result.stratum.model_family: raise InnerCVError("candidate_not_canonical")
        try: validate_candidate(result.stratum.model_family, canonical)
        except ModelAdapterError as exc: raise InnerCVError("candidate_not_canonical") from exc
        if not result.folds or len(result.folds) != 5: raise InnerCVError("candidate_fold_count_invalid")
        if not np.isfinite(result.threshold): raise InnerCVError("candidate_metrics_invalid")
        seen: set[RowKey] = set(); fold_ids: set[str] = set(); all_y: list[np.ndarray] = []; all_scores = {s: [] for s in result.stratum.ordered_selection_seeds}; fold_auc: list[float] = []; fold_tss: list[float] = []
        for fold in result.folds:
            if fold.fold_id in fold_ids or set(fold.keys) & seen or len(fold.keys) != len(set(fold.keys)): raise InnerCVError("candidate_oof_overlap")
            fold_ids.add(fold.fold_id)
            seen.update(fold.keys)
            if fold.fold_id not in {f"fold{i:02d}" for i in range(5)} or not np.isfinite(fold.roc_auc) or fold.tss_at_oof_threshold is None or not np.isfinite(fold.tss_at_oof_threshold): raise InnerCVError("candidate_fold_metric_invalid")
            if fold.y_true.ndim != 1 or fold.y_true.dtype.kind not in "iu" or not np.isin(fold.y_true, [0,1]).all(): raise InnerCVError("candidate_labels_invalid")
            if fold.mean_score.ndim != 1 or len(fold.mean_score) != len(fold.keys): raise InnerCVError("candidate_mean_score_invalid")
            if set(fold.scores_by_seed) != set(result.stratum.ordered_selection_seeds): raise InnerCVError("candidate_seed_keys_invalid")
            for seed, values in fold.scores_by_seed.items():
                values = np.asarray(values)
                if values.ndim != 1 or len(values) != len(fold.keys) or not np.isfinite(values).all() or np.any(values < 0) or np.any(values > 1): raise InnerCVError("candidate_scores_invalid")
                all_scores[seed].append(values)
            recomputed_mean = np.mean(np.vstack([fold.scores_by_seed[s] for s in result.stratum.ordered_selection_seeds]), axis=0)
            if not np.allclose(recomputed_mean, fold.mean_score, rtol=0, atol=1e-12): raise InnerCVError("candidate_mean_score_mismatch")
            try: expected_auc = float(roc_auc_score(fold.y_true, fold.mean_score))
            except ValueError as exc: raise InnerCVError("candidate_fold_class_invalid") from exc
            expected_tss = _tss(fold.y_true, fold.mean_score, result.threshold)
            if not np.isclose(expected_auc, fold.roc_auc, rtol=0, atol=1e-12) or not np.isclose(expected_tss, fold.tss_at_oof_threshold, rtol=0, atol=1e-12): raise InnerCVError("candidate_fold_metric_mismatch")
            all_y.append(fold.y_true); fold_auc.append(expected_auc); fold_tss.append(expected_tss)
        if fold_ids != {f"fold{i:02d}" for i in range(5)}: raise InnerCVError("candidate_fold_ids_invalid")
        threshold_result = select_threshold(np.concatenate(all_y), [np.concatenate(all_scores[s]) for s in result.stratum.ordered_selection_seeds])
        if not np.isclose(result.threshold, threshold_result.threshold, rtol=0, atol=1e-12): raise InnerCVError("candidate_threshold_mismatch")
        if not np.isclose(result.mean_fold_roc_auc, np.mean(fold_auc), rtol=0, atol=1e-12) or not np.isclose(result.mean_fold_tss_at_oof_threshold, np.mean(fold_tss), rtol=0, atol=1e-12): raise InnerCVError("candidate_aggregate_mismatch")
        comparison_signature = (tuple(result.stratum.ordered_selection_seeds), tuple((fold.fold_id, tuple(fold.keys), tuple(int(v) for v in fold.y_true.tolist())) for fold in result.folds))
        if comparison_reference is None:
            comparison_reference = comparison_signature
        elif comparison_signature != comparison_reference:
            raise InnerCVError("candidate_comparability_mismatch")
    first = results[0].stratum
    if any(r.stratum != first for r in results): raise InnerCVError("selection_stratum_mismatch")
    return sorted(results, key=lambda r: (-r.mean_fold_roc_auc, -r.mean_fold_tss_at_oof_threshold, r.candidate_id))[0]


def refit_outer_training(task: TaskKey, endpoint: SubsetEndpoint, candidate: Mapping[str, Any], broker: SplitBroker, provider: FeatureProvider, adapter: ModelAdapter, fold_epochs: FoldEpochs | None) -> tuple[FittedAdapter, FitReport]:
    canonical_seeds = tuple(f"seed{i:02d}" for i in range(5))
    if task.transform_id != "outer" or task.seed_label not in canonical_seeds or adapter.family != task.model_family: raise InnerCVError("outer_task_binding_mismatch")
    if not isinstance(endpoint, SubsetEndpoint): raise InnerCVError("outer_endpoint_invalid")
    canonical = CANONICAL_CANDIDATES.get(task.candidate_id)
    if canonical is None or canonical.get("family") != task.model_family or dict(candidate) != canonical: raise InnerCVError("outer_candidate_binding_mismatch")
    try: validate_candidate(task.model_family, candidate)
    except ModelAdapterError as exc: raise InnerCVError("outer_candidate_binding_mismatch") from exc
    outer = broker.outer_training(task.species_id)
    if task.fraction_id in {"fraction25", "fraction50"} and task.ladder_id not in {"ladder00", "ladder01", "ladder02"}: raise InnerCVError("outer_task_endpoint_invalid")
    if task.fraction_id == "fraction100" and task.ladder_id != "full": raise InnerCVError("outer_task_endpoint_invalid")
    if task.fraction_id not in {"fraction25", "fraction50", "fraction100"}: raise InnerCVError("outer_task_endpoint_invalid")
    expected_map = build_ladders(outer)
    expected = _canonical_endpoint(expected_map, task.fraction_id, task.ladder_id)
    if endpoint != expected: raise InnerCVError("outer_endpoint_semantics_mismatch")
    endpoint_rows = _rowset_for_keys(outer, endpoint.keys)
    encoder = provider.fit_encoder(endpoint_rows, task.model_family, "outer")
    batch = provider.materialize(endpoint_rows, "outer", encoder)
    if task.model_family in {"shallow_ann", "residual_mlp"}:
        if fold_epochs is None or fold_epochs.stratum.species_id != task.species_id or fold_epochs.stratum.fraction_id != task.fraction_id or fold_epochs.stratum.ladder_id != task.ladder_id or fold_epochs.stratum.model_family != task.model_family or fold_epochs.stratum.ordered_selection_seeds != (task.seed_label,) or fold_epochs.candidate_id != task.candidate_id or fold_epochs.seed_label != task.seed_label or len(fold_epochs.best_epochs_by_fold) != 5 or any(type(v) is not int or v < 1 or v > 300 for v in fold_epochs.best_epochs_by_fold) or len(fold_epochs.receipts) != 5:
            raise InnerCVError("fold_epoch_provenance_mismatch")
        for index, receipt in enumerate(fold_epochs.receipts):
            if receipt.task.species_id != task.species_id or receipt.task.fraction_id != task.fraction_id or receipt.task.ladder_id != task.ladder_id or receipt.task.model_family != task.model_family or receipt.task.candidate_id != task.candidate_id or receipt.task.seed_label != task.seed_label or receipt.task.transform_id != f"cv_fold{index:02d}" or receipt.stopping_fold != f"fold{(index + 1) % 5:02d}" or receipt.best_epoch != fold_epochs.best_epochs_by_fold[index] or receipt.discovery_initial_state_digest != receipt.replay_initial_state_digest:
                raise InnerCVError("fold_epoch_receipt_mismatch")
        epochs = sorted(fold_epochs.best_epochs_by_fold)[2]
        return adapter.fit(batch, None, candidate, derive_seed(task, "fit"), exact_epochs=epochs)
    if fold_epochs is not None: raise InnerCVError("conventional_fold_epochs_forbidden")
    return adapter.fit(batch, None, candidate, derive_seed(task, "fit"))


def replay_predictions(model_path: Path, batch: FeatureBatch, expected: np.ndarray, atol: float, expected_model_sha256: str) -> None:
    from .model_adapters import load_fitted_model
    model = load_fitted_model(model_path, expected_model_sha256)
    actual = model.predict_scores(batch); expected = np.asarray(expected, dtype=np.float64).reshape(-1)
    if actual.shape != expected.shape or not np.allclose(actual, expected, rtol=0.0, atol=atol): raise InnerCVError("semantic_replay_mismatch")
