from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def _foundation(species: str = "thylogale_billardierii", n: int = 100):
    from dsdm_phase1.modeling_contract import (
        FeatureProvider,
        LazyFeatureSubstrate,
        RowKey,
        RowSet,
        SplitBroker,
    )

    rows = []
    values = {}
    folds = {}
    for index in range(n):
        key = RowKey(species, f"cell{index:03d}")
        pa_value = index % 2
        rows.append(
            {
                "species_id": species,
                "grid_cell_id": key.grid_cell_id,
                "pa": pa_value,
                "pa_type": "presence" if pa_value else "pseudoabsence",
                "microcluster": f"m{index % 11:02d}",
            }
        )
        values[key] = {
            "continuous": [float(index), float(index % 7), float(index % 13)],
            "categorical": {"soil": f"s{index % 3}"},
        }
        folds[key] = f"fold{index % 5:02d}"
    rowset = RowSet.from_records(rows)
    return (
        SplitBroker(rowset, folds),
        FeatureProvider(LazyFeatureSubstrate(values), frozenset(rowset.keys)),
    )


def _catalog(candidate: str = "enet00"):
    from dsdm.predictor_sensitivity_conventional import (
        ConventionalControlCatalog,
        FAMILIES,
    )
    from dsdm_phase1.goal029_production import ENDPOINTS, SEEDS_BY_FAMILY, SPECIES

    selections = {}
    keys = set()
    family_candidate = {
        "elastic_net": candidate,
        "random_forest": "rf00",
        "hist_gradient_boosting": "hgb00",
        "shallow_ann": "ann00",
    }
    for species in SPECIES:
        for fraction, ladder in ENDPOINTS:
            for family in FAMILIES:
                selected = family_candidate[family]
                selections[(species, fraction, ladder, family)] = selected
                for seed in SEEDS_BY_FAMILY[family]:
                    keys.add((species, fraction, ladder, family, selected, seed))
    return ConventionalControlCatalog(
        Path("unused.parquet"),
        Path("unused.json"),
        {"manifest_digest": "0" * 64},
        selections,
        frozenset(keys),
    )


def test_stage_arithmetic_is_exact():
    from dsdm.predictor_sensitivity_conventional import stage_counts

    assert stage_counts("screen") == {
        "endpoints": 3,
        "leaves": 384,
        "fold_units": 1920,
        "physical_fits": 2520,
    }
    assert stage_counts("confirmation") == {
        "endpoints": 4,
        "leaves": 512,
        "fold_units": 2560,
        "physical_fits": 3360,
    }


def test_plan_freezes_selected_candidate_per_stratum():
    from dsdm.predictor_sensitivity_conventional import build_conventional_plan

    catalog = _catalog("enet09")
    plan = build_conventional_plan(catalog, "screen")
    elastic = [leaf for leaf in plan if leaf.model_family == "elastic_net"]
    assert len(plan) == 384
    assert elastic and {leaf.candidate_id for leaf in elastic} == {"enet09"}


def test_analysis_plan_reuses_only_screen_full_endpoint_for_confirmation():
    from dsdm.predictor_sensitivity_conventional import (
        build_conventional_analysis_plan,
    )

    catalog = _catalog()
    screen = build_conventional_analysis_plan(catalog, "screen")
    confirmation = build_conventional_analysis_plan(catalog, "confirmation")

    assert len(screen) == 384
    assert len(confirmation) == 640
    assert len(set(confirmation)) == 640
    assert {leaf.endpoint for leaf in confirmation} == {
        "fraction25/ladder01",
        "fraction25/ladder02",
        "fraction50/ladder01",
        "fraction50/ladder02",
        "fraction100/full",
    }
    assert sum(leaf.endpoint == "fraction100/full" for leaf in confirmation) == 128


