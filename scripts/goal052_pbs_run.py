"""Bounded Goal052 PBS production runner.

The launch binding is checked before importing the scientific runner.  This
keeps launch validation usable from the host Python on a PBS login/compute
shell, while the actual shard execution is performed by the qualified SIF
runtime.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Dict, List, Mapping, Optional


LAUNCH_STATUS = "goal052_pbs_pretraining_launch_bound"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_DRIVERS = frozenset({
    "scripts/goal052_canary24.py",
    "scripts/goal052_canary28.py",
    "scripts/goal052_pbs.py",
    "scripts/goal052_pbs_run.py",
    "scripts/goal052_pbs_verify.py",
    "scripts/kunanyi/goal052_production.pbs",
    "scripts/kunanyi/goal052_qualify.pbs",
    "scripts/kunanyi/sample_job.py",
})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}_unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}_object_required")
    return value


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _sha(value: Any, label: str) -> str:
    require(isinstance(value, str) and SHA256.fullmatch(value) is not None,
            f"{label}_sha256_invalid")
    return value


def _absolute(value: Any, label: str) -> Path:
    require(isinstance(value, str) and value, f"{label}_path_invalid")
    path = Path(value)
    require(path.is_absolute(), f"{label}_path_must_be_absolute")
    return path.resolve()


def _relative(value: Any, label: str) -> Path:
    require(isinstance(value, str) and value, f"{label}_path_invalid")
    posix = PurePosixPath(value)
    require(not posix.is_absolute() and ".." not in posix.parts,
            f"{label}_path_not_relative")
    return Path(*posix.parts)


def _hash_bound_files(root: Path, mapping: Mapping[str, Any], label: str) -> Dict[str, Path]:
    require(isinstance(mapping, Mapping) and mapping, f"{label}_mapping_missing")
    result: Dict[str, Path] = {}
    for raw_name, raw_digest in mapping.items():
        name = _relative(raw_name, f"{label}_entry")
        digest = _sha(raw_digest, f"{label}_{raw_name}")
        path = (root / name).resolve()
        require(path.is_file(), f"{label}_missing:{raw_name}")
        require(sha256_file(path) == digest, f"{label}_drift:{raw_name}")
        result[str(name)] = path
    return result


def validate_launch_binding(
    launch_path: Path,
    launch_sha256: str,
    root: Path,
    manifest_path: Path,
    expected_manifest_digest: str,
) -> Dict[str, Any]:
    """Validate the immutable launch JSON and every file it binds."""
    launch_path = launch_path.resolve()
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    _sha(launch_sha256, "launch")
    require(launch_path.is_file(), "launch_missing")
    require(sha256_file(launch_path) == launch_sha256, "launch_digest_mismatch")
    launch = read_json(launch_path, "launch")
    require(launch.get("status") == LAUNCH_STATUS, "launch_status_invalid")
    require(_absolute(launch.get("production_root"), "production_root") == root,
            "launch_production_root_drift")
    require(_absolute(launch.get("manifest_path"), "manifest") == manifest_path,
            "launch_manifest_path_drift")
    manifest_digest = _sha(launch.get("manifest_digest"), "manifest")
    require(manifest_digest == expected_manifest_digest,
            "launch_manifest_digest_drift")
    require(manifest_path.is_file(), "manifest_missing")
    require(sha256_file(manifest_path) == _sha(launch.get("manifest_sha256"), "manifest"),
            "manifest_file_digest_drift")
    manifest = read_json(manifest_path, "manifest")
    require(manifest.get("manifest_digest") == expected_manifest_digest,
            "manifest_content_digest_drift")
    require(manifest.get("stage") == "remaining_pretraining",
            "final_targets_dispatch_forbidden")

    sif_path = _absolute(launch.get("sif_path"), "sif")
    require(sif_path.is_file(), "sif_missing")
    require(sha256_file(sif_path) == _sha(launch.get("sif_sha256"), "sif"),
            "sif_digest_drift")
    archive_path = _absolute(launch.get("inputs_archive_path"), "inputs_archive")
    require(archive_path.is_file(), "inputs_archive_missing")
    require(sha256_file(archive_path) == _sha(launch.get("inputs_archive_sha256"), "inputs_archive"),
            "inputs_archive_digest_drift")

    reference_root = _absolute(launch.get("pilot_reference_root"), "pilot_reference_root")
    require(reference_root.is_dir(), "pilot_reference_root_missing")
    reference_files = _hash_bound_files(reference_root, launch.get("pilot_reference_sha256"),
                                        "pilot_reference")
    driver_files = _hash_bound_files(root, launch.get("driver_sha256"), "driver")
    require(REQUIRED_DRIVERS.issubset(set(driver_files)), "driver_binding_incomplete")

    require(launch.get("walltime_hours") == 48, "launch_walltime_invalid")
    require(launch.get("nodes") == 25, "launch_node_count_invalid")
    require(launch.get("workers_per_node") == 28, "launch_worker_count_invalid")
    reference = next((path for name, path in reference_files.items()
                      if Path(name).name == "canary.json"), None)
    require(reference is not None, "pilot_reference_canary_missing")
    return {
        "launch": launch,
        "manifest": manifest,
        "sif_path": sif_path,
        "inputs_archive_path": archive_path,
        "pilot_reference_root": reference_root,
        "pilot_reference": reference,
        "pilot_reference_sha256": sha256_file(reference),
        "driver_files": driver_files,
    }


def _launch_path() -> Path:
    value = os.environ.get("DSDM_LAUNCH")
    require(value is not None and value, "DSDM_LAUNCH_required")
    return Path(value)


def _launch_sha256() -> str:
    value = os.environ.get("DSDM_LAUNCH_SHA256")
    require(value is not None and value, "DSDM_LAUNCH_SHA256_required")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-digest", required=True)
    parser.add_argument("--node", required=False, default=os.environ.get("DSDM_NODE"))
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--profile-review", type=Path)
    parser.add_argument("--job-id", default=os.environ.get("PBS_JOBID"))
    parser.add_argument("--ownership-root", type=Path)
    parser.add_argument("--validate-launch-only", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    binding = validate_launch_binding(
        _launch_path(), _launch_sha256(), args.root, args.manifest,
        args.expected_manifest_digest,
    )
    if args.validate_launch_only:
        print(json.dumps({
            "manifest_digest": args.expected_manifest_digest,
            "sif_path": str(binding["sif_path"]),
            "inputs_archive_path": str(binding["inputs_archive_path"]),
            "pilot_reference_root": str(binding["pilot_reference_root"]),
            "pilot_reference": str(binding["pilot_reference"]),
            "pilot_reference_sha256": binding["pilot_reference_sha256"],
        }, sort_keys=True), flush=True)
        return 0

    require(args.node is not None and args.node, "node_required")
    require(args.qualification is not None, "qualification_required")
    require(args.profile_review is not None, "profile_review_required")
    require(args.job_id is not None and args.job_id, "job_id_required")
    qualification = args.qualification.resolve()
    profile_review = args.profile_review.resolve()
    require(qualification.is_file(), "qualification_missing")
    require(profile_review.is_file(), "profile_review_missing")

    # The adapter records coordinator references relative to the canonical
    # production root.  Native execution must therefore resolve them from
    # that root, independently of the PBS submission directory.
    os.chdir(args.root.resolve())

    # Keep the import inside the runtime-bound execution path.  Launch checks
    # therefore work with the cluster's system Python before SIF activation.
    import goal052_pbs as pbs

    result = pbs.run_node_shard(
        args.manifest,
        args.root,
        args.node,
        {"path": str(qualification), "sha256": sha256_file(qualification)},
        {"path": str(profile_review), "sha256": sha256_file(profile_review)},
        job_id=args.job_id,
        ownership_root=args.ownership_root,
        expected_manifest_digest=args.expected_manifest_digest,
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        raise SystemExit(f"goal052_pbs_run: {exc}")
