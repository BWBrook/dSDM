"""Fail-closed review of one Goal052 PBS host qualification.

The qualification receipts are immutable inputs.  This verifier checks a new
host against the accepted pilot, replays the native fit validators, checks the
current runtime and qualification drivers, and writes separate review receipts.
No ecological scores or sealed outer responses are read.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from dsdm_phase1 import goal052_seawfb_dsdm as native


CANARY_RUNTIME_FIELDS = frozenset({
    "memory_after_full_data_bytes",
    "peak_cuda_allocated_bytes",
    "peak_rss_bytes",
    "pid",
    "runtime_seconds",
})
PROFILE_TOP_LEVEL_RUNTIME_FIELDS = frozenset({
    "lifecycle_runtime_seconds",
    "peak_cuda_allocated_bytes",
    "peak_rss_bytes",
    "pretraining_rows_per_second",
    "pretraining_runtime_seconds",
    "rows_per_second",
    "target_runtime_seconds",
})
MAX_SAMPLED_RSS_BYTES = 100 * 1024**3


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}_invalid") from exc
    _require(isinstance(value, Mapping), f"{label}_invalid")
    return dict(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _without_fields(value: Any, excluded: frozenset[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_fields(item, excluded)
            for key, item in value.items()
            if key not in excluded
        }
    if isinstance(value, list):
        return [_without_fields(item, excluded) for item in value]
    return value


def _runtime_without_host(value: Any, label: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{label}_invalid")
    runtime = dict(value)
    host = runtime.pop("host", None)
    _require(isinstance(host, str) and bool(host), f"{label}_host_invalid")
    return runtime


def _profile_scientific_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(value))
    result.pop("runtime", None)
    for field in PROFILE_TOP_LEVEL_RUNTIME_FIELDS:
        result.pop(field, None)
    return _without_fields(result, frozenset({"runtime_seconds"}))


def _bounded_config(config: Mapping[str, Any]) -> dict[str, Any]:
    bounded = deepcopy(dict(config))
    bounded["architectures"]["constants"].update(max_epochs=1, patience=1)
    return bounded


def _verify_canary_result(
    result: Mapping[str, Any], config: Mapping[str, Any], block: int, fold: int, target: str
) -> None:
    bounded = _bounded_config(config)
    native.verify_fit(
        result["pretraining_fit"], bounded,
        native.stable_seed("goal052-canary-pretraining-v1", block, fold),
        transferred=False, frozen=False,
    )
    shared = result["pretraining_fit"]["final_shared_digest"]
    _require(result["repeat_pretraining_digest"] == shared, "canary_repeat_state_drift")
    fits = result["target_fits"]
    _require(set(fits) == set(native.ARMS), "canary_arms_drift")
    seed = native.target_seed(target, 100, fold, "seawfb_scale", "seed00")
    for arm in native.ARMS:
        transferred = arm in native.ARMS[2:]
        frozen = arm == native.ARMS[2]
        native.verify_fit(fits[arm], bounded, seed, transferred=transferred, frozen=frozen)
        if transferred:
            _require(
                fits[arm]["transfer_digest"] == shared
                and fits[arm]["initial_shared_digest"] == shared,
                "canary_transfer_state_drift",
            )
    _require(
        len({fits[arm]["initial_head_digest"] for arm in native.ARMS}) == 1,
        "canary_paired_head_drift",
    )
    _require(
        fits[native.ARMS[2]]["initial_model_digest"]
        == fits[native.ARMS[3]]["initial_model_digest"],
        "canary_transfer_initialization_drift",
    )


def _verify_profile_fits(profile: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    bounded = _bounded_config(config)
    native.verify_fit(
        profile["pretraining_fit"], bounded, int(profile["pretraining_seed"]),
        transferred=False, frozen=False,
    )
    shared = profile["pretraining_fit"]["final_shared_digest"]
    fits = profile["target_fits"]
    _require(set(fits) == set(native.ARMS), "profile_arms_drift")
    for arm in native.ARMS:
        transferred = arm in native.ARMS[2:]
        frozen = arm == native.ARMS[2]
        native.verify_fit(
            fits[arm], bounded, int(profile["target_seed"]),
            transferred=transferred, frozen=frozen,
        )
        expected_transfer = shared if transferred else None
        _require(
            profile["transferred_state_digests"][arm] == expected_transfer,
            "profile_transferred_state_drift",
        )
        if transferred:
            _require(
                fits[arm]["transfer_digest"] == shared
                and fits[arm]["initial_shared_digest"] == shared,
                "profile_transfer_state_drift",
            )
    _require(
        len({fits[arm]["initial_head_digest"] for arm in native.ARMS}) == 1,
        "profile_paired_head_drift",
    )
    _require(
        fits[native.ARMS[2]]["initial_model_digest"]
        == fits[native.ARMS[3]]["initial_model_digest"],
        "profile_transfer_initialization_drift",
    )


def _verify_driver_hashes(root: Path, receipt: Mapping[str, Any]) -> dict[str, str]:
    bindings = receipt.get("driver_sha256")
    _require(isinstance(bindings, Mapping) and bool(bindings), "canary_driver_bindings_missing")
    checked: dict[str, str] = {}
    root_resolved = root.resolve()
    for relative, expected in sorted(bindings.items()):
        path = Path(str(relative))
        _require(not path.is_absolute(), "canary_driver_path_invalid")
        resolved = (root / path).resolve()
        _require(resolved.is_relative_to(root_resolved), "canary_driver_path_invalid")
        _require(resolved.is_file(), "canary_driver_missing")
        actual = _sha256(resolved)
        _require(actual == expected, "canary_driver_hash_drift")
        checked[str(path)] = actual
    return checked


def _verify_canary(
    root: Path, current: Mapping[str, Any], reference: Mapping[str, Any],
    current_sha: str, reference_sha: str, runtime: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    for label, receipt in (("canary", current), ("reference_canary", reference)):
        _require(receipt.get("status") == "goal052_canary_valid", f"{label}_status_invalid")
        _require(receipt.get("identity") == current["identity"], f"{label}_identity_drift")
        _require(receipt.get("qualified_workers") == 28, f"{label}_worker_count_invalid")
        _require(receipt.get("scope") == "full_auxiliary_memory_bounded_one_epoch_optimization",
                 f"{label}_scope_invalid")
        _require(receipt.get("architecture") == "seawfb_scale", f"{label}_architecture_invalid")
        _require(receipt.get("ecological_metrics_computed") is False, f"{label}_metrics_invalid")
        _require(receipt.get("outer_response_rows_read") == 0, f"{label}_outer_rows_invalid")
        _require(receipt.get("synchronized_waves") == 2, f"{label}_waves_invalid")
        _require(receipt.get("all_nonruntime_fields_match_prior") is True,
                 f"{label}_comparison_status_invalid")
        _require(receipt.get("comparison_excluded_runtime_fields") == sorted(CANARY_RUNTIME_FIELDS),
                 f"{label}_runtime_exclusions_invalid")
        _require(receipt.get("production_authorized") is False, f"{label}_production_flag_invalid")
        results = receipt.get("results")
        _require(isinstance(results, list) and len(results) == 56, f"{label}_result_count_invalid")
        counts = Counter(result.get("pid") for result in results)
        _require(len(counts) == 28 and set(counts.values()) == {2}, f"{label}_concurrency_invalid")
        expected_counts = {str(pid): count for pid, count in sorted(counts.items())}
        _require(receipt.get("jobs_per_worker") == expected_counts, f"{label}_pid_accounting_invalid")
        reference_fields = _without_fields(results[0], CANARY_RUNTIME_FIELDS)
        for result in results:
            _verify_canary_result(result, config, int(receipt["block"]), int(receipt["fold"]), str(receipt["target"]))
            _require(_without_fields(result, CANARY_RUNTIME_FIELDS) == reference_fields,
                     f"{label}_within_host_scientific_drift")
        peak = max(int(result["peak_rss_bytes"]) for result in results)
        _require(receipt.get("peak_worker_rss_bytes") == peak and 0 < peak < MAX_SAMPLED_RSS_BYTES,
                 f"{label}_peak_worker_rss_invalid")
    _require(current["identity"] == native.validate_inputs(root)["identity"], "canary_current_identity_drift")
    _require(current["runtime"] == dict(runtime), "canary_current_runtime_drift")
    _require(_runtime_without_host(reference["runtime"], "reference_canary_runtime")
             == _runtime_without_host(runtime, "current_runtime"), "canary_runtime_environment_drift")
    _require(current["prior_canary_sha256"] == reference_sha, "canary_reference_hash_drift")
    _require(current["driver_sha256"] == reference["driver_sha256"], "canary_driver_set_drift")
    checked_drivers = _verify_driver_hashes(root, current)
    reference_fields = _without_fields(reference["results"][0], CANARY_RUNTIME_FIELDS)
    for result in current["results"]:
        _require(_without_fields(result, CANARY_RUNTIME_FIELDS) == reference_fields,
                 "canary_cross_host_scientific_drift")
    _require(
        (current["block"], current["fold"], current["target"])
        == (reference["block"], reference["fold"], reference["target"]),
        "canary_selection_drift",
    )
    return {
        "canary_sha256": current_sha,
        "reference_canary_sha256": reference_sha,
        "driver_sha256": checked_drivers,
        "result_count": len(current["results"]),
        "qualified_workers": 28,
        "peak_worker_rss_bytes": current["peak_worker_rss_bytes"],
    }


def _verify_profile(
    root: Path, current: Mapping[str, Any], reference: Mapping[str, Any],
    current_sha: str, reference_sha: str, runtime: Mapping[str, Any], config: Mapping[str, Any],
    identity: Mapping[str, Any], canary: Mapping[str, Any], reference_canary: Mapping[str, Any],
) -> dict[str, Any]:
    for label, receipt, bound_canary in (
        ("profile", current, canary), ("reference_profile", reference, reference_canary)
    ):
        _require(receipt.get("status") == "goal052_full_epoch_profile_valid", f"{label}_status_invalid")
        _require(receipt.get("identity") == identity, f"{label}_identity_drift")
        _require(receipt.get("runtime") == bound_canary.get("runtime"), f"{label}_canary_runtime_drift")
        _require(receipt.get("device") == "cpu", f"{label}_device_invalid")
        _require(receipt.get("ecological_metrics_computed") is False, f"{label}_metrics_invalid")
        _require(receipt.get("outer_response_rows_read") == 0, f"{label}_outer_rows_invalid")
        _require((receipt.get("block"), receipt.get("fold"), receipt.get("target"))
                 == (bound_canary.get("block"), bound_canary.get("fold"), bound_canary.get("target")),
                 f"{label}_selection_drift")
        _verify_profile_fits(receipt, config)
    _require(current["runtime"] == dict(runtime), "profile_current_runtime_drift")
    _require(_runtime_without_host(reference["runtime"], "reference_profile_runtime")
             == _runtime_without_host(runtime, "current_runtime"), "profile_runtime_environment_drift")
    _require(_profile_scientific_fields(current) == _profile_scientific_fields(reference),
             "profile_cross_host_scientific_drift")
    return {
        "profile_sha256": current_sha,
        "reference_profile_sha256": reference_sha,
        "allowed_runtime_differences": {
            "runtime": ["host"],
            "top_level": sorted(PROFILE_TOP_LEVEL_RUNTIME_FIELDS),
            "nested": ["runtime_seconds"],
        },
        "peak_rss_bytes": current["peak_rss_bytes"],
        "pretraining_runtime_seconds": current["pretraining_runtime_seconds"],
        "lifecycle_runtime_seconds": current["lifecycle_runtime_seconds"],
    }


def _verify_resource_samples(path: Path, worker_pids: set[int]) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("resource_samples_invalid") from exc
    _require(bool(lines), "resource_samples_empty")
    samples = []
    for line in lines:
        try:
            sample = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("resource_sample_json_invalid") from exc
        _require(isinstance(sample, Mapping), "resource_sample_invalid")
        rss = sample.get("rss_bytes")
        cpu = sample.get("cpu_percent")
        pids = sample.get("pids")
        _require(type(rss) is int and 0 < rss < MAX_SAMPLED_RSS_BYTES, "resource_sample_rss_invalid")
        _require(type(cpu) in (int, float) and math.isfinite(cpu) and cpu >= 0,
                 "resource_sample_cpu_invalid")
        _require(type(sample.get("parent_pid")) is int and sample["parent_pid"] > 0,
                 "resource_sample_parent_invalid")
        _require(sample.get("cpu_measurement") == "interval_live_processes",
                 "resource_sample_method_invalid")
        _require(isinstance(pids, list) and pids == sorted(set(pids))
                 and all(type(pid) is int and pid > 0 for pid in pids), "resource_sample_pids_invalid")
        samples.append(dict(sample))
    parents = {sample["parent_pid"] for sample in samples}
    _require(len(parents) == 1, "resource_sample_parent_drift")
    observed_pids = {pid for sample in samples for pid in sample["pids"]}
    _require(worker_pids <= observed_pids, "resource_samples_missing_canary_workers")
    rss_values = [sample["rss_bytes"] for sample in samples]
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "sample_count": len(samples),
        "parent_pid": next(iter(parents)),
        "observed_pid_count": len(observed_pids),
        "all_canary_workers_observed": True,
        "maximum_rss_bytes": max(rss_values),
        "maximum_rss_gib": max(rss_values) / 1024**3,
        "rss_ceiling_bytes": MAX_SAMPLED_RSS_BYTES,
        "rss_accounting_note": "summed live procfs RSS can double count shared pages",
    }


def verify_host(root: Path, reference_root: Path, output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root, reference_root, output_dir = (Path(value).resolve() for value in (root, reference_root, output_dir))
    current_canary_path = output_dir / "canary.json"
    current_profile_path = output_dir / "full-epoch-profile.json"
    reference_canary_path = reference_root / "canary.json"
    reference_profile_path = reference_root / "full-epoch-profile.json"
    reference_review_path = reference_root / "qualification-reference-review.json"
    current_canary = _read_json(current_canary_path, "canary")
    current_profile = _read_json(current_profile_path, "profile")
    reference_canary = _read_json(reference_canary_path, "reference_canary")
    reference_profile = _read_json(reference_profile_path, "reference_profile")
    reference_review = _read_json(reference_review_path, "qualification_reference_review")
    current_canary_sha = _sha256(current_canary_path)
    current_profile_sha = _sha256(current_profile_path)
    reference_canary_sha = _sha256(reference_canary_path)
    reference_profile_sha = _sha256(reference_profile_path)
    reference_review_sha = _sha256(reference_review_path)
    validated = native.validate_inputs(root)
    identity = validated["identity"]
    _require(current_canary.get("identity") == reference_canary.get("identity") == identity,
             "qualification_identity_drift")
    _require(reference_review.get("status") == "goal052_kunanyi_pilot_qualification_accepted",
             "qualification_reference_review_status_invalid")
    _require(reference_review.get("identity") == identity,
             "qualification_reference_review_identity_drift")
    _require(reference_review.get("canary_sha256") == reference_canary_sha,
             "qualification_reference_canary_hash_drift")
    _require(reference_review.get("profile_sha256") == reference_profile_sha,
             "qualification_reference_profile_hash_drift")
    _require(reference_review.get("qualified_workers") == 28,
             "qualification_reference_worker_count_invalid")
    runtime = native.host_runtime("cpu")
    config = native.config_at(root)
    canary_evidence = _verify_canary(
        root, current_canary, reference_canary, current_canary_sha, reference_canary_sha,
        runtime, config,
    )
    profile_evidence = _verify_profile(
        root, current_profile, reference_profile, current_profile_sha, reference_profile_sha,
        runtime, config, identity, current_canary, reference_canary,
    )
    worker_pids = {int(result["pid"]) for result in current_canary["results"]}
    resource_evidence = _verify_resource_samples(output_dir / "resource-samples.jsonl", worker_pids)
    _require(resource_evidence["maximum_rss_bytes"] >= current_canary["peak_worker_rss_bytes"],
             "resource_samples_below_worker_peak")
    verifier_sha = _sha256(Path(__file__).resolve())
    common = {
        "identity": identity,
        "runtime": runtime,
        "actual_host": runtime["host"],
        "verifier_sha256": verifier_sha,
        "qualification_reference_review_sha256": reference_review_sha,
        "receipt_mutation": False,
        "ecological_metrics_computed": False,
        "outer_response_rows_read": 0,
        "production_authorized": False,
    }
    qualification_review = {
        **common,
        "status": "goal052_pbs_node_qualification_verified",
        "qualified_workers": 28,
        "profile_sha256": current_profile_sha,
        "checks": [
            "current_native_identity_and_runtime",
            "driver_hashes",
            "28_spawned_workers_two_synchronized_waves",
            "native_fit_validation",
            "exact_nonruntime_canary_agreement",
            "positive_procfs_samples_all_workers_observed",
            "sampled_group_rss_below_100_gib",
            "no_ecological_metrics_or_outer_rows",
        ],
        "canary": canary_evidence,
        "resource_samples": resource_evidence,
    }
    profile_review = {
        **common,
        "status": "goal052_full_profile_independently_verified",
        "profile_sha256": current_profile_sha,
        "checks": [
            "native_fit_validation",
            "full_row_and_head_inventory",
            "exact_scientific_field_agreement",
            "runtime_only_differences",
            "no_ecological_metrics_or_outer_rows",
        ],
        "profile": profile_evidence,
    }
    _atomic_json(output_dir / "qualification-review.json", qualification_review)
    _atomic_json(output_dir / "profile-review.json", profile_review)
    return qualification_review, profile_review


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    qualification, profile = verify_host(args.root, args.reference_root, args.output_dir)
    print(json.dumps({
        "qualification_status": qualification["status"],
        "profile_status": profile["status"],
        "host": qualification["actual_host"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
