"""Goal 050 bounded, training-only compute canary.

The export path reads the private Goal 050 substrate and writes only float32
predictors plus uint8 response and knownness arrays.  The run path is
deliberately self-contained: remote hosts need only NumPy and PyTorch.
No scores, losses, thresholds, or ecological outcomes are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import random
import resource
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

CONFIG = Path("config/goal050_seawfb_compute_canary.json")
DEFAULT_ROOT = Path(".")
CONTINUOUS = [f"bio{i:02d}" for i in range(1, 20)] + ["elevation_mean", "elevation_sd"]
CATEGORICAL = ["nvis_mvg", "soil_order", "alum_secondary"]
ARCHITECTURE = {"blocks": 3, "width": 128, "bottleneck": 64, "dropout": 0.0}
RUN_FIELDS = frozenset({"schema_version", "status", "host_class", "hostname", "device", "python", "numpy", "pytorch", "cuda", "cuda_driver", "rows", "heads", "predictor_width", "epochs", "batch_size", "threads", "seed", "repeat", "bundle_sha256", "bundle_metadata_sha256", "canary_source_sha256", "config_sha256", "uv_lock_sha256", "multi_fit_seconds", "single_fit_seconds", "fit_seconds", "multi_epoch_seconds", "single_epoch_seconds", "multi_rows_per_second", "multi_row_head_per_second", "single_known_rows", "single_rows_per_second", "peak_rss_bytes", "gpu_peak_allocated_bytes", "gpu_peak_reserved_bytes", "finite", "deterministic", "multi_state_digest", "multi_probe_digest", "single_state_digest", "single_probe_digest", "ecological_metrics", "exit_status", "process_seconds"})
AGGREGATE_FIELDS = frozenset({"schema_version", "status", "batch_id", "host_class", "device", "requested_jobs", "successful_jobs", "batch_wall_seconds", "jobs_per_second", "row_head_epoch_per_second", "peak_rss_bytes", "gpu_peak_allocated_bytes", "gpu_peak_reserved_bytes", "bundle_sha256", "bundle_metadata_sha256", "canary_source_sha256", "config_sha256", "uv_lock_sha256", "finite", "deterministic", "ecological_metrics", "exit_status"})
EXPECTED_DEVICES = {"mac_cpu": "cpu", "deep_server_cpu": "cpu", "alien_gpu": "cuda:0"}
EXPECTED_AGGREGATES = {"mac_cpu-concurrency3": ("mac_cpu", 3), "deep_server_cpu-concurrency16": ("deep_server_cpu", 16), "deep_server_cpu-concurrency32": ("deep_server_cpu", 32)}


class CanaryError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_config(root: Path) -> dict[str, Any]:
    config = json.loads((root / CONFIG).read_text())
    _require(config.get("schema_version") == "goal050-seawfb-compute-canary-v1", "config_schema_drift")
    protocol = config.get("protocol", {})
    _require(protocol.get("selected_seed") == 394 and protocol.get("held_fold") == 0 and protocol.get("held_block") == 0, "frozen_selection_drift")
    _require(protocol.get("rows") == 90000 and protocol.get("heads") == 167, "canary_dimensions_drift")
    _require(protocol.get("batch_size") == 128 and protocol.get("epochs") == 2 and protocol.get("threads") == 1, "canary_workload_drift")
    aggregate = config.get("aggregate_calibration", {})
    _require(aggregate.get("mac_cpu") == [3] and aggregate.get("deep_server_cpu") == [16, 32] and aggregate.get("threads_per_job") == 1 and aggregate.get("device") == "cpu", "aggregate_calibration_drift")
    _require(protocol.get("architecture") == {"blocks": 3, "width": 128, "bottleneck": 64, "activation": "GELU", "normalization": "LayerNorm", "dropout": 0.0, "optimizer": "AdamW", "learning_rate": 0.001, "weight_decay": 0.001}, "architecture_drift")
    return config


def _deterministic_npz(arrays: Mapping[str, np.ndarray], metadata: Mapping[str, Any]) -> bytes:
    """Build a byte-stable npz; numpy.savez embeds a changing zip timestamp."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        entries = dict(arrays)
        entries["metadata.json"] = np.frombuffer(canonical_json(metadata), dtype=np.uint8)
        for name in sorted(entries):
            raw = io.BytesIO()
            if name == "metadata.json":
                payload = bytes(entries[name].tolist())
            else:
                np.lib.format.write_array(raw, np.asarray(entries[name]), allow_pickle=False)
                payload = raw.getvalue()
            info = zipfile.ZipInfo(f"{name}.npy" if name != "metadata.json" else name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, payload)
    return output.getvalue()


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _encode_predictors(frame: Any, transform: Mapping[str, Any]) -> np.ndarray:
    """Apply the frozen transform and deterministic one-hot encoding."""
    columns: list[np.ndarray] = []
    for name in CONTINUOUS:
        spec = transform["continuous"][name]
        values = np.asarray(frame[name], dtype=float)
        values = np.where(np.isfinite(values), values, float(spec["mean"]))
        columns.append(((values - float(spec["mean"])) / float(spec["population_sd"])).astype(np.float32))
    for name in CATEGORICAL:
        vocab = [str(value) for value in transform["categorical"][name]]
        lookup = {value: i for i, value in enumerate(vocab)}
        values = frame[name].astype("string").fillna("__MISSING__").astype(str).to_numpy()
        indices = np.fromiter((lookup.get(value, lookup["__UNSEEN__"]) for value in values), dtype=np.int64, count=len(values))
        one_hot = np.zeros((len(values), len(vocab)), dtype=np.float32)
        one_hot[np.arange(len(values)), indices] = 1.0
        columns.append(one_hot)
    return np.column_stack(columns).astype(np.float32, copy=False)


