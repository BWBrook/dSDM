"""Immutable plans and complete prediction closure for the bird outer test.

This module has no response loader. Hashes bind the files actually retained;
neither a directory's existence nor a status string proves complete prediction.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from . import goal051_seawfb_conventional as baseline
from . import goal052_seawfb_dsdm as native
from .seawfb_modeling import digest, require, sha256_file, slug, stable_seed

INVENTORY = Path("evidence/seawfb_dsdm/goal052/outer-inventory-20260929.json")
RECOVERY = Path("evidence/seawfb_dsdm/goal052/ann-recovery-review-20261002.json")
PANEL = Path("evidence/seawfb_canonical_response/goal049/panel_summary.json")
PRIVATE = Path("data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003")
CONVENTIONAL = ("selected_conventional", "selected_conventional_plus_q")
ARMS = (*native.ARMS, *CONVENTIONAL)
ENSEMBLE = "fixed_ensemble"
ALL_ARMS = (*ARMS, ENSEMBLE)
FULL_FOLD = -1
EXTRA_SOURCE = (
    "src/dsdm_phase1/goal052_outer_artifacts.py",
    "src/dsdm_phase1/goal052_outer.py",
    "src/dsdm_phase1/goal052_outer_training.py",
    "src/dsdm_phase1/goal052_outer_data.py",
    "src/dsdm_phase1/goal052_outer_predictors.py",
    "src/dsdm_phase1/goal052_outer_diagnostics.py",
    "src/dsdm_phase1/goal052_outer_scoring.py",
    "src/dsdm_phase1/goal052_outer_runtime.py",
    "src/dsdm_phase1/goal052_outer_response.py",
    "src/dsdm_phase1/goal050_compute_canary.py",
    "src/dsdm/inner_evaluation.py",
    "scripts/goal049_canonical_response.py",
    "scripts/validate_goal049_seawfb_canonical_response.py",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    require(isinstance(value, dict), f"object_required:{path}")
    return value


def write_once(path: Path, value: Mapping[str, Any]) -> None:
    """Never replace a completed receipt with a different object."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        require(read_json(path) == value, f"immutable_artifact_conflict:{path}")
        return
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(raw)
    try:
        os.link(temporary, path)
    except FileExistsError:
        require(read_json(path) == value, f"immutable_artifact_conflict:{path}")
    finally:
        temporary.unlink(missing_ok=True)


def source_hashes(root: Path) -> dict[str, str]:
    paths = set(map(str, baseline.SOURCE_PATHS + native.SOURCE_PATHS)) | set(EXTRA_SOURCE)
    return {name: sha256_file(root / name) for name in sorted(paths)}


def task_id(task: Mapping[str, Any]) -> str:
    kind = task["kind"]
    if kind == "q":
        return f"q.block{task['block']:02d}"
    if kind == "pretraining":
        return f"pretraining.block{task['block']:02d}.{task['seed_label']}"
    require(kind in ("neural", "conventional"), "outer_task_kind_invalid")
    return f"{kind}.{slug(task['target'])}.{task['arm']}.{task['seed_label']}"


