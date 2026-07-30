from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from sklearn.metrics import roc_auc_score

import dsdm_phase1.goal028_preflight as preflight
from dsdm_phase1.modeling_contract import ModelingContractError, canonical_json, load_run_config


REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "config/modeling_foundation_preflight.json"


def _config() -> dict:
    return copy.deepcopy(load_run_config(REPO, CONFIG_PATH))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_manifest(evidence: Path, private: Path, changed: Path) -> None:
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if private in changed.parents:
        rel = f"private/{changed.relative_to(private)}"
    else:
        rel = f"evidence/{changed.relative_to(evidence)}"
    manifest["files"][rel] = {"sha256": _sha_file(changed), "bytes": changed.stat().st_size}
    _write_json(manifest_path, manifest)


def _copy_pair(source_private: Path, source_evidence: Path, target: Path) -> tuple[Path, Path]:
    private, evidence = target / "private", target / "evidence"
    shutil.copytree(source_private, private)
    shutil.copytree(source_evidence, evidence)
    return private, evidence


def _semantic_digest(tasks: list[dict]) -> str:
    payload = [{
        "task_id": row["task_id"], "selected": row["selected"],
        "auc": row["mean_fold_roc_auc"], "tss": row["mean_fold_tss_at_oof_threshold"],
        "threshold": row["threshold"], "oof_score_digest": row["oof_score_digest"],
        "replay_score_digest": row["replay_score_digest"],
    } for row in tasks]
    return preflight._sha(payload)


def _rewrite_dependent_receipts(
    private: Path,
    evidence: Path,
    tasks: list[dict],
    oof: list[dict],
    changed_model: Path | None = None,
) -> None:
    oof_path = private / "oof.parquet"
    tasks_path = private / "tasks.parquet"
    pq.write_table(preflight._table_from_rows(oof, preflight.OOF_SCHEMA), oof_path)
    oof_sha = _sha_file(oof_path)
    for task in tasks:
        task["oof_sha256"] = oof_sha
        task["task_digest"] = preflight._task_digest(task)
    pq.write_table(preflight._table_from_rows(tasks, preflight.TASK_SCHEMA), tasks_path)
    semantic_digest = _semantic_digest(tasks)
    run_path = private / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["semantic_digest"] = semantic_digest
    _write_json(run_path, run)
    summary_path = evidence / "preflight_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["semantic_digest"] = semantic_digest
    _write_json(summary_path, summary)
    for changed in (oof_path, tasks_path, run_path, summary_path):
        _refresh_manifest(evidence, private, changed)
    if changed_model is not None:
        _refresh_manifest(evidence, private, changed_model)


@pytest.fixture(scope="module")
def synthetic_pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("goal028-pair")
    result = preflight._run_synthetic_to_destinations(
        REPO,
        CONFIG_PATH,
        root / "private",
        root / "evidence",
    )
    return root / "private", root / "evidence", result


@pytest.mark.synthetic
def test_frozen_synthetic_and_real_plans_are_exact():
    synthetic = preflight._synthetic_task_plan(
        ("sarcophilus_harrisii", "pseudocheirus_peregrinus")
    )
    assert len(synthetic) == 26
    for species in ("sarcophilus_harrisii", "pseudocheirus_peregrinus"):
        rows = [task for task in synthetic if task.species_id == species]
        assert [task.candidate_id for task in rows[:7]] == ["null00"] * 7
        assert [(task.fraction_id, task.ladder_id) for task in rows[:7]] == [
            ("fraction25", "ladder00"),
            ("fraction25", "ladder01"),
            ("fraction25", "ladder02"),
            ("fraction50", "ladder00"),
            ("fraction50", "ladder01"),
            ("fraction50", "ladder02"),
            ("fraction100", "full"),
        ]
        assert [task.candidate_id for task in rows[7:]] == [
            "enet03", "gam02", "rf03", "hgb03", "ann03", "resmlp01"
        ]
        assert all((task.fraction_id, task.ladder_id) == ("fraction100", "full") for task in rows[7:])

    real = preflight._real_task_plan(_config())
    assert len(real) == 46
    assert sum(task.candidate_id == "null00" for task in real) == 14
    assert sum(task.candidate_id in {"enet03", "enet07"} for task in real) == 8
    assert sum(task.candidate_id in {"resmlp01", "resmlp02"} for task in real) == 8
    assert [task.candidate_id for task in real if task.model_family == "gam"] == ["gam01"] * 4
    assert all(task.seed_label == "seed00" for task in real)


