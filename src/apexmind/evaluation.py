"""Temporal hold-out splitting, calibration metrics, and the Phase 2 evaluation report."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


class EvaluationError(ValueError):
    """Raised when a hold-out split or metric cannot be computed."""


def temporal_holdout_split(
    laps_by_benchmark: dict[str, pd.DataFrame], *, holdout_benchmark_id: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split benchmarks into a training history and a held-out future race.

    Random or per-lap splitting would leak information: laps within a stint
    are highly autocorrelated, so a model could effectively memorise a
    race it was "tested" on. Instead this holds out one entire benchmark
    race and trains only on the others, which mirrors the real deployment
    question ("does history from earlier races generalise to a race the
    model has not seen?") rather than measuring in-race interpolation.
    """

    if holdout_benchmark_id not in laps_by_benchmark:
        raise EvaluationError(f"Unknown hold-out benchmark '{holdout_benchmark_id}'.")
    train_frames = [
        laps
        for benchmark_id, laps in laps_by_benchmark.items()
        if benchmark_id != holdout_benchmark_id
    ]
    if not train_frames:
        raise EvaluationError(
            "At least one training benchmark is required besides the hold-out race."
        )

    train = pd.concat(train_frames, ignore_index=True)
    test = laps_by_benchmark[holdout_benchmark_id]
    if train.empty or test.empty:
        raise EvaluationError("Training or hold-out split is empty after filtering.")
    return train, test


def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


WET_WEATHER_COMPOUNDS: frozenset[str] = frozenset({"INTERMEDIATE", "WET"})


def metrics_by_compound_class(
    compound: pd.Series, y_true: np.ndarray, y_pred: np.ndarray
) -> dict[str, dict[str, float]]:
    """Split MAE/RMSE into dry-compound and intermediate/wet-compound subsets.

    Exists because of a concrete finding on the `dutch-2023` hold-out
    (`docs/PACE_MODEL.md`): a single pooled RMSE can look like the model
    is worse than baseline overall, while actually being clearly better
    on the compounds that make up most of a race (79% of that hold-out's
    laps) and clearly worse only on a compound with zero representation
    in the training set for that split (`INTERMEDIATE`, 21% of laps).
    Reporting the split rather than only the pooled number is what makes
    that distinction visible instead of hidden inside one average.
    """

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    is_dry = (~compound.isin(WET_WEATHER_COMPOUNDS)).to_numpy()

    result: dict[str, dict[str, float]] = {}
    for label, mask in (("dry", is_dry), ("intermediate_or_wet", ~is_dry)):
        if not mask.any():
            continue
        result[label] = {
            "row_count": int(mask.sum()),
            "mae": mean_absolute_error(y_true[mask], y_pred[mask]),
            "rmse": root_mean_squared_error(y_true[mask], y_pred[mask]),
        }
    return result


def _standard_normal_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + _vectorized_erf(z / math.sqrt(2.0)))


def _vectorized_erf(z: np.ndarray) -> np.ndarray:
    erf = np.vectorize(math.erf)
    return erf(z)


def _standard_normal_pdf(z: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * z**2) / math.sqrt(2.0 * math.pi)


def gaussian_crps(y_true: np.ndarray, mean: np.ndarray, variance: np.ndarray) -> float:
    """Mean closed-form CRPS assuming a Normal predictive distribution per row.

    Lower is better; a CRPS of 0 means every prediction was a perfectly
    confident point mass on the true value. Formula: Gneiting & Raftery
    (2007), equation for the CRPS of N(mu, sigma^2).
    """

    y_true = np.asarray(y_true, dtype=float)
    mean = np.asarray(mean, dtype=float)
    sigma = np.sqrt(np.asarray(variance, dtype=float))
    if np.any(sigma <= 0):
        raise EvaluationError("Predictive variance must be strictly positive for every row.")

    z = (y_true - mean) / sigma
    crps = sigma * (
        z * (2 * _standard_normal_cdf(z) - 1) + 2 * _standard_normal_pdf(z) - 1 / math.sqrt(math.pi)
    )
    return float(np.mean(crps))