def enumerate_tasks(inventory: Mapping, recovery: Mapping, crossfit: Mapping,
                    config051: Mapping) -> tuple[list[dict], dict[str, dict[str, float]]]:
    budgets = {(r["target"], r["method"]): r for r in recovery["procedures"]}
    tasks: list[dict] = []
    thresholds: dict[str, dict[str, float]] = {}
    blocks = sorted(set(map(int, crossfit["focal_blocks"].values())))
    for block in blocks:
        tasks.append({"kind": "q", "block": block,
                      "seed": stable_seed(baseline._seed_namespace(config051, "q"), "q_linear", block, FULL_FOLD, "full")})
        epoch = inventory["pretraining"]["prospective_epoch_choices"][f"block{block:02d}"]["pooled25_median_selected_epoch"]
        for label in native.SEEDS:
            tasks.append({"kind": "pretraining", "block": block, "seed_label": label,
                          "seed": stable_seed("goal052-pretraining-v1", block, FULL_FOLD, "full", "seawfb_scale", label),
                          "epochs": epoch})
    for row in inventory["neural_target100_full"]["records"]:
        target = row["target"]
        thresholds[target] = {}
        for arm in native.ARMS:
            item = row["arms"][arm]
            thresholds[target][arm] = float(item["oof_threshold"])
            for label in native.SEEDS:
                tasks.append({"kind": "neural", "target": target, "block": int(crossfit["focal_blocks"][target]),
                              "arm": arm, "seed_label": label,
                              "seed": native.target_seed(target, 100, FULL_FOLD, "seawfb_scale", label),
                              "epochs": int(item["median_rounded_epoch"])})
    for row in inventory["conventional_target100"]["records"]:
        target = row["target"]
        for method, arm in zip(("ordinary", "q_full"), CONVENTIONAL):
            item = row[method]
            thresholds[target][arm] = float(item["oof_threshold"])
            epoch = None
            if item["family"] == "shallow_ann":
                budget = budgets[(target, method)]
                require(budget["candidate_id"] == item["candidate_id"], "recovered_candidate_mismatch")
                require(all(budget["exact_checks"].values()), "recovered_budget_unaccepted")
                epoch = int(budget["median_rounded_epoch"])
            for label in item["seed_labels"]:
                tasks.append({"kind": "conventional", "target": target,
                              "block": int(crossfit["focal_blocks"][target]), "arm": arm,
                              "family": item["family"], "candidate_id": item["candidate_id"],
                              "seed_label": label, "epochs": epoch,
                              "seed": baseline._fit_seed(config051, target, 100, FULL_FOLD, item["family"], item["candidate_id"], label)})
    tasks = [{**item, "id": task_id(item)} for item in tasks]
    require(len({t["id"] for t in tasks}) == len(tasks), "outer_task_duplicate")
    return tasks, thresholds


def load_plan(root: Path, run: Path, *, verify_sources: bool = True) -> dict:
    plan = read_json(run / "plan.json")
    identity = {k: v for k, v in plan.items() if k not in ("plan_digest", "created_utc")}
    require(plan.get("plan_digest") == digest(identity), "outer_plan_digest_mismatch")
    require(plan.get("schema_version") == "goal052-outer-plan-v1", "outer_plan_schema")
    if verify_sources:
        require(plan["sources"] == source_hashes(root), "outer_source_drift")
        for name, expected in plan["inputs"].items():
            require(sha256_file(root / name) == expected, f"outer_input_drift:{name}")
        from .seawfb_modeling import CROSSFIT_PATH
        tasks, thresholds = enumerate_tasks(read_json(root / INVENTORY), read_json(root / RECOVERY),
                                             read_json(root / CROSSFIT_PATH), baseline._config(root))
        require(plan["tasks"] == tasks and plan["thresholds"] == thresholds, "outer_plan_recipe_drift")
        require(Counter(t["kind"] for t in tasks) == Counter(q=10, pretraining=50, neural=3140, conventional=1042), "outer_plan_fit_count")
        panel = read_json(root / PANEL)
        expected_panels = {"primary": panel["primary_common"]["species"],
                           "regional": {region: value["species"] for region, value in panel["secondary_region_specific"].items()}}
        require(plan["panels"] == expected_panels and plan["targets"] == sorted(thresholds), "outer_plan_panel_drift")
        require(plan["x20_targets"] == {region: value["species"] for region, value in panel["x20_evaluation_only"].items()}, "outer_plan_x20_panel_drift")
        require(plan["q_numerical_fit"] == baseline._config(root)["community_control"]["numerical_fit"], "outer_plan_q_schedule_drift")
    return plan


def leaf_dir(run: Path, task: Mapping) -> Path:
    return run / "fits" / task["id"]


def checked_file(base: Path, relative: str, expected: str) -> Path:
    path = base / relative
    require(path.resolve().is_relative_to(base.resolve()), "artifact_path_escape")
    require(path.is_file() and sha256_file(path) == expected, f"artifact_hash_mismatch:{relative}")
    return path


