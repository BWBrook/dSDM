from __future__ import annotations

import hashlib
import json
import warnings
import pytest

import numpy as np

from dsdm_phase1.modeling_contract import FeatureBatch, RowKey, canonical_json


def _batch(n=12):
    keys = tuple(RowKey("sp", f"{i:03d}") for i in range(n))
    x = np.column_stack([np.linspace(-2, 2, n), np.asarray([i % 2 for i in range(n)], float)])
    y = np.asarray([i % 2 for i in range(n)], float)
    names = ("x0", "cat__a")
    kinds = ("continuous", "categorical")
    digest = hashlib.sha256(canonical_json({"feature_names": names, "feature_kinds": kinds, "continuous_count": 1}).encode()).hexdigest()
    return FeatureBatch(keys, x, y, names, kinds, 1, digest, {}, "outer", "t" * 64, "e" * 64)


def _candidate(family, ident):
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES
    return CANONICAL_CANDIDATES[ident]


def test_intercept_and_forest_roundtrip(tmp_path):
    from dsdm_phase1.model_adapters import build_adapter, load_fitted_model
    batch = _batch()
    for family, ident in (("intercept", "null00"), ("random_forest", "rf00"), ("hist_gradient_boosting", "hgb00")):
        fitted, report = build_adapter(family).fit(batch, None, _candidate(family, ident), 7)
        scores = fitted.predict_scores(batch)
        assert scores.shape == (len(batch.keys),) and np.isfinite(scores).all()
        path = tmp_path / f"{family}.json"; metadata = fitted.serialize(path)
        loaded = load_fitted_model(path, hashlib.sha256(path.read_bytes()).hexdigest())
        np.testing.assert_allclose(scores, loaded.predict_scores(batch))
        assert report.converged and metadata["family"] == family


def test_neural_exact_fit_and_determinism():
    from dsdm_phase1.model_adapters import build_adapter
    batch = _batch()
    cand = _candidate("shallow_ann", "ann00")
    a, _ = build_adapter("shallow_ann").fit(batch, batch, cand, 11)
    b, _ = build_adapter("shallow_ann").fit(batch, None, cand, 11, exact_epochs=2)
    c, _ = build_adapter("shallow_ann").fit(batch, None, cand, 11, exact_epochs=2)
    assert a.predict_scores(batch).dtype == np.float64
    np.testing.assert_allclose(b.predict_scores(batch), c.predict_scores(batch), atol=1e-6)


def test_elastic_gam_and_residual_real_roundtrip(tmp_path):
    from dsdm_phase1.model_adapters import build_adapter, load_fitted_model, CANONICAL_CANDIDATES
    batch = _batch(20)
    for family, ident in (("elastic_net", "enet00"), ("gam", "gam00")):
        fitted, _ = build_adapter(family).fit(batch, None, CANONICAL_CANDIDATES[ident], 3)
        path = tmp_path / f"{ident}.json"; fitted.serialize(path)
        loaded = load_fitted_model(path, hashlib.sha256(path.read_bytes()).hexdigest())
        np.testing.assert_allclose(fitted.predict_scores(batch), loaded.predict_scores(batch))
    fitted, _ = build_adapter("residual_mlp").fit(batch, None, CANONICAL_CANDIDATES["resmlp00"], 3, exact_epochs=1)
    path = tmp_path / "residual.json"; fitted.serialize(path)
    loaded = load_fitted_model(path, hashlib.sha256(path.read_bytes()).hexdigest())
    np.testing.assert_allclose(fitted.predict_scores(batch), loaded.predict_scores(batch), atol=1e-6)


