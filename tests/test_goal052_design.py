from __future__ import annotations

import math

import pytest

from dsdm_phase1.goal052_design import (
    ARCHITECTURE_IDS,
    base_endpoints,
    endpoint_grid,
    select_architecture,
)


TARGETS = tuple(f"target-{index:03d}" for index in range(157))
PRIMARY = TARGETS[:73]
SELECTION_TARGETS = TARGETS[:73]


def _summary(auc: float, tss: float) -> dict[str, object]:
    return {"mean_fold_roc_auc": auc, "pooled": {"tss": tss}}


def _metrics(default_order: tuple[str, ...] = ARCHITECTURE_IDS):
    return {
        architecture: {
            target: _summary(1.0 - rank * 0.01, 0.5)
            for target in SELECTION_TARGETS
            for rank in [default_order.index(architecture) + 1]
        }
        for architecture in ARCHITECTURE_IDS
    }


def test_goal052_endpoint_grid_has_frozen_counts_and_scopes():
    grid = endpoint_grid(PRIMARY, TARGETS)
    base = base_endpoints(PRIMARY, TARGETS)

    assert len(grid) == len(set(grid)) == 449
    assert len(base) == len(set(base)) == 303
    assert sum(fraction == 25 for _, fraction, _ in grid) == 73
    assert sum(fraction == 50 for _, fraction, _ in grid) == 73
    assert sum(fraction == 100 for _, fraction, _ in grid) == 303
    assert sum(auxiliary == "20" for _, _, auxiliary in grid) == 73
    assert sum(auxiliary == "80" for _, _, auxiliary in grid) == 73
    assert all(auxiliary == "full" for target, fraction, auxiliary in grid if fraction in (25, 50) or target not in PRIMARY)
    assert all(fraction == 100 for _, fraction, auxiliary in grid if auxiliary in {"20", "80"})


def test_within_target_ranking_uses_tss_then_architecture_id_for_auc_ties():
    metrics = _metrics()
    target = SELECTION_TARGETS[0]
    for architecture in ARCHITECTURE_IDS:
        metrics[architecture][target]["mean_fold_roc_auc"] = 0.8
        metrics[architecture][target]["pooled"]["tss"] = 0.3
    metrics["bridge_wide"][target]["pooled"]["tss"] = 0.4
    result = select_architecture(metrics, {target: 0, **{item: 1 for item in SELECTION_TARGETS[1:]}})

    assert result["target_rankings"][target] == ["bridge_wide", "bridge_control", "bridge_deep", "seawfb_scale"]


def test_shared_ranking_uses_mean_auc_after_mean_target_rank():
    metrics = {architecture: {} for architecture in ARCHITECTURE_IDS}
    for index, target in enumerate(SELECTION_TARGETS):
        # The first two candidates exchange rank across targets.  The one
        # third-place result makes their rank sums equal over 73 targets.
        if index == 0:
            order = ("bridge_wide", "bridge_deep", "bridge_control", "seawfb_scale")
        elif index <= 37:
            order = ("bridge_control", "bridge_wide", "bridge_deep", "seawfb_scale")
        else:
            order = ("bridge_wide", "bridge_control", "bridge_deep", "seawfb_scale")
        for rank, architecture in enumerate(order, 1):
            auc = 1.0 - rank * 0.01
            if architecture == "bridge_wide":
                auc += 1e-5
            metrics[architecture][target] = _summary(auc, 0.5)

    result = select_architecture(metrics, {target: index % 3 for index, target in enumerate(SELECTION_TARGETS)})

    assert math.isclose(result["mean_target_rank"]["bridge_control"], result["mean_target_rank"]["bridge_wide"])
    assert result["mean_target_roc_auc"]["bridge_wide"] > result["mean_target_roc_auc"]["bridge_control"]
    assert result["selected_architecture"] == "bridge_wide"


@pytest.mark.parametrize("mutation", ["missing_target", "nonfinite_auc", "nonfinite_tss"])
def test_selection_rejects_incomplete_or_nonfinite_candidates(mutation):
    metrics = _metrics()
    if mutation == "missing_target":
        del metrics["bridge_deep"][SELECTION_TARGETS[-1]]
    elif mutation == "nonfinite_auc":
        metrics["bridge_deep"][SELECTION_TARGETS[0]]["mean_fold_roc_auc"] = float("nan")
    else:
        metrics["bridge_deep"][SELECTION_TARGETS[0]]["pooled"]["tss"] = float("inf")

    with pytest.raises(ValueError):
        select_architecture(metrics, {target: 0 for target in SELECTION_TARGETS})


def test_leave_one_focal_block_out_is_diagnostic_and_cannot_override_winner():
    metrics = {architecture: {} for architecture in ARCHITECTURE_IDS}
    for index, target in enumerate(SELECTION_TARGETS):
        # Main selection favours control (40/73), while omitting that block
        # makes the diagnostic favour wide.
        control_auc = 0.9 if index < 40 else 0.7
        wide_auc = 0.7 if index < 40 else 0.9
        for architecture, auc in {
            "bridge_control": control_auc,
            "bridge_wide": wide_auc,
            "bridge_deep": 0.5,
            "seawfb_scale": 0.4,
        }.items():
            metrics[architecture][target] = _summary(auc, 0.5)
    focal_blocks = {target: (0 if index < 40 else 1) for index, target in enumerate(SELECTION_TARGETS)}

    result = select_architecture(metrics, focal_blocks)

    assert result["selected_architecture"] == "bridge_control"
    assert result["stability"]["selected_architecture"] == "bridge_control"
    assert result["stability"]["selection_overridden"] is False
    assert result["stability"]["diagnostic_winners_all_agree"] is False
    assert result["stability"]["leave_one_focal_block_out"][0]["selected_architecture"] == "bridge_wide"
