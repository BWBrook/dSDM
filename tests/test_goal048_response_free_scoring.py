from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import goal048_response_free_scoring as scoring


def test_even_sample_is_endpoint_inclusive_and_deterministic():
    np.testing.assert_array_equal(scoring.even_sample_indices(10, 4), [0, 3, 6, 9])
    np.testing.assert_array_equal(scoring.even_sample_indices(3, 10), [0, 1, 2])
    np.testing.assert_array_equal(scoring.even_sample_indices(10, 1), [0])


def test_percentiles_use_average_ties():
    np.testing.assert_allclose(scoring.empirical_percentiles([1, 1, 2]), [0.25, 0.25, 1.0])


def test_fragmentation_uses_east_north_rook_edges_and_excludes_missing():
    rows = pd.DataFrame(
        {
            "row": [0, 0, 1, 1, 2],
            "column": [0, 1, 0, 1, 2],
            "nvis_mvg": [1, 19, 1, 99, 19],
        }
    )
    metrics = scoring.fragmentation_metrics(rows)
    assert metrics["fragmentation_denominator"] == 2
    assert metrics["fragmentation_numerator"] == 1
    assert metrics["mapped_cells"] == 4


def test_fragmentation_parses_frozen_nvis_label_strings():
    rows = pd.DataFrame({"row": [0, 0], "column": [0, 1], "nvis_mvg": ["1:Forest", "19:Grassland"]})
    metrics = scoring.fragmentation_metrics(rows, {1: "native_woody", 19: "non_woody"})
    assert metrics["fragmentation_numerator"] == 1
    assert metrics["fragmentation_denominator"] == 1


def test_entropy_uses_global_level_normalisation():
    entropy, normalised = scoring.shannon_entropy(["a", "b", "a"], ["a", "b", "c", "d"])
    assert entropy == pytest.approx(-(2 / 3 * np.log(2 / 3) + 1 / 3 * np.log(1 / 3)))
    assert normalised == pytest.approx(entropy / np.log(4))


def test_pca_projection_is_centered_after_robust_scaling():
    frame = pd.DataFrame({"cell_id": ["a", "b", "c"], **{field: [1.0, 2.0, 3.0] for field in scoring.CONTINUOUS}})
    transform = scoring.fit_common_pca(frame, maximum=3)
    projected = scoring.apply_pca(frame, transform)
    np.testing.assert_allclose(projected.mean(axis=0), 0.0, atol=1e-12)
    assert "centre" in transform


def test_context_reference_embedding_and_xy_share_filtered_cell_identity():
    arrays = {
        "complete_indices": np.array([0, 1, 2, 3]),
        "embeddings": np.array([[0.0], [10.0], [20.0], [40.0]]),
        "xy": np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0], [40.0, 0.0]]),
        "exclusion_masks": {"AUA": np.array([True, False, False, True])},
        "eval_positions": {"AUA": np.array([0, 3])},
    }
    result = scoring._context_score(arrays, ("AUA",))
    # The excluded first cell must not displace the reference embeddings or coordinates.
    assert result["values"]["AUA"]["environmental_raw"] == pytest.approx(19.0)
    assert result["values"]["AUA"]["geographic_raw"] == pytest.approx(15.0 / 1000.0)


def test_buffer_complement_includes_boundary_and_excludes_region():
    from shapely.geometry import Point, box

    regions = {"AUA": box(140, -30, 140.1, -29.9)}
    projected = gpd.GeoSeries([regions["AUA"]], crs=4326).to_crs(3577).iloc[0]
    boundary_xy = Point(projected.centroid.x + 50_000, projected.centroid.y)
    boundary = gpd.GeoSeries([boundary_xy], crs=3577).to_crs(4326).iloc[0]
    frame = pd.DataFrame({"longitude": [140.05, boundary.x, 150.0], "latitude": [-29.95, boundary.y, -20.0]})
    mask = scoring.retained_complement_mask(frame, ["AUA"], regions)
    np.testing.assert_array_equal(mask, [False, False, True])


def test_all_context_and_member_accounting():
    contexts = list(itertools.combinations(scoring.REGIONS, 3))
    assert len(contexts) == 455
    assert sum(len(context) for context in contexts) == 1365
    assert all(sum(code in context for context in contexts) == 91 for code in scoring.REGIONS)


