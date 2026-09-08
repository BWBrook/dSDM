"""Goal 051 retained-training conventional and ``q_linear`` benchmark.

The command surface is deliberately small: validate/plan, prepare shared q
models, run target shards, aggregate, replay-validate, and a metric-free
engineering canary.  Geographic holdout responses are outside this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import platform
import resource
import re
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from .mainland_modeling import summarize_oof
from .model_adapters import CANONICAL_CANDIDATES, ModelAdapterError, build_adapter
from .modeling_contract import FeatureBatch
from .seawfb_modeling import (
    CROSSFIT_PATH,
    CURVES_PATH,
    CELLS_PATH,
    MANIFEST_PATH,
    MEMBERSHIPS_PATH,
    TRANSFORMS_PATH,
    QLinearModel,
    ResponseRows,
    SeawfbModelingError,
    SeawfbStore,
    digest,
    fit_q_linear,
    require,
    q_parameter_digest,
    sha256_file,
    slug,
    stable_seed,
    standardized_q,
)


CONFIG_PATH = Path("config/goal051_seawfb_conventional.json")
GOAL052_CONFIG_PATH = Path("config/goal052_seawfb_dsdm.json")
SOURCE_PATHS = (
    Path("src/dsdm_phase1/seawfb_modeling.py"),
    Path("src/dsdm_phase1/goal051_seawfb_conventional.py"),
    Path("src/dsdm_phase1/model_adapters.py"),
    Path("src/dsdm_phase1/modeling_contract.py"),
    Path("src/dsdm_phase1/mainland_modeling.py"),
    Path("src/dsdm_phase1/goal050_seawfb_foundation.py"),
)
EXPECTED_CANDIDATES = {
    "intercept": ["null00"],
    "elastic_net": ["enet00", "enet04", "enet08", "enet09"],
    "random_forest": ["rf00", "rf02", "rf03", "rf05"],
    "hist_gradient_boosting": ["hgb00", "hgb02", "hgb04", "hgb05"],
    "shallow_ann": ["ann00", "ann02", "ann04"],
}
EXPECTED_SCREEN_SEEDS = {
    "intercept": ["seed00"],
    "elastic_net": ["seed00"],
    "random_forest": ["seed00"],
    "hist_gradient_boosting": ["seed00"],
    "shallow_ann": ["seed00", "seed01", "seed02"],
}
EXPECTED_SELECTED_SEEDS = {
    "intercept": ["seed00"],
    "elastic_net": ["seed00"],
    "random_forest": ["seed00", "seed01", "seed02", "seed03", "seed04"],
    "hist_gradient_boosting": ["seed00"],
    "shallow_ann": ["seed00", "seed01", "seed02", "seed03", "seed04"],
}
EXPECTED_MINIMUM_CANDIDATES = {
    "intercept": 1,
    "elastic_net": 2,
    "random_forest": 2,
    "hist_gradient_boosting": 2,
    "shallow_ann": 2,
}
EXPECTED_DSDM_ARMS = [
    "target_only_random_init_resmlp",
    "target_plus_q_linear_resmlp",
    "multihead_frozen_trunk",
    "multihead_full_finetune",
]
EXPECTED_DSDM_ARCHITECTURES = [
    {"id": "bridge_control", "blocks": 3, "width": 128, "bottleneck": 64, "dropout": 0.0, "weight_decay": 0.001},
    {"id": "bridge_wide", "blocks": 3, "width": 256, "bottleneck": 64, "dropout": 0.0, "weight_decay": 0.001},
    {"id": "bridge_deep", "blocks": 6, "width": 128, "bottleneck": 64, "dropout": 0.0, "weight_decay": 0.001},
    {"id": "seawfb_scale", "blocks": 6, "width": 256, "bottleneck": 128, "dropout": 0.0, "weight_decay": 0.001},
]
EXPECTED_DSDM_CONSTANTS = {
    "activation": "GELU",
    "normalization": "LayerNorm",
    "optimizer": "AdamW",
    "learning_rate": 0.001,
    "batch_size": 128,
    "max_epochs": 300,
    "patience": 30,
    "min_improvement": 0.00001,
    "stopping_fold": "(held_fold+1)%5",
    "discovery_folds": "other_three",
    "replay_folds": "all_four_nonheld_at_selected_epoch",
    "residual_shape": "pre_norm_two_layer_mlp_with_input_projection_and_identity_skip",
}
EXPECTED_DSDM_PRIMARY_CONTRASTS = [
    "multihead_full_finetune_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_target_plus_q_linear_resmlp",
    "multihead_full_finetune_minus_goal051_selected_conventional",
    "multihead_full_finetune_minus_goal051_q_augmented_conventional",
]
EXPECTED_DSDM_MECHANISTIC_CONTRASTS = [
    "multihead_frozen_trunk_minus_target_only_random_init_resmlp",
    "multihead_full_finetune_minus_multihead_frozen_trunk",
]
EXPECTED_DSDM_COMMUNITY_CONTROL = {
    "id": "q_linear",
    "source": "goal051_q_linear_surfaces",
    "target_excluded": True,
    "focal_block_excluded": True,
    "surface_count": 150,
    "surface_identity": ["focal_block", "held_fold", "auxiliary_size"],
    "append_to_target_only_arm": True,
    "q_fit_is_not_retuned": True,
}
EXPECTED_CANARY_HOSTS = {
    "mac": {"hostname": "Barrys-Mac-mini.local", "system": "Darwin"},
    "deep_server": {"hostname": "deep-server", "system": "Linux"},
}
EXPECTED_Q_NUMERICAL_FIT = {
    "solver": "saga",
    "tol": 1e-5,
    "primary_max_iter": 5000,
    "extended_max_iter": 10000,
    "tertiary_max_iter": 20000,
    "tertiary_refit": "from_scratch_same_seed_after_extended_warning_or_ceiling",
    "extended_refit": "from_scratch_same_seed_after_primary_warning_or_ceiling",
    "acceptance": "converged_attempt_only",
    "ceiling_stability_acceptance": False,
}
EXPECTED_GOAL051_AMENDMENTS = [
    {
        "id": "goal051-q-linear-numerical-amendment-1",
        "date": "2026-09-05",
        "trigger": "metric_free_q_linear_primary_nonconvergence",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "changed": ["tol_1e-5", "primary_max_iter_5000", "same_seed_from_scratch_extended_max_iter_10000"],
        "unchanged": ["solver_saga", "C_0.1", "l1_ratio_0.5", "weights", "features", "exclusions", "seed"],
    },
    {
        "id": "goal051-q-linear-numerical-amendment-2",
        "date": "2026-09-05",
        "trigger": "metric_free_q_linear_weight_scaling_and_warning_classification_review",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "authorization": "user_approved_2026-09-05",
        "changed": [
            "solver_sample_weight=w/k_where_k=max_collapsed_sample_weight",
            "solver_C=canonical_C*k",
            "convergence_warning_classification",
            "remove_deprecated_penalty_and_n_jobs_arguments",
        ],
        "unchanged": ["solver_saga", "C_0.1", "l1_ratio_0.5", "weights", "features", "exclusions", "seed"],
    },
    {
        "id": "goal051-q-linear-numerical-amendment-3",
        "date": "2026-09-08",
        "trigger": "retained_training_q_extended_nonconvergence_before_target_fits",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "authorization": "user_approved_2026-09-08",
        "changed": ["same_seed_from_scratch_tertiary_max_iter_20000"],
        "unchanged": ["primary_5000", "extended_10000", "tol_1e-5", "solver_saga", "C_0.1", "l1_ratio_0.5", "weights", "features", "exclusions", "seed"],
    },
]
EXPECTED_GOAL052_AMENDMENTS = [
    {
        "id": "goal051-q-linear-numerical-amendment-1",
        "date": "2026-09-05",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "scope": "goal051_q_linear_convergence_only",
        "dsdm_scientific_design_changed": False,
    },
    {
        "id": "goal051-q-linear-numerical-amendment-2",
        "date": "2026-09-05",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "scope": "goal051_q_linear_representation_and_warning_classification_only",
        "authorization": "user_approved_2026-09-05",
        "dsdm_scientific_design_changed": False,
    },
    {
        "id": "goal051-q-linear-numerical-amendment-3",
        "date": "2026-09-08",
        "timing": "before_any_ecological_scores",
        "classification": "numerical_only",
        "scope": "goal051_q_linear_tertiary_convergence_attempt_only",
        "authorization": "user_approved_2026-09-08",
        "dsdm_scientific_design_changed": False,
    },
]
PREDICTION_SCHEMA = pa.schema(
    [
        pa.field("target", pa.string(), nullable=False),
        pa.field("target_fraction", pa.int8(), nullable=False),
        pa.field("auxiliary_size", pa.string(), nullable=False),
        pa.field("fold", pa.int8(), nullable=False),
        pa.field("cell_id", pa.string(), nullable=False),
        pa.field("y", pa.int8(), nullable=False),
        pa.field("method", pa.string(), nullable=False),
        pa.field("family", pa.string(), nullable=False),
        pa.field("candidate_id", pa.string(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
    ]
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SeawfbModelingError(f"invalid_json:{path}") from exc
    require(isinstance(value, dict), f"invalid_json_object:{path}")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        pq.write_table(table.cast(PREDICTION_SCHEMA), temporary, compression="zstd", use_dictionary=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _config(root: Path) -> dict[str, Any]:
    return _read_json(root / CONFIG_PATH)


def _private_root(root: Path, config: Mapping[str, Any]) -> Path:
    return root / config["execution"]["private_root"]


def _seed_namespace(config: Mapping[str, Any], scope: str) -> str:
    require(scope in {"target", "q"}, "seed_namespace_scope_invalid")
    section = config["execution"] if scope == "target" else config["community_control"]
    value = section.get("fit_seed_namespace")
    if value is None and config.get("_test_fixture") is True:
        value = f"{config.get('goal_id', 'goal051-test')}:{scope}:test-v1"
    require(isinstance(value, str) and bool(value.strip()), f"{scope}_fit_seed_namespace_missing")
    return value


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _validate_q_numerical_fit(value: Mapping[str, Any]) -> None:
    require(value == EXPECTED_Q_NUMERICAL_FIT, "q_numerical_fit_drift")


def _validate_q_attempts(receipt: Mapping[str, Any], numerical_fit: Mapping[str, Any]) -> None:
    attempts = receipt.get("attempts")
    require(isinstance(attempts, list) and len(attempts) in (1, 2, 3), "q_attempt_inventory_drift")
    expected_names = ["primary", "extended", "tertiary"][: len(attempts)]
    expected_max = [numerical_fit["primary_max_iter"], numerical_fit["extended_max_iter"], numerical_fit["tertiary_max_iter"]][: len(attempts)]
    for item, name, max_iter in zip(attempts, expected_names, expected_max):
        require(
            item.get("attempt") == name
            and item.get("max_iter") == max_iter
            and item.get("tol") == numerical_fit["tol"]
            and isinstance(item.get("n_iter"), int)
            and 0 < item["n_iter"] <= max_iter
            and isinstance(item.get("warning"), bool)
            and isinstance(item.get("warning_types"), list)
            and all(isinstance(value, str) for value in item["warning_types"])
            and item.get("warning") == ("ConvergenceWarning" in item["warning_types"])
            and isinstance(item.get("finite_parameters"), bool)
            and isinstance(item.get("numerical_warning"), bool)
            and item.get("numerical_warning") == ("RuntimeWarning" in item["warning_types"])
            and item.get("converged") == (not item["warning"] and not item["numerical_warning"] and item["finite_parameters"] and item["n_iter"] < max_iter),
            "q_attempt_record_drift",
        )
    accepted = receipt.get("accepted_attempt")
    require(
        accepted == expected_names[-1]
        and attempts[-1]["converged"] is True
        and all(item["converged"] is False for item in attempts[:-1]),
        "q_attempt_acceptance_drift",
    )


def _validate_q_weight_rescaling(receipt: Mapping[str, Any]) -> None:
    k = receipt.get("k")
    canonical_c = receipt.get("canonical_C")
    solver_c = receipt.get("solver_C")
    require(
        isinstance(k, (int, float))
        and np.isfinite(k)
        and k > 0
        and isinstance(canonical_c, (int, float))
        and np.isclose(canonical_c, 0.1, rtol=0, atol=0)
        and isinstance(solver_c, (int, float))
        and np.isclose(solver_c, canonical_c * k, rtol=0, atol=1e-12)
        and receipt.get("representation") == "collapsed_weight_divided_by_k_solver_C_multiplied_by_k",
        "q_weight_rescaling_receipt_drift",
    )


def _validate_goal052(goal052: Mapping[str, Any]) -> None:
    require(goal052.get("schema_version") == "goal052-seawfb-dsdm-v1", "goal052_schema_drift")
    require(
        goal052.get("protocol_version") == 4
        and goal052.get("prospective_amendments") == EXPECTED_GOAL052_AMENDMENTS,
        "goal052_amendment_record_drift",
    )
    require(goal052.get("status") == "prospectively_frozen_protocol_only_not_executed", "goal052_not_prospectively_frozen")
    ordering = goal052.get("prospective_ordering", {})
    require(ordering.get("freeze_before_goal051_ecological_scores") is True and ordering.get("goal051_results_may_not_amend_this_protocol") is True, "goal052_ordering_drift")
    require(goal052.get("arms") == EXPECTED_DSDM_ARMS and goal052.get("primary_arm") == "multihead_full_finetune", "goal052_arm_drift")
    scope = goal052.get("scope", {})
    require(
        scope.get("folds") == ["fold00", "fold01", "fold02", "fold03", "fold04"]
        and scope.get("focal_targets") == "all_157_goal050_focal_targets"
        and scope.get("primary_targets") == 73
        and scope.get("full_only_targets") == 84
        and scope.get("target_learning_fractions") == [25, 50, 100]
        and scope.get("full_only_target_learning_fractions") == [100]
        and scope.get("auxiliary_learning_sizes") == [20, 80, "full"]
        and scope.get("nested_target_subsets") is True
        and scope.get("response_row_plan_binding") == "reuse_goal050_frozen_crossfit_and_learning_curve_plans_and_digests"
        and scope.get("crossed_grid") == {"source": "goal051_conventional_q_condition_grid", "q_conditions": 449, "base_endpoints": 303, "q_surfaces": 150}
        and scope.get("primary_richness_rule") == "goal050_X10"
        and scope.get("natural_prevalence") is True
        and scope.get("class_balancing") is False,
        "goal052_scope_drift",
    )
    pretraining = goal052.get("pretraining", {})
    require(
        pretraining.get("heads") == "all_goal050_eligible_heads_except_focal_block"
        and pretraining.get("target_excluded_from_pretraining") is True
        and pretraining.get("focal_block_excluded_from_pretraining") is True
        and pretraining.get("auxiliary_effort_richness_rule") == "goal050_remove_entire_focal_block_from_auxiliary_richness"
        and pretraining.get("strict_held_fold_exclusion") is True
        and pretraining.get("head_weighting") == "equal_total_contribution_per_head"
        and pretraining.get("within_head_class_balancing") is False
        and pretraining.get("auxiliary_endpoints") == [20, 80, "full"],
        "goal052_pretraining_drift",
    )
    require(goal052.get("community_control") == EXPECTED_DSDM_COMMUNITY_CONTROL, "goal052_community_control_drift")
    architectures = goal052.get("architectures", {})
    require(
        architectures.get("selection_scope") == "shared_across_targets"
        and architectures.get("selection_arm") == "multihead_full_finetune"
        and architectures.get("selection_targets") == "73_primary_targets"
        and architectures.get("selection_endpoint") == "target100_auxiliary_full"
        and architectures.get("selection_seed_labels") == ["seed00"]
        and architectures.get("selection_rank")
        == {
            "within_target": [
                "equal_fold_mean_roc_auc_desc",
                "pooled_oof_tss_desc",
                "architecture_id_asc",
            ],
            "shared": [
                "mean_target_rank_asc",
                "mean_target_roc_auc_desc",
                "architecture_id_asc",
            ],
        },
        "goal052_selection_rule_drift",
    )
    require(architectures.get("candidates") == EXPECTED_DSDM_ARCHITECTURES, "goal052_architecture_drift")
    require(architectures.get("constants") == EXPECTED_DSDM_CONSTANTS, "goal052_training_constant_drift")
    replication = goal052.get("replication", {})
    require(
        replication.get("seed_labels") == ["seed00", "seed01", "seed02", "seed03", "seed04"]
        and replication.get("paired_across_arms") is True
        and replication.get("average_seed_predictions_before_primary_evaluation") is True
        and replication.get("primary_contrasts") == EXPECTED_DSDM_PRIMARY_CONTRASTS
        and replication.get("mechanistic_contrasts") == EXPECTED_DSDM_MECHANISTIC_CONTRASTS
        and replication.get("selected_epoch_summary") == "median_selected_epoch_rounded_for_later_retained_full_refit",
        "goal052_replication_drift",
    )
    require(
        goal052.get("stability_audit")
        == {"leave_one_focal_block_out": True, "role": "post_selection_diagnostic_only", "cannot_change_winner": True},
        "goal052_stability_policy_drift",
    )
    require(
        goal052.get("amendment_policy")
        == {
            "before_scores": "goal051_q_linear_numerical_amendments_1_2_and_3_exercised_before_scores; any_further_before_score_change_requires_explicit_versioned_authorization_and_repeated_metric_free_canary",
            "after_scores": "any_scientific_change_requires_versioned_amendment_and_full_prespecified_rerun",
            "performance_driven_goalpost_change": False,
        },
        "goal052_amendment_policy_drift",
    )
    require(goal052.get("upstream", {}).get("outer_access") == "sealed" and goal052.get("evaluation", {}).get("outer_outcomes") is False, "goal052_outer_firewall_drift")
    execution = goal052.get("execution", {})
    require(
        execution.get("protocol_only_in_this_goal") is True
        and execution.get("production_boundary") == "detached_resumable_launch_after_goal051_acceptance",
        "goal052_execution_boundary_drift",
    )
    evaluation = goal052.get("evaluation", {})
    require(
        evaluation.get("primary_metric") == "roc_auc"
        and evaluation.get("threshold_source") == "concatenated_training_oof_predictions"
        and evaluation.get("outer_threshold_selection") is False
        and evaluation.get("outer_outcomes") is False,
        "goal052_evaluation_drift",
    )
    require(
        goal052.get("stopping_boundary")
        == [
            "goal051_conventional_acceptance",
            "outer_NCP_SEH_NNC_evaluation",
            "outer_threshold_selection",
            "full_refit",
            "mapping",
            "manuscript_claims",
        ],
        "goal052_stopping_boundary_drift",
    )


def _source_digest(root: Path) -> str:
    return digest({str(path): sha256_file(root / path) for path in SOURCE_PATHS})


def _identity(root: Path) -> dict[str, str]:
    return {
        "config_sha256": sha256_file(root / CONFIG_PATH),
        "goal052_config_sha256": sha256_file(root / GOAL052_CONFIG_PATH),
        "goal050_manifest_sha256": sha256_file(root / MANIFEST_PATH),
        "goal050_transforms_sha256": sha256_file(root / TRANSFORMS_PATH),
        "goal050_crossfit_sha256": sha256_file(root / CROSSFIT_PATH),
        "goal050_curves_sha256": sha256_file(root / CURVES_PATH),
        "uv_lock_sha256": sha256_file(root / "uv.lock"),
        "source_sha256": _source_digest(root),
    }


def target_endpoints(curves: Mapping[str, Any]) -> list[tuple[str, int]]:
    primary = set(curves["applies_to"]["primary_targets"])
    endpoints = [
        (target, fraction)
        for target in curves["applies_to"]["full_full_focal_targets"]
        for fraction in ((25, 50, 100) if target in primary else (100,))
    ]
    require(len(endpoints) == 303 and len(set(endpoints)) == 303, "target_endpoint_count_drift")
    return endpoints


def q_conditions(curves: Mapping[str, Any]) -> list[tuple[str, int, str]]:
    primary = set(curves["applies_to"]["primary_targets"])
    conditions = [(target, fraction, "full") for target, fraction in target_endpoints(curves)]
    conditions += [
        (target, 100, auxiliary)
        for target in curves["applies_to"]["full_full_focal_targets"]
        if target in primary
        for auxiliary in ("20", "80")
    ]
    require(len(conditions) == 449 and len(set(conditions)) == 449, "q_condition_count_drift")
    return conditions


def q_surface_specs(crossfit: Mapping[str, Any]) -> list[tuple[int, int, str]]:
    specs = [
        (block, fold, auxiliary)
        for block in range(10)
        for fold in range(5)
        for auxiliary in ("20", "80", "full")
    ]
    require(set(crossfit["auxiliary_sets"]) == set(map(str, range(10))), "q_block_inventory_drift")
    require(len(specs) == 150, "q_surface_count_drift")
    return specs


def validate_inputs(root: Path) -> dict[str, Any]:
    root = Path(root)
    config = _config(root)
    require(config.get("schema_version") == "goal051-seawfb-conventional-v1", "goal051_schema_drift")
    require(
        config.get("protocol_version") == 4
        and config.get("amendments") == EXPECTED_GOAL051_AMENDMENTS,
        "goal051_amendment_record_drift",
    )
    require(config.get("status") == "prospectively_frozen_before_ecological_scores", "goal051_not_frozen")
    require(config["upstream"]["outer_access"] == "sealed", "outer_access_not_sealed")
    require(config["evaluation"]["outer_outcomes"] is False, "outer_outcomes_enabled")
    require(config["conventional"]["candidate_ids"] == EXPECTED_CANDIDATES, "candidate_registry_drift")
    require(config["conventional"]["screen_seed_labels"] == EXPECTED_SCREEN_SEEDS, "screen_seed_schedule_drift")
    require(config["conventional"]["selected_seed_labels"] == EXPECTED_SELECTED_SEEDS, "selected_seed_schedule_drift")
    require(config["conventional"]["minimum_complete_candidates"] == EXPECTED_MINIMUM_CANDIDATES, "family_minimum_drift")
    require(config["data_contract"]["row_weight"] == "one" and config["data_contract"]["class_balancing"] is False, "target_weighting_drift")
    require(_seed_namespace(config, "target") != _seed_namespace(config, "q"), "fit_seed_namespaces_not_separate")
    community = config["community_control"]
    require(community["candidate_id"] == "enet04", "q_candidate_drift")
    _validate_q_numerical_fit(community.get("numerical_fit", {}))
    q_candidate = CANONICAL_CANDIDATES["enet04"]
    require(
        community.get("fixed_regularization")
        == {"candidate_id": "enet04", "C": q_candidate["C"], "l1_ratio": q_candidate["l1_ratio"]},
        "q_regularization_drift",
    )
    require(community["downstream_candidate_retuning"] is False, "q_retuning_enabled")
    require(community.get("fit_scope") == ["focal_block", "held_fold", "auxiliary_size"], "q_fit_scope_drift")
    require(community.get("focal_block_excluded") is True, "q_block_exclusion_drift")
    require(community.get("surface_count") == 150, "q_surface_contract_drift")
    goal052 = _read_json(root / GOAL052_CONFIG_PATH)
    _validate_goal052(goal052)
    manifest = _read_json(root / MANIFEST_PATH)
    transforms = _read_json(root / TRANSFORMS_PATH)
    crossfit = _read_json(root / CROSSFIT_PATH)
    curves = _read_json(root / CURVES_PATH)
    require(manifest.get("status") == "complete" and manifest["counts"]["focal_targets"] == 157, "goal050_manifest_drift")
    require(transforms.get("schema_version") == "goal050-transforms-v1", "goal050_transform_drift")
    require(sha256_file(root / CELLS_PATH) == manifest["bindings"]["cells"], "goal050_cells_binding_drift")
    require(sha256_file(root / MEMBERSHIPS_PATH) == manifest["bindings"]["memberships"], "goal050_memberships_binding_drift")
    require(sha256_file(root / CROSSFIT_PATH) == manifest["bindings"]["crossfit"], "goal050_crossfit_binding_drift")
    require(sha256_file(root / CURVES_PATH) == manifest["bindings"]["curves"], "goal050_curves_binding_drift")
    require(sha256_file(root / TRANSFORMS_PATH) == manifest["bindings"]["transforms"], "goal050_transforms_binding_drift")
    require(sha256_file(root / "uv.lock") == manifest["bindings"]["uv_lock"], "uv_lock_binding_drift")
    endpoints = target_endpoints(curves)
    conditions = q_conditions(curves)
    surfaces = q_surface_specs(crossfit)
    inventory = config["planned_inventory"]
    require(
        inventory.get("base_endpoints") == 303
        and inventory.get("q_conditions") == 449
        and inventory.get("q_surfaces") == 150
        and inventory.get("partial_fold_scoring") is False
        and inventory.get("mandatory_null") is True
        and inventory.get("minimum_complete_candidates_per_non_null_family") == 2
        and inventory.get("mandatory_intercept_candidates") == 1
        and inventory.get("primary_full_required_family_groups")
        == {
            "elastic_net": ["elastic_net"],
            "tree_family": ["random_forest", "hist_gradient_boosting"],
            "shallow_ann": ["shallow_ann"],
        }
        and inventory.get("family_coverage_stop_fraction") == 0.95
        and inventory.get("repair_passes_max") == 1,
        "planned_inventory_drift",
    )
    prevalence_gate = inventory.get("prevalence_failure_gate", {})
    require(
        prevalence_gate.get("ranking")
        == "constructed_validation_prevalence_then_target_then_fraction"
        and prevalence_gate.get("extreme_quartiles") == ["lowest", "highest"]
        and prevalence_gate.get("extreme_quartile_minimum_coverage") == 0.9
        and prevalence_gate.get("action") == "stop_for_review",
        "prevalence_failure_gate_drift",
    )
    scope = config["scope"]
    require(
        scope["primary_targets"] == 73
        and scope["full_only_targets"] == 84
        and scope["primary_target_learning_fractions"] == [25, 50, 100]
        and scope["full_only_learning_fractions"] == [100],
        "planned_target_inventory_drift",
    )
    expected_q_endpoints = {
        (100, "20"), (100, "80"), (100, "full"), (25, "full"), (50, "full")
    }
    observed_q_endpoints = {
        (int(item["target_fraction"]), str(item["auxiliary_size"]))
        for item in community["unique_endpoints"]
    }
    require(observed_q_endpoints == expected_q_endpoints, "planned_q_endpoint_drift")
    canary_spec = config["execution"]["canary"]
    require(canary_spec.get("host_expectations") == EXPECTED_CANARY_HOSTS, "canary_host_expectations_drift")
    canary_target = canary_spec["target"]
    require(canary_target in crossfit["focal_blocks"], "canary_target_drift")
    require(canary_spec["focal_block"] == f"block{crossfit['focal_blocks'][canary_target]}", "canary_focal_block_drift")
    require(
        canary_spec.get("held_fold") == "fold00"
        and canary_spec.get("target_fraction") == 100
        and canary_spec.get("candidate_ids") == ["null00", "enet04", "rf02", "hgb04", "ann02"]
        and canary_spec.get("serial_repeats") == 2
        and canary_spec.get("mixed_concurrency") == {"mac": 3, "deep_server": 8},
        "canary_plan_drift",
    )
    require([str(value) for value in canary_spec["auxiliary_sizes"]] == ["20", "full"], "canary_auxiliary_inventory_drift")
    require(canary_spec["metrics_allowed"] is False, "canary_metrics_enabled")
    require(canary_spec["q_augmented_family"] == "hist_gradient_boosting", "canary_q_family_drift")
    return {
        "status": "goal051_inputs_valid",
        "identity": _identity(root),
        "targets": 157,
        "primary_targets": 73,
        "target_endpoints": len(endpoints),
        "q_conditions": len(conditions),
        "q_surfaces": len(surfaces),
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }


def _q_paths(root: Path, config: Mapping[str, Any], block: int, fold: int, auxiliary: str) -> tuple[Path, Path]:
    directory = _private_root(root, config) / "q_linear"
    stem = f"block{block:02d}_fold{fold:02d}_aux{auxiliary}"
    return directory / f"{stem}.npz", directory / f"{stem}.json"


def _write_q(root: Path, config: Mapping[str, Any], identity: Mapping[str, str], model: QLinearModel, receipt: Mapping[str, Any]) -> None:
    model_path, receipt_path = _q_paths(root, config, model.held_block, model.held_fold, model.auxiliary_size)
    _atomic_npz(model_path, coefficient=model.coefficient, intercept=np.asarray([model.intercept]))
    _atomic_json(
        receipt_path,
        {
            "schema_version": "goal051-q-linear-v1",
            "identity": dict(identity),
            "model_sha256": sha256_file(model_path),
            "transform_id": model.transform_id,
            **dict(receipt),
        },
    )


def _load_q(root: Path, config: Mapping[str, Any], identity: Mapping[str, str], block: int, fold: int, auxiliary: str) -> tuple[QLinearModel, dict[str, Any]] | None:
    model_path, receipt_path = _q_paths(root, config, block, fold, auxiliary)
    if not model_path.is_file() or not receipt_path.is_file():
        return None
    receipt = _read_json(receipt_path)
    if receipt.get("identity") != identity or receipt.get("model_sha256") != sha256_file(model_path):
        return None
    if (
        receipt.get("held_block") != block
        or receipt.get("held_fold") != fold
        or receipt.get("auxiliary_size") != auxiliary
        or receipt.get("candidate_id") != "enet04"
    ):
        return None
    with np.load(model_path, allow_pickle=False) as payload:
        coefficient = payload["coefficient"].astype(np.float64)
        intercept = float(payload["intercept"][0])
    require(coefficient.ndim == 1 and np.isfinite(coefficient).all() and np.isfinite(intercept), "q_checkpoint_parameter_drift")
    require(receipt.get("numerical_fit") == config["community_control"]["numerical_fit"], "q_checkpoint_numerical_fit_drift")
    _validate_q_attempts(receipt, config["community_control"]["numerical_fit"])
    require(receipt.get("iterations") == receipt["attempts"][-1]["n_iter"], "q_checkpoint_iteration_drift")
    _validate_q_weight_rescaling(receipt)
    require(receipt.get("parameter_digest") == q_parameter_digest(coefficient, intercept), "q_checkpoint_parameter_digest_drift")
    model = QLinearModel(coefficient, intercept, block, fold, auxiliary, receipt["transform_id"], int(receipt["iterations"]))
    return model, receipt


def prepare_q_surface(root: Path, store: SeawfbStore, config: Mapping[str, Any], block: int, fold: int, auxiliary: str) -> dict[str, Any]:
    identity = _identity(root)
    cached = _load_q(root, config, identity, block, fold, auxiliary)
    if cached is not None:
        return cached[1]
    started = time.perf_counter()
    try:
        model, receipt = fit_q_linear(
            store, block, fold, auxiliary,
            candidate_id=config["community_control"]["candidate_id"],
            seed_namespace=_seed_namespace(config, "q"),
            numerical_fit=config["community_control"]["numerical_fit"],
        )
    except Exception as error:
        failure = {
            "status": "q_fit_failed", "identity": identity,
            "held_block": block, "held_fold": fold, "auxiliary_size": auxiliary,
            "numerical_fit": config["community_control"]["numerical_fit"],
            "runtime_seconds": time.perf_counter() - started,
            "error_type": type(error).__name__, "error": str(error),
            "attempts": getattr(error, "attempts", []),
            "metrics_computed": False, "outer_response_rows_read": 0,
        }
        failure_path = _q_paths(root, config, block, fold, auxiliary)[1]
        _atomic_json(failure_path.with_suffix(".failure.json"), failure)
        print(json.dumps(failure, sort_keys=True), flush=True)
        raise
    receipt = {**receipt, "runtime_seconds": time.perf_counter() - started}
    _write_q(root, config, identity, model, receipt)
    return receipt


def _subset_batch(batch: FeatureBatch, indices: Sequence[int]) -> FeatureBatch:
    selected = np.asarray(indices, dtype=np.int64)
    return FeatureBatch(
        tuple(batch.keys[index] for index in selected),
        batch.x[selected],
        batch.y[selected],
        batch.feature_names,
        batch.feature_kinds,
        batch.continuous_count,
        batch.feature_schema_digest,
        batch.unseen_level_counts,
        batch.transform_id,
        batch.transform_digest,
        batch.encoder_digest,
    )


def _fit_seed(config: Mapping[str, Any], target: str, fraction: int, fold: int, family: str, candidate: str, seed_label: str) -> int:
    """Paired target-model seed; q condition deliberately does not enter."""

    return stable_seed(_seed_namespace(config, "target"), target, fraction, fold, family, candidate, seed_label)


def _fit_predict(
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    fold: int,
    family: str,
    candidate_id: str,
    seed_label: str,
    train_rows: ResponseRows,
    train: FeatureBatch,
    validation: FeatureBatch,
) -> tuple[np.ndarray, dict[str, Any]]:
    candidate = CANONICAL_CANDIDATES[candidate_id]
    adapter = build_adapter(family)
    seed = _fit_seed(config, target, fraction, fold, family, candidate_id, seed_label)
    if family != "shallow_ann":
        fitted, report = adapter.fit(train, None, candidate, seed)
        scores = fitted.predict_scores(validation)
        return scores, {"physical_fits": 1, "runtime_seconds": report.runtime_seconds, "peak_rss_bytes": report.peak_rss_bytes, "best_epoch": None, "converged": report.converged}
    stopping_fold = (fold + 1) % 5
    stopping_indices = np.flatnonzero(train_rows.source_folds == stopping_fold)
    discovery_indices = np.flatnonzero(train_rows.source_folds != stopping_fold)
    require(len(set(train_rows.y[stopping_indices].tolist())) == 2, "ann_stopping_single_class")
    require(len(set(train_rows.y[discovery_indices].tolist())) == 2, "ann_discovery_single_class")
    _, discovery = adapter.fit(_subset_batch(train, discovery_indices), _subset_batch(train, stopping_indices), candidate, seed)
    require(discovery.best_epoch is not None, "ann_best_epoch_missing")
    fitted, replay = adapter.fit(train, None, candidate, seed, exact_epochs=int(discovery.best_epoch))
    require(discovery.initial_state_digest == replay.initial_state_digest, "ann_replay_initialization_drift")
    return fitted.predict_scores(validation), {
        "physical_fits": 2,
        "runtime_seconds": discovery.runtime_seconds + replay.runtime_seconds,
        "peak_rss_bytes": max(discovery.peak_rss_bytes, replay.peak_rss_bytes),
        "best_epoch": int(discovery.best_epoch),
        "converged": discovery.converged and replay.converged,
    }


def _prepared_folds(
    root: Path,
    store: SeawfbStore,
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    auxiliary: str | None,
) -> list[dict[str, Any]]:
    identity = _identity(root)
    block = int(store.crossfit["focal_blocks"][target])
    prepared = []
    for fold in range(5):
        train_rows = store.target_rows(target, fold, fraction, "train")
        validation_rows = store.target_rows(target, fold, 100, "validation")
        train_q = validation_q = None
        q_receipt = None
        if auxiliary is not None:
            loaded = _load_q(root, config, identity, block, fold, auxiliary)
            require(loaded is not None, f"q_checkpoint_missing:{block}:{fold}:{auxiliary}")
            model, q_receipt = loaded
            train_q, validation_q, scale = standardized_q(model, store, fold, train_rows, validation_rows)
            q_receipt = {"model_sha256": q_receipt["model_sha256"], **scale}
        prepared.append(
            {
                "fold": fold,
                "train_rows": train_rows,
                "validation_rows": validation_rows,
                "train": store.batch(target, train_rows, fold, train_q),
                "validation": store.batch(target, validation_rows, fold, validation_q),
                "q": q_receipt,
            }
        )
    return prepared


def _evaluate(
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    family: str,
    candidate_id: str,
    seed_labels: Sequence[str],
    prepared: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    folds, fits = [], []
    for item in prepared:
        scores_by_seed = {}
        for seed_label in seed_labels:
            scores, fit = _fit_predict(
                config,
                target,
                fraction,
                int(item["fold"]),
                family,
                candidate_id,
                seed_label,
                item["train_rows"],
                item["train"],
                item["validation"],
            )
            require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "candidate_score_invalid")
            scores_by_seed[seed_label] = scores
            fits.append({"fold": int(item["fold"]), "seed_label": seed_label, **fit})
        folds.append(
            {
                "fold": int(item["fold"]),
                "cell_ids": item["validation_rows"].cell_ids,
                "y": item["validation_rows"].y,
                "score": np.mean(np.vstack(list(scores_by_seed.values())), axis=0),
                "scores_by_seed": scores_by_seed,
            }
        )
    return {
        "candidate_id": candidate_id,
        "seed_labels": list(seed_labels),
        "folds": folds,
        "metrics": summarize_oof(folds),
        "fit_records": fits,
        "physical_fits": int(sum(item["physical_fits"] for item in fits)),
        "runtime_seconds": float(sum(item["runtime_seconds"] for item in fits)),
    }


def _public(result: Mapping[str, Any]) -> dict[str, Any]:
    epochs = [item["best_epoch"] for item in result["fit_records"] if item["best_epoch"] is not None]
    return {
        "candidate_id": result["candidate_id"],
        "seed_labels": result["seed_labels"],
        "metrics": result["metrics"],
        "physical_fits": result["physical_fits"],
        "runtime_seconds": result["runtime_seconds"],
        "best_epoch_range": [min(epochs), max(epochs)] if epochs else None,
    }


def _selection_key(result: Mapping[str, Any], identity: str) -> tuple[float, float, str]:
    return (-result["metrics"]["mean_fold_roc_auc"], -result["metrics"]["pooled"]["tss"], identity)


def _extend_selected(
    config: Mapping[str, Any], target: str, fraction: int, family: str, selected: Mapping[str, Any], prepared: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    desired = config["conventional"]["selected_seed_labels"][family]
    missing = [label for label in desired if label not in selected["seed_labels"]]
    if not missing:
        return dict(selected)
    extra = _evaluate(config, target, fraction, family, selected["candidate_id"], missing, prepared)
    folds = []
    for base, added in zip(selected["folds"], extra["folds"]):
        combined = {**base["scores_by_seed"], **added["scores_by_seed"]}
        folds.append({**base, "scores_by_seed": combined, "score": np.mean(np.vstack([combined[label] for label in desired]), axis=0)})
    return {
        "candidate_id": selected["candidate_id"],
        "seed_labels": list(desired),
        "folds": folds,
        "metrics": summarize_oof(folds),
        "fit_records": [*selected["fit_records"], *extra["fit_records"]],
        "physical_fits": selected["physical_fits"] + extra["physical_fits"],
        "runtime_seconds": selected["runtime_seconds"] + extra["runtime_seconds"],
    }


def _family_gate(family: str, complete_candidates: int, minimum: int) -> str:
    if complete_candidates >= minimum:
        return "available"
    if family == "intercept":
        raise SeawfbModelingError("mandatory_intercept_unavailable")
    return "unavailable"


def _family_physical_fits(result: Mapping[str, Any]) -> int:
    if result.get("status") != "available":
        return int(sum(candidate["physical_fits"] for candidate in result["candidates"]))
    selected = result["selected"]
    screened = next(
        candidate["physical_fits"]
        for candidate in result["candidates"]
        if candidate["candidate_id"] == selected["candidate_id"]
    )
    return int(
        sum(candidate["physical_fits"] for candidate in result["candidates"])
        + max(0, selected["physical_fits"] - screened)
    )


def _family_coverage(available: int, planned: int) -> float:
    require(planned > 0 and 0 <= available <= planned, "family_coverage_inputs_invalid")
    coverage = available / planned
    require(coverage >= 0.95, "family_coverage_below_0.95")
    return coverage


def _primary_full_family_gate(families: Mapping[str, Mapping[str, Any]]) -> None:
    available = {
        family
        for family, result in families.items()
        if result.get("status") == "available"
    }
    require("intercept" in available, "primary_full_intercept_unavailable")
    require("elastic_net" in available, "primary_full_elastic_net_unavailable")
    require("shallow_ann" in available, "primary_full_shallow_ann_unavailable")
    require(
        bool({"random_forest", "hist_gradient_boosting"} & available),
        "primary_full_tree_family_unavailable",
    )


def _validation_support(prepared: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    folds = []
    for item in prepared:
        rows = item["validation_rows"]
        presence = int(np.sum(rows.y == 1))
        background = int(np.sum(rows.y == 0))
        folds.append(
            {
                "fold": int(item["fold"]),
                "presence": presence,
                "background": background,
                "rows": presence + background,
            }
        )
    require([item["fold"] for item in folds] == list(range(5)), "validation_support_fold_drift")
    presence = sum(item["presence"] for item in folds)
    background = sum(item["background"] for item in folds)
    rows = presence + background
    require(rows > 0 and presence > 0 and background > 0, "validation_support_invalid")
    return {
        "presence": presence,
        "background": background,
        "rows": rows,
        "constructed_prevalence": presence / rows,
        "folds": folds,
    }


def _prevalence_diagnostic(
    endpoints: Sequence[Mapping[str, Any]],
    families: Sequence[str],
    minimum_coverage: float,
) -> dict[str, Any]:
    """Check model-family availability at both prevalence extremes."""

    require(len(endpoints) >= 4 and 0 <= minimum_coverage <= 1, "prevalence_diagnostic_inputs_invalid")
    ranked = sorted(
        endpoints,
        key=lambda item: (
            float(item["validation_support"]["constructed_prevalence"]),
            str(item["target"]),
            int(item["target_fraction"]),
        ),
    )
    quartile_size = len(ranked) // 4
    require(quartile_size > 0, "prevalence_quartile_empty")
    groups = {"lowest": ranked[:quartile_size], "highest": ranked[-quartile_size:]}
    output: dict[str, Any] = {
        "ranking": "constructed_validation_prevalence_then_target_then_fraction",
        "quartile_size": quartile_size,
        "minimum_coverage": minimum_coverage,
        "action": "stop_for_review",
        "quartiles": {},
    }
    for label, selected in groups.items():
        availability = {}
        for family in families:
            available = sum(item["families"][family]["status"] == "available" for item in selected)
            coverage = available / quartile_size
            require(coverage >= minimum_coverage, f"prevalence_{label}_{family}_coverage_below_threshold")
            availability[family] = {"available": available, "planned": quartile_size, "coverage": coverage}
        output["quartiles"][label] = {
            "prevalence_range": [
                float(selected[0]["validation_support"]["constructed_prevalence"]),
                float(selected[-1]["validation_support"]["constructed_prevalence"]),
            ],
            "endpoint_digest": digest(
                [
                    [item["target"], int(item["target_fraction"]), item["validation_support"]["constructed_prevalence"]]
                    for item in selected
                ]
            ),
            "family_availability": availability,
        }
    return output


def _prediction_rows(target: str, fraction: int, auxiliary: str, method: str, family: str, result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "target": target,
            "target_fraction": fraction,
            "auxiliary_size": auxiliary,
            "fold": int(fold["fold"]),
            "cell_id": cell,
            "y": int(y),
            "method": method,
            "family": family,
            "candidate_id": result["candidate_id"],
            "score": float(score),
        }
        for fold in result["folds"]
        for cell, y, score in zip(fold["cell_ids"], fold["y"], fold["score"])
    ]


def _task_paths(root: Path, config: Mapping[str, Any], target: str, fraction: int) -> tuple[Path, Path]:
    directory = _private_root(root, config) / "endpoints"
    stem = f"{slug(target)}_target{fraction}"
    return directory / f"{stem}.json", directory / f"{stem}.parquet"


def run_endpoint(root: Path, store: SeawfbStore, config: Mapping[str, Any], target: str, fraction: int) -> dict[str, Any]:
    started = time.perf_counter()
    base_prepared = _prepared_folds(root, store, config, target, fraction, None)
    families: dict[str, Any] = {}
    predictions: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for family in config["conventional"]["families"]:
        candidates = []
        family_failures = []
        for candidate_id in config["conventional"]["candidate_ids"][family]:
            try:
                candidate = _evaluate(
                    config,
                    target,
                    fraction,
                    family,
                    candidate_id,
                    config["conventional"]["screen_seed_labels"][family],
                    base_prepared,
                )
                candidates.append(candidate)
                predictions.extend(_prediction_rows(target, fraction, "none", "candidate_screen", family, candidate))
            except (SeawfbModelingError, ModelAdapterError, ValueError) as exc:
                failure = {"family": family, "candidate_id": candidate_id, "error": str(exc)}
                failures.append(failure)
                family_failures.append(failure)
        status = _family_gate(
            family,
            len(candidates),
            int(config["conventional"]["minimum_complete_candidates"][family]),
        )
        if status == "unavailable":
            families[family] = {
                "status": status,
                "candidates": [_public(item) for item in candidates],
                "selected": None,
                "failures": family_failures,
            }
            continue
        selected = min(candidates, key=lambda item: _selection_key(item, item["candidate_id"]))
        selected = _extend_selected(config, target, fraction, family, selected, base_prepared)
        predictions.extend(_prediction_rows(target, fraction, "none", "family_selected", family, selected))
        families[family] = {"status": status, "candidates": [_public(item) for item in candidates], "selected": _public(selected), "failures": family_failures, "_private": selected}
    non_null = [
        family
        for family in families
        if family != "intercept" and families[family]["status"] == "available"
    ]
    require(bool(non_null), "no_non_null_family_available")
    best_family = min(non_null, key=lambda family: _selection_key(families[family]["_private"], family))
    best = families[best_family]["_private"]
    q_results = {}
    auxiliaries = ["full", *( ["20", "80"] if fraction == 100 and target in store.primary_targets else [])]
    for auxiliary in auxiliaries:
        prepared = _prepared_folds(root, store, config, target, fraction, auxiliary)
        q_result = _evaluate(
            config,
            target,
            fraction,
            best_family,
            best["candidate_id"],
            config["conventional"]["selected_seed_labels"][best_family],
            prepared,
        )
        predictions.extend(_prediction_rows(target, fraction, auxiliary, "q_linear", best_family, q_result))
        q_results[auxiliary] = {"family": best_family, "candidate_retuned": False, **_public(q_result)}
    for family in families:
        families[family].pop("_private", None)
    result_path, prediction_path = _task_paths(root, config, target, fraction)
    _atomic_parquet(prediction_path, pa.Table.from_pylist(predictions, schema=PREDICTION_SCHEMA))
    result = {
        "schema_version": "goal051-endpoint-v1",
        "identity": _identity(root),
        "target": target,
        "target_fraction": fraction,
        "validation_support": _validation_support(base_prepared),
        "families": families,
        "best_non_null_family": best_family,
        "q_linear": q_results,
        "candidate_failures": failures,
        "prediction_rows": len(predictions),
        "prediction_sha256": sha256_file(prediction_path),
        "physical_fits": sum(_family_physical_fits(family) for family in families.values())
        + sum(item["physical_fits"] for item in q_results.values()),
        "runtime_seconds": time.perf_counter() - started,
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    _atomic_json(result_path, result)
    return result


def _checkpoint(root: Path, config: Mapping[str, Any], identity: Mapping[str, str], target: str, fraction: int) -> dict[str, Any] | None:
    result_path, prediction_path = _task_paths(root, config, target, fraction)
    if not result_path.is_file() or not prediction_path.is_file():
        return None
    result = _read_json(result_path)
    if (
        result.get("identity") != identity
        or result.get("target") != target
        or result.get("target_fraction") != fraction
        or result.get("prediction_sha256") != sha256_file(prediction_path)
    ):
        return None
    return result


def replay_endpoint(
    root: Path,
    config: Mapping[str, Any],
    target: str,
    fraction: int,
    store: SeawfbStore,
) -> dict[str, Any]:
    identity = _identity(root)
    result = _checkpoint(root, config, identity, target, fraction)
    require(result is not None, f"endpoint_checkpoint_missing:{target}:{fraction}")
    require(result.get("schema_version") == "goal051-endpoint-v1", "endpoint_schema_drift")
    require(
        result.get("outer_response_rows_read") == 0
        and result.get("outer_predictor_rows_used") == 0,
        "endpoint_outer_firewall_drift",
    )
    _, prediction_path = _task_paths(root, config, target, fraction)
    frame = pq.read_table(prediction_path).to_pandas()
    require(len(frame) == result.get("prediction_rows"), "prediction_row_count_drift")
    require(
        set(frame.target) == {target}
        and set(frame.target_fraction) == {fraction}
        and np.isfinite(frame.score.to_numpy(dtype=np.float64)).all()
        and frame.score.between(0, 1).all(),
        "prediction_payload_invalid",
    )
    expected_groups = set()
    for family, family_result in result["families"].items():
        expected_groups.update(
            ("candidate_screen", family, candidate["candidate_id"], "none")
            for candidate in family_result["candidates"]
        )
        if family_result["status"] == "available":
            expected_groups.add(("family_selected", family, family_result["selected"]["candidate_id"], "none"))
    expected_groups.update(
        ("q_linear", item["family"], item["candidate_id"], auxiliary)
        for auxiliary, item in result["q_linear"].items()
    )
    observed_groups = set(
        frame[["method", "family", "candidate_id", "auxiliary_size"]].itertuples(index=False, name=None)
    )
    require(observed_groups == expected_groups, "prediction_group_inventory_drift")

    def replay(method: str, family: str, candidate: str, auxiliary: str) -> dict[str, Any]:
        subset = frame[
            (frame.method == method)
            & (frame.family == family)
            & (frame.candidate_id == candidate)
            & (frame.auxiliary_size == auxiliary)
        ]
        require(len(subset) > 0, f"prediction_group_missing:{method}:{family}:{candidate}:{auxiliary}")
        require(not subset.duplicated(["fold", "cell_id"]).any(), f"prediction_group_duplicate:{method}:{family}:{candidate}:{auxiliary}")
        require(set(subset.fold) == set(range(5)), f"prediction_fold_inventory:{method}:{family}:{candidate}:{auxiliary}")
        folds = []
        for fold, part in subset.groupby("fold", sort=True):
            canonical = store.target_rows(target, int(fold), 100, "validation")
            require(tuple(part.cell_id.astype(str)) == canonical.cell_ids, f"prediction_assessment_cells_drift:{method}:{family}:{candidate}:{auxiliary}:{fold}")
            require(np.array_equal(part.y.to_numpy(dtype=np.int8), canonical.y), f"prediction_assessment_labels_drift:{method}:{family}:{candidate}:{auxiliary}:{fold}")
            folds.append({"fold": int(fold), "y": canonical.y, "score": part.score.to_numpy()})
        return summarize_oof(folds)

    canonical_prepared = [
        {"fold": fold, "validation_rows": store.target_rows(target, fold, 100, "validation")}
        for fold in range(5)
    ]
    require(result.get("validation_support") == _validation_support(canonical_prepared), "validation_support_replay_failed")

    for family, family_result in result["families"].items():
        for candidate in family_result["candidates"]:
            require(replay("candidate_screen", family, candidate["candidate_id"], "none") == candidate["metrics"], "candidate_metric_replay_failed")
        if family_result["status"] == "unavailable":
            require(family != "intercept" and family_result["selected"] is None, "unavailable_family_state_drift")
            continue
        selected = family_result["selected"]
        require(replay("family_selected", family, selected["candidate_id"], "none") == selected["metrics"], "selected_metric_replay_failed")
        chosen = min(family_result["candidates"], key=lambda item: _selection_key(item, item["candidate_id"]))
        require(chosen["candidate_id"] == selected["candidate_id"], "candidate_selection_replay_failed")
    non_null = [family for family in result["families"] if family != "intercept" and result["families"][family]["status"] == "available"]
    family_choice = min(non_null, key=lambda family: _selection_key(result["families"][family]["selected"], family))
    require(family_choice == result["best_non_null_family"], "family_selection_replay_failed")
    for auxiliary, q_result in result["q_linear"].items():
        require(q_result["candidate_retuned"] is False, "q_candidate_retuned")
        require(q_result["family"] == family_choice, "q_family_drift")
        require(replay("q_linear", family_choice, q_result["candidate_id"], auxiliary) == q_result["metrics"], "q_metric_replay_failed")
    return {"target": target, "target_fraction": fraction, "status": "replayed", "prediction_rows": len(frame)}


def q_provenance(root: Path, config: Mapping[str, Any], require_complete: bool) -> dict[str, Any]:
    crossfit = _read_json(root / CROSSFIT_PATH)
    identity = _identity(root)
    records = []
    for block, fold, auxiliary in q_surface_specs(crossfit):
        loaded = _load_q(root, config, identity, block, fold, auxiliary)
        if loaded is None:
            continue
        _, receipt = loaded
        expected_heads = crossfit["auxiliary_sets"][str(block)][auxiliary]
        held = {
            species
            for species, assigned in crossfit["focal_blocks"].items()
            if int(assigned) == block
        }
        require(set(receipt["heads"]) == set(expected_heads), "q_receipt_head_inventory_drift")
        require(held.isdisjoint(receipt["heads"]), "q_receipt_block_leakage")
        require(receipt["head_count"] == len(expected_heads), "q_receipt_head_count_drift")
        require(receipt["richness"] == "R_complement" and receipt["within_head_class_balancing"] is False, "q_receipt_science_drift")
        low, high = receipt["head_total_weight_range"]
        require(np.isclose(low, high, rtol=0, atol=1e-8), "q_receipt_head_weight_drift")
        records.append(
            {
                "block": block,
                "fold": fold,
                "auxiliary_size": auxiliary,
                "model_sha256": receipt["model_sha256"],
                "parameter_digest": receipt["parameter_digest"],
                "attempts": receipt["attempts"],
                "accepted_attempt": receipt["accepted_attempt"],
                "k": receipt["k"],
                "canonical_C": receipt["canonical_C"],
                "solver_C": receipt["solver_C"],
                "representation": receipt["representation"],
                "head_count": receipt["head_count"],
                "expanded_rows": receipt["expanded_rows"],
                "collapsed_rows": receipt["collapsed_rows"],
                "runtime_seconds": receipt["runtime_seconds"],
            }
        )
    if require_complete:
        require(len(records) == 150, "q_surface_completion_failed")
    return {
        "ready": len(records),
        "total": 150,
        "combined_receipt_digest": digest(records),
        "by_auxiliary_size": {
            auxiliary: sum(item["auxiliary_size"] == auxiliary for item in records)
            for auxiliary in ("20", "80", "full")
        },
        "expanded_rows_total": int(sum(item["expanded_rows"] for item in records)),
        "collapsed_rows_total": int(sum(item["collapsed_rows"] for item in records)),
        "runtime_seconds_total": float(sum(item["runtime_seconds"] for item in records)),
        "whole_focal_block_excluded": True,
        "richness": "R_complement",
        "equal_total_head_weight": True,
        "within_head_class_balancing": False,
    }


def aggregate(root: Path) -> dict[str, Any]:
    config = _config(root)
    curves = _read_json(root / CURVES_PATH)
    identity = _identity(root)
    store = SeawfbStore(root)
    endpoint_summaries, private = [], []
    primary = set(curves["applies_to"]["primary_targets"])
    available_groups = 0
    available_by_family = {family: 0 for family in config["conventional"]["families"]}
    planned_groups = len(target_endpoints(curves)) * len(config["conventional"]["families"])
    total_physical_fits = 0
    total_prediction_rows = 0
    total_runtime = 0.0
    total_failures = 0
    for target, fraction in target_endpoints(curves):
        result = _checkpoint(root, config, identity, target, fraction)
        require(result is not None, f"endpoint_checkpoint_missing:{target}:{fraction}")
        replay_endpoint(root, config, target, fraction, store)
        require(set(result["families"]) == set(config["conventional"]["families"]), "family_group_inventory_drift")
        expected_auxiliaries = {"full", *({"20", "80"} if target in primary and fraction == 100 else set())}
        require(set(result["q_linear"]) == expected_auxiliaries, "q_endpoint_inventory_drift")
        for family, family_result in result["families"].items():
            available_by_family[family] += family_result["status"] == "available"
        available_groups += sum(item["status"] == "available" for item in result["families"].values())
        if target in primary and fraction == 100:
            _primary_full_family_gate(result["families"])
        total_physical_fits += int(result["physical_fits"])
        total_prediction_rows += int(result["prediction_rows"])
        total_runtime += float(result["runtime_seconds"])
        total_failures += len(result["candidate_failures"])
        result_path, prediction_path = _task_paths(root, config, target, fraction)
        endpoint_summaries.append(
            {
                "target": target,
                "target_fraction": fraction,
                "validation_support": result["validation_support"],
                "best_non_null_family": result["best_non_null_family"],
                "families": result["families"],
                "q_linear": result["q_linear"],
                "candidate_failures": result["candidate_failures"],
            }
        )
        private.append({"endpoint": f"{slug(target)}_target{fraction}", "result_sha256": sha256_file(result_path), "prediction_sha256": sha256_file(prediction_path), "prediction_rows": result["prediction_rows"]})
    coverage = _family_coverage(available_groups, planned_groups)
    family_coverage = {
        family: {
            "available": available,
            "planned": len(endpoint_summaries),
            "coverage": _family_coverage(available, len(endpoint_summaries)),
        }
        for family, available in available_by_family.items()
    }
    prevalence_gate = config["planned_inventory"]["prevalence_failure_gate"]
    prevalence_diagnostic = _prevalence_diagnostic(
        endpoint_summaries,
        config["conventional"]["families"],
        float(prevalence_gate["extreme_quartile_minimum_coverage"]),
    )
    summary = {
        "schema_version": "goal051-summary-v1",
        "status": "complete",
        "identity": identity,
        "target_endpoints": len(endpoint_summaries),
        "q_conditions": sum(len(item["q_linear"]) for item in endpoint_summaries),
        "family_availability": {
            "available_groups": available_groups,
            "planned_groups": planned_groups,
            "coverage": coverage,
            "minimum_accepted": 0.95,
            "primary_full_required": "intercept_elastic_net_shallow_ann_and_at_least_one_tree",
            "by_family": family_coverage,
        },
        "prevalence_failure_diagnostic": prevalence_diagnostic,
        "q_surface_provenance": q_provenance(root, config, require_complete=True),
        "totals": {
            "physical_fits": total_physical_fits,
            "prediction_rows": total_prediction_rows,
            "runtime_seconds": total_runtime,
            "candidate_failures": total_failures,
        },
        "endpoints": endpoint_summaries,
        "private_outputs": private,
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    require(summary["target_endpoints"] == 303 and summary["q_conditions"] == 449, "aggregate_endpoint_count_drift")
    _atomic_json(root / config["execution"]["tracked_summary"], summary)
    return summary


def validate(root: Path, complete: bool = False) -> dict[str, Any]:
    inputs = validate_inputs(root)
    config = _config(root)
    crossfit = _read_json(root / CROSSFIT_PATH)
    identity = _identity(root)
    q_receipts = q_provenance(root, config, require_complete=True) if complete else None
    ready_q = q_receipts["ready"] if complete else sum(
        _load_q(root, config, identity, *spec) is not None for spec in q_surface_specs(crossfit)
    )
    receipt = {**inputs, "q_surfaces_ready": ready_q, "complete_required": complete}
    if complete:
        summary_path = root / config["execution"]["tracked_summary"]
        require(summary_path.is_file(), "goal051_summary_missing")
        summary = _read_json(summary_path)
        require(summary.get("identity") == identity and summary.get("target_endpoints") == 303 and summary.get("q_conditions") == 449, "goal051_summary_drift")
        require(q_receipts == summary["q_surface_provenance"], "q_summary_provenance_drift")
        curves = _read_json(root / CURVES_PATH)
        store = SeawfbStore(root)
        endpoint_specs = target_endpoints(curves)
        summary_endpoints = {
            (item["target"], int(item["target_fraction"])): item
            for item in summary["endpoints"]
        }
        require(len(summary_endpoints) == len(summary["endpoints"]) == 303, "summary_endpoint_inventory_drift")
        primary = set(curves["applies_to"]["primary_targets"])
        available_groups = physical_fits = prediction_rows = candidate_failures = 0
        available_by_family = {family: 0 for family in config["conventional"]["families"]}
        runtime_seconds = 0.0
        expected_private = []
        for target, fraction in endpoint_specs:
            result = _checkpoint(root, config, identity, target, fraction)
            require(result is not None, f"endpoint_checkpoint_missing:{target}:{fraction}")
            replay_endpoint(root, config, target, fraction, store)
            expected_auxiliaries = {"full", *({"20", "80"} if target in primary and fraction == 100 else set())}
            require(set(result["q_linear"]) == expected_auxiliaries, "q_endpoint_inventory_drift")
            if target in primary and fraction == 100:
                _primary_full_family_gate(result["families"])
            expected_summary = {
                "target": target,
                "target_fraction": fraction,
                "validation_support": result["validation_support"],
                "best_non_null_family": result["best_non_null_family"],
                "families": result["families"],
                "q_linear": result["q_linear"],
                "candidate_failures": result["candidate_failures"],
            }
            require(summary_endpoints.get((target, fraction)) == expected_summary, "summary_endpoint_replay_drift")
            available_groups += sum(item["status"] == "available" for item in result["families"].values())
            for family, family_result in result["families"].items():
                available_by_family[family] += family_result["status"] == "available"
            physical_fits += int(result["physical_fits"])
            prediction_rows += int(result["prediction_rows"])
            runtime_seconds += float(result["runtime_seconds"])
            candidate_failures += len(result["candidate_failures"])
            result_path, prediction_path = _task_paths(root, config, target, fraction)
            expected_private.append({"endpoint": f"{slug(target)}_target{fraction}", "result_sha256": sha256_file(result_path), "prediction_sha256": sha256_file(prediction_path), "prediction_rows": result["prediction_rows"]})
        planned_groups = len(endpoint_specs) * len(config["conventional"]["families"])
        expected_availability = {
            "available_groups": available_groups,
            "planned_groups": planned_groups,
            "coverage": available_groups / planned_groups,
            "minimum_accepted": 0.95,
            "primary_full_required": "intercept_elastic_net_shallow_ann_and_at_least_one_tree",
            "by_family": {
                family: {
                    "available": available,
                    "planned": len(endpoint_specs),
                    "coverage": _family_coverage(available, len(endpoint_specs)),
                }
                for family, available in available_by_family.items()
            },
        }
        _family_coverage(available_groups, planned_groups)
        require(summary["family_availability"] == expected_availability, "summary_family_coverage_drift")
        expected_prevalence = _prevalence_diagnostic(
            list(summary_endpoints.values()),
            config["conventional"]["families"],
            float(config["planned_inventory"]["prevalence_failure_gate"]["extreme_quartile_minimum_coverage"]),
        )
        require(summary.get("prevalence_failure_diagnostic") == expected_prevalence, "summary_prevalence_diagnostic_drift")
        require(summary["private_outputs"] == expected_private, "summary_private_receipt_drift")
        require(
            summary["totals"]
            == {
                "physical_fits": physical_fits,
                "prediction_rows": prediction_rows,
                "runtime_seconds": runtime_seconds,
                "candidate_failures": candidate_failures,
            },
            "summary_totals_drift",
        )
        receipt["endpoint_replays"] = len(endpoint_specs)
        receipt["status"] = "goal051_complete_valid"
    return receipt


def _expected_canary_tags(config: Mapping[str, Any], host_key: str) -> list[str]:
    require(host_key in {"mac", "deep_server"}, "canary_host_key_invalid")
    spec = config["execution"]["canary"]
    mixed = int(spec["mixed_concurrency"][host_key])
    return [
        *(f"{host_key}-serial-{index}" for index in range(1, int(spec["serial_repeats"]) + 1)),
        *(f"{host_key}-mixed-{index}" for index in range(1, mixed + 1)),
    ]


def _canary_tag_parts(config: Mapping[str, Any], tag: str | None) -> tuple[str, str, int]:
    require(isinstance(tag, str), "canary_receipt_tag_required")
    match = re.fullmatch(r"(mac|deep_server)-(serial|mixed)-([1-9][0-9]*)", tag)
    require(match is not None, "canary_receipt_tag_invalid")
    host_key, mode, index_text = match.groups()
    require(tag in _expected_canary_tags(config, host_key), "canary_receipt_tag_not_planned")
    return host_key, mode, int(index_text)


def _canary_receipt_path(root: Path, config: Mapping[str, Any], receipt_tag: str | None) -> tuple[Path, str]:
    _canary_tag_parts(config, receipt_tag)
    tag = str(receipt_tag)
    base = root / config["execution"]["canary_receipt"]
    return base.with_name(f"{base.stem}-{tag}{base.suffix}"), tag


def _require_canary_host(config: Mapping[str, Any], host_key: str) -> dict[str, str]:
    expected = config["execution"]["canary"]["host_expectations"].get(host_key)
    require(expected == EXPECTED_CANARY_HOSTS.get(host_key), "canary_host_expectation_invalid")
    require(
        platform.node() == expected["hostname"] and platform.system() == expected["system"],
        f"canary_actual_host_mismatch:{host_key}",
    )
    return expected


def _interval_peak(intervals: Sequence[tuple[int, int]]) -> int:
    require(bool(intervals) and all(end > start for start, end in intervals), "canary_interval_invalid")
    events = [(value, delta) for start, end in intervals for value, delta in ((start, 1), (end, -1))]
    active = peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        peak = max(peak, active)
    return peak


def _canary(root: Path, receipt_tag: str | None = None) -> dict[str, Any]:
    """Run a family-representative engineering probe without computing metrics."""

    start_epoch_ns = time.time_ns()
    wall_started = time.perf_counter()
    config = _config(root)
    validate_inputs(root)
    host_key, run_mode, run_index = _canary_tag_parts(config, receipt_tag)
    _require_canary_host(config, host_key)
    store = SeawfbStore(root)
    spec = config["execution"]["canary"]
    target = spec["target"]
    fold = int(str(spec["held_fold"]).replace("fold", ""))
    fraction = int(spec["target_fraction"])
    train_rows = store.target_rows(target, fold, fraction, "train")
    validation_rows = store.target_rows(target, fold, 100, "validation")
    train = store.batch(target, train_rows, fold)
    validation_batch = store.batch(target, validation_rows, fold)
    entries = []
    for candidate_id in spec["candidate_ids"]:
        family = CANONICAL_CANDIDATES[candidate_id]["family"]
        started = time.perf_counter()
        scores, fit = _fit_predict(config, target, fraction, fold, family, candidate_id, "seed00", train_rows, train, validation_batch)
        entries.append(
            {
                "family": family,
                "candidate_id": candidate_id,
                "runtime_seconds": time.perf_counter() - started,
                "physical_fits": fit["physical_fits"],
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "converged": fit["converged"],
                "best_epoch": fit["best_epoch"],
                "prediction_count": len(scores),
                "finite": bool(np.isfinite(scores).all()),
                "prediction_range": [float(np.min(scores)), float(np.max(scores))],
                "prediction_digest": hashlib.sha256(scores.tobytes()).hexdigest(),
            }
        )
    block = int(store.crossfit["focal_blocks"][target])
    require(spec["focal_block"] == f"block{block}", "canary_focal_block_drift")
    auxiliary_sizes = [str(value) for value in spec["auxiliary_sizes"]]
    require(auxiliary_sizes == ["20", "full"], "canary_auxiliary_inventory_drift")
    q_entries = []
    for auxiliary in auxiliary_sizes:
        q_started = time.perf_counter()
        q_model, q_fit = fit_q_linear(
            store,
            block,
            fold,
            auxiliary,
            seed_namespace=_seed_namespace(config, "q"),
            numerical_fit=config["community_control"]["numerical_fit"],
        )
        train_q, validation_q, scale = standardized_q(q_model, store, fold, train_rows, validation_rows)
        q_train = store.batch(target, train_rows, fold, train_q)
        q_validation = store.batch(target, validation_rows, fold, validation_q)
        q_scores, q_downstream = _fit_predict(
            config,
            target,
            fraction,
            fold,
            spec["q_augmented_family"],
            "hgb04",
            "seed00",
            train_rows,
            q_train,
            q_validation,
        )
        q_entries.append(
            {
                "auxiliary_size": auxiliary,
                "runtime_seconds": time.perf_counter() - q_started,
                "process_peak_rss_bytes": _peak_rss_bytes(),
                "expanded_rows": q_fit["expanded_rows"],
                "collapsed_rows": q_fit["collapsed_rows"],
                "head_count": q_fit["head_count"],
                "iterations": q_fit["iterations"],
                "converged": True,
                "attempts": q_fit["attempts"],
                "accepted_attempt": q_fit["accepted_attempt"],
                "k": q_fit["k"],
                "canonical_C": q_fit["canonical_C"],
                "solver_C": q_fit["solver_C"],
                "representation": q_fit["representation"],
                "parameter_digest": q_fit["parameter_digest"],
                "standardization": scale,
                "downstream_family": spec["q_augmented_family"],
                "downstream_candidate_id": "hgb04",
                "prediction_count": len(q_scores),
                "finite": bool(np.isfinite(q_scores).all()),
                "prediction_range": [float(np.min(q_scores)), float(np.max(q_scores))],
                "prediction_digest": hashlib.sha256(q_scores.tobytes()).hexdigest(),
                "downstream_fit": q_downstream,
            }
        )
    receipt_path, resolved_tag = _canary_receipt_path(root, config, receipt_tag)
    end_epoch_ns = time.time_ns()
    receipt = {
        "schema_version": "goal051-canary-v1",
        "identity": _identity(root),
        "status": "metric_free_complete",
        "host": platform.node(),
        "system": platform.system(),
        "platform": platform.platform(),
        "target": target,
        "held_fold": fold,
        "focal_block": block,
        "receipt_tag": resolved_tag,
        "host_key": host_key,
        "run_mode": run_mode,
        "run_index": run_index,
        "receipt_path": str(receipt_path.relative_to(root)),
        "start_epoch_ns": start_epoch_ns,
        "end_epoch_ns": end_epoch_ns,
        "total_wall_seconds": time.perf_counter() - wall_started,
        "metrics_computed": False,
        "entries": entries,
        "q_linear": q_entries,
        "process_peak_rss_bytes": _peak_rss_bytes(),
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    require(spec["metrics_allowed"] is False, "canary_metrics_enabled")
    _atomic_json(receipt_path, receipt)
    return receipt


def canary(root: Path, receipt_tag: str | None = None) -> dict[str, Any]:
    """Run one canary with the production one-thread estimator contract."""

    with threadpool_limits(limits=1):
        return _canary(root, receipt_tag)


def _canary_process(root: str, receipt_tag: str) -> str:
    return canary(Path(root), receipt_tag)["receipt_tag"]


def canary_batch(root: Path, host_key: str) -> dict[str, Any]:
    """Execute the frozen serial and truly concurrent canary schedule."""

    config = _config(root)
    validate_inputs(root)
    _require_canary_host(config, host_key)
    tags = _expected_canary_tags(config, host_key)
    serial = [tag for tag in tags if "-serial-" in tag]
    mixed = [tag for tag in tags if "-mixed-" in tag]
    for tag in serial:
        canary(root, tag)
    configured = int(config["execution"]["canary"]["mixed_concurrency"][host_key])
    require(len(mixed) == configured, "canary_mixed_schedule_drift")
    with ProcessPoolExecutor(max_workers=configured, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(_canary_process, str(root), tag) for tag in mixed]
        completed = {future.result() for future in as_completed(futures)}
    require(completed == set(mixed), "canary_mixed_completion_drift")
    return canary_summary(root, host_key)


def canary_summary(root: Path, host_key: str) -> dict[str, Any]:
    """Aggregate the exact metric-free receipt inventory for one host class."""

    config = _config(root)
    identity = _identity(root)
    spec = config["execution"]["canary"]
    require(spec.get("host_expectations") == EXPECTED_CANARY_HOSTS, "canary_host_expectations_drift")
    tags = _expected_canary_tags(config, host_key)
    receipts = []
    expected_candidates = list(spec["candidate_ids"])
    expected_auxiliary = [str(value) for value in spec["auxiliary_sizes"]]
    expected_host = spec["host_expectations"][host_key]
    for tag in tags:
        path, _ = _canary_receipt_path(root, config, tag)
        require(path.is_file(), f"canary_receipt_missing:{tag}")
        receipt = _read_json(path)
        expected_host_key, expected_mode, expected_index = _canary_tag_parts(config, tag)
        require(receipt.get("schema_version") == "goal051-canary-v1", f"canary_schema_drift:{tag}")
        require(receipt.get("identity") == identity, f"canary_identity_drift:{tag}")
        require(receipt.get("status") == "metric_free_complete", f"canary_status_drift:{tag}")
        require(
            receipt.get("receipt_tag") == tag
            and receipt.get("receipt_path") == str(path.relative_to(root))
            and receipt.get("host_key") == expected_host_key
            and receipt.get("run_mode") == expected_mode
            and receipt.get("run_index") == expected_index,
            f"canary_run_identity_drift:{tag}",
        )
        require(
            receipt.get("host") == expected_host["hostname"]
            and receipt.get("system") == expected_host["system"]
            and isinstance(receipt.get("platform"), str)
            and bool(receipt["platform"]),
            f"canary_actual_host_mismatch:{tag}",
        )
        require(
            receipt.get("metrics_computed") is False
            and "metrics" not in receipt
            and receipt.get("outer_response_rows_read") == 0
            and receipt.get("outer_predictor_rows_used") == 0,
            f"canary_science_firewall_drift:{tag}",
        )
        expected_fold = int(str(spec["held_fold"]).replace("fold", ""))
        expected_block = int(str(spec["focal_block"]).replace("block", ""))
        require(
            receipt.get("target") == spec["target"]
            and receipt.get("held_fold") == expected_fold
            and receipt.get("focal_block") == expected_block,
            f"canary_endpoint_drift:{tag}",
        )
        start = receipt.get("start_epoch_ns")
        end = receipt.get("end_epoch_ns")
        wall = receipt.get("total_wall_seconds")
        require(
            isinstance(start, int)
            and isinstance(end, int)
            and end > start
            and isinstance(wall, (int, float))
            and np.isfinite(wall)
            and wall > 0,
            f"canary_timing_invalid:{tag}",
        )
        entries = receipt.get("entries", [])
        require([item.get("candidate_id") for item in entries] == expected_candidates, f"canary_candidate_inventory_drift:{tag}")
        q_entries = receipt.get("q_linear", [])
        require([str(item.get("auxiliary_size")) for item in q_entries] == expected_auxiliary, f"canary_q_inventory_drift:{tag}")
        for item in entries:
            low, high = item.get("prediction_range", [np.nan, np.nan])
            require(
                item.get("finite") is True
                and item.get("converged") is True
                and item.get("family") == CANONICAL_CANDIDATES.get(item.get("candidate_id"), {}).get("family")
                and int(item.get("prediction_count", 0)) > 0
                and "metrics" not in item
                and np.isfinite([low, high]).all()
                and 0 <= low <= high <= 1
                and isinstance(item.get("prediction_digest"), str),
                f"canary_candidate_fit_invalid:{tag}:{item.get('candidate_id')}",
            )
        for item in q_entries:
            low, high = item.get("prediction_range", [np.nan, np.nan])
            downstream = item.get("downstream_fit", {})
            _validate_q_attempts(item, config["community_control"]["numerical_fit"])
            _validate_q_weight_rescaling(item)
            require(
                item.get("converged") is True
                and item.get("finite") is True
                and item.get("downstream_family") == spec["q_augmented_family"]
                and item.get("downstream_candidate_id") == "hgb04"
                and downstream.get("converged") is True
                and int(item.get("prediction_count", 0)) > 0
                and int(item.get("expanded_rows", 0)) > 0
                and int(item.get("collapsed_rows", 0)) > 0
                and int(item.get("head_count", 0)) > 0
                and bool(re.fullmatch(r"[0-9a-f]{64}", str(item.get("parameter_digest", ""))))
                and "metrics" not in item
                and "metrics" not in downstream
                and np.isfinite([low, high]).all()
                and 0 <= low <= high <= 1
                and isinstance(item.get("prediction_digest"), str),
                f"canary_q_fit_invalid:{tag}:{item.get('auxiliary_size')}",
            )
        require(int(receipt.get("process_peak_rss_bytes", 0)) > 0, f"canary_peak_rss_invalid:{tag}")
        receipts.append(receipt)

    digest_groups: dict[str, set[str]] = {}
    parameter_digest_groups: dict[str, set[str]] = {}
    for receipt in receipts:
        for item in receipt["entries"]:
            digest_groups.setdefault(f"candidate:{item['candidate_id']}", set()).add(item["prediction_digest"])
        for item in receipt["q_linear"]:
            digest_groups.setdefault(f"q:{item['auxiliary_size']}", set()).add(item["prediction_digest"])
            parameter_digest_groups.setdefault(str(item["auxiliary_size"]), set()).add(item["parameter_digest"])
    require(all(len(values) == 1 for values in digest_groups.values()), "canary_prediction_digest_instability")
    require(all(len(values) == 1 for values in parameter_digest_groups.values()), "canary_q_parameter_digest_instability")
    serial = [receipt for receipt in receipts if receipt["run_mode"] == "serial"]
    mixed = [receipt for receipt in receipts if receipt["run_mode"] == "mixed"]
    actual_hosts = {receipt["host"] for receipt in receipts}
    actual_systems = {receipt["system"] for receipt in receipts}
    actual_platforms = {receipt["platform"] for receipt in receipts}
    require(len(actual_hosts) == len(actual_systems) == len(actual_platforms) == 1, "canary_host_receipt_inconsistency")
    mixed_elapsed = (max(item["end_epoch_ns"] for item in mixed) - min(item["start_epoch_ns"] for item in mixed)) / 1e9
    require(mixed_elapsed > 0, "canary_mixed_elapsed_invalid")
    configured_concurrency = int(spec["mixed_concurrency"][host_key])
    peak_concurrency = _interval_peak(
        [(int(item["start_epoch_ns"]), int(item["end_epoch_ns"])) for item in mixed]
    )
    require(peak_concurrency >= configured_concurrency, "canary_mixed_concurrency_not_proven")
    serial_wall = [float(item["total_wall_seconds"]) for item in serial]
    summary = {
        "schema_version": "goal051-canary-host-summary-v1",
        "identity": identity,
        "status": "metric_free_host_inventory_complete",
        "host_key": host_key,
        "actual_hostname": next(iter(actual_hosts)),
        "actual_system": next(iter(actual_systems)),
        "actual_platform": next(iter(actual_platforms)),
        "receipt_tags": tags,
        "receipt_count": len(receipts),
        "candidate_ids": expected_candidates,
        "auxiliary_sizes": expected_auxiliary,
        "serial_latency_seconds": {
            "values": serial_wall,
            "mean": float(np.mean(serial_wall)),
            "minimum": min(serial_wall),
            "maximum": max(serial_wall),
        },
        "mixed_batch": {
            "runs": len(mixed),
            "configured_concurrency": configured_concurrency,
            "interval_peak_concurrency": peak_concurrency,
            "elapsed_seconds": mixed_elapsed,
            "throughput_runs_per_second": len(mixed) / mixed_elapsed,
        },
        "peak_rss_bytes": max(int(item["process_peak_rss_bytes"]) for item in receipts),
        "prediction_digest_stable": True,
        "prediction_digests": {key: next(iter(values)) for key, values in sorted(digest_groups.items())},
        "q_parameter_digest_stable": True,
        "q_parameter_digests": {
            key: next(iter(values)) for key, values in sorted(parameter_digest_groups.items())
        },
        "metrics_computed": False,
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    _atomic_json(_canary_summary_path(root, config, host_key), summary)
    return summary


def _canary_summary_path(root: Path, config: Mapping[str, Any], host_key: str) -> Path:
    base = root / config["execution"]["canary_receipt"]
    return base.parent / f"summary-{host_key}.json"


def canary_route(root: Path, selected_host: str, workers: int) -> dict[str, Any]:
    """Freeze the production CPU route from both metric-free host summaries."""

    config = _config(root)
    identity = _identity(root)
    require(
        config["execution"]["canary"].get("host_expectations") == EXPECTED_CANARY_HOSTS,
        "canary_host_expectations_drift",
    )
    require(selected_host in {"mac", "deep_server"}, "canary_selected_host_invalid")
    proven = int(config["execution"]["canary"]["mixed_concurrency"][selected_host])
    require(isinstance(workers, int) and 0 < workers <= proven, "canary_route_workers_invalid")
    host_evidence = {}
    for host_key in ("mac", "deep_server"):
        path = _canary_summary_path(root, config, host_key)
        require(path.is_file(), f"canary_host_summary_missing:{host_key}")
        summary = _read_json(path)
        expected_host = config["execution"]["canary"]["host_expectations"][host_key]
        mixed_batch = summary.get("mixed_batch", {})
        interval_peak = mixed_batch.get("interval_peak_concurrency")
        serial_latency = summary.get("serial_latency_seconds", {})
        serial_values = serial_latency.get("values", [])
        require(
            summary.get("schema_version") == "goal051-canary-host-summary-v1"
            and summary.get("status") == "metric_free_host_inventory_complete"
            and summary.get("identity") == identity
            and summary.get("host_key") == host_key
            and summary.get("actual_hostname") == expected_host["hostname"]
            and summary.get("actual_system") == expected_host["system"]
            and isinstance(summary.get("actual_platform"), str)
            and bool(summary["actual_platform"])
            and summary.get("prediction_digest_stable") is True
            and summary.get("q_parameter_digest_stable") is True
            and isinstance(summary.get("prediction_digests"), dict)
            and bool(summary["prediction_digests"])
            and isinstance(summary.get("q_parameter_digests"), dict)
            and bool(summary["q_parameter_digests"])
            and len(serial_values) == int(config["execution"]["canary"]["serial_repeats"])
            and all(isinstance(value, (int, float)) for value in serial_values)
            and np.isfinite(serial_values).all()
            and all(value > 0 for value in serial_values)
            and isinstance(summary.get("peak_rss_bytes"), int)
            and summary["peak_rss_bytes"] > 0
            and mixed_batch.get("runs") == int(config["execution"]["canary"]["mixed_concurrency"][host_key])
            and mixed_batch.get("configured_concurrency") == int(config["execution"]["canary"]["mixed_concurrency"][host_key])
            and isinstance(mixed_batch.get("elapsed_seconds"), (int, float))
            and np.isfinite(mixed_batch["elapsed_seconds"])
            and mixed_batch["elapsed_seconds"] > 0
            and isinstance(mixed_batch.get("throughput_runs_per_second"), (int, float))
            and np.isfinite(mixed_batch["throughput_runs_per_second"])
            and mixed_batch["throughput_runs_per_second"] > 0
            and summary.get("metrics_computed") is False
            and summary.get("outer_response_rows_read") == 0
            and summary.get("outer_predictor_rows_used") == 0
            and isinstance(interval_peak, int)
            and interval_peak >= int(config["execution"]["canary"]["mixed_concurrency"][host_key]),
            f"canary_host_summary_invalid:{host_key}",
        )
        host_evidence[host_key] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "actual_hostname": summary["actual_hostname"],
            "actual_system": summary["actual_system"],
            "actual_platform": summary["actual_platform"],
            "serial_latency_seconds": summary["serial_latency_seconds"],
            "mixed_batch": summary["mixed_batch"],
            "peak_rss_bytes": summary["peak_rss_bytes"],
            "prediction_digest_stable": summary["prediction_digest_stable"],
            "q_parameter_digest_stable": summary["q_parameter_digest_stable"],
        }
    route = {
        "schema_version": "goal051-canary-route-v1",
        "status": "metric_free_route_selected",
        "identity": identity,
        "host_summaries": host_evidence,
        "selected_host": selected_host,
        "selected_workers": workers,
        "proven_mixed_concurrency": proven,
        "metrics_computed": False,
        "outer_response_rows_read": 0,
        "outer_predictor_rows_used": 0,
    }
    _atomic_json(root / config["execution"]["tracked_canary_summary"], route)
    return route


_WORKER_ROOT: Path | None = None
_WORKER_CONFIG: dict[str, Any] | None = None
_WORKER_STORE: SeawfbStore | None = None


def _worker_init(root: str) -> None:
    global _WORKER_ROOT, _WORKER_CONFIG, _WORKER_STORE
    os.environ.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    _WORKER_ROOT = Path(root)
    _WORKER_CONFIG = _config(_WORKER_ROOT)
    _WORKER_STORE = SeawfbStore(_WORKER_ROOT)


def _q_worker(spec: tuple[int, int, str]) -> str:
    require(_WORKER_ROOT is not None and _WORKER_CONFIG is not None and _WORKER_STORE is not None, "worker_not_initialized")
    with threadpool_limits(limits=1):
        prepare_q_surface(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, *spec)
    return f"block{spec[0]:02d}/fold{spec[1]:02d}/aux{spec[2]}"


def _endpoint_worker(spec: tuple[str, int]) -> str:
    require(_WORKER_ROOT is not None and _WORKER_CONFIG is not None and _WORKER_STORE is not None, "worker_not_initialized")
    with threadpool_limits(limits=1):
        run_endpoint(_WORKER_ROOT, _WORKER_STORE, _WORKER_CONFIG, *spec)
    return f"{spec[0]}/target{spec[1]}"


def _run_parallel(root: Path, function: Any, tasks: Sequence[Any], workers: int) -> None:
    if workers == 1:
        _worker_init(str(root))
        for task in tasks:
            print(function(task), flush=True)
        return
    failures = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"), initializer=_worker_init, initargs=(str(root),)) as pool:
        futures = {pool.submit(function, task): task for task in tasks}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as error:
                failures.append(futures[future])
                print(f"task_failed:{futures[future]}:{error}", file=sys.stderr, flush=True)
    require(not failures, f"parallel_tasks_failed:{failures}")


def status(root: Path) -> dict[str, Any]:
    """Cheap filesystem progress view for detached production sessions."""

    config = _config(root)
    curves = _read_json(root / CURVES_PATH)
    crossfit = _read_json(root / CROSSFIT_PATH)
    q_specs = q_surface_specs(crossfit)
    endpoints = target_endpoints(curves)
    q_ready = sum(
        all(path.is_file() for path in _q_paths(root, config, *spec))
        for spec in q_specs
    )
    endpoint_ready = sum(
        all(path.is_file() for path in _task_paths(root, config, *endpoint))
        for endpoint in endpoints
    )
    summary_present = (root / config["execution"]["tracked_summary"]).is_file()
    run_exit = _private_root(root, config) / "run.exit"
    return {
        "status": "goal051_progress",
        "q_surfaces": {"ready": q_ready, "total": len(q_specs)},
        "target_endpoints": {"ready": endpoint_ready, "total": len(endpoints)},
        "summary_present": summary_present,
        "run_exit_present": run_exit.is_file(),
        "apparent_complete": q_ready == len(q_specs) and endpoint_ready == len(endpoints) and summary_present,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("plan", "q", "run", "aggregate", "validate", "canary", "canary-batch", "canary-summary", "canary-route", "status"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--workers", type=int)
    parser.add_argument("--block", type=int)
    parser.add_argument("--fold", type=int)
    parser.add_argument("--auxiliary", choices=("20", "80", "full"))
    parser.add_argument("--target")
    parser.add_argument("--target-index", type=int)
    parser.add_argument("--fraction", type=int, choices=(25, 50, 100))
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--receipt-tag")
    parser.add_argument("--host-key", choices=("mac", "deep_server"))
    parser.add_argument("--selected-host", choices=("mac", "deep_server"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = _config(root)
    workers = args.workers or int(config["execution"]["default_workers"])
    require(workers > 0, "worker_count_invalid")
    if args.command == "status":
        print(json.dumps(status(root), indent=2, sort_keys=True))
        return 0
    # These entrypoints validate their own inputs; other CLI paths own the gate here.
    inputs = None if args.command in {"validate", "canary", "canary-batch"} else validate_inputs(root)
    if args.command == "plan":
        print(json.dumps(inputs, indent=2, sort_keys=True))
    elif args.command == "q":
        specs = q_surface_specs(_read_json(root / CROSSFIT_PATH))
        if args.block is not None:
            specs = [spec for spec in specs if spec[0] == args.block]
        if args.fold is not None:
            specs = [spec for spec in specs if spec[1] == args.fold]
        if args.auxiliary is not None:
            specs = [spec for spec in specs if spec[2] == args.auxiliary]
        _run_parallel(root, _q_worker, specs, workers)
    elif args.command == "run":
        q_provenance(root, config, require_complete=True)
        endpoints = target_endpoints(_read_json(root / CURVES_PATH))
        if args.target_index is not None:
            targets = list(dict.fromkeys(target for target, _ in endpoints))
            require(0 <= args.target_index < len(targets), "target_index_invalid")
            endpoints = [item for item in endpoints if item[0] == targets[args.target_index]]
        if args.target is not None:
            endpoints = [item for item in endpoints if item[0] == args.target]
        if args.fraction is not None:
            endpoints = [item for item in endpoints if item[1] == args.fraction]
        require(bool(endpoints), "empty_endpoint_shard")
        identity = _identity(root)
        endpoints = [item for item in endpoints if _checkpoint(root, config, identity, *item) is None]
        _run_parallel(root, _endpoint_worker, endpoints, workers)
    elif args.command == "aggregate":
        print(json.dumps({key: value for key, value in aggregate(root).items() if key != "endpoints"}, indent=2, sort_keys=True))
    elif args.command == "validate":
        print(json.dumps(validate(root, args.complete), indent=2, sort_keys=True))
    elif args.command == "canary-batch":
        require(args.host_key is not None, "canary_host_key_required")
        print(json.dumps(canary_batch(root, args.host_key), indent=2, sort_keys=True))
    elif args.command == "canary-summary":
        require(args.host_key is not None, "canary_host_key_required")
        print(json.dumps(canary_summary(root, args.host_key), indent=2, sort_keys=True))
    elif args.command == "canary-route":
        require(args.selected_host is not None, "canary_selected_host_required")
        require(args.workers is not None, "canary_route_workers_required")
        print(json.dumps(canary_route(root, args.selected_host, args.workers), indent=2, sort_keys=True))
    else:
        print(json.dumps(canary(root, args.receipt_tag), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
