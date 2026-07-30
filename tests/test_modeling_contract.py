from __future__ import annotations

import hashlib
import json
import csv
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).parents[1]


def _rows():
    return [
        {"species_id": "sp", "grid_cell_id": "b", "pa": 0, "pa_type": "pseudoabsence", "microcluster": "mc1", "cv_fold": "fold01"},
        {"species_id": "sp", "grid_cell_id": "a", "pa": 1, "pa_type": "presence", "microcluster": "mc0", "cv_fold": "fold00"},
        {"species_id": "sp", "grid_cell_id": "c", "pa": 0, "pa_type": "survey_supported_absence", "microcluster": "mc1", "cv_fold": "fold02"},
        {"species_id": "sp", "grid_cell_id": "d", "pa": 1, "pa_type": "presence", "microcluster": "mc0", "cv_fold": "fold03"},
    ]


def _scope_fixture(monkeypatch, tmp_path, response_records, scope):
    """Install compact private readers so scope checks run before partitioning."""
    import dsdm_phase1.modeling_contract as contract

    continuous = [f"c{i}" for i in range(25)]
    categorical = ["soil_class", "veg_mvg", "landuse_secondary"]
    map_records = []
    for row in response_records:
        if row.get("outer_role") == "outer_train":
            map_records.append({"grid_cell_id": row["grid_cell_id"], "predictor_complete": "true", **{name: 1 for name in continuous}, **{name: "1" for name in categorical}})
    fit = {"fits": {"outer": {"means": {name: 1.0 for name in continuous}, "population_sd": {name: 1.0 for name in continuous}, "category_levels": {name: ["1"] for name in categorical}}}}
    feature_contract = {"continuous_predictors": continuous, "categorical_predictors": categorical}
    def read_private(_root, record):
        return response_records if record["kind"] == "response" else map_records
    def read_bound(_root, record):
        return fit if record["kind"] == "fit" else feature_contract
    monkeypatch.setattr(contract, "_read_private_records", read_private)
    monkeypatch.setattr(contract, "_read_bound_json", read_bound)
    config = {"bindings": {"goal025_response_partitioned": {"kind": "response"}, "goal024_map": {"kind": "map"}, "goal026_fit_parameters": {"kind": "fit"}, "goal026_feature_contract": {"kind": "contract"}}, "scope": scope}
    return contract.ingest_private_foundation(tmp_path, config)


def test_environment_and_raw_config():
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.13"
    deps = {d.split("[", 1)[0].split("=", 1)[0].split(">", 1)[0].split("<", 1)[0] for d in pyproject["project"]["dependencies"]}
    assert {"numpy", "scipy", "scikit-learn", "pygam", "pyarrow", "torch"} <= deps
    assert "pytest" in {d.split("=", 1)[0].split(">", 1)[0].split("<", 1)[0] for d in pyproject["dependency-groups"]["dev"]}
    config = json.loads((ROOT / "config" / "modeling_foundation_preflight.json").read_text())
    assert list(config) == ["identity", "bindings", "estimand", "response", "partitions", "subsets", "features", "models", "neural", "selection", "threshold", "replication", "artifacts", "compute", "scope"]
    assert config["identity"]["master_seed"] == "dsdm-goal028-v1"
    assert config["scope"]["real_outer_attempted_open_limit"] == 0
    assert config["scope"]["real_outer_open_limit"] == 0
    assert set(config["bindings"]["required_roles"]) <= set(config["bindings"])
    assert len(config["models"]["candidate_parameters"]) == len(config["models"]["candidates"]) == 39
    assert config["neural"]["batch_size"] == 128
    assert config["neural"]["optimizer"]["amsgrad"] is False
    assert config["models"]["gam_defaults"]["spline_order"] == 3


def test_config_mutations_fail_closed(tmp_path):
    from dsdm_phase1.modeling_contract import ModelingContractError, load_run_config

    config_path = ROOT / "config" / "modeling_foundation_preflight.json"
    config = json.loads(config_path.read_text())
    config["models"]["candidates"][0]["id"] = "drift"
    mutated = tmp_path / "config.json"
    mutated.write_text(json.dumps(config))
    with pytest.raises(ModelingContractError):
        load_run_config(ROOT, mutated)
    config = json.loads(config_path.read_text())
    config["models"]["candidates"][-1]["width"] = 999
    mutated.write_text(json.dumps(config))
    with pytest.raises(ModelingContractError):
        load_run_config(ROOT, mutated)
    config = json.loads(config_path.read_text())
    config["bindings"]["pyproject"]["sha256"] = "not-a-sha"
    mutated.write_text(json.dumps(config))
    with pytest.raises(ModelingContractError):
        load_run_config(ROOT, mutated)


