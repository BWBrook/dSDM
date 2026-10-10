from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tasmania_pseudoabsence_conventional",
    ROOT / "scripts/tasmania_pseudoabsence_conventional.py",
)
assert SPEC and SPEC.loader
conventional = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = conventional
SPEC.loader.exec_module(conventional)


def _synthetic_rows(contract, sources: tuple[str, ...]):
    records = []
    for index, source in enumerate(sources):
        records.append({
            "species_id": "synthetic_species",
            "grid_cell_id": f"cell_{index:02d}",
            "pa": 1 if source == "presence" else 0,
            "pa_type": source,
            "microcluster": f"mc{index % 2:02d}",
        })
    return contract.RowSet.from_records(records)


def _synthetic_provider(contract, rows):
    values = {}
    for index, key in enumerate(rows.keys):
        values[key] = {
            "continuous": [float(index), float(index % 3)],
            "categorical": {"habitat": "a" if index % 2 == 0 else "b"},
        }
    return contract.FeatureProvider(contract.MappingFeatureSubstrate(values), frozenset(rows.keys))


def test_frozen_selection_and_fit_inventory_are_exact():
    strata = conventional._selection_inventory(ROOT)
    inner, outer, counts = conventional.build_task_inventory(strata)

    assert len(strata) == 56
    assert len(inner) == 1200
    assert len(outer) == 240
    assert counts == {
        "strata": 56,
        "inner_logical_tasks": 1200,
        "inner_physical_fits": 1725,
        "outer_logical_tasks": 240,
        "outer_physical_fits": 240,
        "production_physical_fits": 1965,
        "smoke_logical_tasks": 4,
        "smoke_physical_fits": 6,
    }
    assert sum(item.family == "random_forest" for item in strata) == 24
    assert sum(item.family == "hist_gradient_boosting" for item in strata) == 10
    assert sum(item.family == "shallow_ann" for item in strata) == 21
    assert sum(item.family == "elastic_net" for item in strata) == 1


def test_filter_is_exact_and_class_loss_fails_closed():
    modules = conventional._load_archived_modules(ROOT)
    census = conventional._load_census(ROOT)
    rows = _synthetic_rows(
        modules["modeling_contract"],
        ("presence", "survey_supported_absence", "pseudoabsence", "presence"),
    )

    retained = conventional.filter_without_pseudoabsence(rows, census)
    assert set(retained.response_source) == {"presence", "survey_supported_absence"}
    assert {key.grid_cell_id for key in retained.keys} == {"cell_00", "cell_01", "cell_03"}

    failed = _synthetic_rows(modules["modeling_contract"], ("presence", "pseudoabsence"))
    with pytest.raises(census.CensusError, match="missing_class_after_pseudoabsence_removal"):
        conventional.filter_without_pseudoabsence(failed, census)


def test_task_seed_is_the_original_taskkey_fit_namespace():
    modules = conventional._load_archived_modules(ROOT)
    contract = modules["modeling_contract"]
    task = contract.TaskKey(
        "dasyurus_viverrinus", "cv_fold01", "fraction100", "full",
        "random_forest", "rf00", "seed00",
    )
    fields = [
        "dsdm-goal028-v1", task.species_id, task.transform_id,
        task.fraction_id, task.ladder_id, task.model_family,
        task.candidate_id, task.seed_label, "fit",
    ]
    expected = int.from_bytes(
        hashlib.sha256("\x1f".join(fields).encode("utf-8")).digest()[:4],
        "big", signed=False,
    )

    assert contract.derive_seed(task, "fit") == expected


