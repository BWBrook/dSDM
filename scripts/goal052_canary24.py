"""Twenty-four-worker qualification using the unchanged frozen canary worker.

Run under an external process-group resource sampler. This driver writes a
separate qualification receipt; it does not promote it to production metadata.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import multiprocessing
from pathlib import Path

from dsdm_phase1 import goal052_seawfb_dsdm as runner


_START_BARRIER = None
_RUNTIME_FIELDS = {
    "pid", "runtime_seconds", "memory_after_full_data_bytes",
    "peak_rss_bytes", "peak_cuda_allocated_bytes",
}


def _initialize(barrier) -> None:
    global _START_BARRIER
    _START_BARRIER = barrier


def _synchronized_worker(*args) -> dict:
    # Each wave occupies every process before any worker can begin another job.
    _START_BARRIER.wait(timeout=300)
    return runner._canary_worker(*args)


def _scientific_fields(value):
    if isinstance(value, dict):
        return {key: _scientific_fields(item) for key, item in value.items()
                if key not in _RUNTIME_FIELDS}
    if isinstance(value, list):
        return [_scientific_fields(item) for item in value]
    return value


def _verify_result(result, config, block, fold, target) -> None:
    bounded_config = deepcopy(config)
    bounded_config["architectures"]["constants"].update(max_epochs=1, patience=1)
    runner.verify_fit(result["pretraining_fit"], bounded_config,
                      runner.stable_seed("goal052-canary-pretraining-v1", block, fold),
                      transferred=False, frozen=False)
    shared = result["pretraining_fit"]["final_shared_digest"]
    runner.require(result["repeat_pretraining_digest"] == shared, "canary_repeat_state_drift")
    fits = result["target_fits"]
    runner.require(set(fits) == set(runner.ARMS), "canary_arms_drift")
    for arm in runner.ARMS:
        transferred, frozen = arm in runner.ARMS[2:], arm == runner.ARMS[2]
        runner.verify_fit(fits[arm], bounded_config,
                          runner.target_seed(target, 100, fold, "seawfb_scale", "seed00"),
                          transferred=transferred, frozen=frozen)
        if transferred:
            runner.require(fits[arm]["transfer_digest"] == shared
                           and fits[arm]["initial_shared_digest"] == shared,
                           "canary_transfer_state_drift")
    runner.require(len({fit["initial_head_digest"] for fit in fits.values()}) == 1,
                   "canary_paired_head_drift")
    runner.require(fits[runner.ARMS[2]]["initial_model_digest"]
                   == fits[runner.ARMS[3]]["initial_model_digest"],
                   "canary_transfer_initialization_drift")


def main() -> None:
    root = Path.cwd().resolve()
    identity = runner.validate_inputs(root)["identity"]
    config = runner.config_at(root)
    base = root / config["execution"]["private_root"]
    prior_path = base / "qualification-history/e309ca8-eight-worker/goal052_canary.json"
    prior_hash = "6a67e43792656813ae0c40979161d8e0d6101576b7ea08650a0a1f7ad9f36351"
    runner.require(runner.sha256_file(prior_path) == prior_hash, "prior_canary_digest_drift")
    prior = runner.read_json(prior_path)
    runtime = runner.host_runtime("cpu")
    runner.require(prior["identity"] == identity and prior["runtime"] == runtime,
                   "prior_canary_identity_drift")
    runner.require(prior["status"] == "goal052_canary_valid"
                   and prior["qualified_workers"] == 8, "prior_canary_invalid")
    block, fold, target = prior["block"], prior["fold"], prior["target"]
    reference = _scientific_fields(prior["results"][0])
    for result in prior["results"]:
        _verify_result(result, config, block, fold, target)
        runner.require(_scientific_fields(result) == reference, "prior_canary_results_differ")
    driver = Path(__file__).resolve()
    driver_hash = runner.sha256_file(driver)
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=24, mp_context=context,
                             initializer=_initialize, initargs=(context.Barrier(24),)) as pool:
        futures = [pool.submit(_synchronized_worker, str(root), "cpu", identity,
                               block, fold, target) for _ in range(48)]
        results = [future.result() for future in futures]
    counts = Counter(result["pid"] for result in results)
    runner.require(len(counts) == 24 and set(counts.values()) == {2},
                   "canary_concurrency_not_exercised")
    for result in results:
        _verify_result(result, config, block, fold, target)
        runner.require(_scientific_fields(result) == reference, "canary_prior_result_drift")
    runner.require(runner.sha256_file(driver) == driver_hash
                   and runner.identity_at(root) == identity
                   and runner.host_runtime("cpu") == runtime
                   and runner.sha256_file(prior_path) == prior_hash,
                   "qualification_binding_changed")
    receipt = {
        "status": "goal052_canary_valid", "identity": identity, "runtime": runtime,
        "qualified_workers": 24, "scope": "full_auxiliary_memory_bounded_one_epoch_optimization",
        "production_epoch_throughput_measured": False, "architecture": "seawfb_scale",
        "block": block, "fold": fold, "target": target, "results": results,
        "jobs_per_worker": dict(sorted(counts.items())),
        "synchronized_waves": 2, "all_nonruntime_fields_match_prior": True,
        "comparison_excluded_runtime_fields": sorted(_RUNTIME_FIELDS),
        "resource_sampling": "external_process_group_sampler_separate_evidence",
        "ecological_metrics_computed": False, "outer_response_rows_read": 0,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "qualification_driver": "scripts/goal052_canary24.py",
        "qualification_driver_sha256": driver_hash,
        "prior_canary_sha256": prior_hash,
    }
    output = base / "qualification-twentyfour-workers/goal052_canary.json"
    runner.atomic_json(output, receipt)
    print(json.dumps({"status": receipt["status"], "receipt": str(output),
                      "qualified_workers": 24, "jobs": len(results),
                      "all_nonruntime_fields_match_prior": True}), flush=True)


if __name__ == "__main__":
    main()
