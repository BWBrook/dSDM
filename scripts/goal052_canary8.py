"""Authorized eight-worker CPU qualification using the frozen canary worker.

The original CLI caps its canary at two workers. This separate driver changes
only qualification concurrency and binds its own hash in the new receipt.
"""
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import multiprocessing
from pathlib import Path

from dsdm_phase1 import goal052_seawfb_dsdm as runner


def main() -> None:
    root = Path.cwd().resolve()
    identity = runner.validate_inputs(root)["identity"]
    config = runner.config_at(root)
    prior_path = root / config["execution"]["private_root"] / "qualification-history/e309ca8-two-worker/goal052_canary.json"
    runner.require(runner.sha256_file(prior_path) == "578128be69aae014837906d26a64c080455dc2b24910f76fdb856b49ce064c43", "prior_canary_digest_drift")
    prior = runner.read_json(prior_path)
    runtime = runner.host_runtime("cpu")
    runner.require(prior["identity"] == identity and prior["runtime"] == runtime, "prior_canary_identity_drift")
    runner.require(prior["status"] == "goal052_canary_valid", "prior_canary_invalid")
    # Reuse the previously verified, score-free largest-case selection.
    block, fold, target = prior["block"], prior["fold"], prior["target"]
    driver = Path(__file__).resolve()
    driver_hash = runner.sha256_file(driver)
    with ProcessPoolExecutor(max_workers=8, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(runner._canary_worker, str(root), "cpu", identity, block, fold, target) for _ in range(16)]
        results = [future.result() for future in futures]
    runner.require(len({r["pid"] for r in results}) == 8, "canary_concurrency_not_exercised")
    runner.require(len({runner.digest(r["prediction_digests"]) for r in results}) == 1, "canary_spawn_predictions_differ")
    runner.require(len({r["repeat_pretraining_digest"] for r in results}) == 1, "canary_spawn_trunks_differ")
    runner.require(runner.sha256_file(driver) == driver_hash and runner.identity_at(root) == identity, "qualification_source_changed")
    receipt = {
        "status": "goal052_canary_valid", "identity": identity, "runtime": runtime,
        "qualified_workers": 8, "scope": "full_auxiliary_memory_bounded_one_epoch_optimization",
        "production_epoch_throughput_measured": False, "architecture": "seawfb_scale",
        "block": block, "fold": fold, "target": target, "results": results,
        "ecological_metrics_computed": False, "outer_response_rows_read": 0,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "qualification_driver": "scripts/goal052_canary8.py",
        "qualification_driver_sha256": driver_hash,
        "prior_canary_sha256": runner.sha256_file(prior_path),
    }
    runner.atomic_json(root / config["execution"]["canary_receipt"], receipt)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
