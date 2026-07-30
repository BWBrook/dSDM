from __future__ import annotations

import json
import hashlib
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest


def _foundation(species_id: str = "thylogale_billardierii", n: int = 60):
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
        key = RowKey(species_id, f"cell{index:03d}")
        pa = index % 2
        rows.append(
            {
                "species_id": species_id,
                "grid_cell_id": key.grid_cell_id,
                "pa": pa,
                "pa_type": "presence" if pa else (
                    "survey_supported_absence" if index % 4 else "pseudoabsence"
                ),
                "microcluster": f"mc{index % 7:02d}",
            }
        )
        values[key] = {
            "continuous": [
                float(np.sin((index + 1) * (column + 1) / 17.0) + pa * 0.1)
                for column in range(25)
            ],
            "categorical": {
                "soil_class": f"s{index % 3}",
                "veg_mvg": f"v{index % 4}",
                "landuse_secondary": f"l{index % 2}",
            },
        }
        folds[key] = f"fold{index % 5:02d}"
    rowset = RowSet.from_records(rows)
    broker = SplitBroker(rowset, folds)
    provider = FeatureProvider(LazyFeatureSubstrate(values), frozenset(rowset.keys))
    return broker, provider


@pytest.fixture
def goal029_config():
    from dsdm_phase1.goal029_production import load_goal029_config

    root = Path(__file__).resolve().parents[1]
    return load_goal029_config(root)


def test_exact_production_and_calibration_plans(goal029_config):
    from dsdm_phase1.goal029_production import (
        CANDIDATE_STRATA_COUNT,
        FAMILY_STRATA_COUNT,
        LEAF_COUNT,
        SELECTED_REFIT_MAXIMUM,
        calibration_canary_plan,
        calibration_plan,
        fragility_stress_plan,
        production_plan,
    )

    plan = production_plan(goal029_config)
    assert len(plan) == LEAF_COUNT == 7168
    assert len({leaf.family_stratum for leaf in plan}) == FAMILY_STRATA_COUNT == 336
    assert len({leaf.candidate_stratum for leaf in plan}) == CANDIDATE_STRATA_COUNT == 2016
    assert SELECTED_REFIT_MAXIMUM == 1008
    assert goal029_config["models"]["planned_counts"]["oof_producing_fold_units"] == 35840
    assert goal029_config["models"]["planned_counts"]["actual_inner_estimator_fits"] == 44240
    assert goal029_config["failure_policy"]["minimum_complete_valid_candidates_by_family"] == {
        family: (1 if family == "intercept" else 2)
        for family in goal029_config["models"]["families"]
    }
    calibration = calibration_plan(goal029_config)
    assert len(calibration) == 30 and set(calibration) <= set(plan)
    canary = calibration_canary_plan(goal029_config)
    assert canary == (
        next(
            leaf
            for leaf in calibration
            if leaf.species_id == "trichosurus_vulpecula"
            and leaf.fraction_id == "fraction50"
            and leaf.ladder_id == "ladder00"
            and leaf.candidate_id == "gam01"
        ),
        next(
            leaf
            for leaf in calibration
            if leaf.species_id == "vombatus_ursinus"
            and leaf.fraction_id == "fraction50"
            and leaf.ladder_id == "ladder01"
            and leaf.candidate_id == "gam01"
        ),
    )
    stress = fragility_stress_plan()
    assert len(stress) == 32
    assert {leaf.candidate_id for leaf in stress} == {"gam02", "gam03"}
    assert goal029_config["calibration"]["planned_counts"] == {
        "spawn_audit_children": 4,
        "canary_leaf_executions": 4,
        "representative_leaf_executions": 90,
        "fragility_leaf_executions": 32,
        "total_leaf_executions": 126,
        "maximum_estimator_fits": 735,
    }


def test_numerical_thread_policy_is_live_and_fails_closed(goal029_config):
    import os

    from dsdm_phase1.goal029_production import (
        Goal029Error,
        _NUMERICAL_THREAD_ENVIRONMENT,
        _normalise_thread_pool,
        _sha,
        _validate_thread_evidence,
        enforce_numerical_thread_policy,
    )

    assert {
        key: os.environ.get(key) for key in _NUMERICAL_THREAD_ENVIRONMENT
    } == _NUMERICAL_THREAD_ENVIRONMENT
    evidence = enforce_numerical_thread_policy(goal029_config)
    _validate_thread_evidence(evidence, goal029_config)
    assert evidence["torch"] == {
        "intraop_threads": 1,
        "interop_threads": 1,
    }
    assert all(
        pool["num_threads"] <= 1
        for pool in evidence["pools"]
        if pool["user_api"] in {"blas", "openmp"}
    )
    with pytest.raises(Goal029Error, match="thread_pool_limit_failed"):
        _normalise_thread_pool(
            {
                "user_api": "openmp",
                "internal_api": "openmp",
                "prefix": "libomp",
                "num_threads": 2,
            }
        )
    empty_pool_evidence = {**evidence, "pools": []}
    empty_pool_body = dict(empty_pool_evidence)
    empty_pool_body.pop("evidence_digest")
    empty_pool_evidence["evidence_digest"] = _sha(empty_pool_body)
    with pytest.raises(Goal029Error, match="thread_evidence_invalid"):
        _validate_thread_evidence(empty_pool_evidence, goal029_config)


def test_zero_fit_spawn_audit_proves_four_distinct_children(
    goal029_config, tmp_path
):
    from dsdm_phase1.goal029_production import run_thread_spawn_audit

    root = Path(__file__).resolve().parents[1]
    receipt = run_thread_spawn_audit(
        root, goal029_config, tmp_path / "spawn-audit"
    )
    assert receipt["fit_count"] == 0
    assert len({record["worker_pid"] for record in receipt["children"]}) == 4
    assert len(receipt["worker_thread_evidence"]) == 4
    assert receipt["real_outer_attempted_open_count"] == 0
    assert receipt["real_outer_open_count"] == 0


