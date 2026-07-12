import math

import numpy as np
import pandas as pd
import pytest

from apexmind.evaluation import (
    EvaluationError,
    _normal_ppf,
    gaussian_crps,
    interval_coverage,
    mean_absolute_error,
    root_mean_squared_error,
    temporal_holdout_split,
)


def test_temporal_holdout_split_trains_on_the_other_benchmarks() -> None:
    laps = {
        "a": pd.DataFrame({"benchmark_id": ["a"], "value": [1]}),
        "b": pd.DataFrame({"benchmark_id": ["b"], "value": [2]}),
        "c": pd.DataFrame({"benchmark_id": ["c"], "value": [3]}),
    }

    train, test = temporal_holdout_split(laps, holdout_benchmark_id="c")

    assert set(train["benchmark_id"]) == {"a", "b"}
    assert set(test["benchmark_id"]) == {"c"}


def test_temporal_holdout_split_rejects_unknown_benchmark() -> None:
    laps = {"a": pd.DataFrame({"benchmark_id": ["a"], "value": [1]})}

    with pytest.raises(EvaluationError):
        temporal_holdout_split(laps, holdout_benchmark_id="missing")


def test_mae_and_rmse_match_hand_computed_values() -> None:
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 4.0, 3.0])

    assert mean_absolute_error(y_true, y_pred) == pytest.approx(2 / 3)
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(math.sqrt(4 / 3))


def test_gaussian_crps_matches_closed_form_at_zero_error() -> None:
    sigma = 2.0
    y_true = np.array([5.0])
    mean = np.array([5.0])
    variance = np.array([sigma**2])

    expected = sigma * (2 * (1 / math.sqrt(2 * math.pi)) - 1 / math.sqrt(math.pi))
    assert gaussian_crps(y_true, mean, variance) == pytest.approx(expected, rel=1e-6)


def test_gaussian_crps_rejects_nonpositive_variance() -> None:
    with pytest.raises(EvaluationError):
        gaussian_crps(np.array([1.0]), np.array([1.0]), np.array([0.0]))


def test_normal_ppf_matches_known_quantiles() -> None:
    assert _normal_ppf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert _normal_ppf(0.975) == pytest.approx(1.959964, abs=1e-5)
    assert _normal_ppf(0.95) == pytest.approx(1.644854, abs=1e-5)


def test_interval_coverage_matches_nominal_confidence_on_well_specified_data() -> None:
    rng = np.random.default_rng(42)
    n = 20_000
    mean = np.zeros(n)
    variance = np.ones(n)
    y_true = rng.normal(loc=0.0, scale=1.0, size=n)

    coverage = interval_coverage(y_true, mean, variance, confidence=0.95)

    assert coverage == pytest.approx(0.95, abs=0.01)
