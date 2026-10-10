"""Conventional lane for the approved Tasmania pseudoabsence sensitivity.

The lane is deliberately prediction-only with respect to assessment rows.  It
reads canonical responses only for the response-free outer-training allowlist,
reconstructs every original endpoint before subtracting pseudoabsences, calls
the frozen Goal029 adapter directly, and writes private model/prediction
receipts.  It has no scoring or held-response-vault reader.

Stages are intentionally gated::

    prepare -> smoke -> run-inner -> run-outer

``prepare`` performs no fitting.  ``run-inner`` and ``run-outer`` refuse to
start without a successful repeated real-smoke qualification made by the same
script and preparation receipt.  Sharding is deterministic and may be used by
four independent single-threaded workers.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence

# These are process contracts, not performance hints.  They must be set before
# importing NumPy/scikit-learn/Torch in the historical fitting process.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import numpy as np

PROCESS_NONCE = hashlib.sha256(os.urandom(32)).hexdigest()

SPECIES = (
    "thylogale_billardierii",
    "notamacropus_rufogriseus",
    "trichosurus_vulpecula",
    "pseudocheirus_peregrinus",
    "vombatus_ursinus",
    "sarcophilus_harrisii",
    "dasyurus_maculatus",
    "dasyurus_viverrinus",
)
FOLDS = tuple(f"fold{index:02d}" for index in range(5))
ENDPOINTS = (
    "fraction25/ladder00",
    "fraction25/ladder01",
    "fraction25/ladder02",
    "fraction50/ladder00",
    "fraction50/ladder01",
    "fraction50/ladder02",
    "fraction100/full",
)
SEEDS_BY_FAMILY = {
    "elastic_net": tuple(f"seed{index:02d}" for index in range(5)),
    "random_forest": tuple(f"seed{index:02d}" for index in range(5)),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": tuple(f"seed{index:02d}" for index in range(5)),
}
PRIVATE_REL = Path("data/processed/dsdm/tasmania-pseudoabsence-20261008/private/conventional")
ARCHIVE_REL = Path("data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1")
INNER_BUNDLE_REL = Path("data/processed/dsdm/goal035-final-inner-lifecycle/private")
OUTER_BUNDLE_REL = Path("data/processed/dsdm/goal037-outer-ready/private/bundles")
SOURCE_CENSUS_REL = Path("evidence/tasmania_pseudoabsence/20261008/source-census.json")
SELECTION_REL = Path("evidence/dsdm_inner_evaluation/goal036/conventional_selection.csv")
MAP_REL = Path("data/processed/predictors/goal024-predictor-source-repair-domain-freeze/2026-07-26/predictor_cell_map_canonical.csv")
FEATURE_CONTRACT_REL = Path("evidence/model_ready_features/2026-07-27/feature_contract.json")
FIT_PARAMETERS_REL = Path("evidence/model_ready_features/2026-07-27/fit_parameters.json")
RECOVERY_RECEIPT_REL = Path("evidence/tasmania_pseudoabsence/20261009/auxiliary-recovery.json")

SOURCE_CENSUS_SHA256 = "211bad0f88daa140f1d56ac2916fd5da584f4164e6e96e36748547b8dc392352"
SELECTION_SHA256 = "3e05784670f58e88144dcbda43819c3811e8303c59cd15c36f23fdf38736a561"
MAP_SHA256 = "c27b848bd4db81932553ac801029b8e66cf1a1ecd05271343ee2b4d0a3035cc5"
FEATURE_CONTRACT_SHA256 = "e9a8f9b7bee7dee25905dfa052427f6e0a4f1b5ebd6ed02fcfb1761bbd224d98"
FIT_PARAMETERS_SHA256 = "608b99f94af49122bf9e252e35ae7c067812762d20ba080c3e7fbd40f35661d0"
CENSUS_SCRIPT_SHA256 = "7062d2877fe55acd4439e4e357c03b0a99678f0c8dc3da410028ba1b8d1e0618"
RECOVERY_RECEIPT_SHA256 = "2d86a42321dcbaf1abca9f6cb592e9c6f7bb41e5d59c8e97c683c8fe8464c4f9"
ARCHIVE_RECEIPT_SHA256 = "b75a61a31e052477617dedd6b2b3e0d763d727dc85f04d49b5a2bcf4d8099eac"
GOAL037_RECEIPT_SHA256 = "c691bf13f3722431687e0fed0259125a23c066959a114b56566dfe21afed4f13"
CONVENTIONAL_IMPORT_SHA256 = "37b29ec983980a3e79789d6191ae739cc3e6b743f4a4e571ea47b91212a59320"
PRODUCER_REFERENCE_SHA256 = "8da72795de369db9a52585725b1651a26557d37a28dfbd008a76c74b64245321"
EXPECTED_DEPENDENCY_HASHES = {
    "pyproject.toml": "29b7c2f9f810ac35357fa9b85189002d92a54a4933cf87746f57ae27cc0a8d08",
    "uv.lock": "39c22925750ac8821f5420bdfe5ca39554b7906d812bd3a94a04e91c469284fd",
    "config/conventional_baseline_production.json": "62b1c5255c5aa5c74f5ba598818dd13e2f2234c0cb13da58671c3be286ccefae",
}
PRODUCER_COMMIT = "f85e45922e182858fd351fdaf4f1b36b33fb4f2f"
DEFAULT_PRODUCER_CHECKOUT = Path("/data/codex/repos/dsdm-goal029-f85e459")
EXPECTED_SOURCE_HASHES = {
    "model_adapters.py": "5aeae21aaeca0502d40db90c732db9c21de3ca72ec2561c77b709738e3a3e35e",
    "modeling_contract.py": "342bb461ca3e6c6193984e9d0ec22ba3d18ee8a3fcaeaaf84710c72adf5649a9",
    "target_subsets.py": "71988214be2108417437261b66fcb79666865df483cdda90daba60576cf49acc",
    "inner_cv.py": "41a5ebd4641f233ea8b9ba5b0941d9f736f7fa73cd73695ecff521b12eec336c",
}
EXPECTED_RUNTIME = {
    "python": "3.12.3",
    "machine": "x86_64",
    "numpy": "2.5.1",
    "scipy": "1.16.3",
    "scikit-learn": "1.9.0",
    "torch": "2.13.0",
    "pygam": "0.10.1",
    "threadpoolctl": "3.6.0",
}


class ConventionalSensitivityError(ValueError):
    """Raised when the conventional sensitivity lane must fail closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConventionalSensitivityError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: str | Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConventionalSensitivityError(f"invalid_json:{Path(path).name}") from exc
    _require(isinstance(value, Mapping), f"json_object_required:{Path(path).name}")
    return value


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    target = Path(path)
    _require(target.is_file() and not target.is_symlink(), f"invalid_csv:{target.name}")
    with target.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_json_idempotent(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(value) + b"\n"
    if path.exists():
        _require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, f"existing_output_drift:{path.name}")
        return
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _require(path.read_bytes() == raw, f"concurrent_output_drift:{path.name}")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _array_digest(array: np.ndarray) -> str:
    value = np.asarray(array)
    if value.dtype.kind in "fiu":
        if value.dtype.kind == "f":
            canonical = np.asarray(value, dtype=">f8")
        else:
            canonical = np.asarray(value, dtype=">i8")
        payload = canonical.tobytes(order="C")
    elif value.dtype.kind in "US":
        payload = "\n".join(str(item) for item in value.reshape(-1).tolist()).encode("utf-8")
    else:
        raise ConventionalSensitivityError("array_digest_dtype_invalid")
    return hashlib.sha256(payload).hexdigest()


def _prediction_digest(keys: Sequence[str], scores: np.ndarray) -> str:
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    _require(len(keys) == len(values) and np.isfinite(values).all(), "prediction_vector_invalid")
    return digest_value({"keys": list(keys), "scores_be_f8_sha256": _array_digest(values)})


def _id_digest(keys: Iterable[Any]) -> str:
    tokens = sorted(f"{key.species_id}\x1f{key.grid_cell_id}" for key in keys)
    return hashlib.sha256("\n".join(tokens).encode("utf-8")).hexdigest()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"module_import_failed:{path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_census(root: Path) -> ModuleType:
    path = root / "scripts/tasmania_pseudoabsence_census.py"
    _require(path.is_file() and not path.is_symlink(), "census_script_missing")
    # The census executes on import, so authenticate its bytes first.
    _require(sha256_file(path) == CENSUS_SCRIPT_SHA256, "census_script_binding_mismatch")
    name = "_tasmania_conventional_census_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
    return sys.modules.get(name) or _load_module(path, name)


def _load_archived_modules(root: Path) -> Mapping[str, ModuleType]:
    source = (root / ARCHIVE_REL / "src/dsdm_phase1").resolve()
    _require(source.is_dir(), "archived_goal037_source_missing")
    for filename, expected in EXPECTED_SOURCE_HASHES.items():
        _require(sha256_file(source / filename) == expected, f"archived_source_mismatch:{filename}")
    namespace = "_tasmania_conventional_archive_" + hashlib.sha256(str(source).encode()).hexdigest()[:16]
    if namespace not in sys.modules:
        package = ModuleType(namespace)
        package.__path__ = [str(source)]
        sys.modules[namespace] = package
    modules: dict[str, ModuleType] = {}
    for name in ("modeling_contract", "target_subsets", "model_adapters"):
        qualified = f"{namespace}.{name}"
        module = sys.modules.get(qualified)
        if module is None:
            module = _load_module(source / f"{name}.py", qualified)
        modules[name] = module
    return modules


@dataclass(frozen=True)
class SelectedStratum:
    species: str
    endpoint: str
    family: str
    candidate: str
    seeds: tuple[str, ...]


@dataclass(frozen=True)
class InnerTask:
    species: str
    endpoint: str
    family: str
    candidate: str
    held_fold: str
    seed_label: str


@dataclass(frozen=True)
class OuterTask:
    species: str
    endpoint: str
    family: str
    candidate: str
    seed_label: str


def _task_digest(task: InnerTask | OuterTask, lane: str) -> str:
    return digest_value({"lane": lane, "task": asdict(task)})


