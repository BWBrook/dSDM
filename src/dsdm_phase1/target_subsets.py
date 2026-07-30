"""Deterministic hierarchical proportional-deficit target-row ladders."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Mapping

from .modeling_contract import ModelingContractError, RowKey, RowSet


def endpoint_sizes(n: int) -> Mapping[str, int]:
    if n < 1:
        raise ModelingContractError("empty_training_rows")
    return {"fraction25": (n + 2) // 4, "fraction50": (n + 1) // 2, "fraction100": n}


def _priority(master_seed: str, ladder_id: str, kind: str, *parts: str) -> bytes:
    payload = "\x1f".join((master_seed, ladder_id, kind, *map(str, parts))).encode("utf-8")
    return hashlib.sha256(payload).digest()


def hierarchical_order(rows: RowSet, ladder_id: str, master_seed: str) -> tuple[RowKey, ...]:
    if not ladder_id:
        raise ModelingContractError("missing_ladder_id")
    n = len(rows.keys)
    if n == 0:
        raise ModelingContractError("empty_training_rows")
    if len(set(rows.pa.tolist())) < 2:
        raise ModelingContractError("single_class_training")
    # Buckets are keyed by response source then nested Goal025 microcluster.
    buckets: dict[str, dict[str, list[tuple[bytes, RowKey]]]] = defaultdict(lambda: defaultdict(list))
    for key, source, micro in zip(rows.keys, rows.response_source, rows.microcluster):
        buckets[source][micro].append((_priority(master_seed, ladder_id, "row", key.species_id, key.grid_cell_id), key))
    for source in buckets:
        for micro in buckets[source]:
            buckets[source][micro].sort(key=lambda item: item[0])
    source_counts = Counter(rows.response_source)
    cluster_counts = {(source, micro): len(values) for source, clusters in buckets.items() for micro, values in clusters.items()}
    selected_source: Counter[str] = Counter()
    selected_cluster: dict[str, Counter[str]] = {source: Counter() for source in buckets}
    source_priority = {source: _priority(master_seed, ladder_id, "source", source) for source in buckets}
    cluster_priority = {(source, micro): _priority(master_seed, ladder_id, "microcluster", source, micro) for source in buckets for micro in buckets[source]}
    order: list[RowKey] = []
    for k in range(1, n + 1):
        # Equal denominators let us compare exact integer deficits.
        source = min(
            buckets,
            key=lambda s: (
                -(k * source_counts[s] - selected_source[s] * n),
                source_priority[s],
            ),
        )
        selected_source[source] += 1
        k_source = selected_source[source]
        n_source = source_counts[source]
        clusters = buckets[source]
        micro = min(
            clusters,
            key=lambda m: (
                -(k_source * cluster_counts[(source, m)] - selected_cluster[source][m] * n_source),
                cluster_priority[(source, m)],
            ),
        )
        selected_cluster[source][micro] += 1
        _, key = clusters[micro].pop(0)
        order.append(key)
    return tuple(order)


@dataclass(frozen=True)
class SubsetEndpoint:
    fraction_id: str
    ladder_id: str
    keys: tuple[RowKey, ...]
    subset_digest: str
    full_alias_id: str | None


def build_ladders(rows: RowSet, master_seed: str = "dsdm-goal028-v1") -> Mapping[tuple[str, str], SubsetEndpoint]:
    ordering = {}
    out: dict[tuple[str, str], SubsetEndpoint] = {}
    sizes = endpoint_sizes(len(rows.keys))
    full_keys = tuple(sorted(rows.keys))
    full_digest = hashlib.sha256("\n".join(f"{key.species_id}\x1f{key.grid_cell_id}" for key in full_keys).encode()).hexdigest()
    canonical_full = SubsetEndpoint("fraction100", "full", full_keys, full_digest, "full")
    for ladder_id in ("ladder00", "ladder01", "ladder02"):
        ordering[ladder_id] = hierarchical_order(rows, ladder_id, master_seed)
        for fraction_id, size in sizes.items():
            # The full endpoint is one canonical, execute-once alias across ladders.
            if fraction_id == "fraction100":
                out[(fraction_id, ladder_id)] = canonical_full
                continue
            keys = ordering[ladder_id][:size]
            digest = hashlib.sha256("\n".join(f"{key.species_id}\x1f{key.grid_cell_id}" for key in keys).encode()).hexdigest()
            out[(fraction_id, ladder_id)] = SubsetEndpoint(fraction_id, ladder_id, keys, digest, "full" if fraction_id == "fraction100" else None)
    return out


def validate_ladders(rows: RowSet, endpoints: Mapping[tuple[str, str], SubsetEndpoint], master_seed: str = "dsdm-goal028-v1") -> None:
    sizes = endpoint_sizes(len(rows.keys))
    expected = {(fraction, ladder) for fraction in sizes for ladder in ("ladder00", "ladder01", "ladder02")}
    if set(endpoints) != expected:
        raise ModelingContractError("ladder_keys_mismatch")
    all_keys = set(rows.keys)
    for ladder in ("ladder00", "ladder01", "ladder02"):
        expected_order = hierarchical_order(rows, ladder, master_seed)
        e25, e50, e100 = (endpoints[(f, ladder)] for f in ("fraction25", "fraction50", "fraction100"))
        if e25.fraction_id != "fraction25" or e25.ladder_id != ladder or e50.fraction_id != "fraction50" or e50.ladder_id != ladder or e100.fraction_id != "fraction100" or e100.ladder_id != "full":
            raise ModelingContractError("endpoint_metadata_mismatch")
        if len(e25.keys) != sizes["fraction25"] or len(e50.keys) != sizes["fraction50"] or len(e100.keys) != len(rows.keys):
            raise ModelingContractError("ladder_size_mismatch")
        if not set(e25.keys) <= set(e50.keys) <= set(e100.keys) or set(e100.keys) != all_keys:
            raise ModelingContractError("ladder_not_nested")
        for endpoint in (e25, e50):
            expected_keys = expected_order[:sizes[endpoint.fraction_id]]
            expected_digest = hashlib.sha256("\n".join(f"{key.species_id}\x1f{key.grid_cell_id}" for key in expected_keys).encode()).hexdigest()
            if endpoint.keys != expected_keys or endpoint.subset_digest != expected_digest or endpoint.ladder_id != ladder:
                raise ModelingContractError("ladder_endpoint_tampered")
        full_digest = hashlib.sha256("\n".join(f"{key.species_id}\x1f{key.grid_cell_id}" for key in sorted(rows.keys)).encode()).hexdigest()
        if e100.keys != tuple(sorted(rows.keys)) or e100.subset_digest != full_digest or e100.fraction_id != "fraction100":
            raise ModelingContractError("full_endpoint_tampered")
        if e100.full_alias_id != "full":
            raise ModelingContractError("full_alias_missing")
        if len(set(e100.keys)) != len(e100.keys):
            raise ModelingContractError("duplicate_subset_keys")
    full = endpoints[("fraction100", "ladder00")]
    for ladder in ("ladder01", "ladder02"):
        other = endpoints[("fraction100", ladder)]
        if other is not full or other.keys != full.keys or other.subset_digest != full.subset_digest or other.ladder_id != "full" or other.full_alias_id != "full":
            raise ModelingContractError("full_alias_inconsistent")