@pytest.mark.synthetic
def test_common_engine_publishes_exact_footprints_and_full_schema(synthetic_pair):
    private, evidence, result = synthetic_pair
    assert {path.name for path in private.iterdir()} == {
        "tasks.parquet", "oof.parquet", "subsets.parquet", "run.json", "models"
    }
    assert {path.name for path in evidence.iterdir()} == {
        "bindings.json", "contract.json", "preflight_summary.json",
        "runtime_summary.json", "review.json", "manifest.json",
    }
    tasks = pq.read_table(private / "tasks.parquet")
    assert tuple(tasks.schema.names) == tuple(preflight.TASK_SCHEMA.names)
    assert tasks.num_rows == 26
    assert len(list((private / "models").glob("*.model"))) == 26
    run = json.loads((private / "run.json").read_text(encoding="utf-8"))
    assert run["fake_vault_authorized"] is True
    assert run["fake_vault_attempted_open_count"] == 1
    assert run["fake_vault_open_count"] == 1
    assert run["real_outer_attempted_open_count"] == 0
    assert run["real_outer_open_count"] == 0
    assert result["candidate_strata"] == 26
    checked = preflight.validate_publication(REPO, evidence, private, "synthetic", True)
    assert checked["status"] == "pass"
    assert checked["outer_attempted_open_count"] == checked["outer_open_count"] == 0


@pytest.mark.synthetic
def test_synthetic_evidence_is_actual_oof_refit_and_trusted_replay(synthetic_pair):
    private, _, _ = synthetic_pair
    tasks = pq.read_table(private / "tasks.parquet").to_pylist()
    oof = pq.read_table(private / "oof.parquet").to_pylist()
    assert {row["record_kind"] for row in oof} == {"oof", "replay"}
    by_task = {row["task_id"]: row for row in tasks}
    for task_id, task in by_task.items():
        model = private / task["model_path"]
        assert _sha_file(model) == task["model_sha256"]
        task_rows = [row for row in oof if row["task_id"] == task_id]
        assert len({row["fold_id"] for row in task_rows if row["record_kind"] == "oof"}) == 5
        assert any(row["record_kind"] == "replay" for row in task_rows)
        assert task["selected"] is True and task["publication_state"] == "staged_validated"


@pytest.mark.synthetic
def test_semantic_rerun_digest_is_deterministic(tmp_path):
    first = preflight._run_synthetic_to_destinations(
        REPO, CONFIG_PATH, tmp_path / "p1", tmp_path / "e1"
    )
    second = preflight._run_synthetic_to_destinations(
        REPO, CONFIG_PATH, tmp_path / "p2", tmp_path / "e2"
    )
    assert first["semantic_digest"] == second["semantic_digest"]