def test_canary_and_representative_worker_gates(goal029_config):
    from dsdm_phase1.goal029_production import (
        Goal029Error,
        _select_representative_workers,
        _validate_canary_gate,
    )

    gib = 1024**3

    def trial(workers, wall, *, status="complete", swap_after=0):
        return {
            "workers": workers,
            "semantic_digest": "a" * 64,
            "results": [{"status": status}],
            "telemetry": {
                "wall_seconds": wall,
                "free_memory_before_bytes": 12 * gib,
                "free_memory_after_bytes": 8 * gib,
                "swap_before_bytes": 0,
                "swap_after_bytes": swap_after,
            },
        }

    assert _validate_canary_gate(
        [trial(1, 10.0), trial(2, 12.5)], goal029_config
    ) == "a" * 64
    with pytest.raises(Goal029Error, match="canary_slowdown"):
        _validate_canary_gate(
            [trial(1, 10.0), trial(2, 12.5001)], goal029_config
        )
    with pytest.raises(Goal029Error, match="canary_failed"):
        _validate_canary_gate(
            [trial(1, 10.0), trial(2, 9.0, status="invalid_candidate")],
            goal029_config,
        )

    # 1 worker is exactly within 1.10 of the fastest and is preferred.
    assert (
        _select_representative_workers(
            [trial(1, 11.0), trial(2, 10.5), trial(4, 10.0)],
            goal029_config,
        )
        == 1
    )
    # Exclude an unsafe fastest trial, then choose the smallest near-fastest.
    assert (
        _select_representative_workers(
            [
                trial(1, 12.0),
                trial(2, 10.0),
                trial(4, 1.0, swap_after=1),
            ],
            goal029_config,
        )
        == 2
    )


def test_runtime_sensitive_configuration_is_exactly_frozen(tmp_path):
    from dsdm_phase1.goal029_production import Goal029Error, load_goal029_config

    root = Path(__file__).resolve().parents[1]
    canonical = json.loads(
        (root / "config/conventional_baseline_production.json").read_text(
            encoding="utf-8"
        )
    )

    def mutated(*keys, value):
        record = json.loads(json.dumps(canonical))
        target = record
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
        return record

    variants = (
        mutated(
            "failure_policy",
            "allowed_informational_warning_substrings",
            value=[""],
        ),
        mutated("hardening", "challenge_rows_maximum", value=1),
        mutated(
            "execution",
            "runtime_critical_paths",
            value=["config/conventional_baseline_production.json"],
        ),
        mutated("artifacts", "private_destination", value="../escape"),
        mutated("calibration", "receipt_destination", value="/tmp/escape"),
    )
    for index, variant in enumerate(variants):
        path = tmp_path / f"mutated-{index}.json"
        path.write_text(json.dumps(variant), encoding="utf-8")
        with pytest.raises(Goal029Error, match="config_frozen"):
            load_goal029_config(root, path)


def test_swap_telemetry_reads_strict_linux_meminfo(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Linux")

    def read_meminfo(path, *, encoding):
        assert path == Path("/proc/meminfo")
        assert encoding == "ascii"
        return (
            "MemTotal:       16384000 kB\n"
            "SwapTotal:       2097152 kB\n"
            "SwapFree:        1572864 kB\n"
            "SwapCached:            0 kB\n"
        )

    monkeypatch.setattr(
        production.Path,
        "read_text",
        read_meminfo,
    )
    monkeypatch.setattr(
        production.subprocess,
        "check_output",
        lambda *_args, **_kwargs: pytest.fail("Darwin telemetry called on Linux"),
    )
    assert production._swap_used_bytes() == 524288 * 1024


def test_swap_telemetry_accepts_zero_linux_swap(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        production.Path,
        "read_text",
        lambda self, encoding=None: (
            "SwapTotal: 0 kB\nSwapFree: 0 kB\n"
        ),
    )
    assert production._swap_used_bytes() == 0


@pytest.mark.parametrize(
    "meminfo",
    (
        "SwapTotal: 1024 kB\n",
        "SwapTotal: 1024 kB\nSwapTotal: 1024 kB\nSwapFree: 512 kB\n",
        "SwapTotal: 1024 MB\nSwapFree: 512 kB\n",
        "SwapTotal: -1 kB\nSwapFree: 0 kB\n",
        "SwapTotal: 512 kB\nSwapFree: 1024 kB\n",
    ),
)
def test_swap_telemetry_rejects_invalid_linux_meminfo(monkeypatch, meminfo):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        production.Path,
        "read_text",
        lambda self, encoding=None: meminfo,
    )
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()


