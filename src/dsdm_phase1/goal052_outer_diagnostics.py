"""Pure scoring functions for the 1 October outer diagnostic addendum.

No file readers or fitting code belong here. The outer orchestrator must close
and hash every region's predictions before supplying responses to these functions.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score


MINIMUM_CLASS_CELLS = 20
BACKGROUND_BINS = ((10, 25, "10_24"), (25, 100, "25_99"), (100, None, "100_plus"))


def _probabilities(values: np.ndarray, count: int | None = None) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if (result.ndim != 1 or not len(result) or (count is not None and len(result) != count)
            or not np.isfinite(result).all() or np.any((result < 0) | (result > 1))):
        raise ValueError("invalid or misaligned predicted probabilities")
    return result


def fixed_probability_ensemble(finetuned: np.ndarray, conventional: np.ndarray) -> np.ndarray:
    """Average the already seed-averaged component probabilities, without tuning."""
    ft = _probabilities(finetuned)
    conv = _probabilities(conventional, len(ft))
    return 0.5 * ft + 0.5 * conv


def evaluate_richness_diagnostics(
    y: np.ndarray,
    probabilities: Mapping[str, np.ndarray],
    other_species_richness: np.ndarray,
    tile_ids: np.ndarray,
) -> dict[str, Any]:
    """Score one target-region X10 set using the fixed recorded-richness rules.

All vectors must already share an identical cell ordering. Primary panel and
cell-identity validation are responsibilities of the outer scoring caller.
"""
    response = np.asarray(y)
    richness = np.asarray(other_species_richness)
    tiles = np.asarray(tile_ids)
    if (response.ndim != 1 or not len(response) or not np.isin(response, [0, 1]).all()
            or richness.shape != response.shape or tiles.shape != response.shape
            or not np.isfinite(richness).all() or np.any(richness < 0)
            or np.any(richness != np.floor(richness))):
        raise ValueError("invalid or misaligned diagnostic rows")
    if not probabilities:
        raise ValueError("no arm predictions")
    scores = {name: _probabilities(value, len(response)) for name, value in probabilities.items()}
    positive, background = response == 1, response == 0
    if not positive.any() or not background.any():
        raise ValueError("primary X10 set is missing a response class")
    if np.any(richness[background] < 10):
        raise ValueError("background lies outside the X10 response definition")

    def score_subset(present: np.ndarray, absent: np.ndarray) -> dict[str, Any]:
        n_presence, n_background = int(present.sum()), int(absent.sum())
        reportable = min(n_presence, n_background) >= MINIMUM_CLASS_CELLS
        mask = present | absent
        return {
            "presence_cells": n_presence,
            "background_cells": n_background,
            "presence_tiles": int(len(np.unique(tiles[present]))),
            "background_tiles": int(len(np.unique(tiles[absent]))),
            "reportable": reportable,
            "na_reason": None if reportable else "fewer_than_20_cells_in_at_least_one_class",
            "auc": {name: float(roc_auc_score(response[mask], values[mask])) if reportable else None
                    for name, values in scores.items()},
        }

    bin_masks = {
        label: background & (richness >= low) & (True if upper is None else richness < upper)
        for low, upper, label in BACKGROUND_BINS
    }
    membership_count = np.sum(np.vstack(list(bin_masks.values())), axis=0)
    if not np.array_equal(membership_count, background.astype(int)):
        raise ValueError("richness bins do not partition the scored X10 backgrounds")
    strata = {label: score_subset(positive, absent) for label, absent in bin_masks.items()}

    identity = {}
    for name, values in scores.items():
        full_auc = float(roc_auc_score(response, values))
        reconstructed = 0.0
        for absent in bin_masks.values():
            if absent.any():
                # Always the same positive mask; sparse bins participate only
                # in this arithmetic check. Ties use sklearn's standard AUC.
                mask = positive | absent
                reconstructed += float(absent.sum() / background.sum()) * float(
                    roc_auc_score(response[mask], values[mask]))
        error = abs(full_auc - reconstructed)
        if error > 1e-12:
            raise ValueError(f"weighted AUC identity failed for {name}: {error}")
        identity[name] = {"full_x10_auc": full_auc, "reconstructed_auc": reconstructed,
                          "absolute_error": error}

    high = richness >= 100
    return {
        "minimum_cells_per_class": MINIMUM_CLASS_CELLS,
        "background_strata": strata,
        "high_recording_richness_subset": score_subset(positive & high, background & high),
        "weighted_auc_identity": identity,
    }