@pytest.mark.tamper
@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("config_digest", "0" * 64),
        ("task_id", "1" * 64),
        ("subset_digest", "2" * 64),
        ("encoder_digest", "3" * 64),
        ("transform_digest", "4" * 64),
        ("feature_schema_digest", "5" * 64),
        ("oof_sha256", "6" * 64),
        ("publication_state", "tampered"),
        ("fake_vault_authorized", False),
        ("best_epochs_by_fold", "[1,1,1,1,0]"),
        ("discovery_initial_state_digest", canonical_json(["7" * 64] * 5)),
    ],
)
def test_coordinated_task_provenance_tamper_is_rejected(
    synthetic_pair, tmp_path, column, replacement
):
    source_private, source_evidence, _ = synthetic_pair
    private, evidence = _copy_pair(source_private, source_evidence, tmp_path)
    table = pq.read_table(private / "tasks.parquet")
    rows = table.to_pylist()
    index = (
        next(i for i, row in enumerate(rows) if row["model_family"] == "shallow_ann")
        if column in {"best_epochs_by_fold", "discovery_initial_state_digest"}
        else 0
    )
    rows[index][column] = replacement
    rows[index]["task_digest"] = preflight._task_digest(rows[index])
    pq.write_table(preflight._table_from_rows(rows, preflight.TASK_SCHEMA), private / "tasks.parquet")
    _refresh_manifest(evidence, private, private / "tasks.parquet")
    with pytest.raises(ModelingContractError):
        preflight.validate_publication(REPO, evidence, private, "synthetic", True)


@pytest.mark.tamper
@pytest.mark.parametrize("kind", ["oof_score", "subset_row", "model_byte", "aggregate", "manifest_bytes"])
def test_data_model_aggregate_and_manifest_tamper_is_rejected(
    synthetic_pair, tmp_path, kind
):
    source_private, source_evidence, _ = synthetic_pair
    private, evidence = _copy_pair(source_private, source_evidence, tmp_path)
    if kind == "oof_score":
        path = private / "oof.parquet"
        rows = pq.read_table(path).to_pylist()
        rows[0]["score"] = min(1.0, rows[0]["score"] + 0.01)
        pq.write_table(preflight._table_from_rows(rows, preflight.OOF_SCHEMA), path)
        _refresh_manifest(evidence, private, path)
    elif kind == "subset_row":
        path = private / "subsets.parquet"
        rows = pq.read_table(path).to_pylist()
        rows[0]["rank"] = 99
        pq.write_table(preflight._table_from_rows(rows, preflight.SUBSET_SCHEMA), path)
        _refresh_manifest(evidence, private, path)
    elif kind == "model_byte":
        task = pq.read_table(private / "tasks.parquet").to_pylist()[0]
        path = private / task["model_path"]
        path.write_bytes(path.read_bytes() + b"x")
        _refresh_manifest(evidence, private, path)
    elif kind == "aggregate":
        path = evidence / "preflight_summary.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["candidate_strata"] += 1
        _write_json(path, value)
        _refresh_manifest(evidence, private, path)
    else:
        path = evidence / "manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        first = next(iter(value["files"].values()))
        first["bytes"] += 1
        _write_json(path, value)
    with pytest.raises(ModelingContractError):
        preflight.validate_publication(REPO, evidence, private, "synthetic", True)


