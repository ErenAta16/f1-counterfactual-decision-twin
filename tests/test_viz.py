import numpy as np
import pandas as pd
import pytest

from apexmind.pace_features import build_pace_feature_matrix
from apexmind.pace_model import fit_bayesian_pace_model
from apexmind.viz import (
    VizError,
    plot_calibration_reliability,
    plot_monte_carlo_outcomes,
    plot_tyre_degradation,
)


def _fitted_posterior(n: int = 500, seed: int = 0):
    rng = np.random.default_rng(seed)
    compound = pd.Series(rng.choice(["SOFT", "MEDIUM", "HARD"], size=n))
    tyre_life = pd.Series(rng.uniform(0, 30, size=n))
    race_progress = pd.Series(rng.uniform(0, 1, size=n))
    design = build_pace_feature_matrix(compound, tyre_life, race_progress)
    target = pd.Series(rng.normal(scale=0.3, size=n))
    return fit_bayesian_pace_model(design, target)


def test_plot_tyre_degradation_draws_one_line_per_selected_compound() -> None:
    posterior = _fitted_posterior()

    ax = plot_tyre_degradation(posterior, compounds=("SOFT", "HARD"), max_tyre_life=10)

    assert len(ax.lines) == 2
    assert {line.get_label() for line in ax.lines} == {"SOFT", "HARD"}


def test_plot_tyre_degradation_defaults_to_all_compounds() -> None:
    posterior = _fitted_posterior()

    ax = plot_tyre_degradation(posterior)

    assert len(ax.lines) == 5


def test_plot_tyre_degradation_rejects_unknown_compound() -> None:
    posterior = _fitted_posterior()

    with pytest.raises(VizError):
        plot_tyre_degradation(posterior, compounds=("SLICK",))


def test_plot_tyre_degradation_rejects_out_of_range_race_progress() -> None:
    posterior = _fitted_posterior()

    with pytest.raises(VizError):
        plot_tyre_degradation(posterior, race_progress=1.5)


def test_plot_calibration_reliability_plots_one_point_per_confidence_level() -> None:
    rng = np.random.default_rng(1)
    y_true = rng.normal(size=200)
    mean = y_true + rng.normal(scale=0.1, size=200)
    variance = np.full(200, 0.05)

    ax = plot_calibration_reliability(y_true, mean, variance, confidence_levels=(0.5, 0.8, 0.95))

    # One reference diagonal line plus one observed-coverage line.
    assert len(ax.lines) == 2
    observed_line = ax.lines[1]
    assert len(observed_line.get_xdata()) == 3


def test_plot_calibration_reliability_rejects_empty_confidence_levels() -> None:
    y_true = np.array([1.0, 2.0])
    mean = np.array([1.0, 2.0])
    variance = np.array([0.1, 0.1])

    with pytest.raises(VizError):
        plot_calibration_reliability(y_true, mean, variance, confidence_levels=())


def test_plot_monte_carlo_outcomes_draws_one_series_per_strategy() -> None:
    results = pd.DataFrame(
        {
            "strategy_name": ["A"] * 50 + ["B"] * 50,
            "total_race_time_seconds": np.concatenate([np.full(50, 100.0), np.full(50, 105.0)]),
        }
    )

    ax = plot_monte_carlo_outcomes(results)

    assert len(ax.patches) > 0
    legend_labels = {text.get_text() for text in ax.get_legend().get_texts()}
    assert legend_labels == {"A", "B"}


def test_plot_monte_carlo_outcomes_rejects_empty_results() -> None:
    with pytest.raises(VizError):
        plot_monte_carlo_outcomes(
            pd.DataFrame(columns=["strategy_name", "total_race_time_seconds"])
        )


def test_plot_monte_carlo_outcomes_rejects_missing_columns() -> None:
    with pytest.raises(VizError):
        plot_monte_carlo_outcomes(pd.DataFrame({"strategy_name": ["A"]}))


def test_figures_can_be_saved_to_disk(tmp_path) -> None:
    posterior = _fitted_posterior()
    ax = plot_tyre_degradation(posterior, compounds=("SOFT",), max_tyre_life=5)

    output_path = tmp_path / "tyre_degradation.png"
    ax.figure.savefig(output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_plot_tyre_degradation_accepts_both_modes(mode) -> None:
    posterior = _fitted_posterior()

    ax = plot_tyre_degradation(posterior, compounds=("SOFT", "HARD"), mode=mode)

    assert len(ax.lines) == 2


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_plot_calibration_reliability_accepts_both_modes(mode) -> None:
    rng = np.random.default_rng(1)
    y_true = rng.normal(size=50)
    mean = y_true + rng.normal(scale=0.1, size=50)
    variance = np.full(50, 0.05)

    ax = plot_calibration_reliability(y_true, mean, variance, mode=mode)

    assert len(ax.lines) == 2


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_plot_monte_carlo_outcomes_accepts_both_modes(mode) -> None:
    results = pd.DataFrame(
        {
            "strategy_name": ["A"] * 20 + ["B"] * 20,
            "total_race_time_seconds": np.concatenate([np.full(20, 100.0), np.full(20, 105.0)]),
        }
    )

    ax = plot_monte_carlo_outcomes(results, mode=mode)

    assert len(ax.patches) > 0


def test_light_and_dark_modes_render_different_surface_colors() -> None:
    posterior = _fitted_posterior()

    light_ax = plot_tyre_degradation(posterior, compounds=("SOFT",), mode="light")
    dark_ax = plot_tyre_degradation(posterior, compounds=("SOFT",), mode="dark")

    assert light_ax.figure.get_facecolor() != dark_ax.figure.get_facecolor()


def test_dark_mode_tyre_degradation_uses_dark_compound_colors() -> None:
    posterior = _fitted_posterior()

    ax = plot_tyre_degradation(posterior, compounds=("SOFT",), mode="dark")

    from apexmind.viz import COMPOUND_COLORS

    assert ax.lines[0].get_color() == COMPOUND_COLORS["SOFT"]["dark"]