def test_contract_seed_and_task_id():
    from dsdm_phase1.modeling_contract import TaskKey, derive_seed, task_id

    task = TaskKey("sp", "cv_fold00", "fraction25", "ladder00", "intercept", "null00", "seed00")
    fields = ["dsdm-goal028-v1", task.species_id, task.transform_id, task.fraction_id, task.ladder_id, task.model_family, task.candidate_id, task.seed_label, "fit"]
    expected = int.from_bytes(hashlib.sha256("\x1f".join(fields).encode()).digest()[:4], "big")
    assert derive_seed(task, "fit") == expected
    assert task_id(task) == task_id(task)


def test_rowset_and_sealed_vault():
    from dsdm_phase1.modeling_contract import ModelingContractError, OuterVault, RowSet, RowKey

    rows = _rows()
    rowset = RowSet.from_records(rows)
    assert rowset.keys == tuple(sorted(rowset.keys))
    assert rowset.pa.flags.writeable is False
    with pytest.raises(ModelingContractError):
        RowSet.from_records([{**rows[0], "pa": 0, "pa_type": "unknown"}])
    for bad in (256, 257, 1.9, "1", True):
        with pytest.raises(ModelingContractError):
            RowSet.from_records([{**rows[0], "pa": bad}])
    for bad_key in ("", 1, None):
        with pytest.raises(ModelingContractError):
            RowSet.from_records([{**rows[0], "species_id": bad_key}])
    for field, bad in (("pa_type", 1), ("microcluster", 1)):
        with pytest.raises(ModelingContractError):
            RowSet.from_records([{**rows[0], field: bad}])
    vault = OuterVault.synthetic(rows)
    with pytest.raises(ModelingContractError):
        vault.open()
    assert vault.attempted_open_count == 1 and vault.open_count == 0
    assert vault.open({"synthetic": True}).keys


def test_split_and_feature_provider_leakage():
    from dsdm_phase1.modeling_contract import FeatureProvider, LazyFeatureSubstrate, ModelingContractError, RowKey, SplitBroker, RowSet

    rows = _rows()
    rowset = RowSet.from_records(rows)
    broker = SplitBroker(rowset, {key: ("fold00" if i < 2 else "fold01") for i, key in enumerate(rowset.keys)})
    train, validation = broker.inner("sp", "fold00")
    assert set(train.keys).isdisjoint(validation.keys)
    features = {key: {"continuous": [float(i)], "categorical": {"cat": "seen" if i < 2 else "unseen"}} for i, key in enumerate(rowset.keys)}
    provider = FeatureProvider(LazyFeatureSubstrate(features), frozenset(rowset.keys))
    state = provider.fit_encoder(train, "intercept", "cv_fold00")
    batch = provider.materialize(validation, "cv_fold00", state)
    assert batch.unseen_level_counts["cat"] >= 0
    tampered = dict(state); tampered["family"] = "other"
    with pytest.raises(ModelingContractError):
        provider.materialize(validation, "cv_fold00", tampered)
    with pytest.raises(ModelingContractError):
        provider.materialize(RowSet.from_records([{**rows[0], "grid_cell_id": "x"}]), "cv_fold00", state)
    with pytest.raises(ModelingContractError):
        SplitBroker(rowset, {key: "cv_fold00" for key in rowset.keys})
    with pytest.raises(ModelingContractError):
        broker.inner("sp", "cv_fold00")


def test_private_factory_rejects_public_combined_rows_and_explicit_synthetic_factory():
    from dsdm_phase1.modeling_contract import ModelingContractError, OuterVault, RowKey, ingest_private_foundation, ingest_synthetic_foundation

    rows = _rows()
    with pytest.raises(ModelingContractError, match="combined_response"):
        ingest_private_foundation(ROOT, {"_synthetic_rows": rows})
    with pytest.raises(ModelingContractError, match="combined_response"):
        ingest_private_foundation(ROOT, {"private_inputs": {}})
    keys = [RowKey(row["species_id"], row["grid_cell_id"]) for row in rows]
    features = {key: {"continuous": [1.0], "categorical": {}} for key in keys}
    folds = {key: ("fold00" if i < 2 else "fold01") for i, key in enumerate(sorted(keys))}
    broker, provider, vault = ingest_synthetic_foundation(rows, features, folds)
    assert set(broker.outer_training("sp").keys) == set(provider.allowed_keys)
    with pytest.raises(ModelingContractError):
        vault.open()
    assert vault.open({"synthetic": True}).keys
    empty_vault = OuterVault(None, synthetic=False)
    with pytest.raises(ModelingContractError):
        empty_vault.open()
    assert empty_vault.attempted_open_count == 1 and empty_vault.open_count == 0