def test_replay_encoder_is_reused_and_prediction_labels_are_dummy():
    modules = conventional._load_archived_modules(ROOT)
    contract = modules["modeling_contract"]
    replay = _synthetic_rows(
        contract,
        ("presence", "survey_supported_absence", "presence", "survey_supported_absence"),
    )
    provider = _synthetic_provider(contract, replay)
    encoder = provider.fit_encoder(replay, "shallow_ann", "outer")
    discovery = replay.take([0, 1])
    stopping = replay.take([2, 3])
    dummy = contract.RowSet.from_records([
        {
            "species_id": key.species_id,
            "grid_cell_id": key.grid_cell_id,
            "pa": 0,
            "pa_type": "survey_supported_absence",
            "microcluster": "prediction_only",
        }
        for key in replay.keys
    ])

    batches = [
        provider.materialize(rows, "outer", encoder)
        for rows in (discovery, stopping, replay, dummy)
    ]
    assert {batch.encoder_digest for batch in batches} == {encoder["encoder_digest"]}
    assert {batch.feature_schema_digest for batch in batches} == {encoder["feature_schema_digest"]}
    assert np.all(batches[-1].y == 0)


def test_ann_exact_replay_resets_the_same_initial_state(tmp_path: Path):
    modules = conventional._load_archived_modules(ROOT)
    contract = modules["modeling_contract"]
    adapters = modules["model_adapters"]
    rows = _synthetic_rows(
        contract,
        (
            "presence", "survey_supported_absence", "presence", "survey_supported_absence",
            "presence", "survey_supported_absence", "presence", "survey_supported_absence",
        ),
    )
    provider = _synthetic_provider(contract, rows)
    encoder = provider.fit_encoder(rows, "shallow_ann", "outer")
    discovery = provider.materialize(rows.take([0, 1, 2, 3, 4, 5]), "outer", encoder)
    stopping = provider.materialize(rows.take([6, 7]), "outer", encoder)
    replay = provider.materialize(rows, "outer", encoder)
    candidate = dict(adapters.CANONICAL_CANDIDATES["ann00"])
    adapter = adapters.build_adapter("shallow_ann")

    _, discovery_report = adapter.fit(discovery, stopping, candidate, 12345)
    assert discovery_report.best_epoch is not None
    replay_model, replay_report = adapter.fit(
        replay, None, candidate, 12345,
        exact_epochs=int(discovery_report.best_epoch),
    )
    assert replay_report.initial_state_digest == discovery_report.initial_state_digest
    assert replay_report.iterations == discovery_report.best_epoch
    model_path = tmp_path / "model.model"
    replay_model.serialize(model_path)
    scores = replay_model.predict_scores(replay)
    loaded, semantic_digest = conventional._reload_and_verify_model(
        type("Foundation", (), {"adapters": adapters})(),
        model_path,
        replay_model,
        replay,
        scores,
    )
    assert loaded.predict_scores(replay).tolist() == scores.tolist()
    assert semantic_digest == conventional._semantic_model_digest(replay_model, conventional.sha256_file(model_path))


def test_production_gate_requires_smoke_qualification(tmp_path: Path):
    preparation = {"receipt_digest": "a" * 64}
    with pytest.raises(conventional.ConventionalSensitivityError, match="invalid_json:smoke-qualification.json"):
        conventional._load_smoke(ROOT, tmp_path, preparation)


def test_production_caps_bind_smoke_recovery_and_four_workers(tmp_path: Path):
    preparation = {"receipt_digest": "a" * 64}
    smoke = {
        "receipt_digest": "b" * 64,
        "observed": {
            "maximum_fit_runtime_seconds": 2.0,
            "maximum_reported_peak_rss_bytes": 100,
            "private_bytes": 200,
        },
    }
    cap = {
        "schema_version": "tasmania-pseudoabsence-conventional-production-caps-v1",
        "status": "assigned",
        "enforcement": "external_parent_launcher_with_atomic_global_abort",
        "preparation_receipt_digest": preparation["receipt_digest"],
        "smoke_receipt_digest": smoke["receipt_digest"],
        "auxiliary_recovery_sha256": conventional.RECOVERY_RECEIPT_SHA256,
        "runtime_versions": dict(conventional.EXPECTED_RUNTIME),
        "caps": {
            "max_workers": 4,
            "threads_per_worker": 1,
            "wall_time_seconds": 10,
            "peak_rss_bytes": 1000,
            "private_storage_bytes": 2000,
        },
    }
    cap["receipt_digest"] = conventional.digest_value(cap)
    (tmp_path / "production-caps.json").write_bytes(conventional._canonical(cap) + b"\n")

    assert conventional._load_production_caps(ROOT, tmp_path, preparation, smoke)["receipt_digest"] == cap["receipt_digest"]