def test_integrated_canary_runs_all_four_families_full_and_twice_reduced(
    monkeypatch,
):
    from dsdm import predictor_sensitivity as sensitivity
    import dsdm.predictor_sensitivity_conventional as conventional

    catalog = _catalog()
    full_provider = object()
    reduced_provider = object()
    calls = []

    def run_selected(_catalog, leaf, _broker, provider, *, goal029_config):
        calls.append((leaf.model_family, provider))
        return SimpleNamespace(leaf=leaf, candidate_id=leaf.candidate_id)

    def load_control(_catalog, leaf):
        return SimpleNamespace(
            leaf=leaf, row_identity_digest=f"rows-{leaf.model_family}"
        )

    monkeypatch.setattr(conventional, "run_selected_leaf", run_selected)
    monkeypatch.setattr(conventional, "load_control_leaf", load_control)
    monkeypatch.setattr(
        conventional,
        "compare_result_to_control",
        lambda result, control, *, atol: {
            "leaf": {"model_family": result.leaf.model_family},
            "maximum_abs_difference": 0.0,
            "tolerance": atol,
            "receipt_digest": f"full-{result.leaf.model_family}",
        },
    )
    monkeypatch.setattr(
        conventional,
        "compare_reduced_repeats",
        lambda first, second: {
            "row_identity_digest": f"rows-{first.leaf.model_family}",
            "prediction_digest": f"reduced-{first.leaf.model_family}",
            "receipt_digest": f"repeat-{first.leaf.model_family}",
        },
    )
    monkeypatch.setattr(
        conventional,
        "validate_full28_canary_receipts",
        lambda receipts: {"replays": len(receipts), "receipt_digest": "replays"},
    )
    config = SimpleNamespace(
        raw={
            "config_digest": "1" * 64,
            "execution_sources": {"source": {"sha256": "2" * 64}},
            "conventional": {"full28_replay_atol": 0.0},
        }
    )
    audit = {
        "primary": {
            f"fold{index:02d}": {"mask_digest": f"{index}" * 64}
            for index in range(5)
        }
    }

    receipt = sensitivity._run_conventional_canary(
        config,
        audit,
        catalog,
        {},
        object(),
        full_provider,
        reduced_provider,
    )

    assert receipt["family_count"] == 4
    assert receipt["full28_replays"] == 4
    assert receipt["reduced_repeat_fits"] == 8
    assert {row["family"] for row in receipt["families"]} == set(
        conventional.FAMILIES
    )
    assert sum(provider is full_provider for _, provider in calls) == 4
    assert sum(provider is reduced_provider for _, provider in calls) == 8


def test_zeroed_provider_preserves_rows_schema_and_categories():
    from dsdm.predictor_sensitivity_conventional import ZeroedContinuousProvider

    broker, provider = _foundation()
    training, assessment = broker.inner("thylogale_billardierii", "fold00")
    encoder = provider.fit_encoder(training, "elastic_net", "cv_fold00")
    original = provider.materialize(assessment, "cv_fold00", encoder)
    excluded = {fold: (("continuous_01", 2) if fold == "fold00" else (0,)) for fold in (f"fold{i:02d}" for i in range(5))}
    reduced_provider = ZeroedContinuousProvider(provider, excluded)
    reduced = reduced_provider.materialize(assessment, "cv_fold00", encoder)

    assert reduced.keys == original.keys
    assert np.array_equal(reduced.y, original.y)
    assert reduced.feature_names == original.feature_names
    assert reduced.feature_kinds == original.feature_kinds
    assert reduced.feature_schema_digest == original.feature_schema_digest
    assert reduced.transform_digest == original.transform_digest
    assert reduced.encoder_digest == original.encoder_digest
    assert reduced.x.shape == original.x.shape
    assert np.array_equal(reduced.x[:, 0], original.x[:, 0])
    assert np.all(reduced.x[:, [1, 2]] == 0)
    assert np.array_equal(reduced.x[:, 3:], original.x[:, 3:])