def test_swap_telemetry_rejects_linux_read_failure(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Linux")

    def failed_read(*_args, **_kwargs):
        raise OSError("simulated /proc read failure")

    monkeypatch.setattr(production.Path, "read_text", failed_read)
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()


def test_swap_telemetry_reads_strict_darwin_sysctl(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Darwin")

    def check_output(command, *, text):
        assert command == ["sysctl", "-n", "vm.swapusage"]
        assert text is True
        return (
            "total = 4096.00M  used = 128.50M  "
            "free = 3967.50M  (encrypted)\n"
        )

    monkeypatch.setattr(production.subprocess, "check_output", check_output)
    assert production._swap_used_bytes() == int(128.5 * 1024**2)


def test_swap_telemetry_rejects_malformed_or_failed_darwin(monkeypatch):
    import subprocess

    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        production.subprocess,
        "check_output",
        lambda *args, **kwargs: "used = 0.00M\n",
    )
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()

    def failed(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "sysctl")

    monkeypatch.setattr(production.subprocess, "check_output", failed)
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()


def test_swap_telemetry_rejects_incoherent_darwin_record(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        production.subprocess,
        "check_output",
        lambda *args, **kwargs: (
            "total = 1.00M  used = 1.00T  free = 0.00G\n"
        ),
    )
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()


def test_swap_telemetry_rejects_unsupported_platform(monkeypatch):
    import dsdm_phase1.goal029_production as production

    monkeypatch.setattr(production.platform, "system", lambda: "Windows")
    with pytest.raises(
        production.Goal029Error, match="^swap_telemetry_unavailable$"
    ):
        production._swap_used_bytes()


def test_deterministic_audit_is_exact_and_complete(goal029_config):
    from dsdm_phase1.goal029_production import (
        FAMILIES,
        audit_plan,
        production_plan,
    )

    plan = production_plan(goal029_config)
    digest = "a" * 64
    audit = audit_plan(plan, digest)
    assert audit == audit_plan(plan, digest)
    assert len(audit) == 359
    assert len({leaf.family_stratum for leaf in audit}) == 336
    assert {leaf.model_family for leaf in audit} == set(FAMILIES)
    assert {leaf.candidate_id for leaf in audit} == {
        leaf.candidate_id for leaf in plan
    }
    assert {leaf.seed_label for leaf in audit} == {
        f"seed{i:02d}" for i in range(5)
    }


def test_source_audit_reconciles_complete_and_invalid_states(goal029_config):
    from dataclasses import asdict

    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        Goal029Error,
        ProductionLeaf,
        SEEDS_BY_FAMILY,
        _candidate_stratum_key,
        _expected_source_audit_rows,
        _sha,
        _validate_production_source_audit,
        audit_plan,
        audit_salt,
        enforce_numerical_thread_policy,
        numerical_thread_policy,
        production_plan,
    )

    thread_evidence = enforce_numerical_thread_policy(goal029_config)
    context = ExecutionContext(
        *(["1" * 64] * 4),
        "unit-host",
        "2" * 64,
        _sha(numerical_thread_policy(goal029_config)),
        thread_evidence["evidence_digest"],
    )
    plan = production_plan(goal029_config)
    salt = audit_salt(plan, context)
    leaves = audit_plan(plan, salt)
    states = {}
    for leaf in leaves:
        key = _candidate_stratum_key(leaf)
        states.setdefault(
            key,
            {
                "status": "complete",
                "leaves": [
                    {
                        "leaf": asdict(
                            ProductionLeaf(
                                *leaf.candidate_stratum, seed_label
                            )
                        ),
                        "semantic_result_digest": _sha(
                            [
                                *leaf.candidate_stratum,
                                seed_label,
                            ]
                        ),
                    }
                    for seed_label in SEEDS_BY_FAMILY[leaf.model_family]
                ],
            },
        )
    invalid_key = _candidate_stratum_key(leaves[-1])
    states[invalid_key] = {
        "status": "invalid_candidate",
        "failure_code": "model_fit_failed",
    }
    rows = _expected_source_audit_rows(leaves, states)
    assert any(row["status"] == "invalid_candidate" for row in rows)
    run = {
        "selected_workers": 2,
        "candidate_states_file_sha256": "c" * 64,
    }
    plan_record = {"record_digest": "d" * 64}
    audit = {
        "schema_version": "1.0",
        "selection_salt": salt,
        "audit_leaf_digest": _sha([asdict(leaf) for leaf in leaves]),
        "leaf_count": len(leaves),
        "results_digest": _sha(rows),
        "plan_record_digest": plan_record["record_digest"],
        "candidate_states_file_sha256": run[
            "candidate_states_file_sha256"
        ],
        "cache_disabled": True,
        "fresh_process": True,
        "fresh_destination": True,
        "workers": 2,
        "thread_policy_digest": context.thread_policy_digest,
        "parent_thread_evidence": thread_evidence,
        "worker_thread_evidence": [
            {"worker_pid": 1001, "evidence": thread_evidence},
            {"worker_pid": 1002, "evidence": thread_evidence},
        ],
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    audit["receipt_digest"] = _sha(audit)
    _validate_production_source_audit(
        audit, run, context, plan_record, states, goal029_config
    )
    for field, value in (
        ("selection_salt", "e" * 64),
        ("results_digest", "f" * 64),
        ("workers", 1),
        ("real_outer_open_count", 1),
    ):
        tampered = {**audit, field: value}
        tampered.pop("receipt_digest")
        tampered["receipt_digest"] = _sha(tampered)
        with pytest.raises(Goal029Error, match="source_audit_invalid"):
            _validate_production_source_audit(
                tampered,
                run,
                context,
                plan_record,
                states,
                goal029_config,
            )


def test_source_tree_digest_covers_every_project_module_and_audit_salt_is_preresult(
    goal029_config,
):
    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        _audit_leaf_hash,
        _sha,
        audit_salt,
        production_plan,
        source_tree_digest,
    )
    from dsdm_phase1.modeling_contract import sha256_file

    root = Path(__file__).resolve().parents[1]
    files = [
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
        }
        for path in sorted((root / "src/dsdm_phase1").glob("*.py"))
    ]
    files.extend(
        {
            "path": raw,
            "sha256": sha256_file(root / raw),
        }
        for raw in goal029_config["execution"]["runtime_critical_paths"]
    )
    assert any(record["path"].endswith("/__init__.py") for record in files)
    assert source_tree_digest(root, goal029_config) == _sha(files)
    context = ExecutionContext(
        source_tree_digest(root, goal029_config),
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "private-host",
        "4" * 64,
    )
    plan = production_plan()
    salt = audit_salt(plan, context)
    assert len(salt) == 64
    assert _audit_leaf_hash(salt, plan[0]) != _audit_leaf_hash(salt, plan[1])
    changed = replace(context, upstream_binding_digest="5" * 64)
    assert audit_salt(plan, changed) != salt


def test_real_adapter_leaf_checkpoint_resume_and_tamper_rejection(
    goal029_config, tmp_path
):
    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        Goal029Error,
        ProductionLeaf,
        encoder_digests,
        leaf_identity,
        load_leaf_checkpoint,
        membership_records,
        run_leaf,
        write_leaf_checkpoint,
    )

    leaf = ProductionLeaf(
        "thylogale_billardierii",
        "fraction100",
        "full",
        "intercept",
        "null00",
        "seed00",
    )
    broker, provider = _foundation()
    memberships = membership_records(leaf, broker)
    assert set(memberships) == {
        "cv_fold00",
        "cv_fold01",
        "cv_fold02",
        "cv_fold03",
        "cv_fold04",
        "outer",
    }
    assert len({record["record_digest"] for record in memberships.values()}) == 6
    encoders = encoder_digests(leaf, broker, provider, memberships)
    context = ExecutionContext(*(["1" * 64] * 4), "unit-host", "2" * 64)
    identity = leaf_identity(leaf, context, memberships, encoders)
    result = run_leaf(leaf, broker, provider, goal029_config)
    path, reused = write_leaf_checkpoint(
        tmp_path / "checkpoints", identity, result
    )
    assert not reused
    loaded = load_leaf_checkpoint(path, identity)
    assert loaded.candidate_id == "null00"
    assert len(loaded.folds) == 5
    same_path, reused = write_leaf_checkpoint(
        tmp_path / "checkpoints", identity, result
    )
    assert same_path == path and reused

    result_path = path / "result.json"
    original = result_path.read_text(encoding="utf-8")
    result_path.write_text(original.replace('"threshold":', '"threshold_tampered":', 1))
    with pytest.raises(Goal029Error, match="tamper"):
        load_leaf_checkpoint(path, identity)

    result_path.write_text(original, encoding="utf-8")
    wrong = dict(identity)
    wrong["host_id"] = "different-host"
    with pytest.raises(Goal029Error, match="identity"):
        load_leaf_checkpoint(path, wrong)
    wrong_thread_policy = dict(identity)
    wrong_thread_policy["thread_policy_digest"] = "f" * 64
    with pytest.raises(Goal029Error, match="identity"):
        load_leaf_checkpoint(path, wrong_thread_policy)