def test_all_canonical_candidates_and_coordinated_tamper_rejected(tmp_path):
    from dsdm_phase1.model_adapters import (
        CANONICAL_CANDIDATES,
        GOAL029_PSPLINE_CANDIDATES,
        ModelAdapterError,
        build_adapter,
        goal029_candidate_authority,
        load_fitted_model,
        validate_candidate,
    )
    assert {
        candidate_id: CANONICAL_CANDIDATES[candidate_id]
        for candidate_id in ("gam00", "gam01", "gam02", "gam03", "gam04")
    } == {
        "gam00": {"family": "gam", "id": "gam00", "n_splines": 6, "lam": .1, "max_iter": 500, "tol": 1e-5},
        "gam01": {"family": "gam", "id": "gam01", "n_splines": 6, "lam": 1, "max_iter": 500, "tol": 1e-5},
        "gam02": {"family": "gam", "id": "gam02", "n_splines": 8, "lam": 1, "max_iter": 500, "tol": 1e-5},
        "gam03": {"family": "gam", "id": "gam03", "n_splines": 8, "lam": 10, "max_iter": 500, "tol": 1e-5},
        "gam04": {"family": "gam", "id": "gam04", "n_splines": 12, "lam": 10, "max_iter": 500, "tol": 1e-5},
    }
    shared = {
        "family": "gam",
        "implementation": "pspline_logistic_v1",
        "spline_degree": 3,
        "include_bias": False,
        "extrapolation": "constant",
        "knot_strategy": "training_quantile_then_uniform_nonconstant_v1",
        "constant_feature_policy": "omit_exactly_constant",
        "omitted_basis_reference": "append_zero_before_second_difference",
        "objective": "mean_logloss_normalized_d2_plus_ridge_v1",
        "ridge_lambda": 1e-4,
        "optimizer": "L-BFGS-B",
        "max_iter": 1000,
        "gtol": 1e-6,
        "ftol": 1e-12,
        "gradient_inf_norm_max": 1e-5,
    }
    assert GOAL029_PSPLINE_CANDIDATES == {
        f"psgam{index:02d}": {
            **shared,
            "id": f"psgam{index:02d}",
            "n_knots": n_knots,
            "roughness_lambda": roughness_lambda,
        }
        for index, (n_knots, roughness_lambda) in enumerate(
            ((4, .01), (4, .1), (4, 1.0), (6, .01), (6, .1), (6, 1.0))
        )
    }
    assert not any(
        candidate_id in CANONICAL_CANDIDATES
        for candidate_id in GOAL029_PSPLINE_CANDIDATES
    )
    with pytest.raises(ModelAdapterError, match="candidate_registry_mismatch"):
        validate_candidate("gam", GOAL029_PSPLINE_CANDIDATES["psgam00"])
    with goal029_candidate_authority(GOAL029_PSPLINE_CANDIDATES):
        assert all(
            CANONICAL_CANDIDATES[candidate_id] == candidate
            for candidate_id, candidate in GOAL029_PSPLINE_CANDIDATES.items()
        )
        for candidate in GOAL029_PSPLINE_CANDIDATES.values():
            validate_candidate("gam", candidate)
        with pytest.raises(ModelAdapterError, match="candidate_value_drift"):
            validate_candidate(
                "gam",
                {
                    **GOAL029_PSPLINE_CANDIDATES["psgam00"],
                    "n_knots": 4.0,
                },
            )
    with pytest.raises(ModelAdapterError, match="authority_mismatch"):
        with goal029_candidate_authority(
            {"psgam00": GOAL029_PSPLINE_CANDIDATES["psgam00"]}
        ):
            pass
    with pytest.raises(ModelAdapterError, match="candidate_registry_mismatch"):
        validate_candidate(
            "gam",
            {
                "family": "gam",
                "id": "gamr00",
                "n_splines": 4,
                "lam": 10,
                "max_iter": 500,
                "tol": 1e-5,
            },
        )
    for candidate in CANONICAL_CANDIDATES.values():
        validate_candidate(candidate["family"], candidate)
    with pytest.raises(ModelAdapterError): validate_candidate("intercept", {**CANONICAL_CANDIDATES["null00"], "positive_fraction": 0.5})
    with pytest.raises(ModelAdapterError): validate_candidate("random_forest", {**CANONICAL_CANDIDATES["rf00"], "n_estimators": 499})
    batch = _batch(); fitted, _ = build_adapter("intercept").fit(batch, None, CANONICAL_CANDIDATES["null00"], 2)
    path = tmp_path / "tamper.json"; fitted.serialize(path)
    envelope = json.loads(path.read_text()); envelope["candidate"] = CANONICAL_CANDIDATES["enet00"]; envelope["family"] = "elastic_net"
    path.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ModelAdapterError): load_fitted_model(path, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ModelAdapterError): load_fitted_model(path, "A" * 64)