def test_incomplete_prediction_inventory_cannot_close(tmp_path: Path):
    strata = conventional._selection_inventory(ROOT)
    inner, _, counts = conventional.build_task_inventory(strata)
    assert conventional._close_lane(
        ROOT, tmp_path, "inner", inner, counts["inner_physical_fits"], "a" * 64,
    ) is None


def test_recovery_and_accepted_primary_authorities_are_pinned():
    recovery = conventional._load_recovery_closure(ROOT)
    selections, references = conventional._accepted_selection_index(ROOT)

    assert recovery["states"] == recovery["fits"] == 200
    assert len(selections) == 280
    assert len(references) == 952


def test_fit_intent_is_immutable_and_prevents_silent_retry(tmp_path: Path):
    strata = conventional._selection_inventory(ROOT)
    task = conventional._smoke_tasks(strata)[0]
    destination = tmp_path / "inner/leaves" / conventional._task_digest(task, "inner")
    preparation = {"schema_version": "test", "success": True}
    preparation["receipt_digest"] = conventional.digest_value(preparation)
    (tmp_path / "preparation.json").write_bytes(conventional._canonical(preparation) + b"\n")

    attempt, work = conventional._begin_fit_attempt(
        ROOT, tmp_path, "inner", task, destination, ("replay",),
    )
    assert work.is_dir()
    assert (tmp_path / "inner/intents" / f"{destination.name}.json").is_file()
    with pytest.raises(conventional.ConventionalSensitivityError, match="orphan_or_failed_fit_intent"):
        conventional._begin_fit_attempt(
            ROOT, tmp_path, "inner", task, destination, ("replay",),
        )
    assert attempt.is_dir()


def test_sharding_is_capped_at_four_workers():
    with pytest.raises(conventional.ConventionalSensitivityError, match="shard_count_invalid"):
        conventional._shard((1, 2, 3), 0, 5)


def test_ann_semantic_digest_uses_tensor_content_not_pickle_identity():
    import torch

    class Model:
        def __init__(self, value):
            self.value = value

        def state_dict(self):
            return {"layer.weight": self.value}

    class Fitted:
        family = "shallow_ann"
        candidate_digest = "candidate"
        seed = 123
        schema = {"feature_names": ["x"]}

        def __init__(self, value):
            self.model = Model(value)

    first = Fitted(torch.tensor([[1.0, 2.0]], dtype=torch.float32))
    equal = Fitted(torch.tensor([[1.0, 2.0]], dtype=torch.float32))
    changed = Fitted(torch.tensor([[1.0, 3.0]], dtype=torch.float32))

    assert conventional._semantic_model_digest(first, "a" * 64) == conventional._semantic_model_digest(equal, "b" * 64)
    assert conventional._semantic_model_digest(first, "a" * 64) != conventional._semantic_model_digest(changed, "a" * 64)


