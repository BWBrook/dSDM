"""Split-scoped categorical support masks for the Goal035 repair.

The numeric substrate keeps its frozen 77-column shape.  A support mask is
fit from permitted training/replay covariates and turns assessment-only
one-hot indicators into the Goal028 neutral all-zero representation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping

import numpy as np

from .real_data import CATEGORICAL_LEVELS


class SupportMaskError(ValueError):
    """Raised when a support-mask contract is violated."""


CONTINUOUS_COUNT = 25
PREDICTOR_COUNT = 77
_CATEGORY_SLICES: dict[str, slice] = {}
_offset = CONTINUOUS_COUNT
for _name, _levels in CATEGORICAL_LEVELS.items():
    _CATEGORY_SLICES[_name] = slice(_offset, _offset + len(_levels))
    _offset += len(_levels)
if _offset != PREDICTOR_COUNT:  # pragma: no cover - protects the frozen schema
    raise RuntimeError("categorical vocabulary no longer has 77 columns")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SupportMaskError(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class SupportMask:
    """Immutable 77-column support view with no row or level identities."""

    columns: np.ndarray
    digest: str

    def __post_init__(self) -> None:
        values = np.asarray(self.columns, dtype=bool)
        _require(values.shape == (PREDICTOR_COUNT,), "support mask must have 77 columns")
        _require(bool(values[:CONTINUOUS_COUNT].all()), "continuous columns must remain active")
        values = np.array(values, dtype=bool, copy=True)
        values.flags.writeable = False
        object.__setattr__(self, "columns", values)
        expected = support_digest(values)
        _require(self.digest == expected, "support digest mismatch")


def support_digest(columns: np.ndarray) -> str:
    values = np.asarray(columns, dtype=bool)
    _require(values.shape == (PREDICTOR_COUNT,), "support digest shape mismatch")
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.uint8).tobytes()).hexdigest()


def _validate_covariates(x: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(x)
    _require(values.ndim == 2 and values.shape[1] == PREDICTOR_COUNT and values.shape[0] > 0, f"{name} covariates invalid")
    _require(values.dtype == np.float32, f"{name} covariates must be float32")
    _require(np.isfinite(values).all(), f"{name} covariates non-finite")
    return values


def fit_support_mask(x_replay: np.ndarray) -> SupportMask:
    """Fit support only from complete permitted replay covariates.

    A categorical column is supported iff its one-hot indicator occurs in the
    supplied replay view.  Continuous columns are always supported.
    """

    values = _validate_covariates(x_replay, "replay")
    columns = np.zeros(PREDICTOR_COUNT, dtype=bool)
    columns[:CONTINUOUS_COUNT] = True
    for block in _CATEGORY_SLICES.values():
        columns[block] = np.any(values[:, block] != 0.0, axis=0)
    return SupportMask(columns, support_digest(columns))


def fit_support_mask_from_views(views: Iterable[np.ndarray]) -> SupportMask:
    """Fit one mask from multiple permitted complete covariate views."""

    arrays = [_validate_covariates(view, "support view") for view in views]
    _require(arrays, "at least one support view is required")
    return fit_support_mask(np.concatenate(arrays, axis=0))


def _diagnostics(original: np.ndarray, masked: np.ndarray, support: SupportMask) -> dict[str, object]:
    changed = original != masked
    unsupported = ~support.columns
    affected_rows = int(np.any(changed, axis=1).sum())
    affected_instances = int(changed.sum())
    columns = {
        name: int(np.any(changed[:, block], axis=0).sum())
        for name, block in _CATEGORY_SLICES.items()
        if int(np.any(changed[:, block], axis=0).sum())
    }
    return {
        "affected_rows": affected_rows,
        "affected_instances": affected_instances,
        "unsupported_columns": int(np.any(changed, axis=0).sum()),
        "unsupported_columns_by_category": columns,
    }


def apply_support_mask(x: np.ndarray, support: SupportMask) -> tuple[np.ndarray, dict[str, object]]:
    """Apply a support mask without changing continuous values."""

    original = _validate_covariates(x, "input")
    _require(isinstance(support, SupportMask), "support object invalid")
    masked = np.array(original, dtype=np.float32, copy=True, order="C")
    masked[:, ~support.columns] = 0.0
    _require(np.array_equal(original[:, :CONTINUOUS_COUNT], masked[:, :CONTINUOUS_COUNT]), "continuous values changed")
    _require(np.all(masked[:, ~support.columns] == 0.0), "unsupported indicators remain active")
    return masked, _diagnostics(original, masked, support)


def aggregate_diagnostics(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Combine diagnostics without exposing rows, levels, or identities."""

    total_rows = total_instances = total_columns = 0
    by_category: dict[str, int] = {name: 0 for name in CATEGORICAL_LEVELS}
    for row in rows:
        total_rows += int(row.get("affected_rows", 0))
        total_instances += int(row.get("affected_instances", 0))
        total_columns += int(row.get("unsupported_columns", 0))
        for name, value in dict(row.get("unsupported_columns_by_category", {})).items():
            if name in by_category:
                by_category[name] += int(value)
    return {
        "affected_rows": total_rows,
        "affected_instances": total_instances,
        "unsupported_columns": total_columns,
        "unsupported_columns_by_category": {k: v for k, v in by_category.items() if v},
    }


__all__ = [
    "CONTINUOUS_COUNT", "PREDICTOR_COUNT", "SupportMask", "SupportMaskError",
    "aggregate_diagnostics", "apply_support_mask", "fit_support_mask",
    "fit_support_mask_from_views", "support_digest",
]