def test_pspline_objective_gradient_matches_finite_difference():
    from dsdm_phase1.model_adapters import _pspline_objective_and_gradient

    rng = np.random.default_rng(17)
    design = rng.normal(size=(23, 7))
    response = np.asarray([index % 3 == 0 for index in range(23)], dtype=float)
    a = rng.normal(size=(7, 7))
    roughness = a.T @ a / 7
    parameters = rng.normal(scale=.2, size=8)
    _, analytic = _pspline_objective_and_gradient(
        parameters, design, response, roughness, .1, 1e-4
    )
    epsilon = 1e-6
    numeric = np.empty_like(parameters)
    for index in range(len(parameters)):
        step = np.zeros_like(parameters)
        step[index] = epsilon
        plus = _pspline_objective_and_gradient(
            parameters + step, design, response, roughness, .1, 1e-4
        )[0]
        minus = _pspline_objective_and_gradient(
            parameters - step, design, response, roughness, .1, 1e-4
        )[0]
        numeric[index] = (plus - minus) / (2 * epsilon)
    np.testing.assert_allclose(analytic, numeric, rtol=2e-5, atol=2e-7)


def _pspline_batch(
    continuous: np.ndarray,
    categorical: np.ndarray,
    response: np.ndarray,
):
    from dsdm_phase1.modeling_contract import FeatureBatch, RowKey, canonical_json

    continuous = np.asarray(continuous, dtype=float)
    categorical = np.asarray(categorical, dtype=float)
    if continuous.ndim == 1:
        continuous = continuous[:, None]
    if categorical.ndim == 1:
        categorical = categorical[:, None]
    x = np.column_stack([continuous, categorical])
    names = tuple(
        [f"x{index}" for index in range(continuous.shape[1])]
        + [f"cat__{index}" for index in range(categorical.shape[1])]
    )
    kinds = tuple(
        ["continuous"] * continuous.shape[1]
        + ["categorical"] * categorical.shape[1]
    )
    digest = hashlib.sha256(
        canonical_json(
            {
                "feature_names": names,
                "feature_kinds": kinds,
                "continuous_count": continuous.shape[1],
            }
        ).encode()
    ).hexdigest()
    keys = tuple(RowKey("sp", f"{index:03d}") for index in range(len(x)))
    return FeatureBatch(
        keys,
        x,
        np.asarray(response, dtype=float),
        names,
        kinds,
        continuous.shape[1],
        digest,
        {},
        "outer",
        "t" * 64,
        "e" * 64,
    )