@pytest.mark.tamper
def test_full_validation_rejects_coherent_oof_and_metric_substitution(
    synthetic_pair, tmp_path
):
    """A self-consistent replacement must fail against an independent rerun."""
    source_private, source_evidence, _ = synthetic_pair
    private, evidence = _copy_pair(source_private, source_evidence, tmp_path)
    tasks = pq.read_table(private / "tasks.parquet").to_pylist()
    oof = pq.read_table(private / "oof.parquet").to_pylist()
    task = tasks[0]
    task_rows = [
        row for row in oof
        if row["task_id"] == task["task_id"] and row["record_kind"] == "oof"
    ]
    for row in task_rows:
        row["score"] = 1.0 - row["score"]
        row["mean_score"] = row["score"]
    from dsdm_phase1.inner_cv import _tss, select_threshold
    all_y = np.asarray([row["y_true"] for row in task_rows], dtype=np.int8)
    all_score = np.asarray([row["score"] for row in task_rows], dtype=np.float64)
    threshold = select_threshold(all_y, [all_score]).threshold
    fold_auc, fold_tss = [], []
    for fold_id in preflight.FOLDS:
        fold_rows = [row for row in task_rows if row["fold_id"] == fold_id]
        y = np.asarray([row["y_true"] for row in fold_rows], dtype=np.int8)
        score = np.asarray([row["score"] for row in fold_rows], dtype=np.float64)
        auc = float(roc_auc_score(y, score))
        tss = _tss(y, score, threshold)
        fold_auc.append(auc)
        fold_tss.append(tss)
        for row in fold_rows:
            row["fold_roc_auc"] = auc
            row["fold_tss"] = tss
            row["threshold"] = threshold
    for row in oof:
        if row["task_id"] == task["task_id"]:
            row["threshold"] = threshold
    task["threshold"] = threshold
    task["mean_fold_roc_auc"] = float(np.mean(fold_auc))
    task["mean_fold_tss_at_oof_threshold"] = float(np.mean(fold_tss))
    task["oof_score_digest"] = preflight._sha([row["score"] for row in task_rows])
    _rewrite_dependent_receipts(private, evidence, tasks, oof)

    assert preflight.validate_publication(
        REPO, evidence, private, "synthetic", False
    )["status"] == "pass"
    with pytest.raises(ModelingContractError, match="independent_semantic_replay_mismatch"):
        preflight.validate_publication(REPO, evidence, private, "synthetic", True)


@pytest.mark.tamper
def test_full_validation_rejects_coherent_selected_model_and_replay_substitution(
    synthetic_pair, tmp_path
):
    """A substituted fitted model and all matching receipts need an external oracle."""
    source_private, source_evidence, _ = synthetic_pair
    private, evidence = _copy_pair(source_private, source_evidence, tmp_path)
    tasks = pq.read_table(private / "tasks.parquet").to_pylist()
    oof = pq.read_table(private / "oof.parquet").to_pylist()
    task = tasks[0]
    rows, values, folds, vault, fake_provider = preflight._synthetic_fixture()
    from dsdm_phase1.modeling_contract import TaskKey, ingest_synthetic_foundation
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, build_adapter

    broker, provider, _ = ingest_synthetic_foundation(rows, values, folds)
    outer = broker.outer_training(task["species_id"])
    endpoint = preflight._endpoint_lookup(
        outer, task["fraction_id"], task["ladder_id"]
    )
    endpoint_rows = preflight._rowset_for_keys(outer, endpoint.keys)
    encoder = provider.fit_encoder(endpoint_rows, task["model_family"], "outer")
    batch = provider.materialize(endpoint_rows, "outer", encoder)
    altered_batch = replace(batch, y=1.0 - batch.y)
    task_key = TaskKey(
        task["species_id"], task["transform_id"], task["fraction_id"],
        task["ladder_id"], task["model_family"], task["candidate_id"],
        task["seed_label"],
    )
    fitted, _ = build_adapter(task["model_family"]).fit(
        altered_batch, None, CANONICAL_CANDIDATES[task["candidate_id"]],
        preflight.derive_seed(task_key, "fit"),
    )
    model_path = private / task["model_path"]
    fitted.serialize(model_path)
    task["model_sha256"] = _sha_file(model_path)
    scores = fitted.predict_scores(batch)
    replay_rows = [
        row for row in oof
        if row["task_id"] == task["task_id"] and row["record_kind"] == "replay"
    ]
    assert len(replay_rows) == len(scores)
    for row, score in zip(replay_rows, scores):
        row["score"] = float(score)
        row["mean_score"] = float(score)
    task["replay_score_digest"] = preflight._sha(scores.tolist())

    held = vault.open({"synthetic": True})
    held_species = preflight._rowset_for_keys(
        held, [key for key in held.keys if key.species_id == task["species_id"]]
    )
    fake_batch = fake_provider.materialize(held_species, "outer", encoder)
    fake_digest = preflight._sha(fitted.predict_scores(fake_batch).tolist())
    run_path = private / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    receipt = next(
        row for row in run["fake_vault_score_receipts"]
        if row["task_id"] == task["task_id"]
    )
    receipt["score_digest"] = fake_digest
    _write_json(run_path, run)
    _rewrite_dependent_receipts(private, evidence, tasks, oof, model_path)

    assert preflight.validate_publication(
        REPO, evidence, private, "synthetic", False
    )["status"] == "pass"
    with pytest.raises(ModelingContractError, match="independent_semantic_replay_mismatch"):
        preflight.validate_publication(REPO, evidence, private, "synthetic", True)