def load_leaf(run: Path, plan: Mapping, task: Mapping, *, missing_ok: bool = False) -> dict | None:
    directory = leaf_dir(run, task)
    path = directory / "receipt.json"
    if missing_ok and not path.exists():
        return None
    receipt = read_json(path)
    require(receipt.get("status") == "outer_fit_complete", "outer_leaf_not_complete")
    require(receipt.get("plan_digest") == plan["plan_digest"] and receipt.get("task") == task, "outer_leaf_identity_mismatch")
    require(receipt.get("outer_response_rows_read") == 0, "outer_leaf_response_access")
    require(str(receipt["qualification"]).startswith("qualification/"), "outer_qualification_path")
    qualification_path = checked_file(run, receipt["qualification"], receipt["qualification_sha256"])
    qualification = read_json(qualification_path)
    require(qualification.get("status") == "outer_runtime_qualified" and qualification.get("plan_digest") == plan["plan_digest"], "outer_leaf_qualification_invalid")
    validate_fit_receipt(plan, task, receipt)
    files = receipt.get("files", {})
    required = {"model.npz"} if task["kind"] == "q" else {"model.pt", "shared.pt"} if task["kind"] == "pretraining" else {"model.pt", "scores.npz", "fit-input.json"} if task["kind"] == "neural" else {"model.json", "scores.npz", "fit-input.json"}
    require(set(files) == required, "outer_leaf_file_inventory")
    for name, expected in files.items():
        checked_file(directory, name, expected)
    if "fit-input.json" in files:
        bound = read_json(directory / "fit-input.json")
        require(bound == {"plan_digest": plan["plan_digest"], "task": dict(task), "data": receipt["data"], "dependencies": receipt["dependencies"]}, "outer_fit_input_drift")
    for dependent_id, checksum in receipt.get("dependencies", {}).items():
        require(dependent_id in {t["id"] for t in plan["tasks"]}, "outer_unknown_dependency")
        checked_file(run, f"fits/{dependent_id}/receipt.json", checksum)
        if dependent_id.startswith("pretraining."):
            pretraining = read_json(run / f"fits/{dependent_id}/receipt.json")
            require(receipt["fit"]["transfer_digest"] == receipt["fit"]["initial_shared_digest"] == pretraining["fit"]["final_shared_digest"], "outer_transferred_state_drift")
    if "scores.npz" in files:
        with np.load(directory / "scores.npz", allow_pickle=False) as data:
            require(set(data.files) == {"scores"}, "prediction_columns_invalid")
            validate_scores(data["scores"], plan["domain"]["rows"])
    return receipt


