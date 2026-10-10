"""Build identity-checked, filtered neural views without fitting or outer labels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/processed/dsdm/tasmania-outer-assessment-20261005/archive/goal037-ce70bf1"
PRIVATE = ROOT / "data/processed/dsdm/tasmania-pseudoabsence-20261008/private/neural"
CENSUS_PATH = ROOT / "evidence/tasmania_pseudoabsence/20261008/source-census.json"
CENSUS_SHA = "211bad0f88daa140f1d56ac2916fd5da584f4164e6e96e36748547b8dc392352"
INNER = ROOT / "data/processed/dsdm/goal035-final-inner-lifecycle/private"
OUTER = ROOT / "data/processed/dsdm/goal037-outer-ready/private/bundles"
ORIGINAL_ASSESSMENT = ROOT / "data/processed/dsdm/tasmania-outer-assessment-20261005/private"
METHODS = ("target_only_resmlp", "multihead_full_finetune")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def array_digest(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def load_census():
    require(sha(CENSUS_PATH) == CENSUS_SHA, "accepted source census changed")
    report = read_json(CENSUS_PATH)
    require(report["success"] and len(report["records"]) == 896, "source census failed")
    script = ROOT / report["script"]["path"]
    require(sha(script) == report["script"]["sha256"], "census script changed")
    spec = importlib.util.spec_from_file_location("_tasmania_source_census", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, report


def archived_imports():
    config_path = ARCHIVE / "config/dsdm_final_inner_lifecycle.json"
    require(sha(config_path) == "87c3afa6fbb9a2177caafc0b2aacb0130c7f6545523839cd0fd030218795d7c2", "archived inner configuration changed")
    for item in read_json(config_path)["execution_sources"].values():
        require(sha(ARCHIVE / item["path"]) == item["sha256"], "archived neural source changed")
    require(sha(ARCHIVE / "src/dsdm/outer_ready.py") == "8b9cdfbe505f42bc54723b4f4237ad929272ddbfaec517b40e73b9cf073de104", "archived outer source changed")
    for name in ("dsdm", "dsdm_phase1"):
        module = sys.modules.get(name)
        if module is not None:
            require(Path(module.__file__).resolve().parent == ARCHIVE / "src" / name, "non-archived package loaded")
    sys.path.insert(0, str(ARCHIVE / "src"))
    from dsdm.final_inner_data import load_case_npz, ENDPOINTS, ENDPOINT_SLUGS
    from dsdm.outer_ready import load_outer_bundle
    from dsdm.real_data import _encode
    from dsdm_phase1.modeling_contract import RowKey, RowSet, TransformingFeatureSubstrate
    from dsdm_phase1.target_subsets import build_ladders
    return load_case_npz, load_outer_bundle, ENDPOINTS, ENDPOINT_SLUGS, _encode, RowKey, RowSet, TransformingFeatureSubstrate, build_ladders


def load_bound_npz(path):
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(z["metadata_json"].tobytes())
        arrays = {k: np.array(z[k], copy=True) for k in z.files if k != "metadata_json"}
    inventory = {k: array_digest(v) for k, v in sorted(arrays.items())}
    require(inventory == meta["array_digests"], "prepared array hash mismatch")
    body = dict(meta)
    claimed = body.pop("digest")
    require(digest(body) == claimed, "prepared metadata hash mismatch")
    return arrays, meta


def save_bound_npz(path, arrays, metadata):
    meta = dict(metadata, array_digests={k: array_digest(v) for k, v in sorted(arrays.items())})
    meta["digest"] = digest(meta)
    path = Path(path)
    if path.exists():
        _, existing = load_bound_npz(path)
        require(existing == meta, "existing prepared view changed")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, **arrays, metadata_json=np.frombuffer(json.dumps(meta, sort_keys=True, separators=(",", ":")).encode(), dtype=np.uint8))
        temporary.replace(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path), "metadata_digest": meta["digest"]}


def checked_filter(census, reference, keys, x, y, by_key):
    """Join canonical IDs to the original exporter order before subtraction."""
    require(len(keys) == len(x) == len(y), "role row alignment failed")
    require(census._id_digest(keys) == reference["baseline_id_set_digest"], "baseline membership changed")
    expected_y = np.asarray([by_key[k]["pa"] for k in keys], dtype=np.float32)
    require(np.array_equal(y, expected_y), "source labels disagree with accepted ordered array")
    kept = np.asarray([by_key[k]["pa_type"] != "pseudoabsence" for k in keys], dtype=bool)
    retained = [k for k, keep in zip(keys, kept) if keep]
    excluded = [k for k, keep in zip(keys, kept) if not keep]
    require(census._id_digest(retained) == reference["retained_id_set_digest"], "retained membership changed")
    require(census._id_digest(excluded) == reference["excluded_id_set_digest"], "excluded membership changed")
    require(set(y[kept].tolist()) == {0.0, 1.0}, "filtered role lost a class")
    return x[kept].copy(), y[kept].copy(), np.asarray([k.grid_cell_id for k in retained])


def prepare():
    census, report = load_census()
    paths, source_hashes = census._load_bindings(ROOT)
    train, held, assignments = census._allowlist_from_response_free_inputs(paths)
    records = census._read_allowlisted_response_rows(paths["response_partitioned"], train, assignments)
    load_inner, load_outer, endpoints, slugs, encode, Key, Rows, Substrate, ladders = archived_imports()
    rows = Rows.from_records(records)
    by_key = {Key(r["species_id"], r["grid_cell_id"]): r for r in records}
    folds = {key: assignments[key.grid_cell_id]["cv_fold"] for key in rows.keys}
    references = {(r["species"], r["held_fold"], r["endpoint"], r["role"]): r for r in report["records"]}

    foundation = read_json(ROOT / "config/modeling_foundation_preflight.json")
    require(sha(ROOT / "config/modeling_foundation_preflight.json") == "35b6ab72ba2b8ba2267dc82179987bfffaa3f339d64272d68012444e46285f00", "foundation binding changed")
    binding = foundation["bindings"]["goal024_map"]
    map_path = ROOT / binding["path"]
    require(sha(map_path) == binding["sha256"], "map changed")
    feature_path = ROOT / foundation["bindings"]["goal026_feature_contract"]["path"]
    fit_path = ROOT / foundation["bindings"]["goal026_fit_parameters"]["path"]
    require(sha(feature_path) == foundation["bindings"]["goal026_feature_contract"]["sha256"], "feature contract changed")
    require(sha(fit_path) == foundation["bindings"]["goal026_fit_parameters"]["sha256"], "transforms changed")
    features, fits = read_json(feature_path), read_json(fit_path)
    continuous, categorical = features["continuous_predictors"], features["categorical_predictors"]
    with map_path.open() as f:
        map_rows = list(csv.DictReader(f))
    values = {r["grid_cell_id"]: {name: float(r[name]) if name in continuous else str(r[name]) for name in continuous + categorical} for r in map_rows}
    require(len(values) == len(map_rows) == 71023, "structural domain changed")
    source_hashes.update({"map": sha(map_path), "fit_parameters": sha(fit_path), "feature_contract": sha(feature_path)})
    # Species-independent substrate: its private keys are solely lookup keys.
    raw_values = {Key("map", cell): value for cell, value in values.items()}
    substrate = Substrate(raw_values, fits, continuous, categorical)
    encoded_cache = {}

    def encoded(cells, transform):
        result = []
        for cell in cells:
            key = (cell, transform)
            if key not in encoded_cache:
                value = substrate.get(Key("map", cell), transform)
                encoded_cache[key] = encode({"x": value["continuous"], **value["categorical"]})
            result.append(encoded_cache[key])
        return np.stack(result).astype(np.float32)

    # Bind the accepted response-free held inputs through the original closure.
    assessment = read_json(ROOT / "evidence/tasmania_outer_assessment/20261005/receipt.json")
    closure = read_json(ORIGINAL_ASSESSMENT / "prediction-closure.json")
    input_closure = read_json(ORIGINAL_ASSESSMENT / "input-closure.json")
    for value, expected in ((closure, assessment["prediction_closure_digest"]), (input_closure, closure["input_receipt_digest"])):
        body = dict(value)
        claimed = body.pop("receipt_digest")
        require(digest(body) == claimed == expected, "original input closure changed")
    require(closure["receipt_digest"] == "a160318d5cc627ff5a724256ee4a008ad4f13038b9419ba7e809cf01bd6a4e6e", "accepted original prediction closure changed")
    require(assessment["config_digest"] == source_hashes["assessment_config"], "original assessment config changed")
    held_files = {r["species"]: r for r in input_closure["files"]}
    output_records = []
    checks = 0
    for species in census.SPECIES:
        full = rows.take([i for i, k in enumerate(rows.keys) if k.species_id == species])
        for fold in census.FOLDS:
            bundle = load_inner(INNER / f"{species}--{fold}.npz")
            source_meta_hash = census.digest_value(bundle.metadata)
            require(source_meta_hash == report["bundle_metadata_digests"][f"{species}--{fold}"], "accepted inner metadata changed")
            training = full.take([i for i, k in enumerate(full.keys) if folds[k] != fold])
            choices = ladders(training)
            stop = f"fold{(int(fold[-2:]) + 1) % 5:02d}"
            held_keys = [k for k in full.keys if folds[k] == fold]
            require(np.array_equal(encoded([k.grid_cell_id for k in held_keys], f"cv_{fold}"), bundle.arrays["x_held"]), "inner evaluation feature identity changed")
            require(np.array_equal(np.asarray([by_key[k]["pa"] for k in held_keys], dtype=np.float32), bundle.arrays["y_held"]), "inner evaluation label identity changed")
            arrays = {"x_held": bundle.arrays["x_held"], "y_held": bundle.arrays["y_held"], "held_cells": np.asarray([k.grid_cell_id for k in held_keys])}
            for endpoint in endpoints:
                fraction, ladder = endpoint.split("/")
                chosen = choices[(fraction, "ladder00" if fraction == "fraction100" else ladder)]
                require(chosen.subset_digest == bundle.metadata["subset_membership_digests"][endpoint], "original inner subset changed")
                role_keys = {"replay": list(chosen.keys), "stopping": [k for k in chosen.keys if folds[k] == stop], "discovery": [k for k in chosen.keys if folds[k] != stop]}
                for role, keys in role_keys.items():
                    prefix = f"target_{slugs[endpoint]}"
                    x, y = bundle.arrays[f"{prefix}_x_{role}"], bundle.arrays[f"{prefix}_y_{role}"]
                    require(np.array_equal(encoded([k.grid_cell_id for k in keys], f"cv_{fold}"), x), "inner canonical feature join mismatch")
                    xx, yy, cells = checked_filter(census, references[species, fold, endpoint, role], keys, x, y, by_key)
                    arrays.update({f"{prefix}_x_{role}": xx, f"{prefix}_y_{role}": yy, f"{prefix}_cells_{role}": cells})
                    checks += 1
            meta = {"species": species, "fold": fold, "original_bundle_digest": bundle.source_digest, "source_census_sha256": CENSUS_SHA, "script_sha256": sha(Path(__file__)), "evaluation_id_set_digest": census._id_digest(held_keys), "role_filter_checks": 21}
            output_records.append(save_bound_npz(PRIVATE / "inputs" / "inner" / f"{species}--{fold}.npz", arrays, meta))

        bundle = load_outer(OUTER / f"{species}.npz")
        require(census.digest_value(bundle.metadata) == report["bundle_metadata_digests"][species], "accepted outer metadata changed")
        choices = ladders(full)
        held_path = ORIGINAL_ASSESSMENT / "inputs" / f"{species}.npz"
        require(sha(held_path) == held_files[species]["sha256"], "held predictor file changed")
        with np.load(held_path, allow_pickle=False) as z:
            cells = z["grid_cell_id"].copy()
            xheld = z["x_neural"].copy()
            patches = z["patch"].copy()
        expected_held = {Key(sp, cell) for sp, cell in held if sp == species}
        require({Key(species, cell) for cell in cells} == expected_held, "outer evaluation membership changed")
        require(np.array_equal(encoded(cells, "outer"), xheld), "outer canonical feature join mismatch")
        arrays = {"x_held": xheld, "held_cells": cells, "held_patch": patches}
        for endpoint in endpoints:
            fraction, ladder = endpoint.split("/")
            chosen = choices[(fraction, "ladder00" if fraction == "fraction100" else ladder)]
            require(chosen.subset_digest == bundle.metadata["subset_membership_digests"][endpoint], "original outer subset changed")
            prefix = f"target_{slugs[endpoint]}"
            x, y = bundle.arrays[f"{prefix}_x"], bundle.arrays[f"{prefix}_y"]
            require(np.array_equal(encoded([k.grid_cell_id for k in chosen.keys], "outer"), x), "outer canonical feature join mismatch")
            xx, yy, cells = checked_filter(census, references[species, None, endpoint, "outer_fit"], chosen.keys, x, y, by_key)
            arrays.update({f"{prefix}_x": xx, f"{prefix}_y": yy, f"{prefix}_cells": cells})
            checks += 1
        meta = {"species": species, "fold": None, "original_bundle_digest": bundle.bundle_digest, "source_census_sha256": CENSUS_SHA, "script_sha256": sha(Path(__file__)), "evaluation_id_set_digest": census._id_digest(expected_held), "role_filter_checks": 7}
        output_records.append(save_bound_npz(PRIVATE / "inputs" / "outer" / f"{species}.npz", arrays, meta))
    cells = sorted(values)
    output_records.append(save_bound_npz(PRIVATE / "inputs" / "map.npz", {"x": encoded(cells, "outer"), "cells": np.asarray(cells)}, {"rows": 71023, "source_hashes": source_hashes, "script_sha256": sha(Path(__file__))}))
    require(checks == 896, "role filtering incomplete")
    manifest = {"schema_version": "tasmania-sensitivity-neural-inputs-v1", "success": True, "source_census_sha256": CENSUS_SHA, "source_hashes": source_hashes, "files": output_records, "role_filter_checks": checks, "original_array_joins": "canonical row IDs, original endpoint order, exact predictor and response arrays", "outer_response_labels_read": 0, "fits": 0, "script_sha256": sha(Path(__file__))}
    manifest["digest"] = digest(manifest)
    path = PRIVATE / "input-manifest.json"
    if path.exists():
        require(read_json(path) == manifest, "existing input manifest changed")
    else:
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = prepare()
    print(json.dumps({k: v for k, v in result.items() if k not in ("files", "source_hashes")}, indent=2))
