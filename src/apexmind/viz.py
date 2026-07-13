"""Matplotlib charts for the pace model, its calibration, and Monte Carlo outcomes.

Optional: requires the ``viz`` extra (``pip install -e ".[viz]"``). Every
function here takes already-computed data (a fitted posterior, evaluation
arrays, a ``run_monte_carlo`` DataFrame) rather than touching disk or the
network, so the same function works from the CLI, a test, or a notebook.

The Agg backend is forced because this project's tooling discipline
(`docs/SIMULATOR.md`, `docs/EVIDENCE_INTERFACE.md`) is headless and
reproducible by default: these functions write static PNGs, not
interactive windows.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from apexmind.evaluation import interval_coverage
from apexmind.pace_features import COMPOUND_CATEGORIES, build_pace_feature_matrix
from apexmind.pace_model import PacePosterior, predict

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError as error:  # pragma: no cover - exercised by test_viz_requires_matplotlib
    raise ImportError(
        'apexmind.viz requires matplotlib. Install it with `pip install -e ".[viz]"`.'
    ) from error

if TYPE_CHECKING:
    from matplotlib.axes import Axes


class VizError(ValueError):
    """Raised when a chart cannot be built from the given data."""


COMPOUND_COLORS: dict[str, str] = {
    "SOFT": "#e6002b",
    "MEDIUM": "#f0c000",
    "HARD": "#4a4a4a",
    "INTERMEDIATE": "#43b02a",
    "WET": "#0067b1",
}


def plot_tyre_degradation(
    posterior: PacePosterior,
    *,
    compounds: Sequence[str] | None = None,
    max_tyre_life: int = 40,
    race_progress: float = 0.5,
    ax: Axes | None = None,
) -> Axes:
    """Plot each compound's predicted pace delta against tyre age, with a 95% band.

    ``race_progress`` is held fixed (default: mid-race) because the model
    fits a separate fuel-burn slope per compound (`pace_features.py`); this
    isolates the tyre-degradation line from that confound rather than
    mixing both effects into one curve.
    """

    if not 0.0 <= race_progress <= 1.0:
        raise VizError("race_progress must be between 0 and 1.")
    if max_tyre_life < 1:
        raise VizError("max_tyre_life must be at least 1.")

    selected = compounds if compounds is not None else COMPOUND_CATEGORIES
    unknown = set(selected) - set(COMPOUND_CATEGORIES)
    if unknown:
        raise VizError(f"Unknown compound(s): {sorted(unknown)}")

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    tyre_life = np.arange(0, max_tyre_life + 1)
    for compound_name in selected:
        design = build_pace_feature_matrix(
            pd.Series([compound_name] * len(tyre_life)),
            pd.Series(tyre_life),
            pd.Series([race_progress] * len(tyre_life)),
        )
        mean, variance = predict(posterior, design)
        std = np.sqrt(variance)
        color = COMPOUND_COLORS.get(compound_name)
        ax.plot(tyre_life, mean, label=compound_name, color=color, linewidth=2)
        ax.fill_between(tyre_life, mean - 1.96 * std, mean + 1.96 * std, alpha=0.15, color=color)

    ax.set_xlabel("Tyre age (laps)")
    ax.set_ylabel("Predicted pace delta vs. driver baseline (s)")
    ax.set_title(f"Tyre degradation by compound (race progress={race_progress:.0%})")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


DEFAULT_CONFIDENCE_LEVELS: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def plot_calibration_reliability(
    y_true: np.ndarray,
    mean: np.ndarray,
    variance: np.ndarray,
    *,
    confidence_levels: Sequence[float] = DEFAULT_CONFIDENCE_LEVELS,
    ax: Axes | None = None,
) -> Axes:
    """Plot nominal confidence level against the pace model's observed coverage.

    A well-calibrated model's markers sit on the diagonal. Points below the
    diagonal mean the model's intervals are too narrow (falsely confident);
    points above mean they are too wide (falsely cautious) — see
    `apexmind.evaluation.interval_coverage`, which this reuses at each level
    rather than re-implementing the coverage calculation.
    """

    if len(confidence_levels) == 0:
        raise VizError("confidence_levels must be non-empty.")

    if ax is None:
        _, ax = plt.subplots(figsize=(5, 5))

    observed = [
        interval_coverage(y_true, mean, variance, confidence=level) for level in confidence_levels
    ]

    ax.plot([0, 1], [0, 1], linestyle="--", color="#888888", label="Perfect calibration")
    ax.plot(confidence_levels, observed, marker="o", color="#0067b1", label="Observed coverage")
    ax.set_xlabel("Nominal confidence level")
    ax.set_ylabel("Observed coverage")
    ax.set_title("Calibration reliability diagram")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def plot_monte_carlo_outcomes(
    results: pd.DataFrame,
    *,
    ax: Axes | None = None,
) -> Axes:
    """Plot each strategy's total-race-time distribution from ``run_monte_carlo``.

    Strategies share the same simulated race conditions per draw (common
    random numbers, `docs/SIMULATOR.md`), so overlapping histograms here are
    a like-for-like comparison, not independently drawn samples.
    """

    if results.empty:
        raise VizError("results is empty; nothing to plot.")
    for required_column in ("strategy_name", "total_race_time_seconds"):
        if required_column not in results.columns:
            raise VizError(f"results is missing required column '{required_column}'.")

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    for strategy_name, group in results.groupby("strategy_name"):
        ax.hist(group["total_race_time_seconds"], bins=30, alpha=0.55, label=strategy_name)

    ax.set_xlabel("Total race time (s)")
    ax.set_ylabel("Simulated draws")
    ax.set_title("Monte Carlo outcome distribution by strategy")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax
