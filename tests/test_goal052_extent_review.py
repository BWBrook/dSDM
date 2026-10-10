import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.goal052_extent_review import auc, contrasts, distribution, metric_values, outer_target


def test_auc_is_tie_aware_and_single_class_is_na():
    assert auc(np.array([0, 1, 0, 1]), np.array([0.1, 0.9, 0.2, 0.8])) == 1.0
    assert auc(np.array([0, 1]), np.array([0.5, 0.5])) == 0.5
    assert auc(np.array([1, 1]), np.array([0.1, 0.2])) is None


def test_ensemble_metrics_and_requested_contrasts_are_fixed_equal_weight():
    labels = np.array([0, 1, 0, 1])
    values = {
        "multihead_full_finetune": np.array([0.1, 0.9, 0.2, 0.8]),
        "target_only_random_init_resmlp": np.array([0.2, 0.8, 0.3, 0.7]),
        "multihead_frozen_trunk": np.array([0.3, 0.7, 0.4, 0.6]),
        "target_plus_q_linear_resmlp": np.array([0.15, 0.85, 0.25, 0.75]),
        "conventional": np.array([0.4, 0.6, 0.45, 0.55]),
    }
    metrics = metric_values(values, labels)
    assert metrics["ft_conv_ensemble"] == auc(labels, (values["multihead_full_finetune"] + values["conventional"]) / 2)
    assert metrics["to_conv_ensemble"] == auc(labels, (values["target_only_random_init_resmlp"] + values["conventional"]) / 2)
    result = contrasts(metrics)
    assert set(result) == {
        "ft_minus_to", "ft_minus_conv", "fz_minus_to",
        "ft_conv_ensemble_minus_conv", "ft_conv_ensemble_minus_ft",
        "to_conv_ensemble_minus_conv", "to_conv_ensemble_minus_to",
        "ft_conv_ensemble_minus_to_conv_ensemble",
    }


def test_distribution_keeps_sign_count_and_quantiles():
    result = distribution([-0.2, 0.0, 0.4])
    assert result["n"] == 3
    assert result["positive"] == 1
    assert result["min"] == -0.2
    assert result["max"] == 0.4
    assert result["quantiles"]["q25"] == np.quantile([-0.2, 0.0, 0.4], 0.25)


def test_outer_extent_uses_x10_background_mask():
    y = np.array([1, 0, 0, 1], dtype=np.int8)
    richness = np.array([0, 1, 10, 0], dtype=np.int32)
    arrays = {name: np.array([0.1, 0.99, 0.2, 0.8]) for name in (
        "multihead_full_finetune", "target_only_random_init_resmlp",
        "multihead_frozen_trunk", "target_plus_q_linear_resmlp",
        "selected_conventional",
    )}
    arrays["fixed_ensemble"] = arrays["multihead_full_finetune"]
    record = outer_target("synthetic", arrays, {"y": y, "richness": richness}, np.array(["NCP", "NCP", "NCP", "NCP"], dtype=object))
    assert record["whole_domain_x10"]["support"]["background"] == 1