@pytest.mark.tamper
def test_privacy_walker_rejects_forbidden_key_token_and_absolute_path(synthetic_pair, tmp_path):
    source_private, source_evidence, _ = synthetic_pair
    for mutation in ({"grid_cell_id": "x"}, {"safe": "/tmp/private/source.csv"}):
        target = tmp_path / hashlib.sha256(canonical_json(mutation).encode()).hexdigest()[:8]
        private, evidence = _copy_pair(source_private, source_evidence, target)
        path = evidence / "review.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["mutation"] = mutation
        _write_json(path, value)
        _refresh_manifest(evidence, private, path)
        with pytest.raises(ModelingContractError, match="tracked_"):
            preflight.validate_publication(REPO, evidence, private, "synthetic", True)


@pytest.mark.real_scope
@pytest.mark.budget
@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["scope"].update(real_species=list(reversed(c["scope"]["real_species"]))),
        lambda c: c["scope"].update(real_species=c["scope"]["real_species"] + ["extra"]),
        lambda c: c["scope"].update(permitted_endpoints=c["scope"]["permitted_endpoints"] + ["fraction100/ladder00"]),
        lambda c: c["models"].update(real_preflight_ids=c["models"]["real_preflight_ids"] + ["enet00"]),
        lambda c: c["models"]["real_preflight_ids"].__setitem__(3, "gam02"),
        lambda c: c["replication"].update(real_preflight_labels=["seed00", "seed02"]),
        lambda c: c["compute"].update(process_workers=3),
        lambda c: c["compute"].update(platform="deep-server"),
        lambda c: c["compute"].update(task_wall_budget_seconds=1201),
        lambda c: c["compute"].update(peak_rss_budget_bytes=12 * 1024**3 + 1),
        lambda c: c["compute"].update(estimator_threads=2),
    ],
)
def test_real_scope_mutations_fail_before_factory_or_fit(monkeypatch, tmp_path, mutate):
    config = _config()
    mutate(config)
    monkeypatch.setattr(preflight, "load_run_config", lambda *args: config)
    called = {"factory": 0, "fit": 0}

    def factory(*args):
        called["factory"] += 1
        raise AssertionError("factory must not run")

    monkeypatch.setattr(preflight, "ingest_private_foundation", factory)
    monkeypatch.setattr(
        preflight, "run_candidate_oof",
        lambda *args: called.__setitem__("fit", called["fit"] + 1),
    )
    with pytest.raises(ModelingContractError):
        preflight.run_real_preflight(tmp_path, Path("config.json"))
    assert called == {"factory": 0, "fit": 0}


@pytest.mark.budget
@pytest.mark.parametrize(
    ("elapsed", "rss", "message"),
    [(1200.01, 1, "task_wall_budget_overrun"), (1.0, 12 * 1024**3 + 1, "task_rss_budget_overrun")],
)
def test_per_task_runtime_and_rss_overruns_are_hard_failures(elapsed, rss, message):
    with pytest.raises(ModelingContractError, match=message):
        preflight._enforce_task_budget(elapsed, rss, _config())


