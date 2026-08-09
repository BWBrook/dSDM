"""Export the selected Goal029 inner-OOF scores without opening the outer vault.

The exporter is intentionally standalone enough to run beside the immutable
Goal029 producer checkout.  It verifies the finalized private manifest, follows
the frozen within-family selections back to their OOF checkpoints, and writes a
single private Parquet file plus an aggregate provenance manifest.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


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
ENDPOINTS = (
    ("fraction25", "ladder00"),
    ("fraction25", "ladder01"),
    ("fraction25", "ladder02"),
    ("fraction50", "ladder00"),
    ("fraction50", "ladder01"),
    ("fraction50", "ladder02"),
    ("fraction100", "full"),
)
FAMILIES = (
    "intercept",
    "elastic_net",
    "random_forest",
    "hist_gradient_boosting",
    "shallow_ann",
)
SEEDS_BY_FAMILY = {
    "intercept": ("seed00",),
    "elastic_net": tuple(f"seed{i:02d}" for i in range(5)),
    "random_forest": tuple(f"seed{i:02d}" for i in range(5)),
    "hist_gradient_boosting": ("seed00",),
    "shallow_ann": tuple(f"seed{i:02d}" for i in range(5)),
}
PRODUCER_COMMIT = "f85e45922e182858fd351fdaf4f1b36b33fb4f2f"
PRIVATE_RELATIVE_ROOT = Path("data/processed/modeling/goal029-conventional-baseline-production")
HEX = frozenset("0123456789abcdef")


class ConventionalExportError(ValueError):
    """Raised when the sealed conventional OOF transaction is inconsistent."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConventionalExportError(message)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConventionalExportError(f"invalid JSON: {Path(path).name}") from exc
    _require(isinstance(value, dict), f"JSON object required: {Path(path).name}")
    return value


def _verify_manifest_file(root: Path, manifest: Mapping[str, Any], relative: str) -> Path:
    record = manifest.get("files", {}).get(relative)
    _require(isinstance(record, Mapping) and set(record) == {"bytes", "sha256"}, f"file absent from finalized manifest: {relative}")
    path = root / relative
    _require(path.is_file() and not path.is_symlink(), f"sealed file missing: {relative}")
    _require(path.stat().st_size == record["bytes"] and sha256_file(path) == record["sha256"], f"sealed file drift: {relative}")
    return path


def _record_digest(record: Mapping[str, Any]) -> str:
    body = dict(record)
    claimed = body.pop("record_digest", None)
    _require(_is_digest(claimed) and claimed == digest_value(body), "selection record digest mismatch")
    return str(claimed)


def _semantic_result_digest(metadata: Mapping[str, Any], table: pa.Table) -> str:
    stable = deepcopy(dict(metadata))
    for reports in stable.get("fit_reports_by_seed", {}).values():
        for report in reports:
            report.pop("runtime_seconds", None)
            report.pop("peak_rss_bytes", None)
    for record in stable.get("neural_epochs_by_seed", {}).values():
        for receipt in record.get("receipts", []):
            for name in ("discovery_report", "replay_report"):
                receipt[name].pop("runtime_seconds", None)
                receipt[name].pop("peak_rss_bytes", None)
    return digest_value({"metadata": stable, "oof": table.to_pylist()})


def _row_identity_digest(table: pa.Table) -> str:
    return digest_value(table.select(["fold_id", "row_index", "row_token", "y_true"]).to_pylist())


