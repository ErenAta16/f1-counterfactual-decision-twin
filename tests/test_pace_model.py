import numpy as np
import pandas as pd
import pytest

from apexmind.pace_model import PaceModelError, fit_bayesian_pace_model, predict


def _synthetic_design(n: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    tyre_life = rng.uniform(0, 20, size=n)
    is_soft = rng.uniform(size=n) < 0.5
    compound_soft = is_soft.astype(float)
    compound_hard = 1.0 - compound_soft

    # True generating process: SOFT starts 0.5s faster but degrades at
    # 0.08 s/lap; HARD starts at 0 offset and degrades at 0.02 s/lap.
    true_intercept_soft, true_slope_soft = -0.5, 0.08
    true_intercept_hard, true_slope_hard = 0.0, 0.02
    noise = rng.normal(scale=0.05, size=n)

    y = (
        compound_soft * (true_intercept_soft + true_slope_soft * tyre_life)
        + compound_hard * (true_intercept_hard + true_slope_hard * tyre_life)
        + noise
    )
    design = pd.DataFrame(
        {
            "compound_SOFT": compound_soft,
            "tyre_life_SOFT": compound_soft * tyre_life,
            "compound_HARD": compound_hard,
            "tyre_life_HARD": compound_hard * tyre_life,
        }
    )
    return design, pd.Series(y)


def test_fit_recovers_known_coefficients_from_low_noise_data() -> None:
    design, target = _synthetic_design(n=2000, seed=0)

    posterior = fit_bayesian_pace_model(design, target)

    coefficients = dict(zip(posterior.feature_names, posterior.coefficient_mean, strict=True))
    assert coefficients["compound_SOFT"] == pytest.approx(-0.5, abs=0.05)
    assert coefficients["tyre_life_SOFT"] == pytest.approx(0.08, abs=0.01)
    assert coefficients["compound_HARD"] == pytest.approx(0.0, abs=0.05)
    assert coefficients["tyre_life_HARD"] == pytest.approx(0.02, abs=0.01)


def test_predictive_variance_shrinks_with_more_training_data() -> None:
    small_design, small_target = _synthetic_design(n=50, seed=1)
    large_design, large_target = _synthetic_design(n=5000, seed=1)

    small_posterior = fit_bayesian_pace_model(small_design, small_target)
    large_posterior = fit_bayesian_pace_model(large_design, large_target)

    query = pd.DataFrame(
        {
            "compound_SOFT": [1.0],
            "tyre_life_SOFT": [10.0],
            "compound_HARD": [0.0],
            "tyre_life_HARD": [0.0],
        }
    )
    _, small_variance = predict(small_posterior, query)
    _, large_variance = predict(large_posterior, query)

    assert large_variance[0] < small_variance[0]


def test_predict_rejects_mismatched_columns() -> None:
    design, target = _synthetic_design(n=100, seed=2)
    posterior = fit_bayesian_pace_model(design, target)

    with pytest.raises(PaceModelError):
        predict(posterior, design.rename(columns={"compound_SOFT": "unexpected"}))