def test_role_permutation_collapses_to_best_deterministic_assignment():
    codes = ("AUA", "BBS", "KAN")
    values = {
        "AUA": {"supported": 0.9, "edge": 0.1, "mosaic": 0.4, "mosaic_allowed": True},
        "BBS": {"supported": 0.3, "edge": 0.95, "mosaic": 0.3, "mosaic_allowed": True},
        "KAN": {"supported": 0.2, "edge": 0.2, "mosaic": 0.9, "mosaic_allowed": True},
    }
    result = scoring.role_permutation_scores(codes, values)
    assert result["roles"] == {"supported": "AUA", "edge": "BBS", "mosaic": "KAN"}
    assert result["minimum"] == pytest.approx(0.9)


def test_mosaic_role_gate_is_inclusive_and_only_applies_to_mosaic_member():
    codes = ("AUA", "BBS", "KAN")
    values = {code: {"supported": 0.5, "edge": 0.5, "mosaic": 0.5, "mosaic_allowed": code != "BBS"} for code in codes}
    result = scoring.role_permutation_scores(codes, values)
    assert result["roles"]["mosaic"] != "BBS"


def test_production_metric_path_sets_mosaic_allowed():
    rows = pd.DataFrame({"region": ["AUA"] * 4, "row": [0, 0, 1, 1], "column": [0, 1, 0, 1], "nvis_mvg": [1, 19, 1, 19], "alum_secondary": ["a"] * 4, **{field: [1.0] * 4 for field in scoring.CONTINUOUS}, "soil_order": ["a"] * 4})
    metrics = scoring._region_metrics(rows, pd.Series(["AUA"] * 4, dtype="string"), {1: "native_woody", 19: "non_woody"})
    assert bool(metrics.loc[0, "mosaic_allowed"]) is True


def test_unassigned_nullable_region_is_safe_in_metrics_and_eval_indices():
    from shapely.geometry import box

    rows = pd.DataFrame({"cell_id": ["a", "b", "c"], "row": [0, 0, 0], "column": [0, 1, 2], "longitude": [140.05, 141.05, 142.05], "latitude": [-29.95, -29.95, -29.95], "nvis_mvg": [1, 19, 1], "alum_secondary": ["a", "b", "a"], **{field: [1.0, 2.0, 3.0] for field in scoring.CONTINUOUS}, "soil_order": ["a", "a", "a"]})
    assigned = pd.Series(["AUA", pd.NA, "BBS"], dtype="string")
    metrics = scoring._region_metrics(rows, assigned, {1: "native_woody", 19: "non_woody"})
    assert metrics.loc[metrics["region"] == "AUA", "domain_cells"].item() == 1
    transform = scoring.fit_common_pca(rows)
    regions = {code: box(140 + index, -30, 140.1 + index, -29.9) for index, code in enumerate(scoring.REGIONS)}
    arrays = scoring._precompute_scoring_arrays(rows, assigned, regions, transform)
    assert arrays["eval_positions"]["AUA"].tolist() == [0]
    assert arrays["eval_positions"]["BBS"].tolist() == [2]


def test_unique_set_ambiguity_uses_both_frozen_margins():
    contexts = [
        {"regions": ["AUA", "BBS", "KAN"], "structurally_valid": True, "minimum_role_score": 0.80, "sum_role_scores": 2.1},
        {"regions": ["NAN", "NCP", "NET"], "structurally_valid": True, "minimum_role_score": 0.795, "sum_role_scores": 2.09},
    ]
    ranked, ambiguous = scoring.select_ranked_sets(contexts)
    assert len(ranked) == 2
    assert ambiguous is True


def test_interrupted_progress_resumes_only_with_same_identity(tmp_path):
    codes = [("AUA", "BBS", "KAN"), ("AUA", "BBS", "NAN")]
    progress = tmp_path / "progress.json"
    progress.write_text('{"run_identity":"abc","contexts":[{"regions":["AUA","BBS","KAN"]}]}')
    assert len(scoring.load_context_progress(progress, "abc", codes)) == 1
    with pytest.raises(scoring.ScoringError, match="stale context progress"):
        scoring.load_context_progress(progress, "def", codes)


def test_source_has_no_acquisition_or_outcome_imports():
    source = Path(scoring.__file__).read_text()
    assert not re.search(r"(?:urllib|requests|galah|observation|occurrence|species_cell|model_outcome)", source, re.I)
    assert "predictor_substrate.parquet" in source
    assert "response_free" in source
