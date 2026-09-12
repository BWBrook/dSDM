"""Pure design and architecture-selection helpers for Goal 052.

The functions in this module only validate supplied identities and aggregate
already-computed OOF summaries.  They do not read private data, fit models, or
alter the frozen Goal 052 configuration.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Mapping, Sequence


ARCHITECTURE_IDS = (
    "bridge_control",
    "bridge_wide",
    "bridge_deep",
    "seawfb_scale",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _target_ids(values: Sequence[str], name: str) -> tuple[str, ...]:
    try:
        result = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence") from exc
    _require(
        all(isinstance(value, str) and value for value in result),
        f"{name} contains invalid target",
    )
    _require(len(result) == len(set(result)), f"{name} contains duplicates")
    return result


def endpoint_grid(
    primary_targets: Sequence[str], focal_targets: Sequence[str]
) -> list[tuple[str, int, str]]:
    """Return the frozen 449-condition target/fraction/auxiliary grid.

    Base endpoints are emitted with ``auxiliary='full'``.  Primary targets
    additionally receive 100%-target endpoints with auxiliary sizes ``20``
    and ``80``.  The canonical 73-primary/157-focal inventory is enforced.
    """

    primary = _target_ids(primary_targets, "primary_targets")
    focal = _target_ids(focal_targets, "focal_targets")
    _require(len(primary) == 73 and len(focal) == 157, "goal052_target_inventory_invalid")
    _require(set(primary) <= set(focal), "primary_targets_not_subset_of_focal_targets")
    primary_set = set(primary)

    grid = [
        (target, fraction, "full")
        for target in focal
        for fraction in ((25, 50, 100) if target in primary_set else (100,))
    ]
    grid.extend((target, 100, auxiliary) for target in primary for auxiliary in ("20", "80"))
    _require(len(grid) == 449 and len(set(grid)) == 449, "goal052_endpoint_grid_drift")
    return grid


def base_endpoints(
    primary_targets: Sequence[str], focal_targets: Sequence[str]
) -> list[tuple[str, int]]:
    """Return the 303 unique target-learning endpoints used by Goal 052."""

    endpoints = [(target, fraction) for target, fraction, auxiliary in endpoint_grid(primary_targets, focal_targets) if auxiliary == "full"]
    _require(len(endpoints) == 303 and len(set(endpoints)) == 303, "goal052_base_endpoint_drift")
    return endpoints


def _finite_metric(value: Any, name: str) -> float:
    _require(isinstance(value, Real) and not isinstance(value, bool), f"{name}_invalid")
    result = float(value)
    _require(math.isfinite(result), f"{name}_nonfinite")
    return result


def _metric_values(summary: Mapping[str, Any], architecture: str, target: str) -> tuple[float, float]:
    _require(isinstance(summary, Mapping), f"metric_summary_missing:{architecture}:{target}")
    auc = _finite_metric(summary.get("mean_fold_roc_auc"), f"mean_fold_roc_auc:{architecture}:{target}")
    pooled = summary.get("pooled")
    _require(isinstance(pooled, Mapping), f"pooled_metrics_missing:{architecture}:{target}")
    tss = _finite_metric(pooled.get("tss"), f"pooled_tss:{architecture}:{target}")
    return auc, tss


def _rank_targets(
    metrics: Mapping[str, Mapping[str, tuple[float, float]]],
    targets: Sequence[str],
) -> tuple[dict[str, list[str]], dict[str, float], dict[str, float], dict[str, list[int]]]:
    rankings: dict[str, list[str]] = {}
    ranks: dict[str, list[int]] = {architecture: [] for architecture in ARCHITECTURE_IDS}
    for target in targets:
        ordered = sorted(
            ARCHITECTURE_IDS,
            key=lambda architecture: (
                -metrics[architecture][target][0],
                -metrics[architecture][target][1],
                architecture,
            ),
        )
        rankings[target] = ordered
        for rank, architecture in enumerate(ordered, 1):
            ranks[architecture].append(rank)

    mean_rank = {
        architecture: math.fsum(ranks[architecture]) / len(targets)
        for architecture in ARCHITECTURE_IDS
    }
    mean_auc = {
        architecture: math.fsum(metrics[architecture][target][0] for target in targets) / len(targets)
        for architecture in ARCHITECTURE_IDS
    }
    return rankings, mean_rank, mean_auc, ranks


def select_architecture(
    metrics: Mapping[str, Mapping[str, Mapping[str, Any]]],
    focal_blocks: Mapping[str, int],
) -> dict[str, Any]:
    """Select one shared architecture and report a post-selection block audit.

    ``metrics`` must contain all four frozen candidates for the same 73 target
    identities, with finite ``summarize_oof`` AUC and pooled TSS fields.  The
    leave-one-focal-block-out rankings are diagnostic only; their results never
    replace the full-data winner.
    """

    _require(isinstance(metrics, Mapping), "metrics_invalid")
    _require(set(metrics) == set(ARCHITECTURE_IDS), "architecture_candidates_invalid")
    _require(isinstance(focal_blocks, Mapping), "focal_blocks_invalid")
    targets = tuple(metrics[ARCHITECTURE_IDS[0]])
    _require(len(targets) == 73 and len(set(targets)) == 73, "selection_target_inventory_invalid")
    _require(set(focal_blocks) >= set(targets), "focal_blocks_missing_selection_target")
    _require(all(isinstance(target, str) and target for target in targets), "selection_targets_invalid")

    values: dict[str, dict[str, tuple[float, float]]] = {}
    target_set = set(targets)
    for architecture in ARCHITECTURE_IDS:
        candidate = metrics[architecture]
        _require(isinstance(candidate, Mapping) and set(candidate) == target_set, f"candidate_target_inventory_invalid:{architecture}")
        values[architecture] = {
            target: _metric_values(candidate[target], architecture, target)
            for target in targets
        }

    rankings, mean_rank, mean_auc, _ = _rank_targets(values, targets)
    winner = min(ARCHITECTURE_IDS, key=lambda architecture: (mean_rank[architecture], -mean_auc[architecture], architecture))

    block_values: dict[Any, list[str]] = {}
    for target in targets:
        block = focal_blocks[target]
        _require(isinstance(block, (str, int)) and not isinstance(block, bool), "focal_block_invalid")
        block_values.setdefault(block, []).append(target)

    stability: dict[Any, dict[str, Any]] = {}
    for block, omitted_targets in block_values.items():
        remaining = tuple(target for target in targets if target not in set(omitted_targets))
        _require(remaining, f"focal_block_removes_all_selection_targets:{block}")
        block_rankings, block_mean_rank, block_mean_auc, _ = _rank_targets(values, remaining)
        block_winner = min(
            ARCHITECTURE_IDS,
            key=lambda architecture: (block_mean_rank[architecture], -block_mean_auc[architecture], architecture),
        )
        stability[block] = {
            "omitted_targets": list(omitted_targets),
            "remaining_targets": list(remaining),
            "target_rankings": block_rankings,
            "mean_target_rank": block_mean_rank,
            "mean_target_roc_auc": block_mean_auc,
            "selected_architecture": block_winner,
        }

    agreement_count = sum(
        details["selected_architecture"] == winner for details in stability.values()
    )

    return {
        "selected_architecture": winner,
        "target_rankings": rankings,
        "mean_target_rank": mean_rank,
        "mean_target_roc_auc": mean_auc,
        "metrics": metrics,
        "stability": {
            "selected_architecture": winner,
            "selection_overridden": False,
            "diagnostic_winner_agreement_count": agreement_count,
            "diagnostic_winners_all_agree": agreement_count == len(stability),
            "leave_one_focal_block_out": stability,
        },
    }
