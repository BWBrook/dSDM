"""Retained-only predictor covariance check for Fable's 29 September critique.

Reads the frozen 21 continuous predictor columns, never species memberships,
outer predictors or responses. Variance concentration is not predictive sufficiency.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "metadata/goal050_manifest.json"
TRANSFORMS = ROOT / "metadata/goal050_transforms.json"
CONFIG = ROOT / "config/goal050_seawfb_modeling_foundation.json"
CELLS = ROOT / "data/processed/dsdm/goal050-seawfb-modeling-foundation/cells.parquet"
OUTPUT = ROOT / "evidence/seawfb_dsdm/goal052/predictor-review-20261001.json"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def spectrum(x):
    covariance = np.cov(x, rowvar=False, ddof=0)
    eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
    assert np.isfinite(eigenvalues).all() and eigenvalues.min() > -1e-10
    eigenvalues = np.maximum(eigenvalues, 0)
    proportions = eigenvalues / eigenvalues.sum()
    cumulative = np.cumsum(proportions)
    return {
        "rows": len(x),
        "eigenvalues": eigenvalues.tolist(),
        "cumulative_variance_fraction": cumulative.tolist(),
        "components_for_90_percent_variance": int(np.searchsorted(cumulative, 0.90) + 1),
        "components_for_99_percent_variance": int(np.searchsorted(cumulative, 0.99) + 1),
        "participation_ratio": float(eigenvalues.sum() ** 2 / np.square(eigenvalues).sum()),
    }


def main():
    assert sha(MANIFEST) == "239dd61cc5d3ab942a813201c0cb4117820b74367c7ba71deffddc6990d36198"
    manifest = json.loads(MANIFEST.read_text())
    paths = {"cells": CELLS, "transforms": TRANSFORMS, "config": CONFIG}
    hashes = {key: sha(path) for key, path in paths.items()}
    assert all(value == manifest["bindings"][key] for key, value in hashes.items())
    features = json.loads(CONFIG.read_text())["predictors"]["continuous"]
    transform = json.loads(TRANSFORMS.read_text())["transforms"]["retained_full"]["continuous"]
    assert len(features) == 21 and set(features) == set(transform)
    table = pq.read_table(CELLS, columns=features)
    x = np.column_stack([table[name].to_numpy().astype(float) for name in features])
    assert len(x) == manifest["counts"]["retained_training_cells"] == 787357
    complete = np.isfinite(x).all(axis=1)
    missing = {}
    for j, feature in enumerate(features):
        mean = transform[feature]["mean"]
        sd = transform[feature]["population_sd"]
        assert np.isfinite(mean) and np.isfinite(sd) and sd > 0
        mask = ~np.isfinite(x[:, j])
        missing[feature] = int(mask.sum())
        x[mask, j] = mean
        x[:, j] = (x[:, j] - mean) / sd
    result = {
        "status": "posthoc_retained_predictor_covariance_review",
        "board_message": 783,
        "outer_response_rows_read": 0,
        "response_rows_read": 0,
        "features": features,
        "input_sha256": {"manifest": sha(MANIFEST), **hashes},
        "script_sha256": sha(Path(__file__).resolve()),
        "method": "PCA of covariance of frozen retained-full-standardized continuous predictors; mean imputation and covariance recentering; population covariance.",
        "all_retained_cells": spectrum(x),
        "complete_continuous_rows_sensitivity": spectrum(x[complete]),
        "nonfinite_counts_before_imputation": missing,
        "interpretation_limit": "Unsupervised linear variance concentration, not independent ecological dimensions, a bound on predictive complexity, or a test of categorical/context information.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: {k: v for k, v in result[key].items() if k not in ("eigenvalues", "cumulative_variance_fraction")}
                      for key in ("all_retained_cells", "complete_continuous_rows_sensitivity")}, indent=2))


if __name__ == "__main__":
    main()