def test_closure_attempt_inventory_matches_physical_fit_starts(tmp_path: Path):
    tasks = conventional._smoke_tasks(conventional._selection_inventory(ROOT))
    preparation = {"schema_version": "test", "success": True}
    preparation["receipt_digest"] = conventional.digest_value(preparation)
    (tmp_path / "preparation.json").write_bytes(conventional._canonical(preparation) + b"\n")
    receipts = {}
    for task in tasks:
        key = conventional._task_digest(task, "inner")
        stages = ("discovery", "replay") if task.family == "shallow_ann" else ("replay",)
        receipt = {"receipt_digest": conventional.digest_value({"task": key})}
        receipts[key] = receipt
        intent = {
            "schema_version": "tasmania-pseudoabsence-conventional-fit-intent-v1",
            "lane": "inner",
            "task": conventional.asdict(task),
            "task_digest": key,
            "destination": f"inner/leaves/{key}",
            "physical_stages": list(stages),
            "fit_started": False,
            "created_unix_ns": 1,
            "bindings": conventional._leaf_bindings(ROOT),
            "preparation_receipt_digest": preparation["receipt_digest"],
        }
        intent["intent_digest"] = conventional.digest_value(intent)
        intent_path = tmp_path / "inner/intents" / f"{key}.json"
        intent_path.parent.mkdir(parents=True, exist_ok=True)
        intent_path.write_bytes(conventional._canonical(intent) + b"\n")
        attempt = tmp_path / "inner/attempts" / key
        (attempt / "fit-starts").mkdir(parents=True)
        for number, stage in enumerate(stages, start=1):
            start = {
                "schema_version": "tasmania-pseudoabsence-conventional-fit-start-v1",
                "task": conventional.asdict(task),
                "stage": stage,
                "physical_fit_number": number,
                "started_unix_ns": number,
            }
            (attempt / "fit-starts" / f"{number:02d}-{stage}.json").write_bytes(
                conventional._canonical(start) + b"\n"
            )
        completed = {
            "schema_version": "tasmania-pseudoabsence-conventional-fit-complete-v1",
            "task_digest": key,
            "receipt_digest": receipt["receipt_digest"],
            "completed_unix_ns": 3,
        }
        (attempt / "completed.json").write_bytes(conventional._canonical(completed) + b"\n")

    inventory = conventional._validate_fit_attempt_inventory(
        ROOT, tmp_path, "inner", tasks, receipts, 3,
    )
    assert inventory["logical_intents"] == 2
    assert inventory["physical_fit_starts"] == 3
    first_key = conventional._task_digest(tasks[0], "inner")
    completion_path = tmp_path / "inner/attempts" / first_key / "completed.json"
    completion_bytes = completion_path.read_bytes()
    completion_path.unlink()
    assert conventional._validate_fit_attempt_inventory(
        ROOT, tmp_path, "inner", tasks, receipts, 3,
    ) is None
    completion_path.write_bytes(completion_bytes)
    (tmp_path / "inner/attempts/excess").mkdir()
    with pytest.raises(conventional.ConventionalSensitivityError, match="fit_attempt_inventory_mismatch"):
        conventional._validate_fit_attempt_inventory(ROOT, tmp_path, "inner", tasks, receipts, 3)


def test_runner_has_no_generic_endpoint_or_held_response_ingestion_path():
    source = (ROOT / "scripts/tasmania_pseudoabsence_conventional.py").read_text(encoding="utf-8")
    assert "ingest_production_foundation" not in source
    assert "run_candidate_oof" not in source
    assert "refit_outer_training" not in source
    assert "_read_allowlisted_response_rows" in source


@pytest.mark.skipif(
    not (ROOT / conventional.INNER_BUNDLE_REL).is_dir(),
    reason="private accepted bundles unavailable",
)
def test_real_foundation_matches_all_accepted_census_contracts():
    foundation = conventional.Foundation(ROOT)
    assert foundation.census_report["success"] is True
    assert len(foundation.role_index) == 896
    assert len(foundation.outer.keys) == 11039
    assert len(foundation.map_cells) == 71023

    strata = conventional._selection_inventory(ROOT)
    first = strata[0]
    inner = conventional.InnerTask(
        first.species, first.endpoint, first.family, first.candidate,
        "fold00", first.seeds[0],
    )
    outer = conventional.OuterTask(
        first.species, first.endpoint, first.family, first.candidate,
        first.seeds[0],
    )
    inner_context = conventional._inner_context(foundation, inner)
    outer_context = conventional._outer_context(foundation, outer)
    assert "pseudoabsence" not in inner_context["discovery"].response_source
    assert "pseudoabsence" not in inner_context["stopping"].response_source
    assert "pseudoabsence" not in inner_context["replay"].response_source
    assert "pseudoabsence" not in outer_context["retained"].response_source
    assert np.all(inner_context["evaluation"].pa == 0)
    assert np.all(outer_context["evaluation"].pa == 0)