def _validate_checkpoint(
    private_root: Path,
    private_manifest: Mapping[str, Any],
    leaf_record: Mapping[str, Any],
) -> tuple[pa.Table, dict[str, Any]]:
    checkpoint = str(leaf_record.get("checkpoint", ""))
    _require(checkpoint.startswith("checkpoints/") and ".." not in Path(checkpoint).parts, "checkpoint path invalid")
    files = {
        name: _verify_manifest_file(private_root, private_manifest, f"{checkpoint}/{name}")
        for name in ("identity.json", "result.json", "oof.parquet", "checkpoint_manifest.json")
    }
    identity = _read_json(files["identity.json"])
    identity_body = dict(identity)
    claimed_identity = identity_body.pop("identity_digest", None)
    _require(claimed_identity == leaf_record.get("identity_digest") == digest_value(identity_body), "checkpoint identity mismatch")
    _require(identity.get("leaf_task") == leaf_record.get("leaf"), "checkpoint leaf mismatch")

    checkpoint_manifest = _read_json(files["checkpoint_manifest.json"])
    _require(checkpoint_manifest.get("schema_version") == "1.0" and checkpoint_manifest.get("identity_digest") == claimed_identity, "checkpoint manifest identity drift")
    _require(set(checkpoint_manifest.get("files", {})) == {"identity.json", "result.json", "oof.parquet"}, "checkpoint manifest inventory drift")
    for name, record in checkpoint_manifest["files"].items():
        _require(record == {"bytes": files[name].stat().st_size, "sha256": sha256_file(files[name])}, f"checkpoint file receipt drift: {name}")

    result = _read_json(files["result.json"])
    table = pq.read_table(files["oof.parquet"])
    expected_schema = pa.schema([
        ("fold_id", pa.string()),
        ("row_index", pa.int32()),
        ("row_token", pa.string()),
        ("y_true", pa.int8()),
        ("seed_label", pa.string()),
        ("score", pa.float64()),
    ])
    _require(table.schema == expected_schema and table.num_rows > 0, "checkpoint OOF schema drift")
    _require(checkpoint_manifest.get("semantic_result_digest") == leaf_record.get("semantic_result_digest") == _semantic_result_digest(result, table), "checkpoint semantic digest mismatch")

    leaf = leaf_record["leaf"]
    expected_stratum = {
        "species_id": leaf["species_id"],
        "fraction_id": leaf["fraction_id"],
        "ladder_id": leaf["ladder_id"],
        "model_family": leaf["model_family"],
        "ordered_selection_seeds": [leaf["seed_label"]],
    }
    _require(result.get("candidate_id") == leaf["candidate_id"] and result.get("stratum") == expected_stratum, "checkpoint result stratum drift")
    seed_labels = set(table.column("seed_label").to_pylist())
    fold_ids = set(table.column("fold_id").to_pylist())
    y = table.column("y_true").to_numpy(zero_copy_only=False)
    scores = table.column("score").to_numpy(zero_copy_only=False)
    _require(seed_labels == {leaf["seed_label"]} and fold_ids == {f"fold{i:02d}" for i in range(5)}, "checkpoint seed/fold coverage drift")
    _require(np.isin(y, (0, 1)).all() and np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "checkpoint values invalid")
    for fold in sorted(fold_ids):
        mask = np.asarray(table.column("fold_id").to_pylist()) == fold
        _require(set(y[mask].tolist()) == {0, 1}, f"checkpoint classless fold: {fold}")
    return table, result