def _stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:16], 16)


def deidentified_responses(cell_ids: Sequence[str], full_richness: Sequence[int], memberships: Any, selected_indices: Sequence[int], held_species: Sequence[str], complement_heads: Sequence[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct selected Y/mask without returning identifiers or names."""
    ids = np.asarray(cell_ids, dtype=str)
    selected = np.asarray(selected_indices, dtype=np.int64)
    lookup = {cell: i for i, cell in enumerate(ids[selected])}
    full_lookup = {cell: i for i, cell in enumerate(ids)}
    held = set(map(str, held_species)); complement = list(map(str, complement_heads)); head_index = {name: i for i, name in enumerate(complement)}
    held_count = np.zeros(len(ids), dtype=np.int16)
    y = np.zeros((len(selected), len(complement)), dtype=np.uint8)
    for species, cell in memberships.itertuples(index=False, name=None):
        species = str(species); cell = str(cell)
        if cell not in lookup:
            continue
        if species in held:
            held_count[full_lookup[cell]] += 1
        if species in head_index:
            y[lookup[cell], head_index[species]] = 1
    adjusted = np.asarray(full_richness, dtype=np.int64)[selected] - held_count[selected]
    response_mask = ((y == 1) | (adjusted[:, None] >= 10)).astype(np.uint8)
    return y, response_mask, adjusted


def _export_arrays(root: Path, config: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, str]]:
    # These imports stay on export only, so the remote runner needs no project stack.
    import pandas as pd
    import pyarrow.parquet as pq

    source = {key: root / value for key, value in config["source"].items()}
    for key, path in source.items():
        _require(path.is_file(), f"missing_source:{key}")
    bindings = {key: sha256_file(path) for key, path in source.items()}
    manifest = json.loads(source["manifest"].read_text())
    transforms = json.loads(source["transforms"].read_text())
    crossfit = json.loads(source["crossfit"].read_text())
    _require(manifest.get("status") == "complete" and manifest.get("seed") == 394, "foundation_manifest_invalid")
    _require(manifest.get("bindings", {}).get("cells") == bindings["cells"] and manifest.get("bindings", {}).get("memberships") == bindings["memberships"], "foundation_binding_drift")
    _require(transforms.get("seed") == 394 and "fold_0" in transforms.get("transforms", {}), "transform_receipt_invalid")
    complement = list(crossfit.get("auxiliary_sets", {}).get("0", {}).get("full", []))
    held = [species for species, block in crossfit.get("focal_blocks", {}).items() if int(block) == 0]
    _require(len(held) == 16 and len(complement) == 167 and not set(held) & set(complement), "crossfit_block_invalid")

    cells = pq.read_table(source["cells"]).to_pandas()
    memberships = pq.read_table(source["memberships"]).to_pandas()
    required = {"cell_id", "fold", "effort_richness", *CONTINUOUS, *CATEGORICAL}
    _require(required <= set(cells.columns) and cells.cell_id.is_unique, "cell_schema_invalid")
    _require(set(memberships.columns) == {"species", "cell_id"} and memberships.duplicated().sum() == 0, "membership_schema_invalid")
    ids = cells.cell_id.astype(str).to_numpy()
    candidate_mask = cells.fold.to_numpy(dtype=np.int8) != 0
    row_index = {cell: i for i, cell in enumerate(ids)}
    held_count = np.zeros(len(cells), dtype=np.int16)
    for species, cell in memberships.itertuples(index=False, name=None):
        if str(species) in held:
            held_count[row_index[str(cell)]] += 1
    adjusted_richness = cells.effort_richness.to_numpy(dtype=np.int64) - held_count
    complement_presence = np.zeros(len(cells), dtype=bool)
    complement_set = set(complement)
    for species, cell in memberships.itertuples(index=False, name=None):
        if str(species) in complement_set and candidate_mask[row_index[str(cell)]]:
            complement_presence[row_index[str(cell)]] = True
    candidate_mask &= complement_presence | (adjusted_richness >= 10)
    candidate_indices = np.flatnonzero(candidate_mask)
    _require(len(candidate_indices) >= int(config["protocol"]["rows"]), "insufficient_canary_rows")
    ordered = sorted(candidate_indices.tolist(), key=lambda i: (_stable_hash(ids[i]), ids[i]))[: int(config["protocol"]["rows"])]
    selected = cells.iloc[ordered].reset_index(drop=True)
    selected_ids = selected.cell_id.astype(str).to_numpy()
    y, mask, adjusted_richness_selected = deidentified_responses(ids, cells.effort_richness.to_numpy(dtype=np.int64), memberships, ordered, held, complement)
    _require(np.all(y[mask == 1] <= 1), "response_encoding_invalid")
    for head in range(len(complement)):
        known = mask[:, head] == 1
        _require(np.any(y[known, head] == 1) and np.any(y[known, head] == 0), f"head_support_invalid:{head}")
    x = _encode_predictors(selected, transforms["transforms"]["fold_0"])
    _require(x.dtype == np.dtype("float32") and x.shape[0] == len(selected), "encoded_predictor_invalid")
    metadata = {
        "schema_version": "goal050-canary-bundle-v1",
        "rows": int(len(selected)),
        "heads": int(len(complement)),
        "predictor_width": int(x.shape[1]),
        "x_dtype": "float32",
        "y_dtype": "uint8",
        "mask_dtype": "uint8",
        "selected_seed": 394,
        "held_fold": 0,
        "held_block": 0,
        "selection_rule": "stable_sha256_cell_order_after_strict_block_exclusion",
        "transform": "goal050_fold_0_standardized_imputed_one_hot",
        "source_bindings": bindings,
        "support": {"all_heads_have_positive_and_background": True, "minimum_positive": int(min(np.sum((y == 1) & (mask == 1), axis=0))), "minimum_background": int(min(np.sum((y == 0) & (mask == 1), axis=0)))},
    }
    return {"X": x, "Y": y, "response_mask": mask}, metadata, bindings


def export_bundle(root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    root = Path(root); config = load_config(root)
    arrays, metadata, bindings = _export_arrays(root, config)
    raw = _deterministic_npz(arrays, metadata)
    bundle_digest = sha256_bytes(raw)
    bundle_dir = root / config["bundle"]["directory"]
    bundle = bundle_dir / f"bundle-{bundle_digest}.npz"
    _atomic_write(bundle, raw)
    config_path = root / CONFIG
    updated = json.loads(config_path.read_text())
    updated["source_bindings"] = bindings
    updated["bundle"].update({"filename": str(bundle.relative_to(root)), "sha256": bundle_digest, "metadata_sha256": sha256_bytes(canonical_json(metadata))})
    _atomic_write(config_path, json.dumps(updated, indent=2, sort_keys=True).encode() + b"\n")
    return {"status": "complete", "bundle": str(bundle.relative_to(root)), "bundle_sha256": bundle_digest, "metadata": metadata, "source_bindings": bindings}


def _load_bundle(path: Path, expected_digest: str | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    raw = path.read_bytes()
    if expected_digest is not None:
        _require(sha256_bytes(raw) == expected_digest, "bundle_digest_mismatch")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        _require(set(archive.files) == {"X", "Y", "response_mask", "metadata.json"}, "bundle_membership_invalid")
        x = np.asarray(archive["X"]); y = np.asarray(archive["Y"]); mask = np.asarray(archive["response_mask"])
        raw_metadata = archive["metadata.json"]
        metadata_bytes = raw_metadata if isinstance(raw_metadata, bytes) else bytes(raw_metadata.tolist())
        metadata = json.loads(metadata_bytes.decode())
    _require(x.dtype == np.float32 and y.dtype == np.uint8 and mask.dtype == np.uint8, "bundle_dtype_invalid")
    _require(x.ndim == 2 and y.ndim == 2 and mask.shape == y.shape and x.shape[0] == y.shape[0], "bundle_shape_invalid")
    _require(np.isfinite(x).all() and np.isin(y, [0, 1]).all() and np.isin(mask, [0, 1]).all(), "bundle_values_invalid")
    _require(metadata.get("rows") == x.shape[0] and metadata.get("heads") == y.shape[1] and metadata.get("predictor_width") == x.shape[1], "bundle_metadata_drift")
    for head in range(y.shape[1]):
        known = mask[:, head] == 1
        _require(np.any(y[known, head] == 1) and np.any(y[known, head] == 0), f"head_support_invalid:{head}")
    return x, y, mask, metadata


def _canary_provenance(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    configured = config.get("provenance", {})
    source = root / str(configured.get("canary_source", "src/dsdm_phase1/goal050_compute_canary.py"))
    lock = root / str(configured.get("uv_lock", "uv.lock"))
    _require(source.is_file() and lock.is_file(), "canary_provenance_source_missing")
    source_digest = sha256_file(source); lock_digest = sha256_file(lock)
    _require(configured.get("canary_source_sha256") == source_digest, "canary_source_digest_drift")
    _require(configured.get("uv_lock_sha256") == lock_digest, "uv_lock_digest_drift")
    return {"canary_source_sha256": source_digest, "uv_lock_sha256": lock_digest, "config_sha256": sha256_file(root / CONFIG)}


def _seed_all(seed: int, device: str) -> None:
    import torch
    torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def _model(input_width: int, heads: int, multi: bool):
    import torch
    from torch import nn
    class Block(nn.Module):
        def __init__(self):
            super().__init__(); self.norm = nn.LayerNorm(128); self.down = nn.Linear(128, 64); self.act = nn.GELU(); self.up = nn.Linear(64, 128)
        def forward(self, value): return value + self.up(self.act(self.down(self.norm(value))))
    class Net(nn.Module):
        def __init__(self):
            super().__init__(); self.stem = nn.Linear(input_width, 128); self.trunk = nn.Sequential(Block(), Block(), Block()); self.final_norm = nn.LayerNorm(128); self.head = nn.Linear(128, heads if multi else 1)
        def forward(self, value): return self.head(self.final_norm(self.trunk(self.stem(value))))
    model = Net()
    for layer in model.modules():
        if isinstance(layer, nn.Linear): nn.init.xavier_uniform_(layer.weight, gain=1.0); nn.init.zeros_(layer.bias)
        elif isinstance(layer, nn.LayerNorm): nn.init.ones_(layer.weight); nn.init.zeros_(layer.bias)
    return model


def _state_digest(model: Any) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode()); digest.update(str(tuple(value.shape)).encode()); digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def _fit(x: np.ndarray, y: np.ndarray, mask: np.ndarray, *, device_name: str, seed: int, multi: bool, epochs: int, batch_size: int) -> dict[str, Any]:
    import torch
    _seed_all(seed, device_name)
    device = torch.device(device_name)
    model = _model(x.shape[1], y.shape[1] if multi else 1, multi).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.001, foreach=False, fused=False)
    x_t = torch.as_tensor(np.array(x, copy=True), dtype=torch.float32, device=device)
    y_t = torch.as_tensor(np.array(y, copy=True), dtype=torch.float32, device=device)
    m_t = torch.as_tensor(np.array(mask, copy=True), dtype=torch.float32, device=device)
    generator = torch.Generator(device="cpu"); generator.manual_seed(seed)
    start = time.perf_counter(); epoch_seconds: list[float] = []
    for _ in range(epochs):
        epoch_start = time.perf_counter(); order = torch.randperm(len(x_t), generator=generator)
        model.train()
        for begin in range(0, len(order), batch_size):
            index = order[begin: begin + batch_size].to(device)
            logits = model(x_t[index])
            if not multi: logits = logits[:, 0]
            target = y_t[index] if multi else y_t[index, 0]
            known = m_t[index] if multi else m_t[index, 0]
            raw = torch.nn.functional.binary_cross_entropy_with_logits(logits, target, reduction="none")
            if multi:
                counts = known.sum(dim=0); per_head = (raw * known).sum(dim=0) / counts.clamp_min(1.0); loss = per_head[counts > 0].mean()
            else:
                loss = (raw * known).sum() / known.sum().clamp_min(1.0)
            _require(bool(torch.isfinite(loss)), "nonfinite_loss")
            opt.zero_grad(set_to_none=True); loss.backward()
            _require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), "nonfinite_gradient")
            opt.step()
            _require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "nonfinite_parameter")
        epoch_seconds.append(time.perf_counter() - epoch_start)
    fit_seconds = time.perf_counter() - start
    model.eval()
    with torch.no_grad(): probe = model(x_t[: min(32, len(x_t))]).detach().cpu().numpy()
    result = {"fit_seconds": float(fit_seconds), "epoch_seconds": [float(v) for v in epoch_seconds], "state_digest": _state_digest(model), "probe_digest": sha256_bytes(np.asarray(probe, dtype=np.float32).tobytes()), "finite": True}
    if device_name.startswith("cuda"):
        result["gpu_peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated(device)); result["gpu_peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved(device))
    return result


def run_canary(root: Path, bundle_path: Path, host_class: str, repeat: int, device_name: str | None = None, receipt_path: Path | None = None) -> dict[str, Any]:
    import torch
    root = Path(root); config = load_config(root)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    expected = config["bundle"].get("sha256")
    x, y, mask, metadata = _load_bundle(bundle_path, expected)
    provenance = _canary_provenance(root, config)
    _require(host_class in EXPECTED_DEVICES, "host_class_invalid")
    device_name = device_name or EXPECTED_DEVICES[host_class]
    _require(device_name == EXPECTED_DEVICES[host_class], "host_device_contract")
    if device_name.startswith("cuda"): _require(torch.cuda.device_count() >= 1, "cuda_device_missing")
    cuda_driver = None
    if device_name.startswith("cuda"):
        try:
            query = subprocess.run(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"], check=True, capture_output=True, text=True, timeout=10)
            cuda_driver = query.stdout.splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            cuda_driver = None
    process_start = time.perf_counter(); rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    multi = _fit(x, y, mask, device_name=device_name, seed=int(config["protocol"]["seed"]), multi=True, epochs=2, batch_size=128)
    sentinel = 0
    single_known = mask[:, sentinel] == 1
    single = _fit(x[single_known], y[single_known, sentinel:sentinel + 1], mask[single_known, sentinel:sentinel + 1], device_name=device_name, seed=int(config["protocol"]["seed"]) + 1, multi=False, epochs=2, batch_size=128)
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = int(max(rss_before, rss_after) * (1 if platform.system() == "Darwin" else 1024))
    total_rows = int(len(x) * 2); total_row_heads = int(len(x) * y.shape[1] * 2)
    receipt = {
        "schema_version": "goal050-compute-canary-run-v1",
        "status": "complete",
        "host_class": host_class,
        "hostname": socket.gethostname(),
        "device": device_name,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pytorch": torch.__version__,
        "cuda": torch.version.cuda if device_name.startswith("cuda") else None, "cuda_driver": cuda_driver,
        "rows": int(len(x)), "heads": int(y.shape[1]), "predictor_width": int(x.shape[1]),
        "epochs": 2, "batch_size": 128, "threads": int(torch.get_num_threads()), "seed": int(config["protocol"]["seed"]), "repeat": int(repeat),
        "bundle_sha256": sha256_file(bundle_path), "bundle_metadata_sha256": sha256_bytes(canonical_json(metadata)),
        "canary_source_sha256": provenance["canary_source_sha256"], "config_sha256": provenance["config_sha256"], "uv_lock_sha256": provenance["uv_lock_sha256"],
        "multi_fit_seconds": multi["fit_seconds"], "single_fit_seconds": single["fit_seconds"], "fit_seconds": float(multi["fit_seconds"] + single["fit_seconds"]),
        "multi_epoch_seconds": multi["epoch_seconds"], "single_epoch_seconds": single["epoch_seconds"],
        "multi_rows_per_second": float(total_rows / multi["fit_seconds"]), "multi_row_head_per_second": float(total_row_heads / multi["fit_seconds"]),
        "single_known_rows": int(single_known.sum()), "single_rows_per_second": float(single_known.sum() * 2 / single["fit_seconds"]),
        "peak_rss_bytes": rss_bytes,
        "gpu_peak_allocated_bytes": multi.get("gpu_peak_allocated_bytes", 0), "gpu_peak_reserved_bytes": multi.get("gpu_peak_reserved_bytes", 0),
        "finite": bool(multi["finite"] and single["finite"]), "deterministic": True,
        "multi_state_digest": multi["state_digest"], "multi_probe_digest": multi["probe_digest"], "single_state_digest": single["state_digest"], "single_probe_digest": single["probe_digest"],
        "ecological_metrics": 0, "exit_status": 0, "process_seconds": float(time.perf_counter() - process_start)
    }
    if receipt_path is not None:
        _atomic_write(Path(receipt_path), json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n")
    return receipt


def _number(value: Any, message: str, *, positive: bool = False) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value), message)
    if positive:
        _require(float(value) > 0, message)
    return float(value)


def _validate_run(receipt: Mapping[str, Any], config: Mapping[str, Any] | None = None, provenance: Mapping[str, Any] | None = None, expected_repeats: set[int] | None = None) -> None:
    _require(set(receipt) == RUN_FIELDS, "run_schema_drift")
    _require(receipt.get("status") == "complete" and receipt.get("exit_status") == 0, "run_incomplete")
    _require(receipt.get("finite") is True and receipt.get("deterministic") is True and receipt.get("ecological_metrics") == 0, "run_gate_failed")
    _require(receipt.get("schema_version") == "goal050-compute-canary-run-v1", "run_schema_version")
    host = receipt.get("host_class"); _require(host in EXPECTED_DEVICES and receipt.get("device") == EXPECTED_DEVICES[host], "run_host_device")
    _require(isinstance(receipt.get("hostname"), str) and receipt["hostname"], "run_hostname_invalid")
    protocol = config["protocol"] if config is not None else {"rows": 90000, "heads": 167, "batch_size": 128, "epochs": 2, "threads": 1, "seed": 5050394}
    for key in ("rows", "heads", "predictor_width", "epochs", "batch_size", "threads", "seed"):
        expected = 103 if key == "predictor_width" else protocol[key]
        _require(receipt.get(key) == expected, f"run_{key}_drift")
    _require(isinstance(receipt.get("repeat"), int) and not isinstance(receipt["repeat"], bool) and receipt["repeat"] > 0, "run_repeat_invalid")
    if expected_repeats is not None: _require(receipt["repeat"] in expected_repeats, "run_repeat_panel")
    for key in ("multi_fit_seconds", "single_fit_seconds", "fit_seconds", "process_seconds", "multi_rows_per_second", "multi_row_head_per_second", "single_rows_per_second", "single_known_rows", "peak_rss_bytes"):
        _number(receipt.get(key), f"run_{key}_invalid", positive=True)
    for key in ("multi_epoch_seconds", "single_epoch_seconds"):
        values = receipt.get(key); _require(isinstance(values, list) and len(values) == 2, f"run_{key}_invalid")
        for value in values: _number(value, f"run_{key}_invalid", positive=True)
    for key in ("gpu_peak_allocated_bytes", "gpu_peak_reserved_bytes"):
        _number(receipt.get(key), f"run_{key}_invalid", positive=host == "alien_gpu")
    for key in ("multi_state_digest", "multi_probe_digest", "single_state_digest", "single_probe_digest", "bundle_sha256"):
        _require(isinstance(receipt.get(key), str) and len(receipt[key]) == 64, f"receipt_digest_invalid:{key}")
    for key in ("bundle_metadata_sha256", "canary_source_sha256", "config_sha256", "uv_lock_sha256"):
        _require(isinstance(receipt.get(key), str) and len(receipt[key]) == 64, f"receipt_digest_invalid:{key}")
    if config is not None:
        _require(receipt["bundle_sha256"] == config["bundle"]["sha256"] and receipt["bundle_metadata_sha256"] == config["bundle"]["metadata_sha256"], "run_bundle_binding_drift")
    if provenance is not None:
        _require(all(receipt[key] == value for key, value in provenance.items()), "run_provenance_drift")
    if host == "alien_gpu":
        _require(isinstance(receipt.get("cuda"), str) and isinstance(receipt.get("cuda_driver"), str), "run_cuda_metadata_invalid")
    else:
        _require(receipt.get("cuda") is None and receipt.get("cuda_driver") is None, "run_cpu_cuda_metadata")


def _validate_aggregate(receipt: Mapping[str, Any], config: Mapping[str, Any] | None = None, expected_provenance: Mapping[str, str] | None = None) -> None:
    _require(set(receipt) == AGGREGATE_FIELDS, "aggregate_schema_drift")
    _require(receipt.get("status") == "complete" and receipt.get("exit_status") == 0, "aggregate_incomplete")
    _require(receipt.get("schema_version") == "goal050-compute-canary-aggregate-v1", "aggregate_schema_version")
    batch_id = receipt.get("batch_id"); _require(batch_id in EXPECTED_AGGREGATES, "aggregate_batch_contract")
    expected_host, expected_jobs = EXPECTED_AGGREGATES[batch_id]
    _require(receipt.get("host_class") == expected_host and receipt.get("device") == "cpu" and receipt.get("requested_jobs") == expected_jobs and receipt.get("successful_jobs") == expected_jobs, "aggregate_batch_contract")
    _require(receipt.get("finite") is True and receipt.get("deterministic") is True and receipt.get("ecological_metrics") == 0, "aggregate_gate_failed")
    wall = _number(receipt.get("batch_wall_seconds"), "aggregate_wall_invalid", positive=True)
    jobs = _number(receipt.get("successful_jobs"), "aggregate_jobs_invalid", positive=True)
    expected_jobs_per_second = jobs / wall
    rows = int(config["protocol"]["rows"]) if config is not None else 90000
    heads = int(config["protocol"]["heads"]) if config is not None else 167
    epochs = int(config["protocol"]["epochs"]) if config is not None else 2
    expected_row_head = jobs * rows * heads * epochs / wall
    _require(np.isclose(_number(receipt.get("jobs_per_second"), "aggregate_jobs_per_second_invalid", positive=True), expected_jobs_per_second, rtol=1e-12, atol=1e-12), "aggregate_jobs_per_second_forged")
    _require(np.isclose(_number(receipt.get("row_head_epoch_per_second"), "aggregate_row_head_epoch_per_second_invalid", positive=True), expected_row_head, rtol=1e-12, atol=1e-12), "aggregate_row_head_epoch_per_second_forged")
    _number(receipt.get("peak_rss_bytes"), "aggregate_peak_rss_invalid", positive=True)
    _number(receipt.get("gpu_peak_allocated_bytes"), "aggregate_gpu_allocated_invalid")
    _number(receipt.get("gpu_peak_reserved_bytes"), "aggregate_gpu_reserved_invalid")
    for key in ("bundle_sha256", "bundle_metadata_sha256"):
        _require(isinstance(receipt.get(key), str) and len(receipt[key]) == 64, f"aggregate_digest_invalid:{key}")
    if config is not None:
        _require(receipt["bundle_sha256"] == config["bundle"]["sha256"] and receipt["bundle_metadata_sha256"] == config["bundle"]["metadata_sha256"], "aggregate_bundle_binding_drift")
    for key in ("canary_source_sha256", "config_sha256", "uv_lock_sha256"):
        _require(isinstance(receipt.get(key), str) and len(receipt[key]) == 64, f"aggregate_provenance_invalid:{key}")
        if expected_provenance is not None:
            _require(receipt.get(key) == expected_provenance[key], f"aggregate_provenance_drift:{key}")


def run_aggregate(root: Path, bundle_path: Path, host_class: str, concurrency: int, batch_id: str, device_name: str = "cpu") -> dict[str, Any]:
    """Launch bounded clean workers and retain only aggregate evidence."""
    root = Path(root); config = load_config(root)
    expected = {"mac_cpu": [3], "deep_server_cpu": [16, 32]}
    _require(host_class in expected and concurrency in expected[host_class], "aggregate_calibration_panel_drift")
    _require(device_name == "cpu", "aggregate_device_drift")
    _load_bundle(bundle_path, config["bundle"].get("sha256"))
    provenance = _canary_provenance(root, config)
    output_dir = root / config["private_receipt_directory"] / "aggregate" / batch_id
    output_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy(); environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    started = time.perf_counter(); processes = []
    for index in range(concurrency):
        receipt = output_dir / f"job-{index + 1:03d}.json"
        command = [sys.executable, "-m", "dsdm_phase1.goal050_compute_canary", "run", "--root", str(root), "--bundle", str(bundle_path), "--host-class", host_class, "--repeat", str(index + 1), "--device", device_name, "--receipt", str(receipt)]
        processes.append(subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    statuses = [process.wait() for process in processes]
    wall = time.perf_counter() - started; children = []
    for index, status in enumerate(statuses):
        path = output_dir / f"job-{index + 1:03d}.json"
        if status == 0 and path.is_file():
            child = json.loads(path.read_text()); _validate_run(child, config, provenance, set(range(1, concurrency + 1))); children.append(child)
    successful = len(children); total_units = successful * int(config["protocol"]["rows"]) * int(config["protocol"]["heads"]) * int(config["protocol"]["epochs"])
    bundle_digests = {child["bundle_sha256"] for child in children}; metadata_digests = {child["bundle_metadata_sha256"] for child in children}
    result = {"schema_version": "goal050-compute-canary-aggregate-v1", "status": "complete" if successful == concurrency else "failed", "batch_id": batch_id, "host_class": host_class, "device": device_name, "requested_jobs": concurrency, "successful_jobs": successful, "batch_wall_seconds": float(wall), "jobs_per_second": float(successful / wall) if wall else 0.0, "row_head_epoch_per_second": float(total_units / wall) if wall else 0.0, "peak_rss_bytes": int(max((child["peak_rss_bytes"] for child in children), default=0)), "gpu_peak_allocated_bytes": int(max((child.get("gpu_peak_allocated_bytes", 0) for child in children), default=0)), "gpu_peak_reserved_bytes": int(max((child.get("gpu_peak_reserved_bytes", 0) for child in children), default=0)), "bundle_sha256": next(iter(bundle_digests), None) if len(bundle_digests) == 1 else None, "bundle_metadata_sha256": next(iter(metadata_digests), None) if len(metadata_digests) == 1 else None, "canary_source_sha256": provenance["canary_source_sha256"], "config_sha256": provenance["config_sha256"], "uv_lock_sha256": provenance["uv_lock_sha256"], "finite": successful == concurrency and all(child["finite"] for child in children), "deterministic": successful == concurrency and len({child["multi_state_digest"] for child in children}) == 1 and len({child["multi_probe_digest"] for child in children}) == 1, "ecological_metrics": 0, "exit_status": 0 if successful == concurrency and len(bundle_digests) == 1 and len(metadata_digests) == 1 else 1}
    _atomic_write(output_dir.parent / f"{batch_id}.json", json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
    return result


def _aggregate_row_head_rate(receipt: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> float:
    rows = int(config["protocol"]["rows"]) if config is not None else 90000
    heads = int(config["protocol"]["heads"]) if config is not None else 167
    epochs = int(config["protocol"]["epochs"]) if config is not None else 2
    return float(receipt["successful_jobs"] * rows * heads * epochs / receipt["batch_wall_seconds"])


def _select_route(single_medians: Mapping[str, float], aggregate: Mapping[str, Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> tuple[str | None, dict[str, Any]]:
    required = {"mac_cpu": "mac_cpu-concurrency3", "deep_server_cpu_16": "deep_server_cpu-concurrency16", "deep_server_cpu_32": "deep_server_cpu-concurrency32"}
    if set(single_medians) != {"mac_cpu", "deep_server_cpu", "alien_gpu"} or any(key not in aggregate for key in required.values()):
        return None, {"status": "incomplete_evidence", "reason": "single_job_or_required_aggregate_missing"}
    options = {
        "mac_cpu": {"single_fit_seconds": float(single_medians["mac_cpu"]), "aggregate_row_head_epoch_per_second": _aggregate_row_head_rate(aggregate[required["mac_cpu"]], config)},
        "deep_server_cpu": {"single_fit_seconds": float(single_medians["deep_server_cpu"]), "aggregate_row_head_epoch_per_second": float(max(_aggregate_row_head_rate(aggregate[required["deep_server_cpu_16"]], config), _aggregate_row_head_rate(aggregate[required["deep_server_cpu_32"]], config)))},
        "alien_gpu": {"single_fit_seconds": float(single_medians["alien_gpu"]), "aggregate_row_head_epoch_per_second": None, "eligibility": "not comparable for aggregate route because no GPU aggregate calibration was prescribed"},
    }
    latency_winner = min(("mac_cpu", "deep_server_cpu", "alien_gpu"), key=lambda name: options[name]["single_fit_seconds"])
    capacity_options = {name: row["aggregate_row_head_epoch_per_second"] for name, row in options.items() if row["aggregate_row_head_epoch_per_second"] is not None}
    capacity_winner = max(capacity_options, key=capacity_options.get)
    ordered = sorted(capacity_options.values(), reverse=True); margin = float(ordered[0] / ordered[1]) if ordered[1] else float("inf")
    if latency_winner == capacity_winner:
        decision = latency_winner
        reason = "single_job_latency_and_aggregate_capacity_agree"
    elif margin >= 1.10:
        decision = capacity_winner
        reason = "aggregate_capacity_wins_with_at_least_10_percent_margin_over_other_cpu_route"
    else:
        decision = None
        reason = "single_job_latency_and_aggregate_capacity_are_equivocal"
    return decision, {"status": "compared", "options": options, "single_latency_winner": latency_winner, "aggregate_capacity_winner": capacity_winner, "capacity_margin": margin, "reason": reason}


def summarize(root: Path) -> dict[str, Any]:
    root = Path(root); config = load_config(root)
    run_dir = root / config["private_receipt_directory"]
    receipts = []
    for path in sorted(run_dir.glob("*.json")):
        receipt = json.loads(path.read_text()); receipts.append(receipt)
    expected_provenance = _canary_provenance(root, config)
    expected_panel = {(host, repeat) for host in EXPECTED_DEVICES for repeat in (1, 2)}
    seen_panel = set()
    for receipt in receipts:
        _validate_run(receipt, config, expected_provenance)
        panel_key = (receipt["host_class"], receipt["repeat"])
        _require(panel_key in expected_panel and panel_key not in seen_panel, "host_repeat_panel")
        seen_panel.add(panel_key)
    _require(len(receipts) == 6 and seen_panel == expected_panel, "expected_six_runs")
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for receipt in receipts: groups.setdefault(str(receipt["host_class"]), []).append(receipt)
    _require(set(groups) == {"mac_cpu", "deep_server_cpu", "alien_gpu"} and all(len(v) == 2 for v in groups.values()), "host_repeat_contract")
    for group in groups.values():
        _require(group[0]["bundle_sha256"] == group[1]["bundle_sha256"], "repeat_bundle_drift")
        for key in ("multi_state_digest", "multi_probe_digest", "single_state_digest", "single_probe_digest"):
            _require(group[0][key] == group[1][key], f"repeat_{key}_drift")
    all_bundle_digests = {receipt["bundle_sha256"] for receipt in receipts}; all_metadata_digests = {receipt["bundle_metadata_sha256"] for receipt in receipts}
    _require(all_bundle_digests == {config["bundle"]["sha256"]} and all_metadata_digests == {config["bundle"]["metadata_sha256"]}, "cross_host_bundle_digest_drift")
    _require(all(receipt.get(key) == value for receipt in receipts for key, value in expected_provenance.items()), "cross_host_provenance_drift")
    aggregate_dir = run_dir / "aggregate"; aggregate: dict[str, Mapping[str, Any]] = {}
    for path in sorted(aggregate_dir.glob("*.json")):
        receipt = json.loads(path.read_text()); _validate_aggregate(receipt, config, expected_provenance); aggregate[str(receipt["batch_id"])] = receipt
    _require(set(aggregate) == set(EXPECTED_AGGREGATES), "aggregate_panel")
    medians = {name: float(np.median([r["multi_fit_seconds"] for r in rows])) for name, rows in groups.items()}
    passed = all(r["finite"] and r["deterministic"] and r["peak_rss_bytes"] > 0 and r["exit_status"] == 0 for r in receipts) and all(batch["status"] == "complete" for batch in aggregate.values())
    selected_route, route_comparison = _select_route(medians, aggregate, config)
    route = f"{selected_route}_vectorized_pretraining_and_target_jobs" if selected_route else "unresolved_equivocal_latency_capacity" if passed else "no_route_passed"
    per_epoch = {name: {f"epoch_{epoch + 1}": {"seconds": float(np.median([r["multi_epoch_seconds"][epoch] for r in rows])), "rows_per_second": float(config["protocol"]["rows"] / np.median([r["multi_epoch_seconds"][epoch] for r in rows])), "row_head_per_second": float(config["protocol"]["rows"] * config["protocol"]["heads"] / np.median([r["multi_epoch_seconds"][epoch] for r in rows]))} for epoch in range(2)} for name, rows in groups.items()}
    low_units = int(config["protocol"]["rows"] * 20 * 2)
    high_units = int(787357 * config["protocol"]["heads"] * 300)
    result = {"schema_version": "goal050-compute-canary-v1", "status": "complete" if passed else "failed", "bundle": {"filename": config["bundle"]["filename"], "sha256": config["bundle"]["sha256"], "metadata_sha256": config["bundle"]["metadata_sha256"], "rows": config["protocol"]["rows"], "heads": config["protocol"]["heads"], "predictor_width": 103}, "eligibility": {"exact_frozen_candidate_pool_rows": int(config["protocol"].get("eligible_rows_under_frozen_rule", 94873)), "canary_size_rows": int(config["protocol"]["rows"]), "scientific_eligibility_rule_relaxed": False, "resolution": "Only the canary bundle size changed from 100000 to 90000."}, "provenance": expected_provenance, "source_bindings": config.get("source_bindings", {}), "runs": receipts, "aggregate_calibration": list(aggregate.values()), "median_multi_fit_seconds": medians, "per_epoch_multi_throughput": per_epoch, "workload_projection": {"unit": "one row-head-epoch", "canary_units": int(config["protocol"]["rows"] * config["protocol"]["heads"] * config["protocol"]["epochs"]), "planning_unit_range": [low_units, high_units], "interpretation": "Linear workload-unit projection only; production wall time is not claimed."}, "route_comparison": route_comparison, "route_decision": route, "route_scope": "bridge_like_vectorized_pytorch_grids_only", "ecological_metrics": 0, "resumability": {"status": "proposed_untested", "production_launched": False, "sessions": ["goal051-conventional-deep", "goal052-dsdm-deep"], "checkpoint_unit": "one target-fold-seed endpoint", "input_paths": [config["bundle"]["filename"], "config/goal050_seawfb_compute_canary.json"], "output_path_patterns": {"goal051_conventional": "data/processed/dsdm/goal051-conventional/<target>-fold<fold>-<seed>/", "goal052_dsdm": "data/processed/dsdm/goal052-dsdm/<target>-fold<fold>-<seed>/"}, "completion_marker": "atomic run.exit plus independent validation receipt", "wake_up": "dSDM orchestrator when a named tmux session completes or blocks"}}
    _atomic_write(root / config["tracked_output"], json.dumps(result, indent=2, sort_keys=True).encode() + b"\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("export", "run", "aggregate", "summarize"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--host-class")
    parser.add_argument("--repeat", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--batch-id")
    parser.add_argument("--device", default=None)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.command == "export": result = export_bundle(args.root)
    elif args.command == "run":
        _require(args.bundle is not None and args.host_class is not None and args.repeat is not None and args.repeat > 0, "run_arguments_invalid")
        result = run_canary(args.root, args.bundle, args.host_class, args.repeat, args.device, args.receipt)
    elif args.command == "aggregate":
        _require(args.bundle is not None and args.host_class is not None and args.concurrency is not None and args.batch_id is not None, "aggregate_arguments_invalid")
        result = run_aggregate(args.root, args.bundle, args.host_class, args.concurrency, args.batch_id, args.device or "cpu")
    else: result = summarize(args.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