def test_pspline_nonlinearity_penalty_edge_cases_and_roundtrip(tmp_path):
    from dsdm_phase1.model_adapters import (
        GOAL029_PSPLINE_CANDIDATES,
        ModelAdapterError,
        _pspline_roughness_matrix,
        build_adapter,
        goal029_candidate_authority,
        load_fitted_model,
    )

    x = np.linspace(-3, 3, 120)
    repeated = (np.arange(len(x)) >= 100).astype(float)
    constant = np.ones_like(x)
    category = np.asarray([index % 2 for index in range(len(x))], dtype=float)
    response = ((x * x + .8 * category) > 2.7).astype(float)
    batch = _pspline_batch(
        np.column_stack([constant, repeated, x]),
        category,
        response,
    )
    with goal029_candidate_authority(GOAL029_PSPLINE_CANDIDATES):
        weak, weak_report = build_adapter("gam").fit(
            batch, None, GOAL029_PSPLINE_CANDIDATES["psgam00"], 13
        )
        weak_repeat, _ = build_adapter("gam").fit(
            batch, None, GOAL029_PSPLINE_CANDIDATES["psgam00"], 13
        )
        strong, _ = build_adapter("gam").fit(
            batch, None, GOAL029_PSPLINE_CANDIDATES["psgam02"], 13
        )
        weak_scores = weak.predict_scores(batch)
        np.testing.assert_allclose(
            weak_scores, weak_repeat.predict_scores(batch), rtol=0, atol=0
        )
        assert weak_report.converged
        assert weak.model.basis_status == (
            "uniform_fallback_and_constant_omitted"
        )
        assert np.mean(weak_scores[response == 1]) > np.mean(
            weak_scores[response == 0]
        )
        weak_penalty = _pspline_roughness_matrix(
            len(weak.model.coef_), weak.model.block_slices
        )
        strong_penalty = _pspline_roughness_matrix(
            len(strong.model.coef_), strong.model.block_slices
        )
        weak_roughness = float(
            weak.model.coef_ @ weak_penalty @ weak.model.coef_
        )
        strong_roughness = float(
            strong.model.coef_ @ strong_penalty @ strong.model.coef_
        )
        assert strong_roughness <= weak_roughness + 1e-10
        path = tmp_path / "psgam.model"
        weak.serialize(path)
        repeat_path = tmp_path / "psgam-repeat.model"
        weak_repeat.serialize(repeat_path)
        assert path.read_bytes() == repeat_path.read_bytes()
        loaded = load_fitted_model(
            path, hashlib.sha256(path.read_bytes()).hexdigest()
        )
        np.testing.assert_allclose(
            weak_scores, loaded.predict_scores(batch), rtol=0, atol=0
        )
        weak.model.n_knots = 6
        invalid_path = tmp_path / "psgam-invalid.model"
        weak.serialize(invalid_path)
        with pytest.raises(
            ModelAdapterError, match="pspline_serialized_basis_invalid"
        ):
            load_fitted_model(
                invalid_path,
                hashlib.sha256(invalid_path.read_bytes()).hexdigest(),
            )


def test_pspline_high_prevalence_and_categorical_effect():
    from dsdm_phase1.model_adapters import (
        GOAL029_PSPLINE_CANDIDATES,
        build_adapter,
        goal029_candidate_authority,
    )

    n = 80
    continuous = np.linspace(-1, 1, n)
    category = np.asarray([0] * 40 + [1] * 40, dtype=float)
    response = np.ones(n, dtype=float)
    response[0] = 0
    batch = _pspline_batch(continuous, category, response)
    with goal029_candidate_authority(GOAL029_PSPLINE_CANDIDATES):
        fitted, report = build_adapter("gam").fit(
            batch, None, GOAL029_PSPLINE_CANDIDATES["psgam05"], 29
        )
    scores = fitted.predict_scores(batch)
    assert report.converged and np.isfinite(scores).all()
    assert np.all((scores >= 0) & (scores <= 1))
    assert np.mean(scores[category == 1]) > np.mean(scores[category == 0])


def test_neural_epoch_types_and_prediction_schema_rejection():
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, ModelAdapterError, build_adapter
    batch = _batch(); candidate = CANONICAL_CANDIDATES["ann00"]
    with pytest.raises(ModelAdapterError): build_adapter("shallow_ann").fit(batch, None, candidate, 1, exact_epochs=True)
    with pytest.raises(ModelAdapterError): build_adapter("shallow_ann").fit(batch, None, candidate, 1, exact_epochs=0)
    fitted, _ = build_adapter("shallow_ann").fit(batch, None, candidate, 1, exact_epochs=1)
    altered = _batch(); names = ("x1", "cat__a"); digest = hashlib.sha256(__import__("dsdm_phase1.modeling_contract", fromlist=["canonical_json"]).canonical_json({"feature_names": names, "feature_kinds": altered.feature_kinds, "continuous_count": altered.continuous_count}).encode()).hexdigest(); altered = type(altered)(altered.keys, altered.x, altered.y, names, altered.feature_kinds, altered.continuous_count, digest, altered.unseen_level_counts, altered.transform_id, altered.transform_digest, altered.encoder_digest)
    with pytest.raises(ModelAdapterError): fitted.predict_scores(altered)