@pytest.mark.real_scope
def test_real_runner_uses_factory_authority_exact_plan_selection_and_publication(
    monkeypatch, tmp_path
):
    rows, values, folds, vault, _ = preflight._synthetic_fixture()
    from dsdm_phase1.modeling_contract import FeatureProvider, MappingFeatureSubstrate, RowKey, RowSet, SplitBroker

    outer = RowSet.from_records(rows)
    broker = SplitBroker(outer, folds)
    provider = FeatureProvider(MappingFeatureSubstrate(values), frozenset(outer.keys))
    config = _config()
    monkeypatch.setattr(preflight, "load_run_config", lambda *args: config)
    monkeypatch.setattr(preflight, "ingest_private_foundation", lambda *args: (broker, provider, vault))
    monkeypatch.setattr(
        preflight,
        "_publication_destinations",
        lambda root, cfg, synthetic: (tmp_path / "private", tmp_path / "evidence"),
    )
    seen = {"plans": None}

    def fake_engine(**kwargs):
        seen["plans"] = kwargs["task_plan"]
        assert kwargs["vault"] is vault
        return {
            "mode": "real-preflight", "synthetic": False, "status": "pass",
            "candidate_strata": 46, "outer_attempted_open_count": 0,
            "outer_open_count": 0, "semantic_digest": "a" * 64,
        }

    monkeypatch.setattr(preflight, "run_preflight_engine", fake_engine)
    result = preflight.run_real_preflight(tmp_path, Path("config.json"))
    assert len(seen["plans"]) == 46
    assert result["factory_validated_complete_counts"] == config["scope"]["included_row_counts"]
    assert set(result["observed_outer_training_counts"]) == set(config["scope"]["real_species"])
    assert vault.attempted_open_count == vault.open_count == 0


@pytest.mark.tamper
@pytest.mark.parametrize("fail_at", [1, 2])
def test_publication_rolls_back_either_rename(monkeypatch, tmp_path, fail_at):
    private_stage, evidence_stage = tmp_path / "sp", tmp_path / "se"
    private_stage.mkdir()
    evidence_stage.mkdir()
    (private_stage / "x").write_text("x", encoding="utf-8")
    (evidence_stage / "y").write_text("y", encoding="utf-8")
    private_dest, evidence_dest = tmp_path / "p", tmp_path / "e"
    original = preflight.os.rename
    calls = {"n": 0}

    def fail(src, dst):
        calls["n"] += 1
        if calls["n"] == fail_at:
            raise OSError("injected")
        return original(src, dst)

    monkeypatch.setattr(preflight.os, "rename", fail)
    with pytest.raises(ModelingContractError, match="publication_rollback"):
        preflight.publish_staged_pair(private_stage, evidence_stage, private_dest, evidence_dest)
    assert not private_dest.exists() and not evidence_dest.exists()


@pytest.mark.tamper
@pytest.mark.parametrize("kind", ["existing", "symlink"])
def test_publication_refuses_existing_or_symlink_destination(tmp_path, kind):
    private_stage, evidence_stage = tmp_path / "sp", tmp_path / "se"
    private_stage.mkdir()
    evidence_stage.mkdir()
    private_dest, evidence_dest = tmp_path / "p", tmp_path / "e"
    if kind == "existing":
        private_dest.mkdir()
    else:
        private_dest.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(ModelingContractError, match="publication_destination_exists"):
        preflight.publish_staged_pair(private_stage, evidence_stage, private_dest, evidence_dest)


@pytest.mark.synthetic
def test_actual_cli_synthetic_and_full_validation(tmp_path):
    private, evidence = preflight._publication_destinations(REPO, _config(), True)
    if private.exists() or evidence.exists():
        pytest.skip("canonical synthetic destination already exists")
    try:
        run = subprocess.run(
            [sys.executable, "-m", "dsdm_phase1.goal028_preflight", "--root", str(REPO), "--mode", "synthetic"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        assert result["candidate_strata"] == 26
        validate = subprocess.run(
            [sys.executable, "-m", "dsdm_phase1.goal028_preflight", "--root", str(REPO), "--validate", "--synthetic", "--full"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        assert validate.returncode == 0, validate.stderr
        assert json.loads(validate.stdout)["status"] == "pass"
    finally:
        for path in (private, evidence):
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
