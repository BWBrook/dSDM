"""Atomic, fail-closed checkpoints for the Goal 052 neural leaves."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch

from .mainland_dsdm import state_digest
from .seawfb_modeling import digest, require, sha256_file


_PRETRAINING_KIND = "pretraining"
_LEAVES_KIND = "leaves"
_KINDS = {_PRETRAINING_KIND: ".pt", _LEAVES_KIND: ".parquet", "leaf": ".parquet"}
_LEAF_SCHEMA = pa.schema(
    [
        pa.field("cell_id", pa.string(), nullable=False),
        pa.field("y", pa.int8(), nullable=False),
        pa.field("score", pa.float64(), nullable=False),
    ]
)


def _require_key(key: Mapping[str, Any]) -> dict[str, Any]:
    require(isinstance(key, Mapping), "checkpoint_key_invalid")
    result = dict(key)
    require("identity" in result and result["identity"] is not None, "checkpoint_key_identity_missing")
    require(any(name != "identity" for name in result), "checkpoint_key_dimensions_missing")
    try:
        digest(result)
    except (TypeError, ValueError):
        require(False, "checkpoint_key_not_json_serializable")
    return result


def checkpoint_paths(private_root: Path, kind: str, key: Mapping[str, Any]) -> tuple[Path, Path]:
    """Return payload and receipt paths for a key without creating files."""
    require(kind in _KINDS, "checkpoint_kind_invalid")
    checked = _require_key(key)
    stem = digest(checked)
    directory = Path(private_root) / kind
    return directory / f"{stem}{_KINDS[kind]}", directory / f"{stem}.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        require(False, "checkpoint_receipt_invalid")
    require(isinstance(value, dict), "checkpoint_receipt_invalid")
    return value


def _atomic_bytes(path: Path, writer: Any, suffix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=suffix, delete=False) as handle:
            temporary = Path(handle.name)
        writer(temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _atomic_bytes(path, lambda temporary: temporary.write_bytes(raw), ".json")


def _atomic_torch(path: Path, state: Mapping[str, torch.Tensor]) -> None:
    _atomic_bytes(path, lambda temporary: torch.save(dict(state), temporary), ".pt")


def _atomic_parquet(path: Path, table: pa.Table) -> None:
    _atomic_bytes(path, lambda temporary: pq.write_table(table, temporary, compression="zstd"), ".parquet")


def _finite_state(state: Mapping[str, torch.Tensor]) -> None:
    require(isinstance(state, Mapping) and bool(state), "checkpoint_state_invalid")
    require(
        all(isinstance(value, torch.Tensor) and torch.isfinite(value).all().item() for value in state.values()),
        "checkpoint_state_nonfinite",
    )


def _loaded_state(path: Path) -> dict[str, torch.Tensor]:
    try:
        state = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:  # corrupt or non-weights payloads are committed-state failures
        require(False, "checkpoint_payload_invalid")
    require(isinstance(state, Mapping), "checkpoint_state_invalid")
    result = dict(state)
    _finite_state(result)
    return result


def save_pretraining(
    private_root: Path,
    key: Mapping[str, Any],
    state: Mapping[str, torch.Tensor],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically write a shared pretraining state followed by its receipt."""
    checked = _require_key(key)
    require(isinstance(receipt, Mapping), "checkpoint_receipt_invalid")
    payload_path, receipt_path = checkpoint_paths(private_root, _PRETRAINING_KIND, checked)
    _finite_state(state)
    payload = {name: value.detach().cpu().clone() for name, value in state.items()}
    _atomic_torch(payload_path, payload)
    saved = dict(receipt)
    saved.update({
        "key": checked,
        "model_sha256": sha256_file(payload_path),
        "shared_state_digest": state_digest(payload),
    })
    _atomic_json(receipt_path, saved)
    return saved


def load_pretraining(
    private_root: Path, key: Mapping[str, Any]
) -> tuple[dict[str, torch.Tensor], dict[str, Any]] | None:
    """Load a verified pretraining checkpoint; a receipt-less orphan is absent."""
    checked = _require_key(key)
    payload_path, receipt_path = checkpoint_paths(private_root, _PRETRAINING_KIND, checked)
    if not receipt_path.is_file():
        return None
    require(not receipt_path.is_symlink(), "pretraining_receipt_invalid")
    require(payload_path.is_file() and not payload_path.is_symlink(), "pretraining_payload_missing")
    receipt = _read_json(receipt_path)
    require(receipt.get("key") == checked, "pretraining_key_mismatch")
    require(receipt.get("model_sha256") == sha256_file(payload_path), "pretraining_payload_digest_mismatch")
    state = _loaded_state(payload_path)
    require(receipt.get("shared_state_digest") == state_digest(state), "pretraining_state_digest_mismatch")
    return state, receipt