def export_selected_oof(
    repo_root: str | Path,
    output_dir: str | Path,
    *,
    expected_private_manifest_sha256: str,
    expected_commit: str = PRODUCER_COMMIT,
) -> dict[str, Any]:
    """Validate and export all 280 selected within-family OOF strata."""
    repo = Path(repo_root).resolve()
    private_root = repo / PRIVATE_RELATIVE_ROOT
    output = Path(output_dir).resolve()
    _require(repo.is_dir() and private_root.is_dir(), "Goal029 producer root missing")
    _require(_is_digest(expected_private_manifest_sha256), "private manifest binding invalid")
    actual_commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(actual_commit == expected_commit, "Goal029 producer commit drift")

    private_manifest_path = private_root / "core_manifest.json"
    _require(sha256_file(private_manifest_path) == expected_private_manifest_sha256, "private finalized manifest drift")
    private_manifest = _read_json(private_manifest_path)
    _require(private_manifest.get("schema_version") == "1.0" and len(private_manifest.get("files", {})) == 31214, "private finalized manifest schema/count drift")
    selection_path = _verify_manifest_file(private_root, private_manifest, "selection.json")
    states_path = _verify_manifest_file(private_root, private_manifest, "candidate_states.json")
    run_path = _verify_manifest_file(private_root, private_manifest, "run.json")
    source_audit_path = _verify_manifest_file(private_root, private_manifest, "source_audit.json")
    selection = _read_json(selection_path)
    states = _read_json(states_path)
    run = _read_json(run_path)
    source_audit = _read_json(source_audit_path)
    _require(run.get("real_outer_attempted_open_count") == run.get("real_outer_open_count") == 0, "Goal029 run outer boundary drift")
    _require(source_audit.get("real_outer_attempted_open_count") == source_audit.get("real_outer_open_count") == 0, "Goal029 source-audit outer boundary drift")
    _require(run.get("candidate_seed_leaf_count") == 6888 and run.get("family_count") == 280 and run.get("selected_model_seed_count") == 952, "Goal029 run arithmetic drift")
    _require(selection.get("candidate_states_file_sha256") == sha256_file(states_path) and selection.get("selected_model_seed_count") == 952, "Goal029 selection binding drift")
    _require(len(selection.get("family_records", [])) == 280 and len(states.get("candidate_records", [])) == 1736, "Goal029 selection/state count drift")
    state_lookup = {
        tuple(record["candidate_stratum"][key] for key in ("species_id", "fraction_id", "ladder_id", "model_family", "candidate_id")): record
        for record in states["candidate_records"]
    }
    expected_strata = [
        (species, fraction, ladder, family)
        for species in SPECIES
        for fraction, ladder in ENDPOINTS
        for family in FAMILIES
    ]
    actual_strata = [tuple(index["family_stratum"][key] for key in ("species_id", "fraction_id", "ladder_id", "model_family")) for index in selection["family_records"]]
    _require(actual_strata == expected_strata, "Goal029 family stratum order drift")

    output.mkdir(parents=True, exist_ok=True)
    parquet_path = output / "conventional_selected_oof.parquet"
    temporary = output / ".conventional_selected_oof.parquet.tmp"
    manifest_path = output / "manifest.json"
    _require(not parquet_path.exists() and not manifest_path.exists() and not temporary.exists(), "conventional export destination is not fresh")
    writer: pq.ParquetWriter | None = None
    checkpoint_inventory: list[dict[str, Any]] = []
    row_identity_by_species: dict[str, str] = {}
    row_count = 0
    try:
        for index in selection["family_records"]:
            selection_record_path = _verify_manifest_file(private_root, private_manifest, index["relative_path"])
            selection_record = _read_json(selection_record_path)
            _require(_record_digest(selection_record) == index["record_digest"] and selection_record["family_stratum"] == index["family_stratum"], "Goal029 selection record drift")
            stratum = selection_record["family_stratum"]
            candidate_id = selection_record["selected_candidate_id"]
            key = tuple(stratum[name] for name in ("species_id", "fraction_id", "ladder_id", "model_family")) + (candidate_id,)
            state = state_lookup.get(key)
            _require(isinstance(state, Mapping) and state.get("status") == "complete", "selected candidate state incomplete")
            leaves = state.get("leaves", [])
            expected_seeds = SEEDS_BY_FAMILY[stratum["model_family"]]
            _require(tuple(leaf["leaf"]["seed_label"] for leaf in leaves) == expected_seeds, "selected candidate seed coverage drift")
            baseline_identity: str | None = None
            for leaf_record in leaves:
                table, _ = _validate_checkpoint(private_root, private_manifest, leaf_record)
                identity_digest = _row_identity_digest(table)
                if baseline_identity is None:
                    baseline_identity = identity_digest
                _require(identity_digest == baseline_identity, "selected seeds do not share OOF rows")
                species_identity = row_identity_by_species.setdefault(stratum["species_id"], identity_digest)
                _require(identity_digest == species_identity, "OOF rows differ across endpoints or families")
                n = table.num_rows
                enriched = pa.table({
                    "species_id": pa.array([stratum["species_id"]] * n, pa.string()),
                    "fraction_id": pa.array([stratum["fraction_id"]] * n, pa.string()),
                    "ladder_id": pa.array([stratum["ladder_id"]] * n, pa.string()),
                    "model_family": pa.array([stratum["model_family"]] * n, pa.string()),
                    "candidate_id": pa.array([candidate_id] * n, pa.string()),
                    "seed_label": table["seed_label"],
                    "fold_id": table["fold_id"],
                    "row_index": table["row_index"],
                    "row_token": table["row_token"],
                    "y_true": table["y_true"],
                    "score": table["score"],
                })
                if writer is None:
                    writer = pq.ParquetWriter(temporary, enriched.schema, compression="zstd")
                writer.write_table(enriched)
                row_count += n
                checkpoint_inventory.append({
                    "identity_digest": leaf_record["identity_digest"],
                    "semantic_result_digest": leaf_record["semantic_result_digest"],
                    "row_identity_digest": identity_digest,
                    "rows": n,
                })
    except Exception:
        if writer is not None:
            writer.close()
            writer = None
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if writer is not None:
            writer.close()
    _require(len(checkpoint_inventory) == 952 and row_count > 0 and temporary.is_file(), "selected checkpoint export arithmetic drift")
    temporary.replace(parquet_path)
    manifest = {
        "schema_version": "goal036-conventional-oof-export-v1",
        "producer_commit": actual_commit,
        "private_core_manifest_sha256": expected_private_manifest_sha256,
        "selection_sha256": sha256_file(selection_path),
        "candidate_states_sha256": sha256_file(states_path),
        "run_sha256": sha256_file(run_path),
        "source_audit_sha256": sha256_file(source_audit_path),
        "family_strata": 280,
        "selected_checkpoints": 952,
        "rows": row_count,
        "species": list(SPECIES),
        "endpoints": [f"{fraction}/{ladder}" for fraction, ladder in ENDPOINTS],
        "families": list(FAMILIES),
        "seed_count_by_family": {family: len(SEEDS_BY_FAMILY[family]) for family in FAMILIES},
        "row_identity_digest_by_species": dict(sorted(row_identity_by_species.items())),
        "checkpoint_inventory_digest": digest_value(checkpoint_inventory),
        "parquet_sha256": sha256_file(parquet_path),
        "parquet_bytes": parquet_path.stat().st_size,
        "outer_attempted": 0,
        "outer_opened": 0,
    }
    manifest["manifest_digest"] = digest_value(manifest)
    manifest_path.write_text(canonical(manifest).decode() + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conventional_oof_export.py")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--private-manifest-sha256", required=True)
    parser.add_argument("--producer-commit", default=PRODUCER_COMMIT)
    args = parser.parse_args(argv)
    manifest = export_selected_oof(
        args.repo_root,
        args.output_dir,
        expected_private_manifest_sha256=args.private_manifest_sha256,
        expected_commit=args.producer_commit,
    )
    print(canonical(manifest).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