def test_five_seed_merge_and_anchor_quorum(goal029_config):
    from dsdm_phase1.goal029_production import (
        Goal029Error,
        ProductionLeaf,
        merge_seed_leaves,
        run_leaf,
        validate_family_candidates,
    )

    broker, provider = _foundation()
    results = {}
    for seed_index in range(5):
        seed = f"seed{seed_index:02d}"
        leaf = ProductionLeaf(
            "thylogale_billardierii",
            "fraction100",
            "full",
            "elastic_net",
            "enet00",
            seed,
        )
        results[seed] = run_leaf(leaf, broker, provider, goal029_config)
    merged = merge_seed_leaves(results, "elastic_net", "enet00")
    assert merged.stratum.ordered_selection_seeds == tuple(
        f"seed{i:02d}" for i in range(5)
    )
    assert all(len(fold.scores_by_seed) == 5 for fold in merged.folds)
    second = replace(merged, candidate_id="enet01")
    chosen = validate_family_candidates(
        "elastic_net", {"enet00": merged, "enet01": second}, set()
    )
    assert chosen.candidate_id == "enet00"
    with pytest.raises(Goal029Error, match="anchor"):
        validate_family_candidates("elastic_net", {"enet01": second}, {"enet00"})
    with pytest.raises(Goal029Error, match="quorum"):
        validate_family_candidates("elastic_net", {"enet00": merged}, {"enet01"})
    with pytest.raises(Goal029Error, match="seed_set"):
        merge_seed_leaves(
            {key: value for key, value in results.items() if key != "seed04"},
            "elastic_net",
            "enet00",
        )


def test_warning_policy_and_blinded_failure_receipt(goal029_config):
    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        Goal029Error,
        ProductionLeaf,
        blinded_failure_receipt,
        classify_leaf_warnings,
        run_leaf,
    )
    from dsdm_phase1.model_adapters import FitReport

    broker, provider = _foundation()
    leaf = ProductionLeaf(
        "thylogale_billardierii",
        "fraction100",
        "full",
        "intercept",
        "null00",
        "seed00",
    )
    result = run_leaf(leaf, broker, provider, goal029_config)
    unknown = replace(
        result,
        fit_reports_by_seed={
            "seed00": (
                FitReport(True, 1, None, None, None, ("mystery warning",), 0.0, 1),
            )
        },
    )
    with pytest.raises(Goal029Error, match="unclassified_warning"):
        classify_leaf_warnings(leaf, unknown, goal029_config)

    allowed = replace(
        result,
        fit_reports_by_seed={
            "seed00": (
                FitReport(
                    True,
                    1,
                    None,
                    None,
                    None,
                    (
                        "Bitwise inversion '~' on bool is deprecated and will be removed",
                    ),
                    0.0,
                    1,
                ),
            )
        },
    )
    assert classify_leaf_warnings(leaf, allowed, goal029_config)
    context = ExecutionContext(*(["1" * 64] * 4), "unit-host", "2" * 64)
    receipt = blinded_failure_receipt(context, leaf, "model_fit_failed")
    serialized = json.dumps(receipt, sort_keys=True)
    assert receipt["partial_performance_exposed"] is False
    assert all(token not in serialized for token in ('"roc_auc"', '"tss"', '"threshold"', '"score"'))


def test_challenge_is_deterministic_response_free_and_tamper_checked():
    from dsdm_phase1.goal029_production import (
        Goal029Error,
        build_challenge_batch,
        challenge_from_payload,
        challenge_payload,
        canonical_prediction_bytes_sha256,
    )

    broker, provider = _foundation()
    rows = broker.outer_training("thylogale_billardierii")
    encoder = provider.fit_encoder(rows, "intercept", "outer")
    batch = provider.materialize(rows, "outer", encoder)
    challenge = build_challenge_batch(batch, 32)
    assert len(challenge.keys) == 32
    assert np.array_equal(challenge.y, np.zeros(32))
    assert challenge.x.tolist() == build_challenge_batch(batch, 32).x.tolist()
    payload = challenge_payload(challenge)
    assert payload["contains_row_ids"] is False
    assert payload["contains_response"] is False
    rebuilt = challenge_from_payload(payload)
    np.testing.assert_array_equal(rebuilt.x, challenge.x)
    duplicated = replace(batch, x=np.vstack([batch.x[:3], batch.x[:3]]), keys=tuple(
        list(batch.keys[:3]) + [
            type(batch.keys[0])("duplicate", f"row{index}") for index in range(3)
        ]
    ), y=np.zeros(6))
    small = build_challenge_batch(duplicated, 32)
    assert len(small.keys) == 3
    assert canonical_prediction_bytes_sha256([0.1, 0.2]) == canonical_prediction_bytes_sha256(
        np.asarray([0.1, 0.2], dtype=np.float64)
    )
    tampered = dict(payload)
    tampered["matrix"] = [*payload["matrix"]]
    tampered["matrix"][0] = [value + 1 for value in tampered["matrix"][0]]
    with pytest.raises(Goal029Error, match="challenge_payload_invalid"):
        challenge_from_payload(tampered)


