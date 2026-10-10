import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bird_composition_resampling import (
    focal_block_resampling_replicates,
    one_copy_focal_block_mean,
    species_resampling_replicates,
    validate_primary_inventory,
)


def test_species_resampling_reuses_one_joint_draw_for_comparators():
    # A constant paired offset can only remain constant when both comparators
    # use the same sampled species IDs.
    base = np.arange(73, dtype=float) / 100.0
    contrasts = {"target_only": base, "conventional": base + 0.25}
    sampled = species_resampling_replicates(
        contrasts, np.random.default_rng(123), replicates=200, batch_size=37
    )
    np.testing.assert_allclose(sampled["conventional"] - sampled["target_only"], 0.25)


def test_focal_block_ratio_of_sums_preserves_unequal_block_sizes():
    mapping = np.array([0, 1, 1, 1])
    values = np.array([0.0, 0.0, 0.0, 1.0])
    # With three species in block 1, one copy of each block is 1/4.  Fixed
    # draws expose the denominator: 0/2, 1/4, and 2/6.
    assert one_copy_focal_block_mean(values, mapping.tolist()) == pytest.approx(0.25)

    class FixedRng:
        def integers(self, low, high, size):
            assert (low, high, tuple(size)) == (0, 2, (3, 2))
            return np.array([[0, 0], [0, 1], [1, 1]], dtype=int)

    sampled = focal_block_resampling_replicates(
        {"target_only": values, "conventional": values + 0.1},
        mapping.tolist(),
        FixedRng(),
        replicates=3,
        batch_size=3,
    )
    np.testing.assert_allclose(sampled["target_only"], [0.0, 0.25, 1 / 3])
    np.testing.assert_allclose(sampled["conventional"] - sampled["target_only"], 0.1)


def test_focal_inventory_rejects_changed_block_counts():
    species = [f"species-{i:02d}" for i in range(73)]
    mapping = {name: i % 10 for i, name in enumerate(species)}
    with pytest.raises(ValueError, match="focal block counts changed"):
        validate_primary_inventory(species, mapping)