def _selection_inventory(root: Path) -> tuple[SelectedStratum, ...]:
    path = root / SELECTION_REL
    _require(sha256_file(path) == SELECTION_SHA256, "conventional_selection_binding_mismatch")
    rows = _read_csv(path)
    selected: list[SelectedStratum] = []
    for row in rows:
        family = str(row.get("selected_family", ""))
        candidate = str(row.get("selected_candidate", ""))
        species = str(row.get("species", ""))
        endpoint = str(row.get("endpoint", ""))
        _require(species in SPECIES and endpoint in ENDPOINTS and family in SEEDS_BY_FAMILY, "selection_scope_invalid")
        _require(candidate.startswith({"elastic_net": "enet", "random_forest": "rf", "hist_gradient_boosting": "hgb", "shallow_ann": "ann"}[family]), "selection_candidate_family_mismatch")
        selected.append(SelectedStratum(species, endpoint, family, candidate, SEEDS_BY_FAMILY[family]))
    expected = {(species, endpoint) for species in SPECIES for endpoint in ENDPOINTS}
    _require(len(selected) == 56 and {(item.species, item.endpoint) for item in selected} == expected, "selection_inventory_invalid")
    _require(len({(item.species, item.endpoint) for item in selected}) == 56, "selection_duplicate_stratum")
    counts = {family: sum(item.family == family for item in selected) for family in SEEDS_BY_FAMILY}
    _require(counts == {"random_forest": 24, "hist_gradient_boosting": 10, "shallow_ann": 21, "elastic_net": 1}, "selection_family_counts_invalid")
    return tuple(sorted(selected, key=lambda item: (SPECIES.index(item.species), ENDPOINTS.index(item.endpoint))))


def build_task_inventory(strata: Sequence[SelectedStratum]) -> tuple[tuple[InnerTask, ...], tuple[OuterTask, ...], Mapping[str, Any]]:
    inner: list[InnerTask] = []
    outer: list[OuterTask] = []
    physical_inner = 0
    for stratum in strata:
        for fold in FOLDS:
            for seed in stratum.seeds:
                inner.append(InnerTask(stratum.species, stratum.endpoint, stratum.family, stratum.candidate, fold, seed))
                physical_inner += 2 if stratum.family == "shallow_ann" else 1
        for seed in stratum.seeds:
            outer.append(OuterTask(stratum.species, stratum.endpoint, stratum.family, stratum.candidate, seed))
    counts = {
        "strata": len(strata),
        "inner_logical_tasks": len(inner),
        "inner_physical_fits": physical_inner,
        "outer_logical_tasks": len(outer),
        "outer_physical_fits": len(outer),
        "production_physical_fits": physical_inner + len(outer),
        "smoke_logical_tasks": 4,
        "smoke_physical_fits": 6,
    }
    _require(counts == {
        "strata": 56, "inner_logical_tasks": 1200, "inner_physical_fits": 1725,
        "outer_logical_tasks": 240, "outer_physical_fits": 240,
        "production_physical_fits": 1965, "smoke_logical_tasks": 4,
        "smoke_physical_fits": 6,
    }, "fit_inventory_invalid")
    return tuple(inner), tuple(outer), counts


def _runtime_versions() -> Mapping[str, str]:
    packages = {}
    for name in ("numpy", "scipy", "scikit-learn", "torch", "pygam", "threadpoolctl"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "missing"
    return {"python": platform.python_version(), "machine": platform.machine(), **packages}


def _attest_execution_runtime(producer_checkout: Path) -> Mapping[str, Any]:
    actual = _runtime_versions()
    _require(actual == EXPECTED_RUNTIME, "historical_runtime_mismatch")
    checkout = producer_checkout.resolve()
    _require(checkout.is_dir(), "producer_checkout_missing")
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, text=True, capture_output=True, check=False)
    _require(result.returncode == 0 and result.stdout.strip() == PRODUCER_COMMIT, "producer_commit_mismatch")
    source = checkout / "src/dsdm_phase1"
    for filename, expected in EXPECTED_SOURCE_HASHES.items():
        _require(sha256_file(source / filename) == expected, f"producer_source_mismatch:{filename}")
    for relative, expected in EXPECTED_DEPENDENCY_HASHES.items():
        _require(sha256_file(checkout / relative) == expected, f"producer_dependency_mismatch:{relative}")
    from threadpoolctl import threadpool_info
    pools = threadpool_info()
    _require(all(int(item.get("num_threads", 0)) <= 1 for item in pools), "numerical_thread_pool_exceeds_one")
    return {
        "producer_checkout": str(checkout),
        "producer_commit": PRODUCER_COMMIT,
        "versions": actual,
        "source_hashes": dict(EXPECTED_SOURCE_HASHES),
        "dependency_hashes": dict(EXPECTED_DEPENDENCY_HASHES),
        "thread_environment": {name: os.environ.get(name) for name in (
            "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
        )},
        "thread_pools": pools,
    }


def _load_recovery_closure(root: Path) -> Mapping[str, Any]:
    path = root / RECOVERY_RECEIPT_REL
    _require(path.is_file() and not path.is_symlink(), "auxiliary_recovery_closure_missing")
    _require(sha256_file(path) == RECOVERY_RECEIPT_SHA256, "auxiliary_recovery_closure_drift")
    receipt = _read_json(path)
    expected = {
        "schema_version": "tasmania-auxiliary-recovery-v1",
        "status": "accepted",
        "method": "exact_goal035_multihead_replay",
        "states": 200,
        "fits": 200,
        "pooled_reconstructions": 0,
        "q_reconstructions": 0,
        "outer_attempted": 0,
        "outer_opened": 0,
        "workers": 3,
        "threads_per_worker": 1,
    }
    _require(all(receipt.get(key) == value for key, value in expected.items()), "auxiliary_recovery_closure_invalid")
    for key in ("runtime_digest", "serialization_inventory_digest", "semantic_state_inventory_digest"):
        _require(isinstance(receipt.get(key), str) and len(receipt[key]) == 64, f"auxiliary_recovery_{key}_invalid")
    return receipt