def test_feature_batch_schema_is_mandatory_and_ordered():
    from dsdm_phase1.modeling_contract import FeatureBatch, ModelingContractError, RowKey, canonical_json

    keys = (RowKey("sp", "a"),)
    x = np.ones((1, 2)); y = np.ones(1)
    names = ("x", "cat__a"); kinds = ("continuous", "categorical")
    digest = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": 1}).encode()).hexdigest()
    batch = FeatureBatch(keys, x, y, names, kinds, 1, digest, {}, "outer", "0" * 64, "0" * 64)
    assert batch.feature_names == names
    with pytest.raises(ModelingContractError):
        FeatureBatch(keys, x, y, names, ("continuous", "continuous"), 0, digest, {}, "outer", "0" * 64, "0" * 64)
    with pytest.raises(ModelingContractError):
        FeatureBatch(keys, x, y, names, ("categorical", "continuous"), 1, digest, {}, "outer", "0" * 64, "0" * 64)
    with pytest.raises(ModelingContractError):
        FeatureBatch(keys, x, y, names, kinds, 1, "A" * 64, {}, "outer", "0" * 64, "0" * 64)


def test_file_backed_authoritative_factory_filters_held_and_transforms(tmp_path):
    from dsdm_phase1.modeling_contract import ModelingContractError, ingest_private_foundation

    continuous = [f"c{i}" for i in range(25)]
    categorical = ["soil_class", "veg_mvg", "landuse_secondary"]
    response = [
        {"species_id": "sarcophilus_harrisii", "grid_cell_id": "cell-a", "pa": "1", "pa_type": "presence", "microcluster": "mc0", "outer_role": "outer_train", "cv_fold": "fold00"},
        {"species_id": "pseudocheirus_peregrinus", "grid_cell_id": "cell-held", "pa": "0", "pa_type": "pseudoabsence", "microcluster": "mc1", "outer_role": "test", "cv_fold": ""},
    ]
    map_rows = [{"grid_cell_id": "cell-a", "predictor_complete": "true", **{name: (2 if name == "c0" else 1) for name in continuous}, **{name: "1" for name in categorical}}]
    def write_csv(name, rows):
        path = tmp_path / name
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        return path
    response_path = write_csv("response.csv", response); map_path = write_csv("map.csv", map_rows)
    fit = {"fits": {"outer": {"means": {name: 1.0 for name in continuous}, "population_sd": {name: 1.0 for name in continuous}, "category_levels": {name: ["1"] for name in categorical}}}}
    contract = {"continuous_predictors": continuous, "categorical_predictors": categorical}
    fit_path = tmp_path / "fit.json"; fit_path.write_text(json.dumps(fit))
    contract_path = tmp_path / "contract.json"; contract_path.write_text(json.dumps(contract))
    binding = lambda path, private=False: {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **({"private": True} if private else {})}
    config = {"bindings": {"goal025_response_partitioned": binding(response_path, True), "goal024_map": binding(map_path, True), "goal026_fit_parameters": binding(fit_path), "goal026_feature_contract": binding(contract_path)}, "scope": {"real_species": ["sarcophilus_harrisii", "pseudocheirus_peregrinus"], "included_row_counts": {"sarcophilus_harrisii": {"included": 1, "positive": 1}, "pseudocheirus_peregrinus": {"included": 1, "positive": 0}}}}
    broker, provider, vault = ingest_private_foundation(tmp_path, config)
    assert set(provider.allowed_keys) == {next(iter(broker._rows.keys))}
    assert "cell-held" not in repr(provider.substrate.values)
    batch = provider.materialize(broker.outer_training("sarcophilus_harrisii"), "outer", provider.fit_encoder(broker.outer_training("sarcophilus_harrisii"), "intercept", "outer"))
    assert batch.x[0, 0] == 1.0
    assert batch.feature_names and batch.feature_kinds and batch.continuous_count == 25 and batch.feature_schema_digest
    with pytest.raises(ModelingContractError):
        vault.open()
    assert vault.attempted_open_count == 1 and vault.open_count == 0
    tampered = dict(config); tampered["bindings"] = dict(config["bindings"]); tampered["bindings"]["goal024_map"] = dict(config["bindings"]["goal024_map"], sha256="0" * 64)
    with pytest.raises(ModelingContractError):
        ingest_private_foundation(tmp_path, tampered)