def validate_fit_receipt(plan: Mapping, task: Mapping, receipt: Mapping) -> None:
    """Check fixed scientific identities independently of runner completion."""
    fit = receipt["fit"]
    expected_dependencies = set()
    kind = task["kind"]
    if kind in ("neural", "pretraining"):
        require(fit["seed"] == task["seed"] and fit["replay_shuffle_seed"] == task["seed"] + 100000, "outer_neural_seed_drift")
        require(fit["epochs"] == fit["completed_epochs"] == task["epochs"] and fit["batch_size"] == 128, "outer_neural_budget_drift")
        require(fit["fit_mode"] == "fixed_budget" and fit["early_stopping"] is False and fit["discovery_rows"] == fit["stopping_rows"] == 0, "outer_neural_discovery_forbidden")
        require(fit["state_finite"] is True, "outer_neural_nonfinite_state")
        if kind == "pretraining":
            require(receipt["data"] == plan["auxiliary_rows"][str(task["block"])] and not fit["transferred"], "outer_pretraining_data_drift")
        else:
            transferred = task["arm"] in native.ARMS[2:]
            frozen = task["arm"] == native.ARMS[2]
            require(fit["head_initialization_seed"] == task["seed"] + 17, "outer_head_seed_drift")
            require(fit["transferred"] == transferred and fit["freeze_trunk"] == frozen, "outer_transfer_mode_drift")
            if transferred:
                expected_dependencies.add(f"pretraining.block{task['block']:02d}.{task['seed_label']}")
            if frozen:
                require(fit["freeze_shared_state_invariant"] and fit["initial_shared_digest"] == fit["final_shared_digest"], "outer_frozen_trunk_drift")
    elif kind == "conventional":
        require(fit["converged"] and fit["seed"] == task["seed"] and fit["family"] == task["family"] and fit["candidate_id"] == task["candidate_id"], "outer_conventional_fit_drift")
        if task["family"] == "shallow_ann":
            require(fit["best_epoch"] == fit["iterations"] == task["epochs"], "outer_ann_epochs_drift")
    else:
        require(kind == "q" and fit["fit_seed"] == task["seed"] and fit["candidate_id"] == "enet04", "outer_q_fit_drift")
        require(fit["held_block"] == task["block"] and fit["held_fold"] == FULL_FOLD and fit["auxiliary_size"] == "full", "outer_q_scope_drift")
        baseline._validate_q_attempts(fit, plan["q_numerical_fit"])
        baseline._validate_q_weight_rescaling(fit)
        expected = plan["auxiliary_rows"][str(task["block"])]
        require(fit["heads"] == expected["heads"] and fit["expanded_rows"] == expected["rows"] and fit["held_species"] == expected["excluded_species"], "outer_q_rows_drift")
    if kind in ("neural", "conventional"):
        require(fit.get("save_reload_predictions_exact") is True, "outer_prediction_reload_unverified")
        expected = plan["target_rows"][task["target"]]
        require(all(receipt["data"][key] == expected[key] for key in ("row_digest", "cell_id_digest", "rows", "folds_digest")), "outer_target_data_drift")
        augmented = task["arm"] in (native.ARMS[1], CONVENTIONAL[1])
        scaling = receipt["data"]["q_scaling"]
        if augmented:
            expected_dependencies.add(f"q.block{task['block']:02d}")
            require(isinstance(scaling, dict) and np.isfinite(scaling["training_mean"]) and np.isfinite(scaling["training_population_sd"]) and scaling["training_population_sd"] > 0, "outer_q_scaling_invalid")
        else:
            require(scaling is None, "outer_unrequested_q_scaling")
    require(set(receipt.get("dependencies", {})) == expected_dependencies, "outer_dependency_inventory")


def validate_scores(scores: np.ndarray, rows: int) -> None:
    values = np.asarray(scores)
    require(values.shape == (rows,) and values.dtype == np.float64, "outer_prediction_shape_or_dtype")
    require(np.isfinite(values).all() and np.all((values >= 0) & (values <= 1)), "outer_prediction_nonfinite_or_range")


def close_predictions(root: Path, run: Path) -> dict:
    """Validate all fitted leaves, average all seeds, then write closure last."""
    plan = load_plan(root, run)
    if (run / "closure.json").exists():
        return verify_closure(root, run)
    files = {"plan.json": sha256_file(run / "plan.json"), "domain.npz": sha256_file(run / "domain.npz")}
    require(files["domain.npz"] == plan["domain_file_sha256"], "outer_domain_file_drift")
    groups: dict[tuple[str, str], list[Mapping]] = {}
    qualifications = set()
    for task in plan["tasks"]:
        receipt = load_leaf(run, plan, task)
        assert receipt is not None
        rel = leaf_dir(run, task).relative_to(run)
        files[str(rel / "receipt.json")] = sha256_file(run / rel / "receipt.json")
        files.update({str(rel / name): checksum for name, checksum in receipt["files"].items()})
        qualifications.add(receipt["qualification"])
        if task["kind"] in ("neural", "conventional"):
            groups.setdefault((task["target"], task["arm"]), []).append(task)
    for name in sorted(qualifications):
        qualification = read_json(run / name)
        require(qualification["status"] == "outer_runtime_qualified" and qualification["plan_digest"] == plan["plan_digest"], "outer_qualification_invalid")
        files[name] = sha256_file(run / name)
        for relative, checksum in qualification["files"].items():
            checked_file(run, relative, checksum)
            files[relative] = checksum
    require(set(groups) == {(target, arm) for target in plan["targets"] for arm in ARMS}, "outer_prediction_group_inventory")
    prediction_inventory = {}
    for target in plan["targets"]:
        values = {}
        for arm in ARMS:
            tasks = sorted(groups[target, arm], key=lambda item: item["seed_label"])
            arrays = []
            for task in tasks:
                with np.load(leaf_dir(run, task) / "scores.npz", allow_pickle=False) as data:
                    arrays.append(data["scores"])
            values[arm] = np.mean(np.stack(arrays), axis=0, dtype=np.float64)
            validate_scores(values[arm], plan["domain"]["rows"])
        values[ENSEMBLE] = 0.5 * values[native.ARMS[3]] + 0.5 * values[CONVENTIONAL[0]]
        relative = f"predictions/{slug(target)}.npz"
        destination = run / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        with temporary.open("wb") as stream:
            np.savez_compressed(stream, **values)
        os.replace(temporary, destination)
        files[relative] = sha256_file(destination)
        prediction_inventory[target] = relative
    closure = {"schema_version": "goal052-outer-closure-v1", "status": "predictions_closed_before_response",
               "created_utc": now(), "plan_digest": plan["plan_digest"], "fit_counts": dict(Counter(t["kind"] for t in plan["tasks"])),
               "files": files, "predictions": prediction_inventory,
               "thresholds": plan["thresholds"], "domain": plan["domain"],
               "outer_response_rows_read": 0}
    closure["closure_digest"] = digest(closure)
    write_once(run / "closure.json", closure)
    return verify_closure(root, run)