def test_selected_leaf_replay_preserves_task_seeds_and_is_deterministic():
    from dsdm.predictor_sensitivity_conventional import (
        ConventionalLeaf,
        ZeroedContinuousProvider,
        compare_reduced_repeats,
        run_selected_leaf,
    )
    from dsdm_phase1.modeling_contract import TaskKey, derive_seed

    broker, provider = _foundation()
    catalog = _catalog("enet00")
    leaf = ConventionalLeaf(
        "thylogale_billardierii",
        "fraction100",
        "full",
        "hist_gradient_boosting",
        "hgb00",
        "seed00",
    )
    masks = {fold: ("continuous_02",) for fold in (f"fold{i:02d}" for i in range(5))}
    wrapped = ZeroedContinuousProvider(provider, masks)
    first = run_selected_leaf(catalog, leaf, broker, wrapped)
    second = run_selected_leaf(catalog, leaf, broker, wrapped)

    assert first.stratum.ordered_selection_seeds == ("seed00",)
    assert [fold.fold_id for fold in first.folds] == [f"fold{i:02d}" for i in range(5)]
    assert [fold.keys for fold in first.folds] == [fold.keys for fold in second.folds]
    receipt = compare_reduced_repeats(first, second)
    assert receipt["exact"] is True
    task = TaskKey(
        leaf.species_id,
        "cv_fold00",
        leaf.fraction_id,
        leaf.ladder_id,
        leaf.model_family,
        leaf.candidate_id,
        leaf.seed_label,
    )
    assert leaf.task("fold00") == task
    assert derive_seed(leaf.task("fold00"), "fit") == derive_seed(task, "fit")