def test_private_ingestion_gates_complete_counts_before_outer_partition(monkeypatch, tmp_path):
    from dsdm_phase1.modeling_contract import ModelingContractError

    response = [
        {"species_id": "sarcophilus_harrisii", "grid_cell_id": "a", "pa": "1", "pa_type": "presence", "microcluster": "m0", "outer_role": "outer_train", "cv_fold": "fold00"},
        {"species_id": "sarcophilus_harrisii", "grid_cell_id": "b", "pa": 0, "pa_type": "pseudoabsence", "microcluster": "m1", "outer_role": "outer_train", "cv_fold": "fold01"},
        {"species_id": "pseudocheirus_peregrinus", "grid_cell_id": "c", "pa": 1, "pa_type": "presence", "microcluster": "m0", "outer_role": "outer_train", "cv_fold": "fold00"},
        {"species_id": "other_species", "grid_cell_id": "held", "pa": "0", "pa_type": "pseudoabsence", "microcluster": "m1", "outer_role": "test", "cv_fold": ""},
    ]
    scope = {"real_species": ["sarcophilus_harrisii", "pseudocheirus_peregrinus"], "included_row_counts": {"sarcophilus_harrisii": {"included": 2, "positive": 1}, "pseudocheirus_peregrinus": {"included": 1, "positive": 1}}}
    broker, provider, vault = _scope_fixture(monkeypatch, tmp_path, response, scope)
    assert set(broker.outer_training("sarcophilus_harrisii").keys) == {next(key for key in broker._rows.keys if key.grid_cell_id == "a"), next(key for key in broker._rows.keys if key.grid_cell_id == "b")}
    assert set(provider.allowed_keys) == set(broker._rows.keys)
    assert vault.attempted_open_count == 0 and vault.open_count == 0
    with pytest.raises(ModelingContractError):
        vault.open()
    assert vault.attempted_open_count == 1 and vault.open_count == 0


@pytest.mark.parametrize("mutate", [
    lambda scope: scope["included_row_counts"]["sarcophilus_harrisii"].update(included=3),
    lambda scope: scope["included_row_counts"]["pseudocheirus_peregrinus"].update(positive=1),
])
def test_private_ingestion_rejects_complete_count_drift(monkeypatch, tmp_path, mutate):
    from dsdm_phase1.modeling_contract import ModelingContractError

    response = [
        {"species_id": "sarcophilus_harrisii", "grid_cell_id": "a", "pa": 1, "pa_type": "presence", "microcluster": "m0", "outer_role": "outer_train", "cv_fold": "fold00"},
        {"species_id": "pseudocheirus_peregrinus", "grid_cell_id": "b", "pa": 0, "pa_type": "pseudoabsence", "microcluster": "m1", "outer_role": "test", "cv_fold": ""},
    ]
    scope = {"real_species": ["sarcophilus_harrisii", "pseudocheirus_peregrinus"], "included_row_counts": {"sarcophilus_harrisii": {"included": 1, "positive": 1}, "pseudocheirus_peregrinus": {"included": 1, "positive": 0}}}
    mutate(scope)
    with pytest.raises(ModelingContractError, match="scope_mismatch"):
        _scope_fixture(monkeypatch, tmp_path, response, scope)


@pytest.mark.parametrize("mutate, message", [
    (lambda scope: scope.update(real_species=["sarcophilus_harrisii"]), "species_invalid"),
    (lambda scope: scope["real_species"].append("extra_species"), "species_invalid"),
    (lambda scope: scope["included_row_counts"].pop("pseudocheirus_peregrinus"), "counts_invalid"),
    (lambda scope: scope["included_row_counts"].update(extra_species={"included": 0, "positive": 0}), "counts_invalid"),
    (lambda scope: scope["included_row_counts"]["sarcophilus_harrisii"].update(included="1"), "count_type_invalid"),
])
def test_private_ingestion_rejects_scope_species_count_structure(monkeypatch, tmp_path, mutate, message):
    from dsdm_phase1.modeling_contract import ModelingContractError

    response = [
        {"species_id": "sarcophilus_harrisii", "grid_cell_id": "a", "pa": 1, "pa_type": "presence", "microcluster": "m0", "outer_role": "outer_train", "cv_fold": "fold00"},
        {"species_id": "pseudocheirus_peregrinus", "grid_cell_id": "b", "pa": 0, "pa_type": "pseudoabsence", "microcluster": "m1", "outer_role": "test", "cv_fold": ""},
    ]
    scope = {"real_species": ["sarcophilus_harrisii", "pseudocheirus_peregrinus"], "included_row_counts": {"sarcophilus_harrisii": {"included": 1, "positive": 1}, "pseudocheirus_peregrinus": {"included": 1, "positive": 0}}}
    mutate(scope)
    with pytest.raises(ModelingContractError, match=message):
        _scope_fixture(monkeypatch, tmp_path, response, scope)
