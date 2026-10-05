#!/usr/bin/env python3
"""Score a closed Goal052 run after the certified Goal049 zero-row repair.

This entrypoint is deliberately separate from the frozen response loader.  It
does not alter the scientific sources or closure; it binds the original
response-access start receipt, uses the native row reader with the certified
observed 449-species inventory, and writes only new recovery control evidence
plus the previously absent native success and scores receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


PROOF_STATUS = "passed_original_goal049_input_validation"
REGISTERED_SPECIES = 505
OBSERVED_SPECIES = 449
EMPTY_SPECIES = 56
CANONICAL_ROWS = 5_048_061
PROOF_SHA256 = "8e21478e8e7fd312b47a1827606771c0c3b2bf9e0f37d311072d0bc10ea65fea"
CERTIFICATE_SHA256 = "acbce53636cd4e5c02a02781e2265d87cb2f0a09fded7ecdbafde41fca84e8b2"
RESPONSE_STARTED = "response-access.json"
RESPONSE_SUCCESS = "response-access-success.json"
FIT_FAILURE = "scoring-failure.json"
SCORES = "scores.json"


class RecoveryError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file(), "missing file: {}".format(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def string_digest(values: Sequence[str]) -> str:
    payload = json.dumps(list(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RecoveryError("invalid JSON: {}".format(path)) from error
    require(isinstance(value, dict), "JSON object required: {}".format(path))
    return value


def immutable_json(path: Path, value: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".{}.tmp".format(os.getpid()))
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    try:
        os.link(str(temporary), str(path))
    except FileExistsError as error:
        raise RecoveryError("recovery receipt already exists: {}".format(path)) from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return sha256_file(path)


def import_native(root: Path):
    source = root / "src"
    require(source.is_dir(), "missing source directory: {}".format(source))
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from dsdm_phase1 import goal052_outer as native
    return native


def import_response(root: Path):
    source = root / "src"
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from dsdm_phase1 import goal052_outer_response as response
    return response


def safe_path(root: Path, value: str, label: str) -> Path:
    candidate = (root / value).resolve()
    require(candidate.is_relative_to(root.resolve()), "{} path escapes root".format(label))
    require(candidate.is_file(), "{} missing: {}".format(label, candidate))
    return candidate


def metadata_paths(root: Path) -> tuple[Path, Path, Path, Path]:
    config_path = root / "config/goal049_seawfb_canonical_response.json"
    config = read_json(config_path)
    tracked = config.get("tracked_outputs", {})
    completion_path = safe_path(root, str(tracked.get("completion", "")), "completion")
    private = config.get("private_outputs", {})
    private_root = str(private.get("root", ""))
    registry = safe_path(root, str(Path(private_root) / str(private.get("registry", ""))), "registry")
    taxonomy = safe_path(root, str(Path(private_root) / str(private.get("taxonomy", ""))), "taxonomy")
    return config_path, completion_path, registry, taxonomy


def validate_certificate(root: Path, path: Path, expected_sha: str, plan_sha: str,
                         closure_sha: str, completion_path: Path, registry_path: Path,
                         taxonomy_path: Path) -> dict[str, Any]:
    """Bind the compact Goal049 inventory certificate before reading rows."""
    root = root.resolve()
    require(sha256_file(path) == expected_sha == CERTIFICATE_SHA256, "inventory certificate hash mismatch")
    certificate = read_json(path)
    require(certificate.get("schema_version") == "goal052-canonical-inventory-certificate-v1"
            and certificate.get("status") == "certified"
            and certificate.get("source_payloads_unchanged") is True
            and certificate.get("model_outcomes_read") is False, "inventory certificate status invalid")
    require(certificate.get("plan_sha256") == plan_sha and certificate.get("closure_sha256") == closure_sha,
            "inventory certificate run binding mismatch")
    counts = certificate.get("counts", {})
    require(counts == {"active": REGISTERED_SPECIES, "canonical_memberships": CANONICAL_ROWS,
                       "donors": REGISTERED_SPECIES, "empty": EMPTY_SPECIES,
                       "empty_scoring_targets": 0, "nonempty": OBSERVED_SPECIES},
            "inventory certificate counts invalid")
    metadata_files = certificate.get("metadata_files", {})
    progress_path = root / "evidence/seawfb_canonical_response/goal049/acquisition_progress.json"
    run_exit_path = root / "data/processed/dsdm/goal049-seawfb-canonical-response/run.exit"
    expected_files = {"completion": completion_path, "progress": progress_path,
                      "registry": registry_path, "run_exit": run_exit_path, "taxonomy": taxonomy_path}
    for name, local_path in expected_files.items():
        item = metadata_files.get(name, {})
        require(item.get("relative") == str(local_path.relative_to(root))
                and sha256_file(local_path) == item.get("sha256"),
                "inventory certificate metadata binding mismatch: {}".format(name))
    require(isinstance(certificate.get("canonical_sha256"), str)
            and len(certificate["canonical_sha256"]) == 64, "inventory certificate canonical binding missing")
    progress = read_json(progress_path)
    run_exit = read_json(run_exit_path)
    require(progress.get("status") == "complete" and progress.get("completed_species") == REGISTERED_SPECIES
            and progress.get("planned_species") == REGISTERED_SPECIES
            and progress.get("cumulative_retained_species_cells") == CANONICAL_ROWS
            and progress.get("checkpoint_inventory_sha256") == certificate.get("checkpoint_inventory_sha256"),
            "inventory progress certificate binding invalid")
    require(run_exit.get("status") == "complete" and run_exit.get("completed_species") == REGISTERED_SPECIES,
            "inventory run exit binding invalid")
    validator = certificate.get("validator", {})
    validator_path = safe_path(root, str(validator.get("source_relative", "")), "validator source")
    require(validator.get("result_receipt_sha256") == certificate.get("diagnosis_sha256") == PROOF_SHA256
            and sha256_file(validator_path) == validator.get("source_sha256"), "validator certificate binding invalid")
    require(certificate.get("checkpoint_inventory_sha256") and certificate.get("receipt_inventory_sha256")
            and certificate.get("ordered_checkpoint_receipt_ledger_sha256"), "inventory ledger certificate missing")
    return certificate


def validate_proof(root: Path, proof_path: Path, expected_sha: str,
                   completion: Mapping[str, Any], registry_path: Path, taxonomy_path: Path,
                   registry_sha: str | None, taxonomy_sha: str | None) -> dict[str, Any]:
    require(sha256_file(proof_path) == expected_sha == PROOF_SHA256, "inventory proof hash mismatch")
    proof = read_json(proof_path)
    require(proof.get("status") == PROOF_STATUS, "inventory proof status invalid")
    require(proof.get("active_species") == REGISTERED_SPECIES
            and proof.get("effort_donors") == REGISTERED_SPECIES
            and proof.get("nonempty_species") == OBSERVED_SPECIES
            and proof.get("empty_species") == EMPTY_SPECIES, "inventory proof counts invalid")
    active = set(map(str, proof.get("active_names", ())))
    nonempty = set(map(str, proof.get("nonempty_names", ())))
    empty = set(map(str, proof.get("empty_names", ())))
    donors = set(map(str, proof.get("effort_donor_names", ())))
    require(len(active) == REGISTERED_SPECIES and len(nonempty) == OBSERVED_SPECIES and len(empty) == EMPTY_SPECIES,
            "inventory proof identity counts invalid")
    require(active == nonempty | empty and not nonempty & empty and donors == active,
            "inventory proof active/donor partition invalid")
    require(proof.get("canonical_memberships") == CANONICAL_ROWS, "inventory proof row count invalid")
    bindings = completion.get("bindings", {})
    require(sha256_file(registry_path) == bindings.get("registry_sha256") == proof.get("registry_sha256"),
            "registry binding mismatch")
    require(sha256_file(taxonomy_path) == bindings.get("taxonomy_sha256") == proof.get("taxonomy_sha256"),
            "taxonomy binding mismatch")
    if registry_sha is not None:
        require(sha256_file(registry_path) == registry_sha, "staged registry hash mismatch")
    if taxonomy_sha is not None:
        require(sha256_file(taxonomy_path) == taxonomy_sha, "staged taxonomy hash mismatch")
    registry = read_json(registry_path)
    taxonomy = read_json(taxonomy_path)
    require(registry.get("status") == "frozen_response_blind" and taxonomy.get("status") == "frozen_count_free",
            "registry/taxonomy status invalid")
    rows = registry.get("rows", ())
    effort = {str(row.get("name")) for row in rows if row.get("effort") is True}
    require(len(rows) >= REGISTERED_SPECIES and effort == active, "registry effort role inventory mismatch")
    taxonomy_rows = taxonomy.get("rows", ())
    taxonomy_active = {str(row.get("species")) for row in taxonomy_rows if row.get("active") is True}
    taxonomy_effort = {str(row.get("species")) for row in taxonomy_rows
                       if row.get("active") is True and row.get("roles", {}).get("effort") is True}
    require(taxonomy.get("active_species_count") == REGISTERED_SPECIES
            and taxonomy_active == active and taxonomy_effort == active, "taxonomy active/effort inventory mismatch")
    canonical_hash = bindings.get("canonical_species_cells_sha256")
    require(isinstance(canonical_hash, str) and len(canonical_hash) == 64
            and canonical_hash == proof.get("canonical_sha256"), "canonical binding missing or drifted")
    return {"proof": proof, "registry": registry, "taxonomy": taxonomy,
            "active": sorted(active), "nonempty": sorted(nonempty), "empty": sorted(empty)}


def validate_prior_access(run: Path, closure: Mapping[str, Any], expected_sha: str,
                          canonical_hash: str, target_digest: str) -> Path:
    require(not (run / RESPONSE_SUCCESS).exists(), "response success already exists")
    require(not (run / FIT_FAILURE).exists(), "scoring failure already exists")
    require(not (run / SCORES).exists(), "scores already exists")
    extras = sorted(path.name for path in run.glob("response-access*.json") if path.name != RESPONSE_STARTED)
    require(not extras, "unexpected response access receipt: {}".format(extras))
    path = run / RESPONSE_STARTED
    require(sha256_file(path) == expected_sha, "prior response-access hash mismatch")
    access = read_json(path)
    require(access.get("schema_version") == "goal052-outer-response-access-v1"
            and access.get("status") == "response_access_started"
            and access.get("immutable") is True
            and access.get("response_rows_read") is None
            and access.get("success_receipt") == RESPONSE_SUCCESS, "prior response-access identity invalid")
    require(access.get("closure_file_sha256") == sha256_file(run / "closure.json")
            and access.get("closure_digest") == closure.get("closure_digest")
            and access.get("plan_digest") == closure.get("plan_digest")
            and access.get("canonical_species_cells_sha256") == canonical_hash
            and access.get("target_inventory_sha256") == target_digest
            and access.get("domain_rows") == closure.get("domain", {}).get("rows"),
            "prior response-access closure binding drift")
    return path


def validate_audit(path: Path, expected_sha: str, plan: Mapping[str, Any],
                   plan_sha: str, closure: Mapping[str, Any], closure_sha: str) -> str:
    digest = sha256_file(path)
    require(digest == expected_sha, "independent audit hash mismatch")
    audit = read_json(path)
    provenance = audit.get("provenance", {})
    verified = audit.get("verified", {})
    require(audit.get("schema_version") == "dsdm-outer-independent-closure-audit-v1"
            and audit.get("status") == "pass"
            and provenance.get("plan_sha256") == plan_sha
            and provenance.get("plan_digest") == plan.get("plan_digest")
            and provenance.get("closure_sha256") == closure_sha
            and provenance.get("closure_digest") == closure.get("closure_digest")
            and verified.get("pre_score_absence") is True
            and verified.get("pre_response_access_absence") is True
            and verified.get("outer_response_content_opened") is False,
            "independent audit gate invalid")
    return digest


def bind_control(control: Path, args: argparse.Namespace, plan_sha: str, closure_sha: str,
                 audit_sha: str | None, source_hashes: Mapping[str, str], proof_sha: str,
                 metadata: Mapping[str, Any], prior_access_sha: str) -> tuple[Path, str]:
    require(not control.exists(), "recovery control already exists: {}".format(control))
    control.mkdir(parents=True)
    manifest = {
        "schema_version": "goal052-outer-score-recovery-control-v1", "status": "prepared",
        "control": str(control), "run": str(args.run), "plan_sha256": plan_sha,
        "closure_sha256": closure_sha, "audit_sha256": audit_sha,
        "source_hashes": dict(source_hashes), "inventory_proof": str(args.inventory_proof),
        "inventory_proof_sha256": proof_sha, "completion_receipt_sha256": metadata["completion_sha256"],
        "inventory_certificate": str(args.inventory_certificate),
        "inventory_certificate_sha256": args.inventory_certificate_sha256,
        "independent_audit": str(args.audit) if args.audit is not None else None,
        "independent_audit_sha256": audit_sha,
        "canonical_species_cells_sha256": metadata["canonical_sha256"],
        "registry_sha256": metadata["registry_sha256"], "taxonomy_sha256": metadata["taxonomy_sha256"],
        "prior_access_sha256": prior_access_sha, "registered_species": REGISTERED_SPECIES,
        "observed_species": OBSERVED_SPECIES, "empty_species": EMPTY_SPECIES,
    }
    path = control / "manifest.json"
    return path, immutable_json(path, manifest)


def reconstruct_response(root: Path, run: Path, closure: Mapping[str, Any], native: Any, response_native: Any,
                         metadata: Mapping[str, Any]) -> dict[str, Any]:
    config, completion, completion_path, panel_path, canonical_path, canonical_hash, target_digest, targets, donor_species = response_native._metadata_before_response_read(root, closure)
    del config, donor_species
    require(canonical_path.is_file() and sha256_file(canonical_path) == canonical_hash,
            "canonical source hash mismatch")
    require(canonical_hash == metadata["canonical_sha256"], "certificate canonical hash mismatch")
    require(set(targets).isdisjoint(set(metadata["empty"])), "frozen target is an empty species")
    require(set(targets) <= set(metadata["nonempty"]), "frozen target missing from observed species")
    cell_ids, domain_digest = response_native._read_domain(run, closure)
    present, richness, row_count, species_seen, donor_seen = response_native._read_canonical_rows(
        canonical_path, {cell: index for index, cell in enumerate(cell_ids)}, targets,
        None, OBSERVED_SPECIES, OBSERVED_SPECIES)
    require(row_count == CANONICAL_ROWS, "canonical row count mismatch")
    require(set(species_seen) == set(metadata["nonempty"]), "observed species identity mismatch")
    require(set(donor_seen) == set(metadata["nonempty"]), "observed donor identity mismatch")
    by_target: dict[str, dict[str, np.ndarray]] = {}
    target_receipts: dict[str, dict[str, Any]] = {}
    for target in targets:
        focal = richness - present[target].astype(np.int32)
        require(np.all(focal >= 0), "focal-excluded richness negative")
        y = present[target].astype(np.int8, copy=True)
        richness_minus_f = focal.astype(np.int32, copy=False)
        by_target[target] = {"y": y, "richness_minus_f": richness_minus_f}
        target_receipts[target] = {
            "presence_cells": int(y.sum()),
            "y_sha256": response_native._array_digest(y, "<i1"),
            "richness_minus_f_sha256": response_native._array_digest(richness_minus_f, "<i4"),
        }
    provenance = {
        "schema_version": "goal052-outer-response-provenance-v1",
        "closure_file_sha256": sha256_file(run / "closure.json"), "closure_digest": closure.get("closure_digest"),
        "plan_digest": closure.get("plan_digest"), "canonical_species_cells_sha256": canonical_hash,
        "completion_receipt_sha256": sha256_file(completion_path), "panel_summary_sha256": sha256_file(panel_path),
        "domain_cell_ids_sha256": domain_digest, "domain_rows": len(cell_ids),
        "canonical_membership_rows": row_count, "canonical_species_count": OBSERVED_SPECIES,
        "effort_donor_count": OBSERVED_SPECIES, "serialized_nonempty_species_count": OBSERVED_SPECIES,
        "registered_active_species_count": REGISTERED_SPECIES, "registered_effort_donor_count": REGISTERED_SPECIES,
        "target_count": len(by_target), "certificate_canonical_sha256": metadata["canonical_sha256"],
        "target_inventory_sha256": target_digest,
    }
    return {"closure": closure, "by_target": by_target, "response_provenance": provenance,
            "canonical_hash": canonical_hash, "target_digest": target_digest,
            "domain_digest": domain_digest, "targets": targets, "target_receipts": target_receipts,
            "completion_path": completion_path}


def score_response(root: Path, run: Path, response: Mapping[str, Any], native: Any,
                   recovery_provenance: Mapping[str, Any]) -> dict[str, Any]:
    from dsdm_phase1.goal052_outer_artifacts import read_json, write_once
    from dsdm_phase1.goal052_outer_scoring import aggregate_regions, matched_inner_attenuation, score_target_region
    plan = native.load_plan(root, run)
    domain = native.read_domain(run, plan)["arrays"]
    blocks = np.asarray([f"{x},{y}" for x, y in zip(domain["block_x"], domain["block_y"])])
    results = []
    for target in plan["targets"]:
        with np.load(run / response["closure"]["predictions"][target], allow_pickle=False) as payload:
            scores = {arm: payload[arm] for arm in native.ALL_ARMS}
        rows = response["by_target"][target]
        for region in ("NCP", "SEH", "NNC"):
            selected = domain["regions"] == region
            results.append(score_target_region(target, region, rows["y"][selected], rows["richness_minus_f"][selected], blocks[selected],
                                               {arm: values[selected] for arm, values in scores.items()}, plan["thresholds"][target],
                                               primary=target in plan["panels"]["primary"], regional=target in plan["panels"]["regional"][region]))
    failures = [{"target": item["target"], "region": item["region"], "support": item["support"]["x10"]}
                for item in results if item["panel"]["regional"] and not item["support"]["x10"]["passes"]]
    if failures:
        write_once(run / FIT_FAILURE, {"status": "outer_support_failure", "failures": failures,
                                       "closure_sha256": sha256_file(run / "closure.json"),
                                       "recovery_provenance": dict(recovery_provenance)})
    require(not failures, "unexpected frozen panel x10 support failure")
    for region, frozen_targets in plan["x20_targets"].items():
        observed = sorted(item["target"] for item in results if item["region"] == region and item["panel"]["regional"] and item["support"]["x20"]["passes"])
        if observed != sorted(frozen_targets):
            write_once(run / FIT_FAILURE, {"status": "outer_x20_membership_drift", "region": region,
                                           "expected": sorted(frozen_targets), "observed": observed,
                                           "closure_sha256": sha256_file(run / "closure.json"),
                                           "recovery_provenance": dict(recovery_provenance)})
        require(observed == sorted(frozen_targets), "frozen x20 membership drift: {}".format(region))
    aggregate = aggregate_regions(results, plan["panels"]["primary"], plan["panels"]["regional"])
    aggregate["matched_inner_attenuation"] = matched_inner_attenuation(aggregate, read_json(root / "evidence/seawfb_dsdm/goal052/summary.json"))
    output = {"schema_version": "goal052-outer-scores-v1", "created_utc": native.now(),
              "plan_digest": plan["plan_digest"], "closure_sha256": sha256_file(run / "closure.json"),
              "response_provenance": response["response_provenance"], "targets": results, "aggregate": aggregate,
              "recovery_provenance": dict(recovery_provenance),
              "interpretive_limits": [
                  "Threshold metrics use frozen inner-OOF thresholds; retained-full score-scale changes were not recalibrated on outer outcomes.",
                  "Original fitted inner target states were not saved, so the identical-grid inner/full score-scale comparison is unavailable without additional replay fits.",
                  "Presence versus effort-supported target-group background measures recording discrimination, not occupancy or verified absence.",
                  "Recorded-richness diagnostics test a retained-inner discovery prospectively and do not identify ecological versus observation mechanisms.",
                  "Species, regions and seeds are not iid replicates; descriptive sign labels are not significance, equivalence or practical-importance tests.",
              ]}
    require(not (run / SCORES).exists(), "scores appeared before recovery write")
    write_once(run / SCORES, output)
    return output


def recover(args: argparse.Namespace) -> dict[str, Any]:
    root, run, control = args.root.resolve(), args.run.resolve(), args.control.resolve()
    native = import_native(root)
    response_native = import_response(root)
    from dsdm_phase1.goal052_outer_artifacts import verify_closure
    closure = verify_closure(root, run)
    plan = native.load_plan(root, run)
    plan_sha, closure_sha = sha256_file(run / "plan.json"), sha256_file(run / "closure.json")
    require(args.expected_plan_sha256 == plan_sha and args.expected_closure_sha256 == closure_sha,
            "plan or closure hash mismatch")
    audit_sha = None
    if args.audit is not None or args.expected_audit_sha256 is not None:
        require(args.audit is not None and args.expected_audit_sha256 is not None, "audit path and hash must be paired")
        audit_sha = validate_audit(args.audit.resolve(), args.expected_audit_sha256, plan, plan_sha, closure, closure_sha)
    _, completion_path, registry_path, taxonomy_path = metadata_paths(root)
    completion = read_json(completion_path)
    certificate = validate_certificate(root, args.inventory_certificate.resolve(), args.inventory_certificate_sha256,
                                       plan_sha, closure_sha, completion_path, registry_path, taxonomy_path)
    proof = validate_proof(root, args.inventory_proof.resolve(), args.inventory_proof_sha256,
                           completion, registry_path, taxonomy_path, args.registry_sha256, args.taxonomy_sha256)
    require(certificate.get("canonical_sha256") == proof["proof"].get("canonical_sha256")
            and certificate.get("diagnosis_sha256") == args.inventory_proof_sha256,
            "inventory certificate/proof drift")
    for key, names_key in (("active", "active_names"), ("donors", "effort_donor_names"),
                           ("nonempty", "nonempty_names"), ("empty", "empty_names")):
        require(certificate.get("identity_digests", {}).get(key) == string_digest(proof["proof"][names_key]),
                "inventory identity digest drift: {}".format(key))
    require(certificate.get("empty_scoring_targets") in (0, []), "empty scoring target inventory drift")
    _, _, _, _, _, canonical_hash, target_digest, _, _ = response_native._metadata_before_response_read(root, closure)
    require(canonical_hash == certificate["canonical_sha256"], "certificate canonical metadata drift")
    prior_path = validate_prior_access(run, closure, args.prior_access_sha, canonical_hash, target_digest)
    metadata = {"completion_sha256": sha256_file(completion_path), "registry_sha256": sha256_file(registry_path),
                "taxonomy_sha256": sha256_file(taxonomy_path), "certificate_sha256": args.inventory_certificate_sha256,
                "canonical_sha256": certificate["canonical_sha256"], **proof}
    helper_sha = sha256_file(Path(__file__).resolve())
    manifest_path, manifest_sha = bind_control(control, args, plan_sha, closure_sha, audit_sha, plan["sources"],
                                               args.inventory_proof_sha256, metadata, args.prior_access_sha)
    started = {"schema_version": "goal052-outer-score-recovery-started-v1", "status": "response_access_recovery_started",
               "control_manifest": str(manifest_path), "control_manifest_sha256": manifest_sha,
               "helper": str(Path(__file__).resolve()), "helper_sha256": helper_sha,
               "source_hashes": plan["sources"], "plan_sha256": plan_sha, "closure_sha256": closure_sha,
               "prior_access": str(prior_path.relative_to(run)), "prior_access_sha256": args.prior_access_sha,
               "inventory_proof": str(args.inventory_proof), "inventory_proof_sha256": args.inventory_proof_sha256,
               "inventory_certificate": str(args.inventory_certificate), "inventory_certificate_sha256": args.inventory_certificate_sha256,
               "completion_receipt_sha256": metadata["completion_sha256"], "registry_sha256": metadata["registry_sha256"],
               "taxonomy_sha256": metadata["taxonomy_sha256"], "registered_species": REGISTERED_SPECIES,
               "observed_species": OBSERVED_SPECIES, "empty_species": EMPTY_SPECIES,
               "canonical_membership_rows": CANONICAL_ROWS, "canonical_species_cells_sha256": metadata["canonical_sha256"],
               "outer_response_rows_read": 0}
    started_path = control / "response-access-recovery-started.json"
    started_sha = immutable_json(started_path, started)
    try:
        response = reconstruct_response(root, run, closure, native, response_native, metadata)
        access_path = run / RESPONSE_STARTED
        response_native._write_access_success(run, access_path, closure, response["canonical_hash"], response["target_digest"],
                                               response["domain_digest"], response["target_receipts"], CANONICAL_ROWS, OBSERVED_SPECIES)
        native_success = read_json(run / RESPONSE_SUCCESS)
        require(native_success.get("access_started_sha256") == args.prior_access_sha
                and native_success.get("canonical_species_cells_sha256") == metadata["canonical_sha256"]
                and native_success.get("canonical_membership_rows") == CANONICAL_ROWS
                and native_success.get("canonical_species_count") == OBSERVED_SPECIES,
                "native response success binding drift")
        recovery_provenance = {"recovery_helper": str(Path(__file__).resolve()), "recovery_helper_sha256": helper_sha,
                               "recovery_control": str(control), "recovery_manifest_sha256": manifest_sha,
                               "independent_audit_sha256": audit_sha,
                               "recovery_started_receipt_sha256": started_sha, "inventory_proof_sha256": args.inventory_proof_sha256,
                               "inventory_certificate_sha256": args.inventory_certificate_sha256,
                               "completion_receipt_sha256": metadata["completion_sha256"], "registry_sha256": metadata["registry_sha256"],
                               "taxonomy_sha256": metadata["taxonomy_sha256"], "registered_active_species_count": REGISTERED_SPECIES,
                               "registered_effort_donor_count": REGISTERED_SPECIES, "serialized_nonempty_species_count": OBSERVED_SPECIES,
                               "empty_species": EMPTY_SPECIES, "canonical_membership_rows": CANONICAL_ROWS,
                               "prior_access_sha256": args.prior_access_sha}
        output = score_response(root, run, response, native, recovery_provenance)
    except Exception as error:
        failure = {"schema_version": "goal052-outer-score-recovery-failure-v1", "status": "scoring_recovery_failed",
                   "control_manifest_sha256": manifest_sha, "started_receipt_sha256": started_sha,
                   "error_type": type(error).__name__, "error": str(error),
                   "recovery_provenance": {"inventory_proof_sha256": args.inventory_proof_sha256,
                                           "inventory_certificate_sha256": args.inventory_certificate_sha256}}
        immutable_json(control / "response-access-recovery-failure.json", failure)
        if not (run / FIT_FAILURE).exists():
            immutable_json(run / FIT_FAILURE, {"status": "outer_score_recovery_failure",
                                               "recovery_control_manifest_sha256": manifest_sha,
                                               "error_type": type(error).__name__, "error": str(error),
                                               "closure_sha256": closure_sha})
        raise
    success = {"schema_version": "goal052-outer-score-recovery-success-v1", "status": "scoring_complete",
               "control_manifest_sha256": manifest_sha, "started_receipt_sha256": started_sha,
               "native_access_success_sha256": sha256_file(run / RESPONSE_SUCCESS), "scores_sha256": sha256_file(run / SCORES),
               "recovery_provenance": recovery_provenance, "score_schema_version": output["schema_version"]}
    immutable_json(control / "response-access-recovery-success.json", success)
    return success


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--inventory-proof", type=Path, required=True)
    parser.add_argument("--inventory-proof-sha256", required=True)
    parser.add_argument("--inventory-certificate", type=Path, required=True)
    parser.add_argument("--inventory-certificate-sha256", required=True)
    parser.add_argument("--prior-access-sha", "--prior-access-sha256", dest="prior_access_sha", required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--expected-closure-sha256", required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--expected-audit-sha256")
    parser.add_argument("--registry-sha256")
    parser.add_argument("--taxonomy-sha256")
    args = parser.parse_args(argv)
    args.root, args.run, args.control = args.root.resolve(), args.run.resolve(), args.control.resolve()
    return args


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = recover(parse_args(argv))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (RecoveryError, OSError, ValueError) as error:
        print("goal052 score recovery: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