def _leaf_arrays(cell_ids: Sequence[str], y: Sequence[int], scores: Sequence[float]) -> tuple[tuple[str, ...], np.ndarray, np.ndarray]:
    cells = tuple(str(value) if isinstance(value, str) else value for value in cell_ids)
    labels = np.asarray(y)
    probabilities = np.asarray(scores, dtype=np.float64)
    require(labels.ndim == 1 and probabilities.ndim == 1, "leaf_rows_invalid")
    require(len(cells) == len(labels) == len(probabilities) > 0, "leaf_rows_invalid")
    require(all(isinstance(value, str) and value for value in cells), "leaf_cell_ids_invalid")
    require(len(set(cells)) == len(cells), "leaf_cell_ids_duplicate")
    require(np.issubdtype(labels.dtype, np.integer), "leaf_labels_type_invalid")
    require(np.isin(labels, (0, 1)).all(), "leaf_labels_invalid")
    labels = labels.astype(np.int8, copy=False)
    require(np.isfinite(probabilities).all() and np.all((probabilities >= 0) & (probabilities <= 1)), "leaf_scores_invalid")
    return cells, labels, probabilities


def save_leaf(
    private_root: Path,
    key: Mapping[str, Any],
    cells: Sequence[str],
    y: Sequence[int],
    scores: Sequence[float],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically write canonical held-cell scores and its receipt."""
    checked = _require_key(key)
    require(isinstance(receipt, Mapping), "checkpoint_receipt_invalid")
    cell_ids, labels, probabilities = _leaf_arrays(cells, y, scores)
    payload_path, receipt_path = checkpoint_paths(private_root, _LEAVES_KIND, checked)
    table = pa.Table.from_arrays(
        [pa.array(cell_ids, type=pa.string()), pa.array(labels, type=pa.int8()), pa.array(probabilities, type=pa.float64())],
        schema=_LEAF_SCHEMA,
    )
    _atomic_parquet(payload_path, table)
    saved = dict(receipt)
    saved.update({"key": checked, "prediction_sha256": sha256_file(payload_path)})
    _atomic_json(receipt_path, saved)
    return saved


def load_leaf(
    private_root: Path,
    key: Mapping[str, Any],
    expected_cells: Sequence[str],
    expected_y: Sequence[int],
) -> tuple[np.ndarray, dict[str, Any]] | None:
    """Load scores only after exact receipt, schema, cell-order, and label checks."""
    checked = _require_key(key)
    expected_cell_ids, expected_labels, _ = _leaf_arrays(expected_cells, expected_y, np.zeros(len(expected_cells), dtype=np.float64))
    payload_path, receipt_path = checkpoint_paths(private_root, _LEAVES_KIND, checked)
    if not receipt_path.is_file():
        return None
    require(not receipt_path.is_symlink(), "leaf_receipt_invalid")
    require(payload_path.is_file() and not payload_path.is_symlink(), "leaf_payload_missing")
    receipt = _read_json(receipt_path)
    require(receipt.get("key") == checked, "leaf_key_mismatch")
    require(receipt.get("prediction_sha256") == sha256_file(payload_path), "leaf_payload_digest_mismatch")
    try:
        table = pq.read_table(payload_path)
    except Exception:
        require(False, "leaf_payload_invalid")
    require(table.schema == _LEAF_SCHEMA, "leaf_schema_invalid")
    cells = tuple(table["cell_id"].to_pylist())
    labels = table["y"].to_numpy(zero_copy_only=False).astype(np.int8)
    scores = table["score"].to_numpy(zero_copy_only=False).astype(np.float64)
    require(cells == expected_cell_ids, "leaf_cell_order_mismatch")
    require(np.array_equal(labels, expected_labels), "leaf_labels_mismatch")
    require(np.isfinite(scores).all() and np.all((scores >= 0) & (scores <= 1)), "leaf_scores_invalid")
    return scores, receipt


__all__ = [
    "checkpoint_paths",
    "load_leaf",
    "load_pretraining",
    "save_leaf",
    "save_pretraining",
]