def _normal_ppf(probability: float) -> float:
    """Inverse standard-normal CDF via Newton's method on ``math.erf``.

    Avoids a hard-coded rational approximation (a common source of subtle
    off-by-small-amount bugs) at the cost of a few iterations per call.
    """

    if not 0 < probability < 1:
        raise EvaluationError("probability must be strictly between 0 and 1.")
    z = 0.0
    for _ in range(50):
        cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        pdf = math.exp(-0.5 * z**2) / math.sqrt(2.0 * math.pi)
        step = (cdf - probability) / pdf
        z -= step
        if abs(step) < 1e-12:
            break
    return z


def interval_coverage(
    y_true: np.ndarray, mean: np.ndarray, variance: np.ndarray, *, confidence: float
) -> float:
    """Fraction of observations falling inside the model's own central predictive interval.

    A well-calibrated model's coverage should sit close to ``confidence``.
    Coverage well above it means the intervals are too wide (falsely
    cautious); coverage well below it means they are too narrow (falsely
    confident) — the failure mode this project's honesty commitments care
    about most.
    """

    if not 0 < confidence < 1:
        raise EvaluationError("confidence must be strictly between 0 and 1.")
    y_true = np.asarray(y_true, dtype=float)
    mean = np.asarray(mean, dtype=float)
    sigma = np.sqrt(np.asarray(variance, dtype=float))

    z = _normal_ppf(0.5 + confidence / 2)
    within = np.abs(y_true - mean) <= z * sigma
    return float(np.mean(within))


def paired_mean_difference_ci(
    a: np.ndarray, b: np.ndarray, *, confidence: float = 0.95
) -> tuple[float, float, float]:
    """Normal-approximation confidence interval for the paired mean of ``a - b``.

    Built for `run_monte_carlo`'s common-random-numbers draws (`docs/SIMULATOR.md`):
    when ``a`` and ``b`` are two strategies' total race times at the same
    draw indices, this is a paired comparison, so the correct standard
    error comes from the variance of the per-draw difference, not from
    treating the two samples as independent. Returns
    ``(mean_difference, lower_bound, upper_bound)``. An interval that
    excludes zero is the "statistically supported advantage" Gate D
    (`docs/PROJECT_PLAN.md`) asks for.
    """

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise EvaluationError("Paired arrays must have the same shape.")
    if a.size < 2:
        raise EvaluationError("At least two paired observations are required.")
    if not 0 < confidence < 1:
        raise EvaluationError("confidence must be strictly between 0 and 1.")

    difference = a - b
    mean_difference = float(np.mean(difference))
    standard_error = float(np.std(difference, ddof=1) / math.sqrt(difference.size))
    z = _normal_ppf(0.5 + confidence / 2)
    margin = z * standard_error
    return mean_difference, mean_difference - margin, mean_difference + margin


def write_calibration_report(
    path: Path,
    *,
    holdout_benchmark_id: str,
    train_benchmark_ids: tuple[str, ...],
    train_row_count: int,
    test_row_count: int,
    baseline_metrics: dict[str, float],
    model_metrics: dict[str, float],
    coverage: dict[str, float],
    baseline_metrics_by_compound_class: dict[str, dict[str, float]] | None = None,
    model_metrics_by_compound_class: dict[str, dict[str, float]] | None = None,
) -> None:
    """Write the Phase 2 evaluation summary as a portable JSON record."""

    payload = {
        "holdout_benchmark_id": holdout_benchmark_id,
        "train_benchmark_ids": list(train_benchmark_ids),
        "train_row_count": train_row_count,
        "test_row_count": test_row_count,
        "baseline_metrics": baseline_metrics,
        "model_metrics": model_metrics,
        "model_beats_baseline_mae": model_metrics["mae"] <= baseline_metrics["mae"],
        "coverage": coverage,
        "baseline_metrics_by_compound_class": baseline_metrics_by_compound_class or {},
        "model_metrics_by_compound_class": model_metrics_by_compound_class or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
