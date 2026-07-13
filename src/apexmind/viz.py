"""Matplotlib charts for the pace model, its calibration, and Monte Carlo outcomes.

Optional: requires the ``viz`` extra (``pip install -e ".[viz]"``). Every
function here takes already-computed data (a fitted posterior, evaluation
arrays, a ``run_monte_carlo`` DataFrame) rather than touching disk or the
network, so the same function works from the CLI, a test, or a notebook.

The Agg backend is forced because this project's tooling discipline
(`docs/SIMULATOR.md`, `docs/EVIDENCE_INTERFACE.md`) is headless and
reproducible by default: these functions write static PNGs, not
interactive windows.

Every function takes a ``mode`` of ``"light"`` or ``"dark"`` and renders a
matching, independently colour-checked theme rather than a plain white
figure — a chart embedded in a GitHub README sits on whichever surface the
viewer's OS theme picks, and a white plot on a dark page reads as broken.
Colours are not hand-picked: every categorical hue used here (tyre
compound, candidate strategy) passed the CVD-separation, lightness-band,
chroma-floor, and surface-contrast checks in both modes before being used
- see the project's data-visualisation review for the validated values.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

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


Mode = Literal["light", "dark"]

# Chart chrome: surface, ink, and gridline tokens per mode. Both modes are
# independently selected (not one auto-inverted from the other) and
# validated against their own surface colour.
_THEME: dict[Mode, dict[str, str]] = {
    "light": {
        "surface": "#fcfcfb",
        "primary_ink": "#0b0b0b",
        "secondary_ink": "#52514e",
        "muted_ink": "#898781",
        "gridline": "#e1e0d9",
        "baseline": "#c3c2b7",
    },
    "dark": {
        "surface": "#1a1a19",
        "primary_ink": "#ffffff",
        "secondary_ink": "#c3c2b7",
        "muted_ink": "#898781",
        "gridline": "#2c2c2a",
        "baseline": "#383835",
    },
}

# Tyre-compound identity colours. SOFT/MEDIUM/INTERMEDIATE/WET follow F1's
# own broadcast convention (red/yellow/green/blue) - the strongest existing
# colour language this project's audience already reads - snapped to the
# nearest validated palette step per mode. HARD has no legible non-white
# convention, so it takes the palette's magenta slot; the resulting 5-way
# set (plus the 3-way SOFT/MEDIUM/HARD subset the CLI actually renders by
# default) both pass CVD-separation, lightness-band, and chroma-floor in
# both modes.
COMPOUND_COLORS: dict[str, dict[Mode, str]] = {
    "SOFT": {"light": "#e34948", "dark": "#e66767"},
    "MEDIUM": {"light": "#eda100", "dark": "#c98500"},
    "HARD": {"light": "#e87ba4", "dark": "#d55181"},
    "INTERMEDIATE": {"light": "#008300", "dark": "#008300"},
    "WET": {"light": "#2a78d6", "dark": "#3987e5"},
}

# Fixed-order categorical palette (blue, aqua, yellow, green, violet, red,
# magenta, orange) for series with no domain colour of their own, such as
# candidate strategies. Assigned in this order and never cycled or
# re-sorted by value.
_CATEGORICAL: dict[Mode, tuple[str, ...]] = {
    "light": (
        "#2a78d6",
        "#1baf7a",
        "#eda100",
        "#008300",
        "#4a3aa7",
        "#e34948",
        "#e87ba4",
        "#eb6834",
    ),
    "dark": (
        "#3987e5",
        "#199e70",
        "#c98500",
        "#008300",
        "#9085e9",
        "#e66767",
        "#d55181",
        "#d95926",
    ),
}

_ACCENT: dict[Mode, str] = {"light": "#2a78d6", "dark": "#3987e5"}

_FIGURE_DPI = 200


def _new_figure(figsize: tuple[float, float], mode: Mode) -> Axes:
    theme = _THEME[mode]
    fig, ax = plt.subplots(figsize=figsize, dpi=_FIGURE_DPI)
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])
    return ax


def _apply_theme(ax: Axes, mode: Mode) -> None:
    """Recessive grid/spines, ink-toned text, no chart border - applied last so it wins."""

    theme = _THEME[mode]
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme["baseline"])
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=theme["muted_ink"], labelsize=9)
    ax.yaxis.grid(True, color=theme["gridline"], linewidth=1.0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.title.set_color(theme["primary_ink"])
    ax.xaxis.label.set_color(theme["secondary_ink"])
    ax.yaxis.label.set_color(theme["secondary_ink"])
    ax.title.set_fontweight("bold")
    legend = ax.get_legend()
    if legend is not None:
        legend.get_frame().set_facecolor(theme["surface"])
        legend.get_frame().set_edgecolor(theme["baseline"])
        legend.get_frame().set_linewidth(0.75)
        for text in legend.get_texts():
            text.set_color(theme["secondary_ink"])


def plot_tyre_degradation(
    posterior: PacePosterior,
    *,
    compounds: Sequence[str] | None = None,
    max_tyre_life: int = 40,
    race_progress: float = 0.5,
    mode: Mode = "light",
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
        ax = _new_figure((8, 5), mode)
    theme = _THEME[mode]

    tyre_life = np.arange(0, max_tyre_life + 1)
    for compound_name in selected:
        design = build_pace_feature_matrix(
            pd.Series([compound_name] * len(tyre_life)),
            pd.Series(tyre_life),
            pd.Series([race_progress] * len(tyre_life)),
        )
        model_mean, variance = predict(posterior, design)
        std = np.sqrt(variance)
        color = COMPOUND_COLORS.get(compound_name, {}).get(mode, _ACCENT[mode])
        ax.plot(tyre_life, model_mean, label=compound_name, color=color, linewidth=2.2, zorder=3)
        ax.fill_between(
            tyre_life, model_mean - 1.96 * std, model_mean + 1.96 * std, alpha=0.12, color=color
        )
        # Direct end-of-line label: the legend is always present, but a
        # label riding the line itself lets a compound be read without
        # matching swatches, and is the required relief channel for the
        # lighter hues (MEDIUM/HARD) in light mode.
        ax.annotate(
            compound_name,
            xy=(tyre_life[-1], model_mean[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=theme["secondary_ink"],
            fontweight="bold",
        )

    ax.set_xlabel("Tyre age (laps)")
    ax.set_ylabel("Predicted pace delta vs. driver baseline (s)")
    ax.set_title(f"Tyre degradation by compound (race progress={race_progress:.0%})")
    legend = ax.legend(frameon=True, loc="upper left")
    ax.margins(x=0.08)
    _apply_theme(ax, mode)
    legend.get_frame().set_facecolor(theme["surface"])
    return ax


DEFAULT_CONFIDENCE_LEVELS: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def plot_calibration_reliability(
    y_true: np.ndarray,
    mean: np.ndarray,
    variance: np.ndarray,
    *,
    confidence_levels: Sequence[float] = DEFAULT_CONFIDENCE_LEVELS,
    mode: Mode = "light",
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
        ax = _new_figure((5.5, 5.5), mode)
    theme = _THEME[mode]

    observed = [
        interval_coverage(y_true, mean, variance, confidence=level) for level in confidence_levels
    ]

    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1.5, color=theme["muted_ink"], zorder=1)
    ax.annotate(
        "perfect calibration",
        xy=(0.62, 0.62),
        rotation=45,
        rotation_mode="anchor",
        fontsize=8,
        color=theme["muted_ink"],
        ha="center",
        va="bottom",
    )
    ax.plot(
        confidence_levels,
        observed,
        marker="o",
        markersize=8,
        markerfacecolor=_ACCENT[mode],
        markeredgecolor=theme["surface"],
        markeredgewidth=1.5,
        linewidth=2.2,
        color=_ACCENT[mode],
        label="Observed coverage",
        zorder=3,
    )
    ax.set_xlabel("Nominal confidence level")
    ax.set_ylabel("Observed coverage")
    ax.set_title("Calibration reliability diagram")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    _apply_theme(ax, mode)
    return ax


def plot_monte_carlo_outcomes(
    results: pd.DataFrame,
    *,
    mode: Mode = "light",
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
        ax = _new_figure((8, 5), mode)
    theme = _THEME[mode]
    palette = _CATEGORICAL[mode]

    strategy_names = sorted(results["strategy_name"].unique())
    for index, strategy_name in enumerate(strategy_names):
        color = palette[index % len(palette)]
        values = results.loc[results["strategy_name"] == strategy_name, "total_race_time_seconds"]
        ax.hist(
            values,
            bins=30,
            facecolor=color,
            alpha=0.5,
            edgecolor=color,
            linewidth=1.0,
            label=strategy_name,
        )

    ax.set_xlabel("Total race time (s)")
    ax.set_ylabel("Simulated draws")
    ax.set_title("Monte Carlo outcome distribution by strategy")
    legend = ax.legend(frameon=True, loc="upper right")
    _apply_theme(ax, mode)
    legend.get_frame().set_facecolor(theme["surface"])
    return ax