class Foundation:
    """Training-only rows plus response-free evaluation/map predictors."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.census = _load_census(self.root)
        self.modules = _load_archived_modules(self.root)
        self.contract = self.modules["modeling_contract"]
        self.subsets = self.modules["target_subsets"]
        self.adapters = self.modules["model_adapters"]
        self.paths, _ = self.census._load_bindings(self.root)
        train_allowlist, test_allowlist, assignments = self.census._allowlist_from_response_free_inputs(self.paths)
        records = self.census._read_allowlisted_response_rows(self.paths["response_partitioned"], train_allowlist, assignments)
        _require(len(records) == 11039, "training_response_inventory_mismatch")
        self.outer = self.contract.RowSet.from_records(records)
        self.fold_by_key = {key: assignments[key.grid_cell_id]["cv_fold"] for key in self.outer.keys}
        self.test_allowlist = frozenset(test_allowlist)
        self.assignments = assignments
        self.census_report = self.census.run_census(self.root)
        saved = _read_json(self.root / SOURCE_CENSUS_REL)
        _require(sha256_file(self.root / SOURCE_CENSUS_REL) == SOURCE_CENSUS_SHA256, "source_census_file_mismatch")
        _require(self.census_report == saved and saved.get("success") is True, "source_census_replay_mismatch")
        self.role_index = {
            (row["species"], row.get("held_fold"), row["endpoint"], row["role"]): row
            for row in saved["records"]
        }
        _require(len(self.role_index) == 896, "source_census_role_inventory_mismatch")
        self.inner_metadata = {}
        for species in SPECIES:
            for fold in FOLDS:
                metadata, _ = self.census._bundle_inventory(self.root / INNER_BUNDLE_REL / f"{species}--{fold}.npz")
                self.inner_metadata[(species, fold)] = metadata
        self.outer_metadata = {}
        for species in SPECIES:
            metadata, _ = self.census._bundle_inventory(self.root / OUTER_BUNDLE_REL / f"{species}.npz")
            self.outer_metadata[species] = metadata
        _require(sha256_file(self.root / MAP_REL) == MAP_SHA256, "goal024_map_binding_mismatch")
        _require(sha256_file(self.root / FEATURE_CONTRACT_REL) == FEATURE_CONTRACT_SHA256, "goal026_feature_contract_binding_mismatch")
        _require(sha256_file(self.root / FIT_PARAMETERS_REL) == FIT_PARAMETERS_SHA256, "goal026_fit_parameters_binding_mismatch")
        feature_contract = _read_json(self.root / FEATURE_CONTRACT_REL)
        self.continuous = tuple(feature_contract.get("continuous_predictors", ()))
        self.categorical = tuple(feature_contract.get("categorical_predictors", ()))
        _require(len(self.continuous) == 25 and len(self.categorical) == 3, "feature_contract_schema_mismatch")
        self.fit_parameters = _read_json(self.root / FIT_PARAMETERS_REL)
        self.raw_by_cell = self._load_map()
        self.map_cells = tuple(sorted(self.raw_by_cell))
        _require(len(self.map_cells) == 71023, "map_cell_inventory_mismatch")
        self._outer_by_species = {
            species: self.outer.take([index for index, key in enumerate(self.outer.keys) if key.species_id == species])
            for species in SPECIES
        }
        self._accepted_primary_cache = None

    def _load_map(self) -> Mapping[str, Mapping[str, Any]]:
        rows = _read_csv(self.root / MAP_REL)
        values: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            cell = str(row.get("grid_cell_id", ""))
            _require(cell and cell not in values, "map_cell_duplicate_or_missing")
            _require(row.get("predictor_complete") in ("true", "True", "1"), "map_predictor_incomplete")
            try:
                values[cell] = {
                    name: float(row[name]) if name in self.continuous else str(row[name])
                    for name in self.continuous + self.categorical
                }
            except (KeyError, TypeError, ValueError) as exc:
                raise ConventionalSensitivityError("map_predictor_invalid") from exc
        return values

    def outer_species(self, species: str):
        return self._outer_by_species[species]

    def provider(self, species: str):
        RowKey = self.contract.RowKey
        raw = {RowKey(species, cell): values for cell, values in self.raw_by_cell.items()}
        substrate = self.contract.TransformingFeatureSubstrate(raw, self.fit_parameters, self.continuous, self.categorical)
        return self.contract.FeatureProvider(substrate, frozenset(raw))

    def dummy_rows(self, species: str, cells: Sequence[str]):
        return self.contract.RowSet.from_records([
            {"species_id": species, "grid_cell_id": cell, "pa": 0, "pa_type": "survey_supported_absence", "microcluster": "prediction_only"}
            for cell in cells
        ])

    def inner_assessment(self, species: str, held_fold: str):
        rows = self.outer_species(species)
        cells = [key.grid_cell_id for key in rows.keys if self.fold_by_key[key] == held_fold]
        return self.dummy_rows(species, cells)

    def outer_assessment(self, species: str):
        cells = sorted(cell for member_species, cell in self.test_allowlist if member_species == species)
        _require(cells, "outer_evaluation_membership_empty")
        return self.dummy_rows(species, cells)

    def map_rows(self, species: str):
        return self.dummy_rows(species, self.map_cells)

    def accepted_primary_authority(self):
        if self._accepted_primary_cache is None:
            self._accepted_primary_cache = _accepted_selection_index(self.root)
        return self._accepted_primary_cache


def filter_without_pseudoabsence(rows: Any, census: ModuleType) -> Any:
    retained, excluded = census.filter_rowset_without_pseudoabsence(rows)
    _require("pseudoabsence" not in retained.response_source, "pseudoabsence_filter_failed")
    _require(set(retained.keys) | set(excluded) == set(rows.keys), "pseudoabsence_filter_union_mismatch")
    _require(set(retained.keys).isdisjoint(excluded), "pseudoabsence_filter_overlap")
    return retained


def _rowset_for_keys(rows: Any, keys: Sequence[Any]) -> Any:
    lookup = {key: index for index, key in enumerate(rows.keys)}
    _require(len(set(keys)) == len(keys) and all(key in lookup for key in keys), "endpoint_key_not_in_training")
    return rows.take([lookup[key] for key in keys])


def _verify_role(foundation: Foundation, species: str, held_fold: str | None, endpoint: str, role: str, baseline: Any, retained: Any) -> None:
    record = foundation.role_index.get((species, held_fold, endpoint, role))
    _require(record is not None and record.get("failure") is None, "accepted_role_record_missing")
    _require(record["baseline_id_set_digest"] == _id_digest(baseline.keys), "baseline_role_membership_mismatch")
    _require(record["retained_id_set_digest"] == _id_digest(retained.keys), "retained_role_membership_mismatch")
    _require(record["retained"]["rows"] == len(retained.keys), "retained_role_count_mismatch")


def _inner_context(foundation: Foundation, task: InnerTask) -> Mapping[str, Any]:
    full = foundation.outer_species(task.species)
    train = full.take([index for index, key in enumerate(full.keys) if foundation.fold_by_key[key] != task.held_fold])
    fraction, ladder = task.endpoint.split("/")
    lookup_ladder = "ladder00" if fraction == "fraction100" else ladder
    endpoint = foundation.subsets.build_ladders(train)[(fraction, lookup_ladder)]
    expected = foundation.inner_metadata[(task.species, task.held_fold)]["subset_membership_digests"][task.endpoint]
    _require(endpoint.subset_digest == expected, "inner_endpoint_membership_mismatch")
    baseline_replay = _rowset_for_keys(train, endpoint.keys)
    stopping_fold = f"fold{(int(task.held_fold[-2:]) + 1) % 5:02d}"
    baseline_stopping = _rowset_for_keys(baseline_replay, [key for key in baseline_replay.keys if foundation.fold_by_key[key] == stopping_fold])
    baseline_discovery = _rowset_for_keys(baseline_replay, [key for key in baseline_replay.keys if foundation.fold_by_key[key] != stopping_fold])
    replay = filter_without_pseudoabsence(baseline_replay, foundation.census)
    stopping = filter_without_pseudoabsence(baseline_stopping, foundation.census)
    discovery = filter_without_pseudoabsence(baseline_discovery, foundation.census)
    for role, baseline, retained in (
        ("replay", baseline_replay, replay), ("stopping", baseline_stopping, stopping), ("discovery", baseline_discovery, discovery),
    ):
        _verify_role(foundation, task.species, task.held_fold, task.endpoint, role, baseline, retained)
    evaluation = foundation.inner_assessment(task.species, task.held_fold)
    original_eval = [key for key in full.keys if foundation.fold_by_key[key] == task.held_fold]
    _require(_id_digest(evaluation.keys) == _id_digest(original_eval), "inner_evaluation_membership_mismatch")
    return {
        "endpoint_digest": expected, "stopping_fold": stopping_fold,
        "discovery": discovery, "stopping": stopping, "replay": replay,
        "evaluation": evaluation,
    }


def _outer_context(foundation: Foundation, task: OuterTask) -> Mapping[str, Any]:
    full = foundation.outer_species(task.species)
    fraction, ladder = task.endpoint.split("/")
    lookup_ladder = "ladder00" if fraction == "fraction100" else ladder
    endpoint = foundation.subsets.build_ladders(full)[(fraction, lookup_ladder)]
    expected = foundation.outer_metadata[task.species]["subset_membership_digests"][task.endpoint]
    _require(endpoint.subset_digest == expected, "outer_endpoint_membership_mismatch")
    baseline = _rowset_for_keys(full, endpoint.keys)
    retained = filter_without_pseudoabsence(baseline, foundation.census)
    _verify_role(foundation, task.species, None, task.endpoint, "outer_fit", baseline, retained)
    return {"endpoint_digest": expected, "baseline": baseline, "retained": retained, "evaluation": foundation.outer_assessment(task.species)}


def _batch_digest(batch: Any) -> str:
    return digest_value({
        "keys": [f"{key.species_id}\x1f{key.grid_cell_id}" for key in batch.keys],
        "x": _array_digest(batch.x), "y": _array_digest(batch.y),
        "feature_schema_digest": batch.feature_schema_digest,
        "transform_digest": batch.transform_digest,
        "encoder_digest": batch.encoder_digest,
    })


def _report_payload(report: Any) -> Mapping[str, Any]:
    value = asdict(report)
    value["warnings"] = list(value.get("warnings", ()))
    return value


def _semantic_report(report: Any) -> Mapping[str, Any]:
    value = dict(_report_payload(report))
    value.pop("runtime_seconds", None)
    value.pop("peak_rss_bytes", None)
    return value


def _candidate(foundation: Foundation, family: str, candidate_id: str) -> Mapping[str, Any]:
    candidate = foundation.adapters.CANONICAL_CANDIDATES.get(candidate_id)
    _require(isinstance(candidate, Mapping) and candidate.get("family") == family, "candidate_registry_mismatch")
    return dict(candidate)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical(value) + b"\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ConventionalSensitivityError(f"immutable_record_exists:{path.name}") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _ensure_run_active(private_root: Path) -> None:
    _require(not (private_root / "ABORT.json").exists(), "conventional_panel_aborted")


def _current_preparation_digest(private_root: Path) -> str:
    receipt = _read_json(private_root / "preparation.json")
    return _validated_self_digest(receipt, "receipt_digest", "preparation_receipt_invalid")


def _begin_fit_attempt(
    root: Path,
    private_root: Path,
    lane: str,
    task: InnerTask | OuterTask,
    destination: Path,
    physical_stages: Sequence[str],
) -> tuple[Path, Path]:
    _ensure_run_active(private_root)
    task_digest = _task_digest(task, "inner" if isinstance(task, InnerTask) else "outer")
    attempt_key = destination.name
    lane_root = destination.parent.parent
    intent = lane_root / "intents" / f"{attempt_key}.json"
    attempt = lane_root / "attempts" / attempt_key
    _require(not destination.exists(), "fit_destination_already_exists")
    _require(not intent.exists() and not attempt.exists(), "orphan_or_failed_fit_intent")
    payload = {
        "schema_version": "tasmania-pseudoabsence-conventional-fit-intent-v1",
        "lane": lane, "task": asdict(task), "task_digest": task_digest,
        "destination": str(destination.relative_to(private_root)),
        "physical_stages": list(physical_stages), "fit_started": False,
        "created_unix_ns": time.time_ns(), "bindings": _leaf_bindings(root),
        "preparation_receipt_digest": _current_preparation_digest(private_root),
    }
    payload["intent_digest"] = digest_value(payload)
    _write_json_exclusive(intent, payload)
    attempt.mkdir(parents=True, exist_ok=False)
    work = attempt / "work"
    work.mkdir()
    return attempt, work


def _record_fit_start(attempt: Path, task: InnerTask | OuterTask, stage: str, physical_fit_number: int) -> None:
    _ensure_run_active(attempt.parents[2])
    _write_json_exclusive(attempt / "fit-starts" / f"{physical_fit_number:02d}-{stage}.json", {
        "schema_version": "tasmania-pseudoabsence-conventional-fit-start-v1",
        "task": asdict(task), "stage": stage,
        "physical_fit_number": physical_fit_number,
        "started_unix_ns": time.time_ns(),
    })


def _mark_fit_failure(private_root: Path, lane: str, task: InnerTask | OuterTask, attempt: Path, exc: BaseException) -> None:
    failure = {
        "schema_version": "tasmania-pseudoabsence-conventional-fit-failure-v1",
        "lane": lane, "task": asdict(task),
        "exception_type": type(exc).__name__, "exception": str(exc),
        "traceback": traceback.format_exc(), "failed_unix_ns": time.time_ns(),
    }
    failure["failure_digest"] = digest_value(failure)
    failure_path = attempt / "failure.json"
    if not failure_path.exists():
        _write_json_exclusive(failure_path, failure)
    abort = dict(failure)
    abort["attempt"] = str(attempt.relative_to(private_root))
    abort["abort_digest"] = digest_value(abort)
    abort_path = private_root / "ABORT.json"
    if not abort_path.exists():
        try:
            _write_json_exclusive(abort_path, abort)
        except ConventionalSensitivityError:
            pass


def _semantic_model_digest(fitted: Any, file_sha256: str) -> str:
    if getattr(fitted, "family", None) != "shallow_ann":
        return file_sha256
    model = getattr(fitted, "model", None)
    _require(model is not None and hasattr(model, "state_dict"), "ann_semantic_model_state_missing")
    records = []
    for name, tensor in sorted(model.state_dict().items()):
        array = tensor.detach().cpu().contiguous().numpy()
        records.append({
            "name": name, "dtype": str(array.dtype), "shape": list(array.shape),
            "bytes_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        })
    return digest_value({
        "family": fitted.family, "candidate_digest": fitted.candidate_digest,
        "fit_seed": fitted.seed, "schema": fitted.schema, "state": records,
    })


def _reload_and_verify_model(foundation: Foundation, path: Path, fitted: Any, batch: Any, scores: np.ndarray) -> tuple[Any, str]:
    file_sha = sha256_file(path)
    loaded = foundation.adapters.load_fitted_model(path, file_sha)
    loaded_scores = np.asarray(loaded.predict_scores(batch), dtype=np.float64)
    _require(np.array_equal(loaded_scores, np.asarray(scores, dtype=np.float64)), "serialized_model_prediction_mismatch")
    fitted_digest = _semantic_model_digest(fitted, file_sha)
    loaded_digest = _semantic_model_digest(loaded, file_sha)
    _require(fitted_digest == loaded_digest, "serialized_model_semantic_mismatch")
    return loaded, loaded_digest


def _fit_inner_task(
    foundation: Foundation,
    task: InnerTask,
    destination: Path,
    private_root: Path,
    production_caps_receipt_digest: str | None = None,
) -> Mapping[str, Any]:
    context = _inner_context(foundation, task)
    provider = foundation.provider(task.species)
    transform_id = f"cv_{task.held_fold}"
    encoder = provider.fit_encoder(context["replay"], task.family, transform_id)
    replay_batch = provider.materialize(context["replay"], transform_id, encoder)
    evaluation_batch = provider.materialize(context["evaluation"], transform_id, encoder)
    _require(np.all(evaluation_batch.y == 0), "prediction_batch_labels_not_dummy")
    candidate = _candidate(foundation, task.family, task.candidate)
    TaskKey = foundation.contract.TaskKey
    key = TaskKey(task.species, transform_id, *task.endpoint.split("/"), task.family, task.candidate, task.seed_label)
    seed = foundation.contract.derive_seed(key, "fit")
    adapter = foundation.adapters.build_adapter(task.family)
    destination.parent.mkdir(parents=True, exist_ok=True)
    physical_stages = ("discovery", "replay") if task.family == "shallow_ann" else ("replay",)
    attempt, stage = _begin_fit_attempt(foundation.root, private_root, "inner", task, destination, physical_stages)
    try:
        discovery_report = None
        discovery_model_sha = None
        discovery_prediction_digest = None
        discovery_input_digest = None
        if task.family == "shallow_ann":
            discovery_batch = provider.materialize(context["discovery"], transform_id, encoder)
            stopping_batch = provider.materialize(context["stopping"], transform_id, encoder)
            _record_fit_start(attempt, task, "discovery", 1)
            discovered, discovery_report = adapter.fit(discovery_batch, stopping_batch, candidate, seed)
            _require(discovery_report.best_epoch is not None, "ann_best_epoch_missing")
            discovery_report = replace(discovery_report, stopping_fold=context["stopping_fold"])
            discovery_envelope = discovered.serialize(stage / "discovery.model")
            discovery_model_sha = sha256_file(stage / "discovery.model")
            discovery_scores = discovered.predict_scores(stopping_batch)
            _, discovery_model_semantic_digest = _reload_and_verify_model(
                foundation, stage / "discovery.model", discovered, stopping_batch, discovery_scores,
            )
            discovery_prediction_digest = _prediction_digest([key.grid_cell_id for key in stopping_batch.keys], discovery_scores)
            discovery_input_digest = _batch_digest(discovery_batch)
            _record_fit_start(attempt, task, "replay", 2)
            fitted, replay_report = adapter.fit(replay_batch, None, candidate, seed, exact_epochs=int(discovery_report.best_epoch))
            _require(
                discovery_report.initial_state_digest is not None
                and discovery_report.initial_state_digest == replay_report.initial_state_digest
                and replay_report.iterations == discovery_report.best_epoch,
                "ann_replay_reset_mismatch",
            )
            physical_fits = 2
        else:
            discovery_model_semantic_digest = None
            _record_fit_start(attempt, task, "replay", 1)
            fitted, replay_report = adapter.fit(replay_batch, None, candidate, seed)
            physical_fits = 1
        model_envelope = fitted.serialize(stage / "model.model")
        model_sha = sha256_file(stage / "model.model")
        scores = fitted.predict_scores(evaluation_batch)
        _, model_semantic_digest = _reload_and_verify_model(
            foundation, stage / "model.model", fitted, evaluation_batch, scores,
        )
        keys = np.asarray([key.grid_cell_id for key in evaluation_batch.keys], dtype=str)
        np.savez_compressed(stage / "predictions.npz", grid_cell_id=keys, scores=np.asarray(scores, dtype=np.float64))
        (stage / "encoder.json").write_bytes(_canonical(encoder) + b"\n")
        receipt = {
            "schema_version": "tasmania-pseudoabsence-conventional-inner-leaf-v1",
            "task": asdict(task), "task_digest": _task_digest(task, "inner"),
            "process_id": os.getpid(),
            "process_nonce": PROCESS_NONCE,
            "physical_fits": physical_fits, "fit_seed_uint32": seed,
            "candidate": candidate, "candidate_digest": digest_value(candidate),
            "endpoint_membership_digest": context["endpoint_digest"],
            "retained_role_id_digests": {role: _id_digest(context[role].keys) for role in ("discovery", "stopping", "replay")},
            "evaluation_id_digest": _id_digest(context["evaluation"].keys),
            "encoder_digest": encoder["encoder_digest"],
            "encoder_sha256": sha256_file(stage / "encoder.json"),
            "feature_schema_digest": replay_batch.feature_schema_digest,
            "transform_digest": replay_batch.transform_digest,
            "input_digests": {
                "discovery": discovery_input_digest,
                "stopping": _batch_digest(provider.materialize(context["stopping"], transform_id, encoder)) if task.family == "shallow_ann" else None,
                "replay": _batch_digest(replay_batch),
                "evaluation_dummy": _batch_digest(evaluation_batch),
            },
            "discovery_report": _report_payload(discovery_report) if discovery_report is not None else None,
            "replay_report": _report_payload(replay_report),
            "selected_epoch": int(discovery_report.best_epoch) if discovery_report is not None else None,
            "discovery_model_sha256": discovery_model_sha,
            "discovery_model_semantic_digest": discovery_model_semantic_digest,
            "discovery_model_identity_digest": discovery_envelope["identity_digest"] if discovery_report is not None else None,
            "discovery_prediction_digest": discovery_prediction_digest,
            "model_sha256": model_sha,
            "model_semantic_digest": model_semantic_digest,
            "model_identity_digest": model_envelope["identity_digest"],
            "prediction_sha256": sha256_file(stage / "predictions.npz"),
            "prediction_digest": _prediction_digest(keys.tolist(), scores),
            "bindings": _leaf_bindings(foundation.root),
            "preparation_receipt_digest": _current_preparation_digest(private_root),
            "production_caps_receipt_digest": production_caps_receipt_digest,
            "labels_in_prediction_batch": False,
            "held_response_vault_read": False,
        }
        receipt["receipt_digest"] = digest_value(receipt)
        (stage / "receipt.json").write_bytes(_canonical(receipt) + b"\n")
        _publish_leaf(stage, destination, receipt)
        _write_json_exclusive(attempt / "completed.json", {
            "schema_version": "tasmania-pseudoabsence-conventional-fit-complete-v1",
            "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
            "completed_unix_ns": time.time_ns(),
        })
        return receipt
    except Exception as exc:
        _mark_fit_failure(private_root, "inner", task, attempt, exc)
        raise


def _lower_median(values: Sequence[int]) -> int:
    _require(len(values) == 5 and all(type(value) is int and 1 <= value <= 300 for value in values), "ann_epoch_inventory_invalid")
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def _inner_epoch(root: Path, task: OuterTask, held_fold: str, project_root: Path, production_caps_receipt_digest: str) -> int:
    inner = InnerTask(task.species, task.endpoint, task.family, task.candidate, held_fold, task.seed_label)
    receipt = _validated_leaf(
        root / "inner/leaves" / _task_digest(inner, "inner"), inner, "inner", project_root,
        production_caps_receipt_digest,
    )
    epoch = receipt.get("selected_epoch")
    _require(type(epoch) is int, "ann_inner_epoch_missing")
    return epoch


def _validated_self_digest(value: Mapping[str, Any], field: str, failure: str) -> str:
    body = dict(value)
    claimed = body.pop(field, None)
    _require(isinstance(claimed, str) and claimed == digest_value(body), failure)
    return claimed


def _accepted_selection_index(root: Path) -> tuple[
    Mapping[tuple[str, str, str], Mapping[str, Any]],
    Mapping[str, Mapping[str, Any]],
]:
    archive = root / ARCHIVE_REL
    archive_receipt_path = archive / "archive-receipt.json"
    goal037_path = archive / "evidence/dsdm_outer_ready/goal037/receipt.json"
    conventional_root = archive / "data/processed/dsdm/goal037-outer-ready/private/conventional"
    import_path = conventional_root / "import_receipt.json"
    reference_path = conventional_root / "producer-reference.json"
    for path, expected in (
        (archive_receipt_path, ARCHIVE_RECEIPT_SHA256),
        (goal037_path, GOAL037_RECEIPT_SHA256),
        (import_path, CONVENTIONAL_IMPORT_SHA256),
        (reference_path, PRODUCER_REFERENCE_SHA256),
    ):
        _require(path.is_file() and not path.is_symlink() and sha256_file(path) == expected, f"accepted_authority_drift:{path.name}")
    archive_receipt = _read_json(archive_receipt_path)
    goal037 = _read_json(goal037_path)
    imported = _read_json(import_path)
    reference = _read_json(reference_path)
    goal037_digest = _validated_self_digest(goal037, "receipt_digest", "goal037_receipt_digest_invalid")
    import_digest = _validated_self_digest(imported, "receipt_digest", "conventional_import_digest_invalid")
    reference_digest = _validated_self_digest(reference, "receipt_digest", "producer_reference_digest_invalid")
    _require(
        archive_receipt.get("success") is True
        and archive_receipt.get("authority_hashes", {}).get("goal036_conventional_selection") == SELECTION_SHA256
        and archive_receipt.get("execution_source_hashes", {}).get("uv_lock") == EXPECTED_DEPENDENCY_HASHES["uv.lock"]
        and goal037.get("success") is True
        and goal037.get("conventional_import_receipt_digest") == import_digest
        and imported.get("success") is True
        and imported.get("producer_reference_receipt_digest") == reference_digest
        and imported.get("selected_refits") == 952
        and reference.get("producer_commit") == PRODUCER_COMMIT
        and len(reference.get("records", ())) == 952,
        "accepted_authority_chain_invalid",
    )
    copy_root = root / ARCHIVE_REL / "data/processed/dsdm/goal037-outer-ready/private/conventional/copy"
    directory = copy_root / "selections"
    _require(directory.is_dir(), "accepted_conventional_selection_copy_missing")
    selection_index = _read_json(copy_root / "selection.json")
    family_records = selection_index.get("family_records")
    _require(isinstance(family_records, list) and len(family_records) == 280, "accepted_selection_index_invalid")
    index = {}
    tasks = []
    selection_receipts = []
    primary_seeds = {
        "intercept": ("seed00",), "elastic_net": SEEDS_BY_FAMILY["elastic_net"],
        "random_forest": SEEDS_BY_FAMILY["random_forest"],
        "hist_gradient_boosting": SEEDS_BY_FAMILY["hist_gradient_boosting"],
        "shallow_ann": SEEDS_BY_FAMILY["shallow_ann"],
    }
    for family_record in family_records:
        relative = Path(str(family_record.get("relative_path", "")))
        _require(
            not relative.is_absolute() and len(relative.parts) == 2
            and relative.parts[0] == "selections" and ".." not in relative.parts,
            "accepted_selection_path_invalid",
        )
        path = copy_root / relative
        value = _read_json(path)
        stratum = value.get("family_stratum", {})
        endpoint = f"{stratum.get('fraction_id')}/{stratum.get('ladder_id')}"
        key = (str(stratum.get("species_id", "")), endpoint, str(stratum.get("model_family", "")))
        _require(key not in index, "accepted_selection_duplicate")
        body = dict(value); claimed = body.pop("record_digest", None)
        _require(
            claimed == family_record.get("record_digest") == digest_value(body)
            and family_record.get("family_stratum") == stratum,
            "accepted_selection_record_digest_invalid",
        )
        family = str(stratum.get("model_family", ""))
        receipts = value.get("refit_receipts")
        _require(isinstance(receipts, list) and len(receipts) == len(primary_seeds.get(family, ())), "accepted_refit_seed_inventory_invalid")
        for receipt, seed_label in zip(receipts, primary_seeds[family], strict=True):
            expected_task = {
                "species_id": stratum["species_id"], "transform_id": "outer",
                "fraction_id": stratum["fraction_id"], "ladder_id": stratum["ladder_id"],
                "model_family": family, "candidate_id": value["selected_candidate_id"],
                "seed_label": seed_label,
            }
            _require(receipt.get("selected_task") == expected_task, "accepted_refit_task_invalid")
            tasks.append(expected_task)
            selection_receipts.append(receipt)
        index[key] = value
    _require(
        len(index) == 280 and len(tasks) == 952
        and digest_value(tasks) == imported.get("task_inventory_digest")
        and len(selection_receipts) == 952,
        "accepted_selection_inventory_invalid",
    )
    reference_index: dict[str, Mapping[str, Any]] = {}
    for record in reference["records"]:
        task = record.get("task")
        _require(isinstance(task, Mapping), "producer_reference_task_invalid")
        key = digest_value(task)
        _require(key not in reference_index, "producer_reference_duplicate_task")
        reference_index[key] = record
    _require(len(reference_index) == 952, "producer_reference_inventory_invalid")
    for receipt in selection_receipts:
        task = receipt["selected_task"]
        record = reference_index.get(digest_value(task))
        _require(
            record is not None and record.get("task") == task
            and record.get("model_sha256") == receipt.get("model_sha256")
            and record.get("challenge_digest") == receipt.get("challenge_digest")
            and record.get("prediction_digest") == receipt.get("canonical_prediction_bytes_sha256"),
            "accepted_selection_producer_reference_mismatch",
        )
    return index, reference_index


def _baseline_map_scores(foundation: Foundation, task: OuterTask, provider: Any, baseline_endpoint: Any) -> tuple[np.ndarray, Mapping[str, Any]]:
    index, reference_index = foundation.accepted_primary_authority()
    selection = index.get((task.species, task.endpoint, task.family))
    _require(selection is not None and selection.get("selected_candidate_id") == task.candidate, "accepted_baseline_selection_mismatch")
    receipt = next((item for item in selection.get("refit_receipts", ()) if item.get("selected_task", {}).get("seed_label") == task.seed_label), None)
    _require(isinstance(receipt, Mapping), "accepted_baseline_seed_missing")
    expected_task = {
        "species_id": task.species, "transform_id": "outer",
        "fraction_id": task.endpoint.split("/")[0], "ladder_id": task.endpoint.split("/")[1],
        "model_family": task.family, "candidate_id": task.candidate,
        "seed_label": task.seed_label,
    }
    _require(receipt.get("selected_task") == expected_task, "accepted_baseline_task_mismatch")
    reference = reference_index.get(digest_value(expected_task))
    _require(
        reference is not None
        and reference.get("task") == expected_task
        and reference.get("model_sha256") == receipt.get("model_sha256")
        and reference.get("challenge_digest") == receipt.get("challenge_digest")
        and reference.get("prediction_digest") == receipt.get("canonical_prediction_bytes_sha256"),
        "accepted_baseline_producer_reference_mismatch",
    )
    original_encoder = provider.fit_encoder(baseline_endpoint, task.family, "outer")
    _require(original_encoder["encoder_digest"] == receipt.get("encoder_digest"), "accepted_baseline_encoder_mismatch")
    original_map_batch = provider.materialize(foundation.map_rows(task.species), "outer", original_encoder)
    copy_root = foundation.root / ARCHIVE_REL / "data/processed/dsdm/goal037-outer-ready/private/conventional/copy"
    model_path = copy_root / str(receipt["bundle_path"]) / "model.model"
    model = foundation.adapters.load_fitted_model(model_path, str(receipt["model_sha256"]))
    envelope = _read_json(model_path)
    _require(envelope.get("identity_digest") == receipt.get("model_envelope_identity_digest"), "accepted_baseline_model_identity_mismatch")
    scores = model.predict_scores(original_map_batch)
    return scores, {
        "model_sha256": receipt["model_sha256"],
        "model_identity_digest": receipt["model_envelope_identity_digest"],
        "encoder_digest": original_encoder["encoder_digest"],
        "prediction_digest": _prediction_digest(foundation.map_cells, scores),
    }


def _fit_outer_task(
    foundation: Foundation,
    task: OuterTask,
    destination: Path,
    private_root: Path,
    production_caps_receipt_digest: str,
) -> Mapping[str, Any]:
    context = _outer_context(foundation, task)
    provider = foundation.provider(task.species)
    encoder = provider.fit_encoder(context["retained"], task.family, "outer")
    training_batch = provider.materialize(context["retained"], "outer", encoder)
    evaluation_batch = provider.materialize(context["evaluation"], "outer", encoder)
    _require(np.all(evaluation_batch.y == 0), "prediction_batch_labels_not_dummy")
    candidate = _candidate(foundation, task.family, task.candidate)
    TaskKey = foundation.contract.TaskKey
    key = TaskKey(task.species, "outer", *task.endpoint.split("/"), task.family, task.candidate, task.seed_label)
    seed = foundation.contract.derive_seed(key, "fit")
    exact_epoch = None
    inner_epochs = None
    if task.family == "shallow_ann":
        inner_epochs = [
            _inner_epoch(private_root, task, fold, foundation.root, production_caps_receipt_digest)
            for fold in FOLDS
        ]
        exact_epoch = _lower_median(inner_epochs)
    adapter = foundation.adapters.build_adapter(task.family)
    destination.parent.mkdir(parents=True, exist_ok=True)
    attempt, stage = _begin_fit_attempt(foundation.root, private_root, "outer", task, destination, ("outer",))
    try:
        _record_fit_start(attempt, task, "outer", 1)
        fitted, report = adapter.fit(training_batch, None, candidate, seed, exact_epochs=exact_epoch)
        _require(exact_epoch is None or report.iterations == exact_epoch, "outer_ann_epoch_mismatch")
        envelope = fitted.serialize(stage / "model.model")
        held_scores = fitted.predict_scores(evaluation_batch)
        _, model_semantic_digest = _reload_and_verify_model(
            foundation, stage / "model.model", fitted, evaluation_batch, held_scores,
        )
        held_keys = np.asarray([key.grid_cell_id for key in evaluation_batch.keys], dtype=str)
        arrays: dict[str, np.ndarray] = {"grid_cell_id": held_keys, "scores": np.asarray(held_scores, dtype=np.float64)}
        map_record = None
        baseline_record = None
        if task.endpoint == "fraction100/full":
            map_rows = foundation.map_rows(task.species)
            map_batch = provider.materialize(map_rows, "outer", encoder)
            map_scores = fitted.predict_scores(map_batch)
            baseline_scores, baseline_record = _baseline_map_scores(foundation, task, provider, context["baseline"])
            arrays.update({
                "map_grid_cell_id": np.asarray(foundation.map_cells, dtype=str),
                "map_scores": np.asarray(map_scores, dtype=np.float64),
                "baseline_map_scores": np.asarray(baseline_scores, dtype=np.float64),
            })
            map_record = {
                "rows": 71023,
                "prediction_digest": _prediction_digest(foundation.map_cells, map_scores),
                "cell_id_digest": hashlib.sha256("\n".join(foundation.map_cells).encode()).hexdigest(),
            }
        np.savez_compressed(stage / "predictions.npz", **arrays)
        (stage / "encoder.json").write_bytes(_canonical(encoder) + b"\n")
        receipt = {
            "schema_version": "tasmania-pseudoabsence-conventional-outer-leaf-v1",
            "task": asdict(task), "task_digest": _task_digest(task, "outer"),
            "process_id": os.getpid(),
            "process_nonce": PROCESS_NONCE,
            "physical_fits": 1, "fit_seed_uint32": seed,
            "candidate": candidate, "candidate_digest": digest_value(candidate),
            "endpoint_membership_digest": context["endpoint_digest"],
            "retained_outer_id_digest": _id_digest(context["retained"].keys),
            "evaluation_id_digest": _id_digest(context["evaluation"].keys),
            "encoder_digest": encoder["encoder_digest"],
            "encoder_sha256": sha256_file(stage / "encoder.json"),
            "feature_schema_digest": training_batch.feature_schema_digest,
            "transform_digest": training_batch.transform_digest,
            "input_digest": _batch_digest(training_batch),
            "evaluation_dummy_digest": _batch_digest(evaluation_batch),
            "inner_selected_epochs": inner_epochs,
            "outer_selected_epoch": exact_epoch,
            "fit_report": _report_payload(report),
            "model_sha256": sha256_file(stage / "model.model"),
            "model_semantic_digest": model_semantic_digest,
            "model_identity_digest": envelope["identity_digest"],
            "prediction_sha256": sha256_file(stage / "predictions.npz"),
            "prediction_digest": _prediction_digest(held_keys.tolist(), held_scores),
            "map": map_record,
            "accepted_primary_map": baseline_record,
            "bindings": _leaf_bindings(foundation.root),
            "preparation_receipt_digest": _current_preparation_digest(private_root),
            "production_caps_receipt_digest": production_caps_receipt_digest,
            "labels_in_prediction_batch": False,
            "held_response_vault_read": False,
        }
        receipt["receipt_digest"] = digest_value(receipt)
        (stage / "receipt.json").write_bytes(_canonical(receipt) + b"\n")
        _publish_leaf(stage, destination, receipt)
        _write_json_exclusive(attempt / "completed.json", {
            "schema_version": "tasmania-pseudoabsence-conventional-fit-complete-v1",
            "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
            "completed_unix_ns": time.time_ns(),
        })
        return receipt
    except Exception as exc:
        _mark_fit_failure(private_root, "outer", task, attempt, exc)
        raise


def _leaf_bindings(root: Path) -> Mapping[str, str]:
    return {
        "source_census_sha256": SOURCE_CENSUS_SHA256,
        "source_census_script_sha256": CENSUS_SCRIPT_SHA256,
        "auxiliary_recovery_sha256": RECOVERY_RECEIPT_SHA256,
        "selection_sha256": SELECTION_SHA256,
        "goal024_map_sha256": MAP_SHA256,
        "goal026_feature_contract_sha256": FEATURE_CONTRACT_SHA256,
        "goal026_fit_parameters_sha256": FIT_PARAMETERS_SHA256,
        "goal037_archive_receipt_sha256": ARCHIVE_RECEIPT_SHA256,
        "goal037_aggregate_receipt_sha256": GOAL037_RECEIPT_SHA256,
        "goal037_conventional_import_sha256": CONVENTIONAL_IMPORT_SHA256,
        "goal029_producer_reference_sha256": PRODUCER_REFERENCE_SHA256,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        **{f"source_{name}": value for name, value in EXPECTED_SOURCE_HASHES.items()},
        **{f"dependency_{name}": value for name, value in EXPECTED_DEPENDENCY_HASHES.items()},
    }


def _publish_leaf(stage: Path, destination: Path, receipt: Mapping[str, Any]) -> None:
    _require(not destination.exists(), "leaf_identity_collision")
    try:
        os.rename(stage, destination)
    except FileExistsError as exc:
        raise ConventionalSensitivityError("leaf_identity_collision") from exc


def _validated_leaf(
    path: Path,
    task: InnerTask | OuterTask,
    lane: str,
    root: Path,
    production_caps_receipt_digest: str | None = None,
) -> Mapping[str, Any]:
    _require(path.is_dir() and not path.is_symlink(), f"{lane}_leaf_missing")
    receipt = _read_json(path / "receipt.json")
    body = dict(receipt)
    claimed = body.pop("receipt_digest", None)
    _require(claimed == digest_value(body), f"{lane}_leaf_receipt_mismatch")
    _require(receipt.get("task") == asdict(task) and receipt.get("task_digest") == _task_digest(task, lane), f"{lane}_leaf_task_mismatch")
    expected_files = {"receipt.json", "model.model", "predictions.npz", "encoder.json"}
    if receipt.get("discovery_model_sha256") is not None:
        expected_files.add("discovery.model")
    _require(
        {item.name for item in path.iterdir()} == expected_files
        and not any(item.is_symlink() for item in path.iterdir()),
        f"{lane}_leaf_file_inventory_mismatch",
    )
    _require(receipt.get("bindings") == _leaf_bindings(root), f"{lane}_leaf_binding_mismatch")
    _require(
        receipt.get("preparation_receipt_digest") == _current_preparation_digest(path.parents[2]),
        f"{lane}_leaf_preparation_mismatch",
    )
    _require(
        receipt.get("production_caps_receipt_digest") == production_caps_receipt_digest,
        f"{lane}_leaf_production_caps_mismatch",
    )
    _require(sha256_file(path / "model.model") == receipt.get("model_sha256"), f"{lane}_leaf_model_mismatch")
    _require(sha256_file(path / "predictions.npz") == receipt.get("prediction_sha256"), f"{lane}_leaf_prediction_file_mismatch")
    encoder_path = path / "encoder.json"
    _require(encoder_path.is_file() and not encoder_path.is_symlink(), f"{lane}_leaf_encoder_missing")
    _require(sha256_file(encoder_path) == receipt.get("encoder_sha256"), f"{lane}_leaf_encoder_file_mismatch")
    encoder = _read_json(encoder_path)
    _require(
        encoder.get("encoder_digest") == receipt.get("encoder_digest")
        and encoder.get("feature_schema_digest") == receipt.get("feature_schema_digest")
        and encoder.get("transform_digest") == receipt.get("transform_digest"),
        f"{lane}_leaf_encoder_identity_mismatch",
    )
    if receipt.get("discovery_model_sha256") is not None:
        _require(sha256_file(path / "discovery.model") == receipt.get("discovery_model_sha256"), f"{lane}_leaf_discovery_model_mismatch")
    try:
        with np.load(path / "predictions.npz", allow_pickle=False) as loaded:
            files = set(loaded.files)
            expected = {"grid_cell_id", "scores"}
            if receipt.get("map") is not None:
                expected |= {"map_grid_cell_id", "map_scores", "baseline_map_scores"}
            _require(files == expected, f"{lane}_leaf_prediction_inventory_mismatch")
            keys = np.asarray(loaded["grid_cell_id"])
            scores = np.asarray(loaded["scores"], dtype=np.float64)
            _require(keys.ndim == scores.ndim == 1 and keys.dtype.kind == "U" and len(set(keys.tolist())) == len(keys), f"{lane}_leaf_prediction_shape_mismatch")
            _require(_prediction_digest(keys.tolist(), scores) == receipt.get("prediction_digest"), f"{lane}_leaf_prediction_digest_mismatch")
            if receipt.get("map") is not None:
                map_keys = np.asarray(loaded["map_grid_cell_id"])
                map_scores = np.asarray(loaded["map_scores"], dtype=np.float64)
                baseline_scores = np.asarray(loaded["baseline_map_scores"], dtype=np.float64)
                _require(map_keys.shape == map_scores.shape == baseline_scores.shape == (71023,), f"{lane}_leaf_map_shape_mismatch")
                _require(map_keys.dtype.kind == "U" and len(set(map_keys.tolist())) == 71023, f"{lane}_leaf_map_identity_mismatch")
                _require(_prediction_digest(map_keys.tolist(), map_scores) == receipt["map"]["prediction_digest"], f"{lane}_leaf_map_prediction_mismatch")
                _require(_prediction_digest(map_keys.tolist(), baseline_scores) == receipt["accepted_primary_map"]["prediction_digest"], f"{lane}_leaf_primary_map_prediction_mismatch")
    except (OSError, ValueError) as exc:
        raise ConventionalSensitivityError(f"{lane}_leaf_prediction_invalid") from exc
    return receipt


def prepare(root: Path, private_root: Path) -> Mapping[str, Any]:
    root = root.resolve()
    private_root = private_root.resolve()
    _require(private_root == (root / PRIVATE_REL).resolve() or private_root.is_relative_to(root / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private"), "private_root_outside_sensitivity")
    recovery = _load_recovery_closure(root)
    accepted_selections, producer_reference = _accepted_selection_index(root)
    foundation = Foundation(root)
    strata = _selection_inventory(root)
    inner, outer, counts = build_task_inventory(strata)
    # Construct every context here.  This independently rechecks all 336
    # memberships and 896 exact-subtraction roles before fitting is possible,
    # and freezes the 336 retained-row encoder identities before any fit.
    encoder_records = []
    for species in SPECIES:
        provider = foundation.provider(species)
        for task in inner:
            if task.species != species or task.seed_label != SEEDS_BY_FAMILY[task.family][0]:
                continue
            context = _inner_context(foundation, task)
            transform_id = f"cv_{task.held_fold}"
            encoder = provider.fit_encoder(context["replay"], task.family, transform_id)
            encoder_records.append({
                "scope": "inner", "species": species, "held_fold": task.held_fold,
                "endpoint": task.endpoint, "family": task.family,
                "retained_id_digest": _id_digest(context["replay"].keys),
                "encoder_digest": encoder["encoder_digest"],
                "feature_schema_digest": encoder["feature_schema_digest"],
                "transform_digest": encoder["transform_digest"],
            })
        for task in outer:
            if task.species != species or task.seed_label != SEEDS_BY_FAMILY[task.family][0]:
                continue
            context = _outer_context(foundation, task)
            encoder = provider.fit_encoder(context["retained"], task.family, "outer")
            encoder_records.append({
                "scope": "outer", "species": species, "held_fold": None,
                "endpoint": task.endpoint, "family": task.family,
                "retained_id_digest": _id_digest(context["retained"].keys),
                "encoder_digest": encoder["encoder_digest"],
                "feature_schema_digest": encoder["feature_schema_digest"],
                "transform_digest": encoder["transform_digest"],
            })
        del provider
    _require(len(encoder_records) == 336, "encoder_inventory_invalid")
    selection_records = [
        {**asdict(item), "candidate_parameters": _candidate(foundation, item.family, item.candidate)}
        for item in strata
    ]
    receipt = {
        "schema_version": "tasmania-pseudoabsence-conventional-preparation-v1",
        "success": True, "fitting": False, "scoring": False,
        "source_census_sha256": SOURCE_CENSUS_SHA256,
        "source_census_receipt_digest": digest_value(foundation.census_report),
        "selection_sha256": SELECTION_SHA256,
        "selected_strata": selection_records,
        "selected_strata_digest": digest_value(selection_records),
        "task_counts": counts,
        "inner_task_inventory_digest": digest_value([asdict(item) for item in inner]),
        "outer_task_inventory_digest": digest_value([asdict(item) for item in outer]),
        "membership_checks": {"inner": 280, "outer": 56, "roles": 896},
        "accepted_primary_authority": {
            "goal037_receipt_sha256": GOAL037_RECEIPT_SHA256,
            "conventional_import_sha256": CONVENTIONAL_IMPORT_SHA256,
            "producer_reference_sha256": PRODUCER_REFERENCE_SHA256,
            "selection_records": len(accepted_selections),
            "producer_reference_records": len(producer_reference),
        },
        "auxiliary_recovery": {
            "sha256": RECOVERY_RECEIPT_SHA256,
            "states": recovery["states"],
            "semantic_state_inventory_digest": recovery["semantic_state_inventory_digest"],
            "serialization_inventory_digest": recovery["serialization_inventory_digest"],
        },
        "encoder_records": encoder_records,
        "encoder_inventory_digest": digest_value(encoder_records),
        "evaluation_membership": foundation.census_report["evaluation_membership"],
        "bindings": _leaf_bindings(root),
        "execution_contract": {
            "producer_commit": PRODUCER_COMMIT,
            "default_producer_checkout": str(DEFAULT_PRODUCER_CHECKOUT),
            "required_runtime": dict(EXPECTED_RUNTIME),
            "workers": 4, "threads_per_worker": 1,
            "production_cap_enforcement": "external_parent_launcher_with_atomic_global_abort",
            "prediction_labels": "dummy_zero_only",
            "outer_held_response_vault_reads": 0,
        },
    }
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json_idempotent(private_root / "preparation.json", receipt)
    return receipt


def _load_preparation(root: Path, private_root: Path) -> Mapping[str, Any]:
    receipt = _read_json(private_root / "preparation.json")
    body = dict(receipt); claimed = body.pop("receipt_digest", None)
    _require(claimed == digest_value(body) and receipt.get("success") is True, "preparation_receipt_invalid")
    _require(receipt.get("bindings") == _leaf_bindings(root), "preparation_script_or_binding_drift")
    return receipt


def _smoke_tasks(strata: Sequence[SelectedStratum]) -> tuple[InnerTask, InnerTask]:
    lookup = {(item.species, item.endpoint): item for item in strata}
    rf = lookup[("dasyurus_viverrinus", "fraction100/full")]
    ann = lookup[("pseudocheirus_peregrinus", "fraction100/full")]
    _require((rf.family, rf.candidate) == ("random_forest", "rf00"), "rf_smoke_selection_drift")
    _require((ann.family, ann.candidate) == ("shallow_ann", "ann04"), "ann_smoke_selection_drift")
    return (
        InnerTask(rf.species, rf.endpoint, rf.family, rf.candidate, "fold01", "seed00"),
        InnerTask(ann.species, ann.endpoint, ann.family, ann.candidate, "fold01", "seed00"),
    )


def _smoke_equivalence(receipts: Sequence[Mapping[str, Any]], family: str) -> Mapping[str, Any]:
    _require(len(receipts) == 2, "smoke_repetition_count_invalid")
    keys = [
        "task", "physical_fits", "fit_seed_uint32", "candidate_digest",
        "endpoint_membership_digest", "retained_role_id_digests",
        "evaluation_id_digest", "encoder_digest", "feature_schema_digest",
        "transform_digest", "input_digests", "selected_epoch",
        "discovery_model_semantic_digest", "discovery_prediction_digest",
        "model_semantic_digest", "prediction_digest", "bindings",
    ]
    first = {key: receipts[0].get(key) for key in keys}
    second = {key: receipts[1].get(key) for key in keys}
    _require(first == second, f"smoke_repeat_mismatch:{family}")
    first_semantic = _semantic_report_payload(receipts[0])
    second_semantic = _semantic_report_payload(receipts[1])
    _require(first_semantic == second_semantic, f"smoke_report_mismatch:{family}")
    _require(receipts[0].get("process_nonce") != receipts[1].get("process_nonce"), f"smoke_process_not_clean:{family}")
    return {"family": family, "equivalence_digest": digest_value(first), "semantic_report_digest": digest_value(first_semantic)}


def _semantic_report_payload(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    out = {}
    for name in ("discovery_report", "replay_report"):
        value = receipt.get(name)
        if value is None:
            out[name] = None
        else:
            record = dict(value); record.pop("runtime_seconds", None); record.pop("peak_rss_bytes", None)
            out[name] = record
    return out


def smoke(root: Path, private_root: Path, producer_checkout: Path) -> Mapping[str, Any]:
    preparation = _load_preparation(root, private_root)
    _load_recovery_closure(root)
    runtime = _attest_execution_runtime(producer_checkout)
    strata = _selection_inventory(root)
    tasks = _smoke_tasks(strata)
    all_receipts = []
    comparisons = []
    for task in tasks:
        repeated = []
        for repetition in range(2):
            destination = private_root / "smoke/leaves" / f"{_task_digest(task, 'inner')}--repeat{repetition + 1}"
            if destination.exists():
                receipt = _validated_leaf(destination, task, "inner", root)
            else:
                command = [
                    sys.executable, str(Path(__file__).resolve()), "smoke-one",
                    "--root", str(root), "--private-root", str(private_root),
                    "--producer-checkout", str(producer_checkout),
                    "--smoke-family", task.family, "--smoke-repeat", str(repetition + 1),
                ]
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
                _require(completed.returncode == 0, f"smoke_subprocess_failed:{task.family}:repeat{repetition + 1}:{completed.stderr[-1000:]}")
                receipt = _validated_leaf(destination, task, "inner", root)
            repeated.append(receipt); all_receipts.append(receipt)
        comparisons.append(_smoke_equivalence(repeated, task.family))
    _require(sum(int(item["physical_fits"]) for item in all_receipts) == 6, "smoke_fit_count_mismatch")
    receipt = {
        "schema_version": "tasmania-pseudoabsence-conventional-smoke-v1",
        "success": True, "non_promotable": True,
        "preparation_receipt_digest": preparation["receipt_digest"],
        "runtime": runtime, "logical_tasks": 4, "physical_fits": 6,
        "comparisons": comparisons,
        "observed": {
            "maximum_fit_runtime_seconds": max(
                float(report.get("runtime_seconds", 0.0))
                for item in all_receipts for report in (item.get("discovery_report"), item.get("replay_report")) if report is not None
            ),
            "maximum_reported_peak_rss_bytes": max(
                int(report.get("peak_rss_bytes", 0))
                for item in all_receipts for report in (item.get("discovery_report"), item.get("replay_report")) if report is not None
            ),
            "private_bytes": sum(
                path.stat().st_size for path in (private_root / "smoke").rglob("*") if path.is_file()
            ),
        },
        "production_caps_assigned": False,
        "held_response_vault_read": False,
    }
    receipt["receipt_digest"] = digest_value(receipt)
    _write_json_idempotent(private_root / "smoke-qualification.json", receipt)
    return receipt


def smoke_one(
    root: Path,
    private_root: Path,
    producer_checkout: Path,
    family: str,
    repetition: int,
) -> Mapping[str, Any]:
    _require(family in ("random_forest", "shallow_ann") and repetition in (1, 2), "smoke_worker_scope_invalid")
    _load_preparation(root, private_root)
    _load_recovery_closure(root)
    _attest_execution_runtime(producer_checkout)
    tasks = {task.family: task for task in _smoke_tasks(_selection_inventory(root))}
    task = tasks[family]
    destination = private_root / "smoke/leaves" / f"{_task_digest(task, 'inner')}--repeat{repetition}"
    _require(not destination.exists(), "smoke_worker_destination_exists")
    foundation = Foundation(root)
    return _fit_inner_task(foundation, task, destination, private_root)


def _load_smoke(root: Path, private_root: Path, preparation: Mapping[str, Any]) -> Mapping[str, Any]:
    receipt = _read_json(private_root / "smoke-qualification.json")
    body = dict(receipt); claimed = body.pop("receipt_digest", None)
    _require(claimed == digest_value(body) and receipt.get("success") is True, "smoke_qualification_invalid")
    _require(receipt.get("preparation_receipt_digest") == preparation.get("receipt_digest"), "smoke_preparation_binding_mismatch")
    _require(receipt.get("physical_fits") == 6 and receipt.get("non_promotable") is True, "smoke_scope_mismatch")
    _require(receipt.get("held_response_vault_read") is False, "smoke_held_response_access")
    _require(receipt.get("runtime", {}).get("producer_commit") == PRODUCER_COMMIT, "smoke_runtime_binding_mismatch")
    _require(receipt.get("runtime", {}).get("versions") == EXPECTED_RUNTIME, "smoke_runtime_version_mismatch")
    _require(receipt.get("runtime", {}).get("source_hashes") == EXPECTED_SOURCE_HASHES, "smoke_source_binding_mismatch")
    _require(receipt.get("runtime", {}).get("dependency_hashes") == EXPECTED_DEPENDENCY_HASHES, "smoke_dependency_binding_mismatch")
    _require(receipt.get("comparisons") and len(receipt["comparisons"]) == 2, "smoke_repeat_evidence_missing")
    return receipt


def _load_production_caps(
    root: Path,
    private_root: Path,
    preparation: Mapping[str, Any],
    smoke_receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    receipt = _read_json(private_root / "production-caps.json")
    claimed = _validated_self_digest(receipt, "receipt_digest", "production_caps_digest_invalid")
    caps = receipt.get("caps")
    observed = smoke_receipt.get("observed", {})
    _require(
        receipt.get("schema_version") == "tasmania-pseudoabsence-conventional-production-caps-v1"
        and receipt.get("status") == "assigned"
        and receipt.get("enforcement") == "external_parent_launcher_with_atomic_global_abort"
        and receipt.get("preparation_receipt_digest") == preparation.get("receipt_digest")
        and receipt.get("smoke_receipt_digest") == smoke_receipt.get("receipt_digest")
        and receipt.get("auxiliary_recovery_sha256") == RECOVERY_RECEIPT_SHA256
        and receipt.get("runtime_versions") == EXPECTED_RUNTIME
        and isinstance(caps, Mapping),
        "production_caps_binding_invalid",
    )
    _require(caps.get("max_workers") == 4 and caps.get("threads_per_worker") == 1, "production_worker_caps_invalid")
    for name in ("wall_time_seconds", "peak_rss_bytes", "private_storage_bytes"):
        _require(type(caps.get(name)) in (int, float) and caps[name] > 0, f"production_cap_invalid:{name}")
    _require(caps["wall_time_seconds"] >= observed.get("maximum_fit_runtime_seconds", 0), "production_wall_cap_below_smoke")
    _require(caps["peak_rss_bytes"] >= observed.get("maximum_reported_peak_rss_bytes", 0), "production_rss_cap_below_smoke")
    _require(caps["private_storage_bytes"] >= observed.get("private_bytes", 0), "production_storage_cap_below_smoke")
    return {**receipt, "receipt_digest": claimed}


def _shard(tasks: Sequence[Any], shard_index: int, shard_count: int) -> tuple[Any, ...]:
    _require(type(shard_count) is int and 1 <= shard_count <= 4, "shard_count_invalid")
    _require(type(shard_index) is int and 0 <= shard_index < shard_count, "shard_index_invalid")
    return tuple(task for index, task in enumerate(tasks) if index % shard_count == shard_index)


def _validate_fit_attempt_inventory(
    root: Path,
    private_root: Path,
    lane: str,
    tasks: Sequence[InnerTask | OuterTask],
    receipts: Mapping[str, Mapping[str, Any]],
    expected_fits: int,
) -> Mapping[str, Any] | None:
    _ensure_run_active(private_root)
    lane_root = private_root / lane
    intent_root = lane_root / "intents"
    attempt_root = lane_root / "attempts"
    expected_keys = {_task_digest(task, lane) for task in tasks}
    intent_entries = list(intent_root.iterdir()) if intent_root.is_dir() else []
    attempt_entries = list(attempt_root.iterdir()) if attempt_root.is_dir() else []
    _require(
        {path.name for path in intent_entries} == {f"{key}.json" for key in expected_keys}
        and all(path.is_file() and not path.is_symlink() for path in intent_entries),
        f"{lane}_fit_intent_inventory_mismatch",
    )
    _require(
        {path.name for path in attempt_entries} == expected_keys
        and all(path.is_dir() and not path.is_symlink() for path in attempt_entries),
        f"{lane}_fit_attempt_inventory_mismatch",
    )
    if any(not (attempt_root / key / "completed.json").is_file() for key in expected_keys):
        return None
    fit_starts = 0
    completion_records = []
    current_preparation = _current_preparation_digest(private_root)
    current_bindings = _leaf_bindings(root)
    for task in tasks:
        key = _task_digest(task, lane)
        receipt = receipts[key]
        intent = _read_json(intent_root / f"{key}.json")
        _validated_self_digest(intent, "intent_digest", f"{lane}_fit_intent_digest_invalid")
        expected_stages = (
            ("discovery", "replay")
            if lane == "inner" and task.family == "shallow_ann"
            else (("replay",) if lane == "inner" else ("outer",))
        )
        _require(
            intent.get("schema_version") == "tasmania-pseudoabsence-conventional-fit-intent-v1"
            and intent.get("lane") == lane
            and intent.get("task") == asdict(task)
            and intent.get("task_digest") == key
            and intent.get("destination") == f"{lane}/leaves/{key}"
            and intent.get("physical_stages") == list(expected_stages)
            and intent.get("fit_started") is False
            and intent.get("bindings") == current_bindings
            and intent.get("preparation_receipt_digest") == current_preparation,
            f"{lane}_fit_intent_invalid",
        )
        attempt = attempt_root / key
        _require(
            {item.name for item in attempt.iterdir()} == {"fit-starts", "completed.json"}
            and not any(item.is_symlink() for item in attempt.iterdir()),
            f"{lane}_fit_attempt_not_clean",
        )
        start_root = attempt / "fit-starts"
        expected_start_names = {
            f"{number:02d}-{stage}.json"
            for number, stage in enumerate(expected_stages, start=1)
        }
        start_entries = list(start_root.iterdir())
        _require(
            {item.name for item in start_entries} == expected_start_names
            and all(item.is_file() and not item.is_symlink() for item in start_entries),
            f"{lane}_fit_start_inventory_mismatch",
        )
        for number, stage in enumerate(expected_stages, start=1):
            start = _read_json(start_root / f"{number:02d}-{stage}.json")
            _require(
                start.get("schema_version") == "tasmania-pseudoabsence-conventional-fit-start-v1"
                and start.get("task") == asdict(task)
                and start.get("stage") == stage
                and start.get("physical_fit_number") == number
                and type(start.get("started_unix_ns")) is int,
                f"{lane}_fit_start_invalid",
            )
            fit_starts += 1
        completed = _read_json(attempt / "completed.json")
        _require(
            completed.get("schema_version") == "tasmania-pseudoabsence-conventional-fit-complete-v1"
            and completed.get("task_digest") == key
            and completed.get("receipt_digest") == receipt.get("receipt_digest")
            and type(completed.get("completed_unix_ns")) is int,
            f"{lane}_fit_completion_invalid",
        )
        completion_records.append({
            "task_digest": key,
            "intent_digest": intent["intent_digest"],
            "receipt_digest": receipt["receipt_digest"],
            "physical_fit_starts": len(expected_stages),
        })
    _require(fit_starts == expected_fits, f"{lane}_fit_start_total_mismatch")
    return {
        "logical_intents": len(expected_keys),
        "completion_records": len(completion_records),
        "physical_fit_starts": fit_starts,
        "inventory_digest": digest_value(completion_records),
    }


def _close_lane(
    root: Path,
    private_root: Path,
    lane: str,
    tasks: Sequence[InnerTask | OuterTask],
    expected_fits: int,
    production_caps_receipt_digest: str,
) -> Mapping[str, Any] | None:
    _ensure_run_active(private_root)
    records = []
    receipt_by_task = {}
    for task in tasks:
        path = private_root / lane / "leaves" / _task_digest(task, lane)
        if not path.is_dir():
            return None
        receipt = _validated_leaf(path, task, lane, root, production_caps_receipt_digest)
        receipt_by_task[receipt["task_digest"]] = receipt
        records.append({
            "task_digest": receipt["task_digest"], "receipt_digest": receipt["receipt_digest"],
            "model_sha256": receipt["model_sha256"], "prediction_digest": receipt["prediction_digest"],
            "physical_fits": receipt["physical_fits"],
        })
    leaf_root = private_root / lane / "leaves"
    leaf_entries = list(leaf_root.iterdir())
    _require(
        {item.name for item in leaf_entries} == {_task_digest(task, lane) for task in tasks}
        and all(item.is_dir() and not item.is_symlink() for item in leaf_entries),
        f"{lane}_leaf_directory_inventory_mismatch",
    )
    _require(sum(int(item["physical_fits"]) for item in records) == expected_fits, f"{lane}_physical_fit_inventory_mismatch")
    attempt_inventory = _validate_fit_attempt_inventory(
        root, private_root, lane, tasks, receipt_by_task, expected_fits,
    )
    if attempt_inventory is None:
        return None
    if lane == "outer":
        _require(sum(_read_json(private_root / lane / "leaves" / item["task_digest"] / "receipt.json").get("map") is not None for item in records) == 32, "outer_map_seed_inventory_mismatch")
    closure = {
        "schema_version": f"tasmania-pseudoabsence-conventional-{lane}-closure-v1",
        "success": True, "lane": lane, "logical_tasks": len(tasks),
        "physical_fits": expected_fits, "records": records,
        "inventory_digest": digest_value(records), "held_response_vault_read": False,
        "fit_attempt_inventory": attempt_inventory,
        "production_caps_receipt_digest": production_caps_receipt_digest,
        "bindings": _leaf_bindings(root),
    }
    closure["receipt_digest"] = digest_value(closure)
    _write_json_idempotent(private_root / f"{lane}-closure.json", closure)
    return closure


def run_inner(root: Path, private_root: Path, producer_checkout: Path, shard_index: int, shard_count: int) -> Mapping[str, Any]:
    preparation = _load_preparation(root, private_root)
    _load_recovery_closure(root)
    smoke_receipt = _load_smoke(root, private_root, preparation)
    caps = _load_production_caps(root, private_root, preparation, smoke_receipt)
    _require(shard_count <= caps["caps"]["max_workers"], "shard_count_exceeds_production_cap")
    _ensure_run_active(private_root)
    runtime = _attest_execution_runtime(producer_checkout)
    _require(runtime["versions"] == smoke_receipt["runtime"]["versions"], "runtime_drift_after_smoke")
    strata = _selection_inventory(root)
    tasks, _, counts = build_task_inventory(strata)
    selected = _shard(tasks, shard_index, shard_count)
    foundation = Foundation(root)
    completed = 0
    reused = 0
    for task in selected:
        _ensure_run_active(private_root)
        destination = private_root / "inner/leaves" / _task_digest(task, "inner")
        if destination.exists():
            _validated_leaf(destination, task, "inner", root, caps["receipt_digest"]); reused += 1
        else:
            _fit_inner_task(foundation, task, destination, private_root, caps["receipt_digest"]); completed += 1
    closure = _close_lane(root, private_root, "inner", tasks, counts["inner_physical_fits"], caps["receipt_digest"])
    return {
        "success": True, "lane": "inner", "shard_index": shard_index, "shard_count": shard_count,
        "assigned_tasks": len(selected), "new_tasks": completed, "reused_tasks": reused,
        "closed": closure is not None, "closure_receipt_digest": closure.get("receipt_digest") if closure else None,
    }


def run_outer(root: Path, private_root: Path, producer_checkout: Path, shard_index: int, shard_count: int) -> Mapping[str, Any]:
    preparation = _load_preparation(root, private_root)
    _load_recovery_closure(root)
    smoke_receipt = _load_smoke(root, private_root, preparation)
    caps = _load_production_caps(root, private_root, preparation, smoke_receipt)
    _require(shard_count <= caps["caps"]["max_workers"], "shard_count_exceeds_production_cap")
    _ensure_run_active(private_root)
    runtime = _attest_execution_runtime(producer_checkout)
    _require(runtime["versions"] == smoke_receipt["runtime"]["versions"], "runtime_drift_after_smoke")
    strata = _selection_inventory(root)
    inner_tasks, tasks, counts = build_task_inventory(strata)
    inner_closure = _close_lane(
        root, private_root, "inner", inner_tasks, counts["inner_physical_fits"], caps["receipt_digest"],
    )
    _require(inner_closure is not None, "inner_closure_required")
    selected = _shard(tasks, shard_index, shard_count)
    foundation = Foundation(root)
    completed = 0
    reused = 0
    for task in selected:
        _ensure_run_active(private_root)
        destination = private_root / "outer/leaves" / _task_digest(task, "outer")
        if destination.exists():
            _validated_leaf(destination, task, "outer", root, caps["receipt_digest"]); reused += 1
        else:
            _fit_outer_task(foundation, task, destination, private_root, caps["receipt_digest"]); completed += 1
    closure = _close_lane(root, private_root, "outer", tasks, counts["outer_physical_fits"], caps["receipt_digest"])
    return {
        "success": True, "lane": "outer", "shard_index": shard_index, "shard_count": shard_count,
        "assigned_tasks": len(selected), "new_tasks": completed, "reused_tasks": reused,
        "closed": closure is not None, "closure_receipt_digest": closure.get("receipt_digest") if closure else None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "smoke", "smoke-one", "run-inner", "run-outer"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--private-root", type=Path)
    parser.add_argument("--producer-checkout", type=Path, default=DEFAULT_PRODUCER_CHECKOUT)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--smoke-family", choices=("random_forest", "shallow_ann"))
    parser.add_argument("--smoke-repeat", type=int)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    private_root = args.private_root.resolve() if args.private_root else (root / PRIVATE_REL).resolve()
    if args.stage == "prepare":
        result = prepare(root, private_root)
    elif args.stage == "smoke":
        result = smoke(root, private_root, args.producer_checkout)
    elif args.stage == "smoke-one":
        result = smoke_one(
            root, private_root, args.producer_checkout,
            str(args.smoke_family), int(args.smoke_repeat or 0),
        )
    elif args.stage == "run-inner":
        result = run_inner(root, private_root, args.producer_checkout, args.shard_index, args.shard_count)
    else:
        result = run_outer(root, private_root, args.producer_checkout, args.shard_index, args.shard_count)
    print(_canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ConventionalSensitivityError", "Foundation", "InnerTask", "OuterTask",
    "SelectedStratum", "build_task_inventory", "filter_without_pseudoabsence",
    "prepare", "run_inner", "run_outer", "smoke", "smoke_one",
]
