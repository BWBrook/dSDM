"""Aggregate training-response census for the Tasmania pseudoabsence sensitivity.

This module deliberately has no model, prediction, or response-vault opening
path.  It reads the allowlisted training responses, excludes held-response
labels, reconstructs the original unfiltered RowSets from the archived
Goal025/Goal026 identity boundary, checks every accepted inner and outer ladder
digest, and reports only aggregate source/class counts and digests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence


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
FOLDS = tuple(f"fold{i:02d}" for i in range(5))
ENDPOINTS = (
    "fraction25/ladder00",
    "fraction25/ladder01",
    "fraction25/ladder02",
    "fraction50/ladder00",
    "fraction50/ladder01",
    "fraction50/ladder02",
    "fraction100/full",
)
ROLES = ("discovery", "stopping", "replay", "outer_fit")
SOURCE_VALUES = ("presence", "survey_supported_absence", "pseudoabsence")
ARCHIVE_REL = Path("data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1")
INNER_BUNDLE_REL = Path("data/processed/dsdm/goal035-final-inner-lifecycle/private")
OUTER_BUNDLE_REL = Path("data/processed/dsdm/goal037-outer-ready/private/bundles")


class CensusError(ValueError):
    """Raised when the training-response census cannot establish its contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_archived_contract(root: Path):
    """Load archived helpers in an isolated namespace, without live imports."""
    source = (root / ARCHIVE_REL / "src").resolve()
    if not source.is_dir():
        raise CensusError("archived_goal037_source_missing")
    namespace = "_tasmania_census_archive_" + hashlib.sha256(str(source).encode()).hexdigest()[:16]
    package = ModuleType(namespace)
    package.__path__ = [str(source / "dsdm_phase1")]
    sys.modules[namespace] = package
    modules = []
    for name in ("modeling_contract", "target_subsets"):
        qualified = f"{namespace}.{name}"
        spec = importlib.util.spec_from_file_location(qualified, source / "dsdm_phase1" / f"{name}.py")
        _require(spec is not None and spec.loader is not None, "archived_rowset_import_failed")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        modules.append(module)
    modeling_contract, target_subsets = modules
    _require(Path(modeling_contract.__file__).resolve() == source / "dsdm_phase1/modeling_contract.py", "archived_modeling_contract_path_mismatch")
    _require(Path(target_subsets.__file__).resolve() == source / "dsdm_phase1/target_subsets.py", "archived_target_subsets_path_mismatch")
    RowKey, RowSet, build_ladders = modeling_contract.RowKey, modeling_contract.RowSet, target_subsets.build_ladders
    return RowKey, RowSet, build_ladders


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CensusError(message)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _prefix_key(line: str) -> tuple[str, str]:
    """Read only the two identity columns, leaving held payload opaque."""
    parts = line.rstrip("\r\n").split(",", 2)
    if len(parts) < 2:
        raise CensusError("canonical_response_identity_prefix_invalid")
    return parts[0], parts[1]