def test_selected_refit_serializes_and_replays_challenge_without_vault_access(
    goal029_config, tmp_path
):
    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        Goal029Error,
        ProductionLeaf,
        _sha,
        canonical_prediction_bytes_sha256,
        challenge_from_payload,
        merge_seed_leaves,
        refit_selected_candidate,
        run_leaf,
        validate_selected_refit_receipt,
    )
    from dsdm_phase1.model_adapters import load_fitted_model
    from dsdm_phase1.modeling_contract import (
        OuterVault,
        TaskKey,
        canonical_json,
    )

    broker, provider = _foundation()
    leaf = ProductionLeaf(
        "thylogale_billardierii",
        "fraction100",
        "full",
        "intercept",
        "null00",
        "seed00",
    )
    result = run_leaf(leaf, broker, provider, goal029_config)
    selected = merge_seed_leaves({"seed00": result}, "intercept", "null00")
    vault = OuterVault(None, synthetic=False)
    context = ExecutionContext(*(["1" * 64] * 4), "unit-host", "2" * 64)
    private = tmp_path / "private"
    receipts = refit_selected_candidate(
        selected,
        broker,
        provider,
        vault,
        goal029_config,
        private / "selected",
        context,
    )
    assert len(receipts) == 1
    bundle = private / receipts[0]["bundle_path"]
    assert bundle.name == receipts[0]["selected_bundle_digest"]
    assert {path.name for path in bundle.iterdir()} == {
        "model.model",
        "challenge.json",
        "receipt.json",
    }
    validate_selected_refit_receipt(
        receipts[0],
        private,
        expected_task=TaskKey(**receipts[0]["selected_task"]),
        broker=broker,
        provider=provider,
        config=goal029_config,
        context=context,
    )
    expected_task = TaskKey(**receipts[0]["selected_task"])
    for wrong_task in (
        replace(expected_task, candidate_id="enet00"),
        replace(expected_task, seed_label="seed01"),
    ):
        with pytest.raises(Goal029Error, match="task_authority"):
            validate_selected_refit_receipt(
                receipts[0],
                private,
                expected_task=wrong_task,
                broker=broker,
                provider=provider,
                config=goal029_config,
                context=context,
            )
    escaped = dict(receipts[0])
    escaped["bundle_path"] = "../outside"
    with pytest.raises(Goal029Error, match="path_invalid"):
        validate_selected_refit_receipt(
            escaped,
            private,
            expected_task=expected_task,
            broker=broker,
            provider=provider,
            config=goal029_config,
            context=context,
        )

    original_challenge = json.loads(
        (bundle / "challenge.json").read_text(encoding="utf-8")
    )
    challenge_body = {
        key: value
        for key, value in original_challenge.items()
        if key != "challenge_digest"
    }
    challenge_body["matrix"] = challenge_body["matrix"][:1]
    challenge_body["matrix_bytes_sha256"] = hashlib.sha256(
        np.asarray(challenge_body["matrix"], dtype=">f8").tobytes(order="C")
    ).hexdigest()
    degenerate_challenge = {
        **challenge_body,
        "challenge_digest": _sha(challenge_body),
    }
    model = load_fitted_model(
        bundle / "model.model", receipts[0]["model_sha256"]
    )
    degenerate_scores = model.predict_scores(
        challenge_from_payload(degenerate_challenge)
    )
    degenerate_receipt = dict(receipts[0])
    degenerate_receipt["challenge_digest"] = degenerate_challenge[
        "challenge_digest"
    ]
    degenerate_receipt[
        "canonical_prediction_bytes_sha256"
    ] = canonical_prediction_bytes_sha256(degenerate_scores)
    identity_fields = (
        "schema_version",
        "selected_task",
        "model_sha256",
        "challenge_digest",
        "canonical_prediction_bytes_sha256",
        "feature_schema_digest",
        "transform_digest",
        "encoder_digest",
        "execution_context_digest",
        "model_envelope_identity_digest",
        "model_runtime_versions_digest",
        "model_candidate_digest",
        "fit_seed_uint32",
    )
    degenerate_digest = _sha(
        {key: degenerate_receipt[key] for key in identity_fields}
    )
    degenerate_receipt["selected_bundle_digest"] = degenerate_digest
    degenerate_receipt["bundle_path"] = f"selected/{degenerate_digest}"
    degenerate_bundle = private / degenerate_receipt["bundle_path"]
    degenerate_bundle.mkdir()
    shutil.copy2(bundle / "model.model", degenerate_bundle / "model.model")
    (degenerate_bundle / "challenge.json").write_text(
        canonical_json(degenerate_challenge) + "\n", encoding="utf-8"
    )
    (degenerate_bundle / "receipt.json").write_text(
        canonical_json(degenerate_receipt) + "\n", encoding="utf-8"
    )
    with pytest.raises(Goal029Error, match="challenge_provenance"):
        validate_selected_refit_receipt(
            degenerate_receipt,
            private,
            expected_task=expected_task,
            broker=broker,
            provider=provider,
            config=goal029_config,
            context=context,
        )

    (bundle / "unexpected.bin").write_bytes(b"extra")
    with pytest.raises(Goal029Error, match="file_inventory"):
        validate_selected_refit_receipt(
            receipts[0],
            private,
            expected_task=expected_task,
            broker=broker,
            provider=provider,
            config=goal029_config,
            context=context,
        )
    assert vault.attempted_open_count == 0 and vault.open_count == 0