def verify_closure(root: Path, run: Path) -> dict:
    """Mandatory gate called before importing the outer-response reader."""
    plan = load_plan(root, run)
    closure = read_json(run / "closure.json")
    require(closure.get("closure_digest") == digest({k: v for k, v in closure.items() if k != "closure_digest"}), "closure_digest_mismatch")
    require(closure.get("status") == "predictions_closed_before_response" and closure.get("outer_response_rows_read") == 0, "response_firewall_not_closed")
    require(closure.get("plan_digest") == plan["plan_digest"] and closure.get("thresholds") == plan["thresholds"], "closure_plan_or_threshold_drift")
    require(closure.get("fit_counts") == dict(Counter(t["kind"] for t in plan["tasks"])), "closure_fit_inventory")
    require(set(closure.get("predictions", {})) == set(plan["targets"]), "closure_target_inventory")
    expected_files = {"plan.json", "domain.npz"}
    for task in plan["tasks"]:
        receipt = load_leaf(run, plan, task)
        assert receipt is not None
        relative = leaf_dir(run, task).relative_to(run)
        expected_files.add(str(relative / "receipt.json"))
        expected_files.update(str(relative / name) for name in receipt["files"])
        expected_files.add(receipt["qualification"])
        expected_files.update(read_json(run / receipt["qualification"])["files"])
    expected_files.update(closure["predictions"].values())
    require(set(closure["files"]) == expected_files, "closure_file_inventory")
    for name, expected in closure["files"].items():
        checked_file(run, name, expected)
    for target, relative in closure["predictions"].items():
        with np.load(run / relative, allow_pickle=False) as data:
            require(set(data.files) == set(ALL_ARMS), f"closed_arm_inventory:{target}")
            for arm in ALL_ARMS:
                validate_scores(data[arm], plan["domain"]["rows"])
            for arm in ARMS:
                tasks = sorted((t for t in plan["tasks"] if t.get("target") == target and t.get("arm") == arm), key=lambda t: t["seed_label"])
                require(tasks, "closed_arm_seed_inventory")
                arrays = []
                for task in tasks:
                    with np.load(leaf_dir(run, task) / "scores.npz", allow_pickle=False) as seed_data:
                        arrays.append(seed_data["scores"])
                expected = np.mean(np.stack(arrays), axis=0, dtype=np.float64)
                require(np.array_equal(data[arm], expected), f"closed_seed_average_drift:{target}:{arm}")
            require(np.array_equal(data[ENSEMBLE], 0.5 * data[native.ARMS[3]] + 0.5 * data[CONVENTIONAL[0]]), "closed_ensemble_drift")
    return closure