def test_gam_exhaustion_and_raw_random_forest_exception(monkeypatch):
    import dsdm_phase1.model_adapters as adapters
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, ModelAdapterError, build_adapter
    batch = _batch()
    class ExhaustedGAM:
        def __init__(self, *args, **kwargs): self.logs_ = {"diffs": [1.0] * 500}; self.coef_ = np.ones(3)
        def fit(self, x, y): return self
        def predict_proba(self, x): return np.column_stack([np.zeros(len(x)), np.ones(len(x)) * .5])
    monkeypatch.setattr(adapters, "LogisticGAM", ExhaustedGAM)
    with pytest.raises(ModelAdapterError, match="gam_nonconverged"): build_adapter("gam").fit(batch, None, CANONICAL_CANDIDATES["gam00"], 1)

    class ExactFinalIterationGAM:
        def __init__(self, *args, **kwargs): self.logs_ = {"diffs": [1.0] * 499 + [1e-6]}; self.coef_ = np.ones(3)
        def fit(self, x, y): return self
        def predict_proba(self, x): return np.column_stack([np.zeros(len(x)), np.ones(len(x)) * .5])

    monkeypatch.setattr(adapters, "LogisticGAM", ExactFinalIterationGAM)
    _, report = build_adapter("gam").fit(batch, None, CANONICAL_CANDIDATES["gam00"], 1)
    assert report.converged and report.iterations == 500

    class BrokenRF:
        def __init__(self, *args, **kwargs): pass
        def fit(self, x, y): raise RuntimeError("boom")
    monkeypatch.setattr(adapters, "RandomForestClassifier", BrokenRF)
    with pytest.raises(ModelAdapterError, match="random_forest_fit_failed"): build_adapter("random_forest").fit(batch, None, CANONICAL_CANDIDATES["rf00"], 1)


@pytest.mark.parametrize("warning_message", ["overflow encountered in exp", "divide by zero encountered in log"])
def test_gam_numerical_runtime_warning_is_nonconverged(monkeypatch, warning_message):
    import dsdm_phase1.model_adapters as adapters
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, ModelAdapterError, build_adapter
    batch = _batch()

    class NumericalWarningGAM:
        def __init__(self, *args, **kwargs): self.logs_ = {"diffs": [1e-6]}; self.coef_ = np.ones(3)
        def fit(self, x, y):
            warnings.warn(warning_message, RuntimeWarning)
            return self
        def predict_proba(self, x): return np.column_stack([np.zeros(len(x)), np.ones(len(x)) * .5])

    monkeypatch.setattr(adapters, "LogisticGAM", NumericalWarningGAM)
    with pytest.raises(ModelAdapterError, match="gam_nonconverged"):
        build_adapter("gam").fit(batch, None, CANONICAL_CANDIDATES["gam00"], 1)


def test_neural_patience_reports_actual_completed_epoch(monkeypatch):
    import dsdm_phase1.model_adapters as adapters
    from dsdm_phase1.model_adapters import CANONICAL_CANDIDATES, build_adapter
    batch = _batch()
    class NoOpOptimizer:
        def __init__(self, *args, **kwargs): pass
        def zero_grad(self, *args, **kwargs): pass
        def step(self): pass
    monkeypatch.setattr(adapters.torch.optim, "AdamW", NoOpOptimizer)
    _, report = build_adapter("shallow_ann").fit(batch, batch, CANONICAL_CANDIDATES["ann00"], 4)
    assert report.neural_stop_status == "patience_stop" and 1 <= report.iterations <= 300 and report.best_epoch <= report.iterations