def test_transaction_marker_validation_unmarked_rejection_and_rollback(
    monkeypatch, tmp_path
):
    import dsdm_phase1.goal029_production as production
    from dsdm_phase1.goal029_production import (
        Goal029Error,
        publish_transaction_pair,
        validate_transaction_pair,
    )

    stage_private = tmp_path / "stage-private"
    stage_evidence = tmp_path / "stage-evidence"
    stage_private.mkdir()
    stage_evidence.mkdir()
    (stage_private / "payload.bin").write_bytes(b"private")
    (stage_evidence / "summary.json").write_text('{"status":"pass"}\n')
    private = tmp_path / "private"
    evidence = tmp_path / "evidence"
    publish_transaction_pair(
        stage_private, stage_evidence, private, evidence, "a" * 64
    )
    assert validate_transaction_pair(private, evidence)["status"] == "pass"
    assert not (private / "pair_manifest.json").exists()
    descriptor = json.loads((evidence / "PAIR.json").read_text())
    marker = json.loads((evidence / "FINALIZED.json").read_text())
    assert set(descriptor) == {
        "schema_version",
        "transaction_id",
        "private_core_manifest_sha256",
        "tracked_core_manifest_sha256",
    }
    assert set(marker) == {
        "schema_version",
        "transaction_id",
        "pair_descriptor_sha256",
        "publication_state",
    }
    (evidence / "FINALIZED.json").unlink()
    with pytest.raises(Goal029Error, match="unmarked"):
        validate_transaction_pair(private, evidence)
    (evidence / "FINALIZED.json").write_text(
        json.dumps(marker, sort_keys=True), encoding="utf-8"
    )
    (evidence / "unexpected.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(Goal029Error, match="file_set"):
        validate_transaction_pair(private, evidence)

    stage_private = tmp_path / "stage-private-rollback"
    stage_evidence = tmp_path / "stage-evidence-rollback"
    stage_private.mkdir()
    stage_evidence.mkdir()
    (stage_private / "payload.bin").write_bytes(b"private")
    (stage_evidence / "summary.json").write_text('{"status":"pass"}\n')
    private = tmp_path / "private-rollback"
    evidence = tmp_path / "evidence-rollback"
    real_rename = production.os.rename
    calls = {"count": 0}

    def fail_second(source, destination):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated")
        return real_rename(source, destination)

    monkeypatch.setattr(production.os, "rename", fail_second)
    with pytest.raises(Goal029Error, match="rollback"):
        publish_transaction_pair(
            stage_private, stage_evidence, private, evidence, "b" * 64
        )
    assert not private.exists() and not evidence.exists()
    assert (stage_private / "payload.bin").read_bytes() == b"private"
    assert (stage_evidence / "summary.json").is_file()

    stage_private = tmp_path / "stage-private-marker"
    stage_evidence = tmp_path / "stage-evidence-marker"
    stage_private.mkdir()
    stage_evidence.mkdir()
    (stage_private / "payload.bin").write_bytes(b"private")
    (stage_evidence / "summary.json").write_text('{"status":"pass"}\n')
    private = tmp_path / "private-marker"
    evidence = tmp_path / "evidence-marker"
    calls = {"count": 0}

    def fail_marker(source, destination):
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("simulated marker rename failure")
        return real_rename(source, destination)

    monkeypatch.setattr(production.os, "rename", fail_marker)
    with pytest.raises(Goal029Error, match="rollback"):
        publish_transaction_pair(
            stage_private, stage_evidence, private, evidence, "c" * 64
        )
    assert not private.exists() and not evidence.exists()
    assert (stage_private / "payload.bin").read_bytes() == b"private"
    assert (stage_evidence / "summary.json").is_file()
    assert not (stage_evidence / "FINALIZED.json").exists()


def test_tracked_privacy_walker_rejects_metrics_paths_and_response_ids():
    from dsdm_phase1.goal029_production import Goal029Error, _privacy_walk

    _privacy_walk({"status": "pass", "outer_attempted_open_count": 0})
    for value in (
        {"roc_auc": 0.7},
        {"grid_cell_id": "cell"},
        {"pointer": "/private/location"},
        {"nested": [{"threshold": 0.2}]},
        {"status": "raw warning text"},
        {"status": "Traceback happened"},
        {"hostname": "private-host"},
    ):
        with pytest.raises(Goal029Error):
            _privacy_walk(value)


def test_staged_file_inventory_rejects_unlisted_files(tmp_path):
    from dsdm_phase1.goal029_production import (
        Goal029Error,
        _validate_exact_file_inventory,
    )

    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "summary.json").write_text("{}\n", encoding="utf-8")
    _validate_exact_file_inventory(
        stage, {"summary.json"}, "staged_inventory"
    )
    (stage / "orphan.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(Goal029Error, match="staged_inventory"):
        _validate_exact_file_inventory(
            stage, {"summary.json"}, "staged_inventory"
        )


def test_production_scheduler_groups_exact_candidate_seed_strata(goal029_config):
    from dsdm_phase1.goal029_production import (
        CANDIDATE_STRATA_COUNT,
        SEEDS_BY_FAMILY,
        _production_candidate_groups,
        _sha,
        production_plan,
    )
    from dataclasses import asdict

    plan = production_plan(goal029_config)
    record = {
        "record_digest": "a" * 64,
        "leaf_records": [
            {"leaf": asdict(leaf), "identity": {"identity_digest": _sha(asdict(leaf))}}
            for leaf in plan
        ],
    }
    groups = _production_candidate_groups(record)
    assert len(groups) == CANDIDATE_STRATA_COUNT == 2016
    assert [key for key, _ in groups] == list(dict.fromkeys(key for key, _ in groups))
    for _, records in groups:
        leaves = [record["leaf"] for record in records]
        assert [leaf["seed_label"] for leaf in leaves] == list(
            SEEDS_BY_FAMILY[leaves[0]["model_family"]]
        )


def test_candidate_failure_preserves_reused_checkpoint_until_durable_cleanup(
    monkeypatch, goal029_config, tmp_path
):
    from dataclasses import asdict

    import dsdm_phase1.goal029_production as production
    from dsdm_phase1.goal029_production import (
        ExecutionContext,
        ProductionLeaf,
        _candidate_state_value,
        _candidate_stratum_key,
        _finish_invalid_candidate_cleanup,
        _load_candidate_states,
        _normalize_production_candidate_state,
        _production_worker_candidate,
        _replace_atomic_json_file,
        _sha,
        enforce_numerical_thread_policy,
        numerical_thread_policy,
    )
    from dsdm_phase1.model_adapters import ModelAdapterError
    from dsdm_phase1.modeling_contract import OuterVault

    checkpoint_root = tmp_path / "private/checkpoints"
    checkpoint_root.mkdir(parents=True)
    records = []
    for index in range(5):
        leaf = ProductionLeaf(
            "thylogale_billardierii",
            "fraction100",
            "full",
            "elastic_net",
            "enet00",
            f"seed{index:02d}",
        )
        records.append(
            {
                "leaf": asdict(leaf),
                "identity": {"identity_digest": f"{index + 1:064x}"},
            }
        )
    reused = checkpoint_root / records[0]["identity"]["identity_digest"]
    reused.mkdir()
    (reused / "checkpoint_manifest.json").write_text(
        json.dumps({"semantic_result_digest": "a" * 64}), encoding="utf-8"
    )
    monkeypatch.setattr(production, "_CALIBRATION_CONFIG", goal029_config)
    thread_evidence = enforce_numerical_thread_policy(goal029_config)
    monkeypatch.setattr(
        production, "_WORKER_THREAD_EVIDENCE", thread_evidence
    )
    monkeypatch.setattr(production, "_CALIBRATION_BROKER", object())
    monkeypatch.setattr(production, "_CALIBRATION_PROVIDER", object())
    monkeypatch.setattr(
        production, "_CALIBRATION_VAULT", OuterVault(None, synthetic=False)
    )
    monkeypatch.setattr(production, "load_leaf_checkpoint", lambda *_: object())

    def fail_new_leaf(*_args, **_kwargs):
        raise ModelAdapterError("simulated_fit_failure")

    monkeypatch.setattr(production, "run_leaf", fail_new_leaf)
    result = _production_worker_candidate(
        {"checkpoint_root": str(checkpoint_root), "leaves": records}
    )
    assert result["status"] == "invalid_candidate"
    assert reused.is_dir()

    context = ExecutionContext(
        *(["1" * 64] * 4),
        "unit-host",
        "2" * 64,
        _sha(numerical_thread_policy(goal029_config)),
        thread_evidence["evidence_digest"],
    )
    plan_record = {
        "record_digest": "f" * 64,
        "execution_context": asdict(context),
    }
    private_stage = tmp_path / "private"
    state = _normalize_production_candidate_state(
        result,
        records,
        checkpoint_root,
        private_stage,
        plan_record,
        goal029_config,
    )
    assert state["cleanup_complete"] is False and reused.is_dir()
    key = _candidate_stratum_key(ProductionLeaf(**records[0]["leaf"]))
    groups = ((key, tuple(records)),)
    state_by_key = {key: state}
    _replace_atomic_json_file(
        private_stage / "candidate_states.json",
        _candidate_state_value(plan_record, groups, state_by_key),
    )
    _finish_invalid_candidate_cleanup(
        private_stage, plan_record, groups, state_by_key
    )
    assert not reused.exists()
    persisted = json.loads(
        (private_stage / "candidate_states.json").read_text(encoding="utf-8")
    )
    assert persisted["candidate_records"][0]["cleanup_complete"] is True
    assert (
        persisted["candidate_records"][0]["worker_thread_evidence"]
        == thread_evidence
    )
    monkeypatch.setattr(
        production, "_production_candidate_groups", lambda _: groups
    )
    _load_candidate_states(
        private_stage, plan_record, goal029_config, require_complete=True
    )
    persisted["candidate_records"][0]["worker_thread_evidence_digest"] = (
        "b" * 64
    )
    _replace_atomic_json_file(
        private_stage / "candidate_states.json", persisted
    )
    with pytest.raises(
        production.Goal029Error, match="production_invalid_state_invalid"
    ):
        _load_candidate_states(
            private_stage,
            plan_record,
            goal029_config,
            require_complete=True,
        )


def test_calibration_authority_revalidates_linked_trials(
    goal029_config, tmp_path
):
    from dataclasses import asdict
    import socket

    from dsdm_phase1.goal029_production import (
        Goal029Error,
        _sha,
        calibration_canary_plan,
        calibration_plan,
        execution_context,
        fragility_stress_plan,
        load_calibration_authority,
    )
    from dsdm_phase1.modeling_contract import canonical_json

    repo_root = Path(__file__).resolve().parents[1]
    context = execution_context(repo_root, goal029_config)
    # Authority requires the evidence that was bound into the live context.
    from dsdm_phase1.goal029_production import enforce_numerical_thread_policy

    thread_evidence = enforce_numerical_thread_policy(goal029_config)
    assert thread_evidence["evidence_digest"] == context.thread_evidence_digest
    canary_leaves = calibration_canary_plan(goal029_config)
    representative_leaves = calibration_plan(goal029_config)
    fragility_leaves = fragility_stress_plan()
    calibration_id = _sha(
        {
            "execution_context": asdict(context),
            "stage_order": goal029_config["calibration"]["stage_order"],
            "canary_leaves": [asdict(leaf) for leaf in canary_leaves],
            "representative_leaves": [
                asdict(leaf) for leaf in representative_leaves
            ],
            "fragility_leaves": [
                asdict(leaf) for leaf in fragility_leaves
            ],
            "canary_workers": [1, 2],
            "representative_workers": [1, 2, 4],
        }
    )
    private_root = (
        tmp_path
        / "data/processed/modeling/goal029-conventional-baseline-calibration"
        / calibration_id
    )

    def write(relative, value):
        path = private_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_json(value) + "\n", encoding="utf-8")

    gib = 1024**3
    spawn_children = [
        {
            "worker_pid": 1000 + index,
            "fit_count": 0,
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        for index in range(4)
    ]
    spawn = {
        "schema_version": "goal029_calibration_spawn_audit_v1",
        "requested_children": 4,
        "actual_host": socket.gethostname(),
        "parent_thread_evidence": thread_evidence,
        "children": spawn_children,
        "worker_thread_evidence": [
            {
                "worker_pid": record["worker_pid"],
                "evidence": thread_evidence,
            }
            for record in spawn_children
        ],
        "fit_count": 0,
        "telemetry": {
            "wall_seconds": 1.0,
            "free_memory_before_bytes": 16 * gib,
            "free_memory_after_bytes": 15 * gib,
            "swap_before_bytes": 0,
            "swap_after_bytes": 0,
        },
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    spawn["receipt_digest"] = _sha(spawn)
    write("spawn-audit/receipt.json", spawn)

    def make_trial(role, leaves, workers, wall_seconds):
        pids = [2000 + workers * 10 + index for index in range(workers)]
        results = [
            {
                "leaf": asdict(leaf),
                "status": "complete",
                "semantic_result_digest": _sha(asdict(leaf)),
                "failure_code": "",
                "peak_rss_bytes": 1024,
                "worker_pid": pids[index % workers],
                "real_outer_attempted_open_count": 0,
                "real_outer_open_count": 0,
            }
            for index, leaf in enumerate(leaves)
        ]
        semantic_rows = [
            {
                key: record[key]
                for key in (
                    "leaf",
                    "status",
                    "semantic_result_digest",
                    "failure_code",
                )
            }
            for record in results
        ]
        trial = {
            "schema_version": "goal029_calibration_trial_v2",
            "role": role,
            "workers": workers,
            "actual_host": socket.gethostname(),
            "thread_policy_digest": context.thread_policy_digest,
            "parent_thread_evidence": thread_evidence,
            "worker_thread_evidence": [
                {"worker_pid": pid, "evidence": thread_evidence}
                for pid in pids
            ],
            "fresh_processes": True,
            "checkpoint_reuse": False,
            "fresh_destination": True,
            "leaf_count": len(results),
            "results": results,
            "semantic_digest": _sha(semantic_rows),
            "telemetry": {
                "wall_seconds": wall_seconds,
                "peak_rss_bytes": 1024,
                "free_memory_before_bytes": 16 * gib,
                "free_memory_after_bytes": 12 * gib,
                "swap_before_bytes": 0,
                "swap_after_bytes": 0,
            },
            "real_outer_attempted_open_count": 0,
            "real_outer_open_count": 0,
        }
        trial["receipt_digest"] = _sha(trial)
        write(f"{role}/workers{workers}/receipt.json", trial)
        return trial

    canary_trials = [
        make_trial("canary", canary_leaves, 1, 10.0),
        make_trial("canary", canary_leaves, 2, 10.0),
    ]
    representative_trials = [
        make_trial("representative", representative_leaves, 1, 10.0),
        make_trial("representative", representative_leaves, 2, 9.5),
        make_trial("representative", representative_leaves, 4, 9.2),
    ]
    selected_workers = 1
    fragility_trial = make_trial(
        "fragility", fragility_leaves, selected_workers, 8.0
    )

    support = []
    for species_id in goal029_config["scope"]["species"]:
        for endpoint in goal029_config["partitions"]["endpoints"]:
            fraction_id, ladder_id = endpoint.split("/")
            support.append(
                {
                    "species_id": species_id,
                    "fraction_id": fraction_id,
                    "ladder_id": ladder_id,
                    "folds": [
                        {
                            "fold_id": f"fold{index:02d}",
                            "endpoint_zero_count": 1,
                            "endpoint_one_count": 1,
                            "assessment_zero_count": 1,
                            "assessment_one_count": 1,
                        }
                        for index in range(5)
                    ],
                    "outer_endpoint_zero_count": 1,
                    "outer_endpoint_one_count": 1,
                    "status": "pass",
                }
            )
    private = {
        "schema_version": "goal029_calibration_master_v2",
        "calibration_id": calibration_id,
        "actual_host": socket.gethostname(),
        "execution_context": asdict(context),
        "thread_policy_digest": context.thread_policy_digest,
        "thread_evidence_digest": context.thread_evidence_digest,
        "class_support_scan": support,
        "class_support_scan_digest": _sha(support),
        "spawn_audit_receipt": {
            "relative_path": "spawn-audit/receipt.json",
            "receipt_digest": spawn["receipt_digest"],
        },
        "canary_receipts": [
            {
                "role": "canary",
                "workers": trial["workers"],
                "relative_path": (
                    f"canary/workers{trial['workers']}/receipt.json"
                ),
                "receipt_digest": trial["receipt_digest"],
            }
            for trial in canary_trials
        ],
        "representative_receipts": [
            {
                "role": "representative",
                "workers": trial["workers"],
                "relative_path": (
                    f"representative/workers{trial['workers']}/receipt.json"
                ),
                "receipt_digest": trial["receipt_digest"],
            }
            for trial in representative_trials
        ],
        "fragility_receipt": {
            "role": "fragility",
            "workers": selected_workers,
            "relative_path": (
                f"fragility/workers{selected_workers}/receipt.json"
            ),
            "receipt_digest": fragility_trial["receipt_digest"],
        },
        "selected_workers": selected_workers,
        "canary_semantic_digest": canary_trials[0]["semantic_digest"],
        "representative_semantic_digest": representative_trials[0][
            "semantic_digest"
        ],
        "fragility_semantic_digest": fragility_trial["semantic_digest"],
        "fragility_invalid_candidate_count": 0,
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    private["receipt_digest"] = _sha(private)
    write("receipt.json", private)
    tracked = {
        "schema_version": "goal029_calibration_index_v2",
        "goal_id": goal029_config["identity"]["goal_id"],
        "status": "pass",
        "thread_policy_digest": context.thread_policy_digest,
        "thread_evidence_digest": context.thread_evidence_digest,
        "spawn_audit_child_count": 4,
        "canary_workers": [1, 2],
        "canary_leaf_count": 2,
        "canary_semantic_digest": canary_trials[0]["semantic_digest"],
        "representative_workers": [1, 2, 4],
        "representative_leaf_count": 30,
        "representative_semantic_digest": representative_trials[0][
            "semantic_digest"
        ],
        "selected_workers": selected_workers,
        "fragility_workers": selected_workers,
        "fragility_leaf_count": 32,
        "fragility_semantic_digest": fragility_trial["semantic_digest"],
        "class_support_strata_count": 56,
        "fragility_invalid_candidate_count": 0,
        "private_receipt_digest": private["receipt_digest"],
        "actual_host_digest": _sha(socket.gethostname()),
        "real_outer_attempted_open_count": 0,
        "real_outer_open_count": 0,
    }
    tracked_path = (
        tmp_path / goal029_config["calibration"]["receipt_destination"] / "receipt.json"
    )
    tracked_path.parent.mkdir(parents=True)
    tracked_path.write_text(canonical_json(tracked) + "\n", encoding="utf-8")

    authority = load_calibration_authority(
        tmp_path, goal029_config, context
    )
    assert authority["private"]["selected_workers"] == 1
    assert [trial["workers"] for trial in authority["trials"]] == [1, 2, 4]
    assert authority["fragility_trial"]["workers"] == 1

    tampered = {
        **tracked,
        "selected_workers": 2,
        "fragility_workers": 2,
    }
    tracked_path.write_text(
        canonical_json(tampered) + "\n", encoding="utf-8"
    )
    with pytest.raises(Goal029Error, match="calibration"):
        load_calibration_authority(tmp_path, goal029_config, context)