def _read_allowlisted_response_rows(path: Path, allowlist: set[tuple[str, str]], assignments: Mapping[str, Mapping[str, str]]) -> list[dict[str, Any]]:
    """Parse canonical response fields only after identity allowlisting.

    The prefix parser intentionally does not materialize the held row payload.
    A held response row therefore cannot supply pa, pa_type, or any source field
    to this census.
    """
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        header_line = handle.readline()
        if not header_line:
            raise CensusError("canonical_response_header_missing")
        header = next(csv.reader([header_line]))
        _require(header[:2] == ["species_id", "grid_cell_id"], "canonical_response_identity_prefix_invalid")
        expected = {"species_id", "grid_cell_id", "pa", "pa_type"}
        _require(expected <= set(header), "canonical_response_schema_missing")
        for line in handle:
            species, cell = _prefix_key(line)
            key = (species, cell)
            if key not in allowlist:
                continue
            if key in seen:
                raise CensusError("duplicate_allowlisted_response_identity")
            values = next(csv.reader([line]))
            row = dict(zip(header, values, strict=True))
            assignment = assignments.get(cell)
            _require(assignment is not None, "allowlisted_cell_assignment_missing")
            _require(row.get("species_id") == species and row.get("grid_cell_id") == cell, "canonical_response_identity_drift")
            try:
                pa = int(row["pa"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CensusError("canonical_response_pa_invalid") from exc
            _require(pa in (0, 1), "canonical_response_pa_invalid")
            source = str(row.get("pa_type", ""))
            _require(source in SOURCE_VALUES, "canonical_response_source_invalid")
            _require((pa == 1 and source == "presence") or (pa == 0 and source != "presence"), "canonical_response_pa_source_mismatch")
            rows.append({
                "species_id": species,
                "grid_cell_id": cell,
                "pa": pa,
                "pa_type": source,
                "microcluster": str(assignment["microcluster"]),
                "cv_fold": str(assignment.get("cv_fold", "")),
            })
            seen.add(key)
    _require(seen == allowlist, "allowlisted_response_inventory_mismatch")
    return rows


def _id_digest(keys: Iterable[Any]) -> str:
    tokens = sorted(f"{key.species_id}\x1f{key.grid_cell_id}" for key in keys)
    return hashlib.sha256("\n".join(tokens).encode()).hexdigest()


def _ordered_digest(keys: Iterable[Any]) -> str:
    tokens = [f"{key.species_id}\x1f{key.grid_cell_id}" for key in keys]
    return hashlib.sha256("\n".join(tokens).encode()).hexdigest()


def verify_membership_digest(actual: str, expected: str, label: str) -> None:
    """Fail closed when an accepted endpoint membership digest differs."""
    if actual != expected:
        raise CensusError(f"membership_digest_mismatch:{label}")


def filter_rowset_without_pseudoabsence(rows: Any) -> tuple[Any, tuple[Any, ...]]:
    """Return exact pseudoabsence subtraction and excluded RowKeys.

    A missing retained class is refused.  Callers may catch CensusError to
    record the failure, but no caller may silently pool or drop that role.
    """
    keep = [index for index, source in enumerate(rows.response_source) if source != "pseudoabsence"]
    excluded = tuple(rows.keys[index] for index, source in enumerate(rows.response_source) if source == "pseudoabsence")
    retained = rows.take(keep)
    if len(set(int(value) for value in retained.pa.tolist())) != 2:
        raise CensusError("missing_class_after_pseudoabsence_removal")
    if any(int(rows.pa[index]) != 0 for index, source in enumerate(rows.response_source) if source == "pseudoabsence"):
        raise CensusError("pseudoabsence_positive_class_mismatch")
    _require(set(retained.keys) | set(excluded) == set(rows.keys), "pseudoabsence_subtraction_union_mismatch")
    _require(set(retained.keys).isdisjoint(excluded), "pseudoabsence_subtraction_overlap")
    return retained, excluded


def _counts(rows: Any) -> dict[str, dict[str, int]]:
    classes = Counter(str(int(value)) for value in rows.pa.tolist())
    sources = Counter(str(value) for value in rows.response_source)
    return {
        "rows": int(len(rows.keys)),
        "class": {str(key): int(classes.get(key, 0)) for key in ("0", "1")},
        "source": {key: int(sources.get(key, 0)) for key in SOURCE_VALUES},
    }


def _role_record(*, species: str, held_fold: str | None, endpoint: str, role: str, rows: Any, expected_digest: str | None) -> dict[str, Any]:
    actual = rows
    baseline = _counts(actual)
    try:
        retained, excluded_keys = filter_rowset_without_pseudoabsence(actual)
    except CensusError as exc:
        excluded_keys = tuple(key for key, source in zip(actual.keys, actual.response_source, strict=True) if source == "pseudoabsence")
        retained = None
        failure = str(exc)
    else:
        failure = None
    expected = expected_digest
    record = {
        "species": species,
        "held_fold": held_fold,
        "endpoint": endpoint,
        "role": role,
        "membership_digest": _ordered_digest(actual.keys),
        "endpoint_membership_digest": expected,
        "baseline_id_set_digest": _id_digest(actual.keys),
        "excluded_id_set_digest": _id_digest(excluded_keys),
        "baseline": baseline,
        "excluded": {
            "rows": int(len(excluded_keys)),
            "class": {"0": 0, "1": 0},
            "source": {"pseudoabsence": 0, "presence": 0, "survey_supported_absence": 0},
        },
        "failure": failure,
    }
    excluded_index = {key: index for index, key in enumerate(actual.keys)}
    for key in excluded_keys:
        index = excluded_index[key]
        record["excluded"]["class"][str(int(actual.pa[index]))] += 1
        record["excluded"]["source"][str(actual.response_source[index])] += 1
    if retained is not None:
        record["retained_id_set_digest"] = _id_digest(retained.keys)
        record["retained"] = _counts(retained)
        _require(record["retained"]["rows"] + record["excluded"]["rows"] == baseline["rows"], "pseudoabsence_subtraction_count_mismatch")
        _require(record["retained"]["class"]["0"] + record["excluded"]["class"]["0"] == baseline["class"]["0"], "pseudoabsence_subtraction_class_mismatch")
    else:
        record["retained_id_set_digest"] = None
        record["retained"] = None
    return record


def _bundle_inventory(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Verify the metadata commitment without accessing response arrays.

    The recorded array hashes participate in the accepted bundle commitment;
    validating their numerical payloads belongs to subsequent fit qualification.
    """
    import numpy as np

    _require(path.is_file() and not path.is_symlink(), f"bundle_missing:{path.name}")
    with np.load(path, allow_pickle=False) as loaded:
        _require("metadata_json" in loaded.files, "bundle_metadata_field_missing")
        metadata = json.loads(np.asarray(loaded["metadata_json"], dtype=np.uint8).tobytes().decode("utf-8"))
    _require(isinstance(metadata, dict), "bundle_metadata_schema_invalid")
    array_inventory = metadata.get("array_digests")
    _require(isinstance(array_inventory, dict) and bool(array_inventory), f"bundle_array_inventory_missing:{path.name}")
    body = dict(metadata)
    claimed = body.pop("bundle_digest", None)
    _require(isinstance(claimed, str), f"bundle_digest_missing:{path.name}")
    _require(claimed == digest_value({"metadata": body, "arrays": array_inventory}), f"bundle_digest_mismatch:{path.name}")
    return metadata, array_inventory


def _validate_bundle_identity(path: Path, metadata: Mapping[str, Any], *, species: str, held_fold: str | None, expected_config: str, expected_source_binding: str) -> None:
    _require(metadata.get("target") == species, f"bundle_target_mismatch:{path.name}")
    if held_fold is not None:
        expected_partition = {
            "held": held_fold,
            "stopping": f"fold{(int(held_fold[-2:]) + 1) % 5:02d}",
            "discovery": sorted(set(FOLDS) - {held_fold, f"fold{(int(held_fold[-2:]) + 1) % 5:02d}"}),
            "replay": sorted(set(FOLDS) - {held_fold}),
        }
        _require(metadata.get("case_id") == f"{species}--{held_fold}" and metadata.get("held_fold") == held_fold, f"bundle_case_identity_mismatch:{path.name}")
        _require(metadata.get("fold_partition") == expected_partition, f"bundle_fold_partition_mismatch:{path.name}")
        _require(metadata.get("config_digest") == expected_config and metadata.get("source_binding_digest") == expected_source_binding, f"bundle_binding_mismatch:{path.name}")
    else:
        _require(metadata.get("goal035_config_sha256") == "87c3afa6fbb9a2177caafc0b2aacb0130c7f6545523839cd0fd030218795d7c2", f"outer_goal035_config_mismatch:{path.name}")
        _require(metadata.get("source_binding_digest") == "e8997e6b899d35a39bd496e9442b18dbeeaa126475565c45cf294bfb82d520c1", f"outer_source_binding_mismatch:{path.name}")
    _require(metadata.get("outer_attempted") == 0 and metadata.get("outer_opened") == 0, f"bundle_outer_access_drift:{path.name}")


def _validate_saved_bundle_inventories(root: Path, inner_metadata: Mapping[tuple[str, str], Mapping[str, Any]], outer_metadata: Mapping[str, Mapping[str, Any]], paths: Mapping[str, Path]) -> None:
    aggregate = json.loads(paths["goal035_aggregate"].read_text(encoding="utf-8"))
    receipt = json.loads(paths["goal037_receipt"].read_text(encoding="utf-8"))
    inner_inventory = digest_value(sorted(str(metadata["bundle_digest"]) for metadata in inner_metadata.values()))
    outer_inventory = digest_value([{"target": species, "bundle_digest": str(outer_metadata[species]["bundle_digest"])} for species in SPECIES])
    _require(inner_inventory == aggregate.get("bundle_inventory_digest"), "goal035_bundle_inventory_mismatch")
    _require(outer_inventory == receipt.get("bundle_inventory_digest"), "goal037_bundle_inventory_mismatch")


def _load_bindings(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    paths = {
        "assessment_config": root / "config/tasmania_outer_assessment.json",
        "response_partitioned": root / "data/processed/partitions/goal025-spatial-partition/2026-07-26/response_partitioned.csv",
        "response_support": root / "data/processed/features/goal026-model-ready-feature-substrate/2026-07-27/response_support.csv",
        "response_cell_assignments": root / "data/processed/partitions/goal025-spatial-partition/2026-07-26/response_cell_assignments.csv",
        "goal035_aggregate": root / "evidence/dsdm_final_inner_lifecycle/goal035/aggregate.json",
        "goal037_receipt": root / "evidence/dsdm_outer_ready/goal037/receipt.json",
        "archive_receipt": root / ARCHIVE_REL / "archive-receipt.json",
        "archived_modeling_contract": root / ARCHIVE_REL / "src/dsdm_phase1/modeling_contract.py",
        "archived_target_subsets": root / ARCHIVE_REL / "src/dsdm_phase1/target_subsets.py",
    }
    for name, path in paths.items():
        _require(path.is_file(), f"binding_missing:{name}")
    digests = {name: sha256_file(path) for name, path in paths.items()}
    config = json.loads(paths["assessment_config"].read_text(encoding="utf-8"))
    _require(digests["assessment_config"] == "0913b323f1c53addee4cc7c0f181e850ee08ff5fe0fcbdd776450652f13e7a48", "assessment_config_binding_mismatch")
    _require(digests["archive_receipt"] == "b75a61a31e052477617dedd6b2b3e0d763d727dc85f04d49b5a2bcf4d8099eac", "archive_receipt_binding_mismatch")
    response_free = config.get("response_free_inputs", {})
    _require(response_free.get("response_support", {}).get("sha256") == digests["response_support"] == "6f4b246cf3acd24e164118101b762e506a268a4897b34dd316821c2d3778c3d8", "response_support_binding_mismatch")
    _require(response_free.get("response_cell_assignments", {}).get("sha256") == digests["response_cell_assignments"] == "f74b1df0ce62b71ee0b0c96b2f51060bfed370eece628dfb1c83d7eea5d6ab84", "response_cell_assignments_binding_mismatch")
    _require(config.get("response_vault", {}).get("sha256") == digests["response_partitioned"] == "b93fbdfa4df2b2d8617dd890cdb7fc4c3aa54ed10c72eed9c9ebc93df18edafc", "response_partitioned_binding_mismatch")
    archive = json.loads(paths["archive_receipt"].read_text(encoding="utf-8"))
    _require(archive.get("assessment_config_sha256") == digests["assessment_config"], "archive_config_binding_mismatch")
    _require(archive.get("execution_source_hashes", {}).get("modeling_contract") == digests["archived_modeling_contract"], "archive_modeling_contract_binding_mismatch")
    _require(archive.get("execution_source_hashes", {}).get("target_subsets") == digests["archived_target_subsets"], "archive_target_subsets_binding_mismatch")
    aggregate = json.loads(paths["goal035_aggregate"].read_text(encoding="utf-8"))
    goal037 = json.loads(paths["goal037_receipt"].read_text(encoding="utf-8"))
    archive_authorities = archive.get("authority_hashes", {})
    _require(archive_authorities.get("goal035_aggregate") == digests["goal035_aggregate"], "goal035_aggregate_binding_mismatch")
    _require(all(archive_authorities.get(key) == value for key, value in aggregate.get("authority_digests", {}).items() if key in archive_authorities), "goal035_authority_binding_mismatch")
    _require(goal037.get("authority_digests") == archive_authorities, "goal037_authority_binding_mismatch")
    _require(config.get("goal037", {}).get("bindings", {}).get("config", {}).get("sha256") == goal037.get("config_digest"), "goal037_config_binding_mismatch")
    _require(config.get("goal037", {}).get("bindings", {}).get("receipt", {}).get("sha256") == sha256_file(paths["goal037_receipt"]), "goal037_receipt_binding_mismatch")
    return paths, digests


def _allowlist_from_response_free_inputs(paths: Mapping[str, Path]) -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[str, dict[str, str]]]:
    support = _read_csv(paths["response_support"])
    assignments_rows = _read_csv(paths["response_cell_assignments"])
    assignments: dict[str, dict[str, str]] = {}
    for row in assignments_rows:
        cell = str(row.get("grid_cell_id", ""))
        _require(cell and cell not in assignments, "duplicate_response_cell_assignment")
        assignments[cell] = row
    train = {
        (str(row["species_id"]), str(row["grid_cell_id"]))
        for row in support
        if row.get("transform_id") == "outer" and row.get("outer_role") == "outer_train"
    }
    test = {
        (str(row["species_id"]), str(row["grid_cell_id"]))
        for row in support
        if row.get("transform_id") == "outer" and row.get("outer_role") == "test"
    }
    _require(train and test and train.isdisjoint(test), "response_free_outer_membership_invalid")
    _require(all(cell in assignments and assignments[cell].get("outer_role") == "outer_train" for _, cell in train), "response_free_training_assignment_invalid")
    _require(all(cell in assignments and assignments[cell].get("outer_role") == "test" for _, cell in test), "response_free_test_assignment_invalid")
    _require({species for species, _ in train} == set(SPECIES), "response_free_training_species_invalid")
    _require({species for species, _ in test} == set(SPECIES), "response_free_test_species_invalid")
    return train, test, assignments


def _rowset_for_keys(rows: Any, keys: Sequence[Any]) -> Any:
    index = {key: index for index, key in enumerate(rows.keys)}
    try:
        return rows.take([index[key] for key in keys])
    except KeyError as exc:
        raise CensusError("endpoint_key_not_in_training_rowset") from exc


def _source_binding_digest(rows: Any, fold_by_key: Mapping[Any, str]) -> str:
    tokens = sorted(
        f"{key.species_id}|{key.grid_cell_id}|{fold_by_key[key]}|{source}"
        for key, source in zip(rows.keys, rows.response_source, strict=True)
    )
    return hashlib.sha256("\n".join(tokens).encode()).hexdigest()


def _outer_source_binding_digest(rows: Any, fold_by_key: Mapping[Any, str]) -> str:
    tokens = [
        (key.species_id, key.grid_cell_id, fold_by_key[key], str(source), int(pa))
        for key, source, pa in zip(rows.keys, rows.response_source, rows.pa, strict=True)
    ]
    return digest_value(tokens)


def run_census(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    paths, binding_digests = _load_bindings(root)
    RowKey, RowSet, build_ladders = _load_archived_contract(root)
    train_allowlist, test_allowlist, assignments = _allowlist_from_response_free_inputs(paths)

    # This is the first point at which canonical response source/class fields
    # are read, and only allowlisted outer-training rows reach the full parser.
    records = _read_allowlisted_response_rows(paths["response_partitioned"], train_allowlist, assignments)
    _require(len(records) == len(train_allowlist), "training_row_inventory_mismatch")
    outer = RowSet.from_records(records)
    fold_by_key = {key: assignments[key.grid_cell_id]["cv_fold"] for key in outer.keys}
    _require(set(fold_by_key.values()) == set(FOLDS), "training_fold_inventory_invalid")
    _require(_source_binding_digest(outer, fold_by_key) == "07bfb944dfb7d4097a429d5d295c58225c938b863487b3260c0b78738d256b7f", "goal035_source_binding_mismatch")
    _require(_outer_source_binding_digest(outer, fold_by_key) == "e8997e6b899d35a39bd496e9442b18dbeeaa126475565c45cf294bfb82d520c1", "goal037_source_binding_mismatch")

    inner_metadata_root = root / INNER_BUNDLE_REL
    outer_metadata_root = root / OUTER_BUNDLE_REL
    inner_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    metadata_digests: dict[str, str] = {}
    for species in SPECIES:
        for fold in FOLDS:
            bundle_path = inner_metadata_root / f"{species}--{fold}.npz"
            metadata, _ = _bundle_inventory(bundle_path)
            _validate_bundle_identity(bundle_path, metadata, species=species, held_fold=fold, expected_config="87c3afa6fbb9a2177caafc0b2aacb0130c7f6545523839cd0fd030218795d7c2", expected_source_binding="07bfb944dfb7d4097a429d5d295c58225c938b863487b3260c0b78738d256b7f")
            inner_metadata[(species, fold)] = metadata
            metadata_digests[f"{species}--{fold}"] = digest_value(metadata)
    outer_metadata: dict[str, dict[str, Any]] = {}
    for species in SPECIES:
        bundle_path = outer_metadata_root / f"{species}.npz"
        metadata, _ = _bundle_inventory(bundle_path)
        _validate_bundle_identity(bundle_path, metadata, species=species, held_fold=None, expected_config="", expected_source_binding="")
        outer_metadata[species] = metadata
        metadata_digests[species] = digest_value(metadata)
    _validate_saved_bundle_inventories(root, inner_metadata, outer_metadata, paths)
    role_records: list[dict[str, Any]] = []
    digest_match = {"inner": 0, "outer": 0}
    failures: list[dict[str, Any]] = []
    outer_by_species = {species: outer.take([i for i, key in enumerate(outer.keys) if key.species_id == species]) for species in SPECIES}
    endpoint_plans: list[dict[str, Any]] = []

    for species in SPECIES:
        full_outer = outer_by_species[species]
        ladders_outer = build_ladders(full_outer)
        outer_meta = outer_metadata[species]
        for endpoint in ENDPOINTS:
            fraction, ladder = endpoint.split("/")
            lookup = "ladder00" if fraction == "fraction100" else ladder
            endpoint_rows = ladders_outer[(fraction, lookup)]
            expected = outer_meta["subset_membership_digests"].get(endpoint)
            verify_membership_digest(endpoint_rows.subset_digest, expected, f"outer:{species}:{endpoint}")
            digest_match["outer"] += 1
            endpoint_plans.append({"scope": "outer", "species": species, "held_fold": None, "endpoint": endpoint, "role": "outer_fit", "rows": _rowset_for_keys(full_outer, endpoint_rows.keys), "endpoint_digest": expected})

        for held_fold in FOLDS:
            train_indices = [i for i, key in enumerate(full_outer.keys) if fold_by_key[key] != held_fold]
            inner_train = full_outer.take(train_indices)
            ladders = build_ladders(inner_train)
            metadata = inner_metadata[(species, held_fold)]
            stopping_fold = f"fold{(int(held_fold[-2:]) + 1) % 5:02d}"
            for endpoint in ENDPOINTS:
                fraction, ladder = endpoint.split("/")
                lookup = "ladder00" if fraction == "fraction100" else ladder
                endpoint_rows = ladders[(fraction, lookup)]
                expected = metadata["subset_membership_digests"].get(endpoint)
                verify_membership_digest(endpoint_rows.subset_digest, expected, f"inner:{species}:{held_fold}:{endpoint}")
                digest_match["inner"] += 1
                by_fold = {key: fold_by_key[key] for key in endpoint_rows.keys}
                selected = {
                    "discovery": [key for key in endpoint_rows.keys if by_fold[key] not in {held_fold, stopping_fold}],
                    "stopping": [key for key in endpoint_rows.keys if by_fold[key] == stopping_fold],
                    "replay": list(endpoint_rows.keys),
                }
                for role in ("discovery", "stopping", "replay"):
                    role_rows = _rowset_for_keys(inner_train, selected[role])
                    endpoint_plans.append({"scope": "inner", "species": species, "held_fold": held_fold, "endpoint": endpoint, "role": role, "rows": role_rows, "endpoint_digest": expected, "stopping_fold": stopping_fold})

    # All accepted endpoint memberships have now been checked.  Only this
    # second pass is allowed to access pa_type for pseudoabsence subtraction.
    for plan in endpoint_plans:
        record = _role_record(
            species=plan["species"], held_fold=plan["held_fold"], endpoint=plan["endpoint"],
            role=plan["role"], rows=plan["rows"], expected_digest=plan["endpoint_digest"],
        )
        if "stopping_fold" in plan:
            record["stopping_fold"] = plan["stopping_fold"]
        role_records.append(record)
        if record["failure"]:
            failures.append({"scope": plan["scope"], "species": plan["species"], "held_fold": plan["held_fold"], "endpoint": plan["endpoint"], "role": plan["role"], "failure": record["failure"]})

    # Response-free evaluation identities: inner assessment is the held fold;
    # outer assessment is the Goal026 outer/test allowlist.  No response row is
    # consulted for these hashes.
    eval_inner = []
    for species in SPECIES:
        species_keys = {(key.species_id, key.grid_cell_id): key for key in outer.keys if key.species_id == species}
        for fold in FOLDS:
            keys = [key for key in species_keys.values() if fold_by_key[key] == fold]
            eval_inner.append({"species": species, "fold": fold, "rows": len(keys), "id_set_digest": _id_digest(keys)})
    eval_outer = []
    for species in SPECIES:
        keys = [RowKey(species, cell) for sp, cell in sorted(test_allowlist) if sp == species]
        eval_outer.append({"species": species, "rows": len(keys), "id_set_digest": _id_digest(keys)})

    # Aggregate-only summaries retain all exact role records but expose no raw
    # row identifiers.  The per-role digests are identity-set commitments.
    role_summary: dict[str, Any] = {}
    for role in ROLES:
        records_for_role = [record for record in role_records if record["role"] == role]
        if not records_for_role:
            continue
        retained_counts = [record["retained"]["class"] if record["retained"] else {"0": 0, "1": 0} for record in records_for_role]
        role_summary[role] = {
            "roles": len(records_for_role),
            "minimum_retained_class_counts": {"0": min(value["0"] for value in retained_counts), "1": min(value["1"] for value in retained_counts)},
            "missing_class_failures": sum(record["failure"] is not None for record in records_for_role),
            "baseline_rows": sum(record["baseline"]["rows"] for record in records_for_role),
            "retained_rows": sum(record["retained"]["rows"] for record in records_for_role if record["retained"]),
            "excluded_rows": sum(record["excluded"]["rows"] for record in records_for_role),
            "source_counts": {
                state: {source: sum(record[state]["source"][source] for record in records_for_role if record[state]) for source in SOURCE_VALUES}
                for state in ("baseline", "retained", "excluded")
            },
            "class_counts": {
                state: {label: sum(record[state]["class"][label] for record in records_for_role if record[state]) for label in ("0", "1")}
                for state in ("baseline", "retained", "excluded")
            },
            "role_digest": digest_value([(record["species"], record["held_fold"], record["endpoint"], record["baseline_id_set_digest"], record["retained_id_set_digest"], record["excluded_id_set_digest"]) for record in records_for_role]),
        }

    script_path = Path(__file__).resolve()
    report = {
        "schema_version": "tasmania-pseudoabsence-source-census-v1",
        "purpose": "training_response_census_with_held_label_exclusion",
        "success": not failures,
        "fitting": False,
        "predictions": False,
        "scoring": False,
        "training_response_rows_read": len(records),
        "held_response_labels_read": False,
        "held_response_source_fields_read": False,
        "scope": {"species": len(SPECIES), "endpoints": len(ENDPOINTS), "inner_endpoint_memberships": 280, "outer_endpoint_memberships": 56},
        "membership_verification": {"inner": {"expected": 280, "matched": digest_match["inner"]}, "outer": {"expected": 56, "matched": digest_match["outer"]}},
        "role_summary": role_summary,
        "evaluation_membership": {"inner": {"memberships": len(eval_inner), "rows": sum(item["rows"] for item in eval_inner), "digest": digest_value(eval_inner)}, "outer": {"memberships": len(eval_outer), "rows": sum(item["rows"] for item in eval_outer), "digest": digest_value(eval_outer)}},
        "failures": failures,
        "records": role_records,
        "source_paths": {name: str(path.relative_to(root)) for name, path in paths.items()},
        "source_hashes": binding_digests,
        "bundle_metadata_digests": dict(sorted(metadata_digests.items())),
        "bundle_numerical_arrays_read": False,
        "original_response_membership_checks": {
            "training_allowlisted_rows": len(train_allowlist),
            "training_rows_parsed": len(records),
            "held_response_membership_excluded": True,
            "inner_evaluation_memberships": len(eval_inner),
            "outer_evaluation_memberships": len(eval_outer),
        },
        "archive_source_hashes": {name: binding_digests[name] for name in ("archived_modeling_contract", "archived_target_subsets")},
        "script": {"path": str(script_path.relative_to(root)), "sha256": sha256_file(script_path)},
        "privacy": {"raw_rows": False, "coordinates": False, "grid_cell_ids": False, "held_labels": False},
    }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_census(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0 if report["success"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
