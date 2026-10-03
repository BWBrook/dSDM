"""Retained-full fitting and response-free prediction for the frozen bird test."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import fcntl
import gc
import json
import multiprocessing
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

# These must be fixed before loading numerical libraries in spawned workers.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import torch

from dsdm.models import ResidualMLP
from . import goal051_seawfb_conventional as baseline
from . import goal052_seawfb_dsdm as native
from .goal052_outer_artifacts import (
    ALL_ARMS, ARMS, CONVENTIONAL, FULL_FOLD, INVENTORY, PANEL, PRIVATE, RECOVERY,
    close_predictions, digest, leaf_dir, load_leaf, load_plan, now, read_json,
    source_hashes, task_id, enumerate_tasks, validate_scores, write_once,
)
from .goal052_outer_data import RetainedFullStore, auxiliary_full_data, full_encoded_metadata, prediction_batch, target_full_data
from .goal052_outer_predictors import read_outer_predictors
from .goal052_outer_training import fit_pretraining_fixed, fit_target_fixed
from .model_adapters import CANONICAL_CANDIDATES, build_adapter, load_fitted_model
from .seawfb_dsdm_training import _predict
from .seawfb_modeling import (
    CELLS_PATH, MEMBERSHIPS_PATH, CROSSFIT_PATH, CURVES_PATH, TRANSFORMS_PATH,
    MANIFEST_PATH, QLinearModel, fit_q_linear, q_parameter_digest, require, sha256_file,
)


def event(stage: str, **items: Any) -> None:
    print(json.dumps({"utc": now(), "stage": stage, **items}, sort_keys=True), flush=True)


def prepare(root: Path, run: Path) -> dict:
    """Freeze sources, retained rows, budgets, thresholds and the outer grid."""
    if (run / "plan.json").exists():
        return load_plan(root, run)
    native.validate_inputs(root)
    inventory, recovery, panel = (read_json(root / p) for p in (INVENTORY, RECOVERY, PANEL))
    require(sha256_file(root / RECOVERY) == "2b0221fa6492f7827d38b706035c963e68e711480213ef121a119658fd462903", "ann_recovery_acceptance_drift")
    config051 = baseline._config(root)
    store = RetainedFullStore(root)
    tasks, thresholds = enumerate_tasks(inventory, recovery, store.crossfit, config051)
    require(Counter(t["kind"] for t in tasks) == Counter(q=10, pretraining=50, neural=3140, conventional=1042), "outer_full_fit_inventory")
    targets = sorted(thresholds)
    require(len(targets) == 157 and targets == sorted(store.focal_targets), "outer_target_identity")
    require(all(set(v) == set(ARMS) and np.isfinite(list(v.values())).all() for v in thresholds.values()), "outer_threshold_inventory")
    domain = read_outer_predictors(root)
    require(domain["summary"]["rows"] == 144860, "outer_domain_count")
    feature_metadata = full_encoded_metadata(store)
    require(list(feature_metadata["feature_names"]) == domain["summary"]["feature_order"], "outer_full_feature_order")
    run.mkdir(parents=True, exist_ok=True)
    with (run / "domain.npz").open("wb") as stream:
        np.savez_compressed(stream, **domain["arrays"])
    target_rows = {}
    for target in targets:
        data = target_full_data(store, target)
        target_rows[target] = dict(data.metadata)
        del data
    auxiliary_rows = {}
    for block in range(10):
        data = auxiliary_full_data(store, block)
        auxiliary_rows[str(block)] = dict(data.metadata)
        event("prepare_auxiliary", block=block, rows=len(data.replay.y), heads=len(data.heads))
        del data
        gc.collect()
    cfg050 = read_json(root / "config/goal050_seawfb_modeling_foundation.json")
    input_paths = {str(p) for p in (
        INVENTORY, RECOVERY, PANEL, CELLS_PATH, MEMBERSHIPS_PATH, CROSSFIT_PATH,
        CURVES_PATH, TRANSFORMS_PATH, MANIFEST_PATH, native.CONFIG, baseline.CONFIG_PATH,
        native.BASE_SUMMARY, native.ACCEPTANCE,
        Path("evidence/seawfb_dsdm/goal052/summary.json"),
        Path("evidence/seawfb_dsdm/goal052/completion_review.json"),
        Path("config/goal050_seawfb_modeling_foundation.json"),
        Path("config/goal049_seawfb_canonical_response.json"),
        Path("evidence/seawfb_canonical_response/goal049/completion_receipt.json"),
        Path("metadata/goal049_registry_taxonomy_freeze.json"), Path("uv.lock"),
    )}
    input_paths.update(cfg050["upstream"][key] for key in ("goal048_predictors", "goal048_region_ledger"))
    plan = {"schema_version": "goal052-outer-plan-v1", "sources": source_hashes(root),
            "inputs": {name: sha256_file(root / name) for name in sorted(input_paths)},
            "tasks": tasks, "targets": targets, "thresholds": thresholds,
            "architecture": next(s for s in native.config_at(root)["architectures"]["candidates"] if s["id"] == "seawfb_scale"),
            "batch_size": 128, "full_fold_sentinel": FULL_FOLD,
            "q_numerical_fit": config051["community_control"]["numerical_fit"],
            "panels": {"primary": panel["primary_common"]["species"],
                       "regional": {region: value["species"] for region, value in panel["secondary_region_specific"].items()}},
            "x20_targets": {region: value["species"] for region, value in panel["x20_evaluation_only"].items()},
            "target_rows": target_rows, "auxiliary_rows": auxiliary_rows,
            "features": feature_metadata, "domain": domain["summary"],
            "domain_file_sha256": sha256_file(run / "domain.npz"),
            "outer_response_rows_read": 0}
    plan["plan_digest"] = digest(plan)
    plan["created_utc"] = now()
    write_once(run / "plan.json", plan)
    event("prepared", plan_digest=plan["plan_digest"], fits=len(tasks), rows=domain["summary"]["rows"])
    return load_plan(root, run)


def read_domain(run: Path, plan: Mapping) -> dict:
    require(sha256_file(run / "domain.npz") == plan["domain_file_sha256"], "outer_domain_hash_drift")
    with np.load(run / "domain.npz", allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    require(arrays["x"].shape == (plan["domain"]["rows"], 103), "outer_domain_shape")
    require(len(np.unique(arrays["cell_ids"])) == plan["domain"]["rows"], "outer_domain_duplicate")
    return {"arrays": arrays, "summary": plan["domain"]}


def _atomic_npz(path: Path, **values: np.ndarray) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **values)
    os.replace(temporary, path)


def _atomic_torch(path: Path, state: Mapping) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    torch.save(dict(state), temporary)
    os.replace(temporary, path)


def get_task(plan: Mapping, **values: Any) -> dict:
    selected = [task for task in plan["tasks"] if all(task.get(k) == v for k, v in values.items())]
    require(len(selected) == 1, f"unique_task_required:{values}")
    return selected[0]


def load_q(run: Path, plan: Mapping, block: int) -> tuple[QLinearModel, dict]:
    task = get_task(plan, kind="q", block=block)
    receipt = load_leaf(run, plan, task)
    assert receipt is not None
    fit = receipt["fit"]
    with np.load(leaf_dir(run, task) / "model.npz", allow_pickle=False) as payload:
        coefficient, intercept = payload["coefficient"], float(payload["intercept"][0])
    require(q_parameter_digest(coefficient, intercept) == fit["parameter_digest"], "outer_q_parameter_drift")
    require(fit["fit_seed"] == task["seed"] and fit["held_fold"] == FULL_FOLD, "outer_q_seed_or_fold")
    model = QLinearModel(coefficient, intercept, block, FULL_FOLD, "full", "retained_full", int(fit["iterations"]))
    return model, receipt


class FitContext:
    def __init__(self, root: Path, run: Path, plan: Mapping, qualification: str, device: str = "cpu"):
        self.root, self.run, self.plan = root, run, plan
        self.qualification, self.device = qualification, device
        self.store = RetainedFullStore(root)
        self.domain = read_domain(run, plan)
        self.config051 = baseline._config(root)
        self.spec = native.spec_for(native.config_at(root), "seawfb_scale")
        self._target = None
        self._target_data = {}
        self._prediction = {}
        self._q = {}

    def target_data(self, target: str, augmented: bool):
        if self._target != target:
            self._target = target
            self._target_data.clear()
            self._prediction.clear()
        if augmented not in self._target_data:
            block = int(self.store.crossfit["focal_blocks"][target])
            q_model = None
            if augmented:
                if block not in self._q:
                    self._q[block] = load_q(self.run, self.plan, block)
                q_model = self._q[block][0]
            data = target_full_data(self.store, target, q_model)
            original = self.plan["target_rows"][target]
            require(all(data.metadata[key] == original[key] for key in ("row_digest", "cell_id_digest", "rows", "folds_digest")), "outer_target_rows_drift")
            prediction = prediction_batch(self.store, self.domain, q_model, data.metadata["q_scaling"])
            self._target_data[augmented], self._prediction[augmented] = data, prediction
        return self._target_data[augmented], self._prediction[augmented]


def run_fit(context: FitContext, task: Mapping) -> dict:
    run, plan = context.run, context.plan
    directory = leaf_dir(run, task)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cached = load_leaf(run, plan, task, missing_ok=True)
        if cached is not None:
            return cached
        require(not (run / "closure.json").exists(), "closed_run_cannot_fit")
        qualification_hash = sha256_file(run / context.qualification)
        started = time.monotonic()
        event("fit_started", task=task["id"])
        metadata: dict = {}
        dependencies: dict = {}
        if task["kind"] == "q":
            q, fit = fit_q_linear(context.store, task["block"], FULL_FOLD, "full",
                                  baseline._seed_namespace(context.config051, "q"),
                                  context.config051["community_control"]["numerical_fit"])
            require(fit["fit_seed"] == task["seed"], "outer_q_fit_seed")
            baseline._validate_q_attempts(fit, context.config051["community_control"]["numerical_fit"])
            baseline._validate_q_weight_rescaling(fit)
            expected = plan["auxiliary_rows"][str(task["block"])]
            require(fit["heads"] == expected["heads"] and fit["expanded_rows"] == expected["rows"], "outer_q_head_rows_drift")
            require(fit["held_species"] == expected["excluded_species"], "outer_q_exclusion_drift")
            _atomic_npz(directory / "model.npz", coefficient=q.coefficient, intercept=np.array([q.intercept]))
            names = ("model.npz",)
        elif task["kind"] == "pretraining":
            data = auxiliary_full_data(context.store, task["block"])
            metadata = dict(data.metadata)
            require(metadata == plan["auxiliary_rows"][str(task["block"])], "outer_auxiliary_rows_drift")
            full, shared, fit = fit_pretraining_fixed(context.spec, data.replay, data.heads,
                                                     seed=task["seed"], epochs=task["epochs"], device_name=context.device)
            _atomic_torch(directory / "model.pt", full)
            _atomic_torch(directory / "shared.pt", shared)
            require(native.state_digest(torch.load(directory / "model.pt", map_location="cpu", weights_only=True)) == fit["final_model_digest"], "pretraining_serialization_drift")
            require(native.state_digest(torch.load(directory / "shared.pt", map_location="cpu", weights_only=True)) == native.state_digest(shared), "shared_serialization_drift")
            names = ("model.pt", "shared.pt")
            del data, full, shared
        else:
            augmented = task["arm"] in (native.ARMS[1], CONVENTIONAL[1])
            data, prediction = context.target_data(task["target"], augmented)
            metadata = dict(data.metadata)
            if augmented:
                q_task = get_task(plan, kind="q", block=task["block"])
                dependencies[q_task["id"]] = sha256_file(leaf_dir(run, q_task) / "receipt.json")
            transferred = None
            if task["kind"] == "neural" and task["arm"] in native.ARMS[2:]:
                pre_task = get_task(plan, kind="pretraining", block=task["block"], seed_label=task["seed_label"])
                load_leaf(run, plan, pre_task)
                dependencies[pre_task["id"]] = sha256_file(leaf_dir(run, pre_task) / "receipt.json")
                transferred = torch.load(leaf_dir(run, pre_task) / "shared.pt", map_location="cpu", weights_only=True)
            # Persist the actual q scaling and transferred-state dependencies
            # before fitting, never reconstruct them from outcomes afterward.
            fit_input = {"plan_digest": plan["plan_digest"], "task": dict(task), "data": metadata, "dependencies": dependencies}
            write_once(directory / "fit-input.json", fit_input)
            if task["kind"] == "neural":
                scores, full, fit = fit_target_fixed(context.spec, data.replay, prediction.x,
                                                    seed=task["seed"], epochs=task["epochs"], device_name=context.device,
                                                    transferred_state=transferred, freeze_trunk=task["arm"] == native.ARMS[2])
                _atomic_torch(directory / "model.pt", full)
                reloaded = ResidualMLP(context.spec, prediction.x.shape[1]).to(context.device)
                reloaded.load_state_dict(torch.load(directory / "model.pt", map_location=context.device, weights_only=True))
                check = _predict(reloaded, prediction.x, torch.device(context.device), 128)
                require(np.array_equal(scores, check), "outer_neural_save_reload_prediction_drift")
                names = ("model.pt", "scores.npz", "fit-input.json")
                del full, reloaded, check
            else:
                require(context.device == "cpu", "conventional_requires_cpu")
                fitted, report = build_adapter(task["family"]).fit(data.train, None, CANONICAL_CANDIDATES[task["candidate_id"]], task["seed"], exact_epochs=task["epochs"])
                require(report.converged, "outer_conventional_nonconvergence")
                if task["family"] == "shallow_ann":
                    require(report.best_epoch == task["epochs"] and report.iterations == task["epochs"], "outer_ann_budget_drift")
                scores = fitted.predict_scores(prediction)
                temporary = directory / "model.tmp"
                envelope = fitted.serialize(temporary)
                checksum = envelope["whole_file_sha256"]
                del envelope, fitted
                os.replace(temporary, directory / "model.json")
                reloaded = load_fitted_model(directory / "model.json", checksum)
                require(np.array_equal(scores, reloaded.predict_scores(prediction)), "outer_conventional_save_reload_prediction_drift")
                del reloaded
                fit = asdict(report)
                fit.update({"seed": task["seed"], "candidate_id": task["candidate_id"], "family": task["family"]})
                names = ("model.json", "scores.npz", "fit-input.json")
            validate_scores(scores, plan["domain"]["rows"])
            _atomic_npz(directory / "scores.npz", scores=scores)
            fit["save_reload_predictions_exact"] = True
        receipt = {"status": "outer_fit_complete", "plan_digest": plan["plan_digest"], "task": dict(task),
                   "qualification": context.qualification, "qualification_sha256": qualification_hash,
                   "created_utc": now(), "data": metadata,
                   "dependencies": dependencies, "fit": fit, "runtime_seconds": time.monotonic() - started,
                   "files": {name: sha256_file(directory / name) for name in names}, "outer_response_rows_read": 0}
        write_once(directory / "receipt.json", receipt)
        event("fit_complete", task=task["id"], runtime_seconds=receipt["runtime_seconds"])
        gc.collect()
        return receipt


_CONTEXT: FitContext | None = None


def worker_init(root: str, run: str, plan: Mapping, qualification: str, device: str) -> None:
    global _CONTEXT
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    _CONTEXT = FitContext(Path(root), Path(run), plan, qualification, device)


def worker(tasks: Sequence[Mapping]) -> int:
    require(_CONTEXT is not None, "outer_worker_uninitialized")
    assert _CONTEXT is not None
    for task in tasks:
        run_fit(_CONTEXT, task)
    return len(tasks)


def run_stage(root: Path, run: Path, stage: str, workers: int, device: str = "cpu",
              shard: int = 0, shards: int = 1) -> dict:
    from .goal052_outer_runtime import require_qualification
    plan = load_plan(root, run)
    qualification = require_qualification(root, run, plan, device, workers)
    require(0 <= shard < shards and workers >= 1, "outer_parallel_scope")
    require(stage in ("q", "pretraining", "neural", "conventional"), "outer_stage_invalid")
    groups: dict[str, list] = {}
    for task in plan["tasks"]:
        if task["kind"] == stage:
            key = task.get("target", task["id"])
            groups.setdefault(key, []).append(task)
    selected = [tasks for index, (_, tasks) in enumerate(sorted(groups.items())) if index % shards == shard]
    event("stage_started", stage_name=stage, groups=len(selected), workers=workers, shard=shard, shards=shards)
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                             initializer=worker_init, initargs=(str(root), str(run), plan, qualification, device)) as pool:
        futures = [pool.submit(worker, tasks) for tasks in selected]
        try:
            for future in as_completed(futures):
                future.result()
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    result = {"status": "outer_stage_complete", "stage": stage, "shard": shard,
              "shards": shards, "fits": sum(map(len, selected)), "outer_response_rows_read": 0}
    event("stage_complete", **result)
    return result


def score_closed(root: Path, run: Path) -> dict:
    # Response imports are deliberately deferred until this explicit command.
    from .goal052_outer_response import load_closed_outer_responses
    from .goal052_outer_scoring import aggregate_regions, matched_inner_attenuation, score_target_region
    response = load_closed_outer_responses(root, run)
    plan = load_plan(root, run)
    domain = read_domain(run, plan)["arrays"]
    blocks = np.asarray([f"{x},{y}" for x, y in zip(domain["block_x"], domain["block_y"])])
    results = []
    for target in plan["targets"]:
        with np.load(run / response["closure"]["predictions"][target], allow_pickle=False) as payload:
            scores = {arm: payload[arm] for arm in ALL_ARMS}
        rows = response["by_target"][target]
        for region in ("NCP", "SEH", "NNC"):
            selected = domain["regions"] == region
            results.append(score_target_region(target, region, rows["y"][selected], rows["richness_minus_f"][selected], blocks[selected],
                                               {arm: values[selected] for arm, values in scores.items()}, plan["thresholds"][target],
                                               primary=target in plan["panels"]["primary"], regional=target in plan["panels"]["regional"][region]))
    failures = [{"target": item["target"], "region": item["region"], "support": item["support"]["x10"]}
                for item in results if item["panel"]["regional"] and not item["support"]["x10"]["passes"]]
    if failures:
        write_once(run / "scoring-failure.json", {"status": "outer_support_failure", "failures": failures,
                                                "closure_sha256": sha256_file(run / "closure.json")})
        require(False, "unexpected_frozen_panel_x10_support_failure")
    for region, frozen_targets in plan["x20_targets"].items():
        observed = sorted(item["target"] for item in results if item["region"] == region and item["panel"]["regional"] and item["support"]["x20"]["passes"])
        if observed != sorted(frozen_targets):
            write_once(run / "scoring-failure.json", {"status": "outer_x20_membership_drift", "region": region,
                                                    "expected": sorted(frozen_targets), "observed": observed,
                                                    "closure_sha256": sha256_file(run / "closure.json")})
            require(False, "unexpected_frozen_x20_membership_drift")
    aggregate = aggregate_regions(results, plan["panels"]["primary"], plan["panels"]["regional"])
    aggregate["matched_inner_attenuation"] = matched_inner_attenuation(aggregate, read_json(root / "evidence/seawfb_dsdm/goal052/summary.json"))
    output = {"schema_version": "goal052-outer-scores-v1", "created_utc": now(),
              "plan_digest": plan["plan_digest"], "closure_sha256": sha256_file(run / "closure.json"),
              "response_provenance": response["response_provenance"], "targets": results, "aggregate": aggregate,
              "interpretive_limits": [
                  "Threshold metrics use frozen inner-OOF thresholds; retained-full score-scale changes were not recalibrated on outer outcomes.",
                  "Original fitted inner target states were not saved, so the identical-grid inner/full score-scale comparison is unavailable without additional replay fits.",
                  "Presence versus effort-supported target-group background measures recording discrimination, not occupancy or verified absence.",
                  "Recorded-richness diagnostics test a retained-inner discovery prospectively and do not identify ecological versus observation mechanisms.",
                  "Species, regions and seeds are not iid replicates; descriptive sign labels are not significance, equivalence or practical-importance tests.",
              ]}
    write_once(run / "scores.json", output)
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "qualify", "profile", "run", "close", "verify", "score", "status"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--stage", choices=("q", "pretraining", "neural", "conventional"))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    run = (args.run or root / PRIVATE).resolve()
    if args.command == "prepare":
        result = prepare(root, run)
        event("ready", plan_digest=result["plan_digest"])
    elif args.command in ("qualify", "profile"):
        from .goal052_outer_runtime import qualify, profile
        result = (qualify if args.command == "qualify" else profile)(root, run, args.device, args.workers)
        event(args.command, **result)
    elif args.command == "run":
        require(args.stage is not None, "stage_required")
        run_stage(root, run, args.stage, args.workers, args.device, args.shard, args.shards)
    elif args.command in ("close", "verify"):
        from .goal052_outer_artifacts import verify_closure
        result = (close_predictions if args.command == "close" else verify_closure)(root, run)
        event(args.command, closure_digest=result["closure_digest"])
    elif args.command == "score":
        result = score_closed(root, run)
        event("scored", targets=len(result["targets"]))
    else:
        plan = load_plan(root, run)
        counts = Counter()
        for task in plan["tasks"]:
            if (leaf_dir(run, task) / "receipt.json").is_file():
                counts[task["kind"]] += 1
        event("status", receipt_counts=dict(counts), required=dict(Counter(t["kind"] for t in plan["tasks"])),
              closure_exists=(run / "closure.json").exists(), scores_exist=(run / "scores.json").exists(),
              warning="Receipt counts are a progress snapshot, not validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