def _write_synthetic_control(tmp_path: Path):
    from dsdm.predictor_sensitivity_conventional import (
        ALL_CONTROL_FAMILIES,
        PRODUCER_COMMIT,
        EXPECTED_PRIVATE_CORE_MANIFEST,
        digest_value,
        sha256_file,
    )
    from dsdm_phase1.goal029_production import ENDPOINTS, SEEDS_BY_FAMILY, SPECIES

    candidate = {
        "intercept": "null00",
        "elastic_net": "enet00",
        "random_forest": "rf00",
        "hist_gradient_boosting": "hgb00",
        "shallow_ann": "ann00",
    }
    rows = {name: [] for name in (
        "species_id", "fraction_id", "ladder_id", "model_family", "candidate_id",
        "seed_label", "fold_id", "row_index", "row_token", "y_true", "score",
    )}
    for species in SPECIES:
        for fraction, ladder in ENDPOINTS:
            for family in ALL_CONTROL_FAMILIES:
                for seed in SEEDS_BY_FAMILY[family]:
                    for fold_index in range(5):
                        for row_index in range(2):
                            rows["species_id"].append(species)
                            rows["fraction_id"].append(fraction)
                            rows["ladder_id"].append(ladder)
                            rows["model_family"].append(family)
                            rows["candidate_id"].append(candidate[family])
                            rows["seed_label"].append(seed)
                            rows["fold_id"].append(f"fold{fold_index:02d}")
                            rows["row_index"].append(row_index)
                            rows["row_token"].append(json.dumps([species, f"c{fold_index}{row_index}"], separators=(",", ":")))
                            rows["y_true"].append(row_index)
                            rows["score"].append(0.25 + 0.5 * row_index)
    table = pa.table({
        "species_id": pa.array(rows["species_id"], pa.string()),
        "fraction_id": pa.array(rows["fraction_id"], pa.string()),
        "ladder_id": pa.array(rows["ladder_id"], pa.string()),
        "model_family": pa.array(rows["model_family"], pa.string()),
        "candidate_id": pa.array(rows["candidate_id"], pa.string()),
        "seed_label": pa.array(rows["seed_label"], pa.string()),
        "fold_id": pa.array(rows["fold_id"], pa.string()),
        "row_index": pa.array(rows["row_index"], pa.int32()),
        "row_token": pa.array(rows["row_token"], pa.string()),
        "y_true": pa.array(rows["y_true"], pa.int8()),
        "score": pa.array(rows["score"], pa.float64()),
    })
    parquet = tmp_path / "controls.parquet"
    pq.write_table(table, parquet)
    manifest = {
        "schema_version": "goal036-conventional-oof-export-v1",
        "producer_commit": PRODUCER_COMMIT,
        "private_core_manifest_sha256": EXPECTED_PRIVATE_CORE_MANIFEST,
        "selection_sha256": "1" * 64,
        "candidate_states_sha256": "2" * 64,
        "run_sha256": "3" * 64,
        "source_audit_sha256": "4" * 64,
        "family_strata": 280,
        "selected_checkpoints": 952,
        "rows": table.num_rows,
        "species": list(SPECIES),
        "endpoints": [f"{fraction}/{ladder}" for fraction, ladder in ENDPOINTS],
        "families": list(ALL_CONTROL_FAMILIES),
        "seed_count_by_family": {family: len(SEEDS_BY_FAMILY[family]) for family in ALL_CONTROL_FAMILIES},
        "row_identity_digest_by_species": {species: "5" * 64 for species in SPECIES},
        "checkpoint_inventory_digest": "6" * 64,
        "parquet_sha256": sha256_file(parquet),
        "parquet_bytes": parquet.stat().st_size,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    manifest["manifest_digest"] = digest_value(manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    return parquet, manifest_path, manifest


def test_control_catalog_validates_selection_and_loads_private_leaf(tmp_path):
    from dsdm.predictor_sensitivity_conventional import (
        ConventionalLeaf,
        load_control_leaf,
        load_full28_controls,
    )

    parquet, manifest_path, manifest = _write_synthetic_control(tmp_path)
    catalog = load_full28_controls(
        parquet,
        manifest_path,
        expected_manifest_digest=manifest["manifest_digest"],
        expected_parquet_sha256=manifest["parquet_sha256"],
    )
    assert len(catalog.selections) == 224
    assert len(catalog.leaf_keys) == 896
    leaf = ConventionalLeaf(
        "thylogale_billardierii", "fraction25", "ladder00", "elastic_net", "enet00", "seed00"
    )
    control = load_control_leaf(catalog, leaf)
    assert len(control.folds) == 5
    assert all(fold.y_true.flags.writeable is False for fold in control.folds)


def test_atomic_reduced_leaf_resume_and_corruption_fail_closed(tmp_path):
    from dsdm.predictor_sensitivity_conventional import (
        ConventionalLeaf,
        reduced_leaf_identity,
        run_selected_leaf,
        write_reduced_leaf,
        load_reduced_leaf,
        inventory_status,
    )

    broker, provider = _foundation()
    catalog = _catalog("enet00")
    leaf = ConventionalLeaf(
        "thylogale_billardierii", "fraction100", "full", "hist_gradient_boosting", "hgb00", "seed00"
    )
    result = run_selected_leaf(catalog, leaf, broker, provider)
    identity = reduced_leaf_identity(
        leaf,
        stage="screen",
        config_digest="1" * 64,
        source_fingerprint="2" * 64,
        control_manifest_digest="3" * 64,
        mask_digest_by_fold={f"fold{i:02d}": str(i) * 64 for i in range(5)},
    )
    path, reused = write_reduced_leaf(tmp_path, identity, result)
    assert reused is False
    _, reused = write_reduced_leaf(tmp_path, identity, result)
    assert reused is True
    assert load_reduced_leaf(tmp_path, identity).candidate_id == "hgb00"
    assert inventory_status(tmp_path, [identity])["complete"] == 1

    (path / "result.json").write_text("{}\n")
    with pytest.raises(Exception):
        load_reduced_leaf(tmp_path, identity)
    status = inventory_status(tmp_path, [identity])
    assert status["invalid"] == 1 and status["complete"] == 0


def test_result_control_comparison_rejects_score_drift(tmp_path):
    from dsdm.predictor_sensitivity_conventional import (
        ControlFold,
        ControlLeaf,
        ConventionalLeaf,
        compare_result_to_control,
        run_selected_leaf,
    )

    broker, provider = _foundation()
    catalog = _catalog("enet00")
    leaf = ConventionalLeaf(
        "thylogale_billardierii", "fraction100", "full", "hist_gradient_boosting", "hgb00", "seed00"
    )
    result = run_selected_leaf(catalog, leaf, broker, provider)
    folds = tuple(
        ControlFold(
            fold.fold_id,
            tuple(json.dumps([key.species_id, key.grid_cell_id], separators=(",", ":")) for key in fold.keys),
            fold.y_true.astype(np.int8),
            np.asarray(fold.scores_by_seed["seed00"], dtype=np.float64),
        )
        for fold in result.folds
    )
    control = ControlLeaf(leaf, folds, "1" * 64, "2" * 64)
    receipt = compare_result_to_control(result, control)
    assert receipt["maximum_abs_difference"] == 0.0

    changed = list(folds)
    changed_score = changed[0].scores.copy()
    changed_score[0] += 1e-4
    changed[0] = replace(changed[0], scores=changed_score)
    with pytest.raises(Exception, match="full28_replay_prediction_mismatch"):
        compare_result_to_control(result, replace(control, folds=tuple(changed)))


def test_aggregate_family_effects_is_aggregate_only_and_paired(monkeypatch):
    import dsdm.predictor_sensitivity_conventional as conventional
    from dsdm_phase1.inner_cv import CandidateOOF, FoldOOF, SelectionStratum
    from dsdm_phase1.modeling_contract import RowKey

    catalog = _catalog("enet00")
    endpoint = ("fraction100", "full")
    leaves = tuple(
        leaf
        for leaf in conventional.build_conventional_plan(catalog, "screen")
        if (leaf.fraction_id, leaf.ladder_id) == endpoint
    )
    controls = {}
    reduced = {}
    for leaf in leaves:
        control_folds = []
        result_folds = []
        for fold_index, fold in enumerate(conventional.FOLDS):
            tokens = tuple(
                json.dumps([leaf.species_id, f"c{fold_index}{row}"], separators=(",", ":"))
                for row in range(2)
            )
            keys = tuple(RowKey(leaf.species_id, f"c{fold_index}{row}") for row in range(2))
            y = np.asarray([0, 1], dtype=np.int8)
            scores = np.asarray([0.25, 0.75], dtype=np.float64)
            control_folds.append(conventional.ControlFold(fold, tokens, y, scores))
            result_folds.append(
                FoldOOF(fold, keys, y, {leaf.seed_label: scores}, scores, 1.0, 1.0)
            )
        controls[leaf] = conventional.ControlLeaf(
            leaf, tuple(control_folds), "1" * 64, "2" * 64
        )
        reduced[leaf] = CandidateOOF(
            SelectionStratum(
                leaf.species_id,
                leaf.fraction_id,
                leaf.ladder_id,
                leaf.model_family,
                (leaf.seed_label,),
            ),
            leaf.candidate_id,
            tuple(result_folds),
            0.5,
            1.0,
            1.0,
            {},
            {},
            {},
        )
    monkeypatch.setattr(
        conventional, "load_control_leaf", lambda _catalog, leaf: controls[leaf]
    )

    receipt = conventional.aggregate_family_effects(
        catalog, reduced, endpoints=[endpoint]
    )
    assert receipt["strata"] == 8 * 4
    assert receipt["leaf_count"] == 8 * 16
    assert len(receipt["family_endpoint_summaries"]) == 4
    assert all(
        summary["mean_delta"] == {"roc_auc": 0.0, "tss": 0.0, "mcc": 0.0}
        for summary in receipt["family_endpoint_summaries"]
    )
    serialized = json.dumps(receipt)
    assert "row_token" not in serialized and '"score"' not in serialized and '"y_true"' not in serialized


def test_variant_metrics_weight_folds_equally_despite_unequal_sizes():
    from dsdm.predictor_sensitivity_conventional import _variant_metrics

    large_y = np.asarray([0] * 100 + [1] * 100, dtype=np.int8)
    large_score = np.asarray([0.1] * 100 + [0.9] * 100, dtype=np.float64)
    reversed_y = np.asarray([0, 1], dtype=np.int8)
    reversed_score = np.asarray([0.9, 0.1], dtype=np.float64)
    labels = [large_y, reversed_y, reversed_y, reversed_y, reversed_y]
    scores = [large_score, reversed_score, reversed_score, reversed_score, reversed_score]

    first = _variant_metrics(labels, scores)
    doubled = _variant_metrics(
        [np.tile(large_y, 2), *labels[1:]],
        [np.tile(large_score, 2), *scores[1:]],
    )
    assert first["roc_auc"] == pytest.approx(0.2)
    assert doubled["roc_auc"] == pytest.approx(first["roc_auc"])
