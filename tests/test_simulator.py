import numpy as np
import pandas as pd
import pytest

from apexmind.pace_model import fit_bayesian_pace_model
from apexmind.safety_car import SafetyCarScenario
from apexmind.simulator import (
    SimulatorError,
    Stint,
    StrategyPlan,
    run_monte_carlo,
    simulate_race,
    summarize_simulations,
)


def _near_zero_posterior():
    # A large, all-zero synthetic dataset drives the posterior mean to
    # (almost) zero and its predictive variance to (almost) zero too, which
    # makes total-race-time arithmetic in these tests exact enough to
    # assert on directly instead of only checking broad plausibility.
    design = pd.DataFrame(
        {
            "compound_SOFT": [1.0] * 500,
            "tyre_life_SOFT": list(range(1, 501)),
            "compound_MEDIUM": [0.0] * 500,
            "tyre_life_MEDIUM": [0.0] * 500,
            "compound_HARD": [0.0] * 500,
            "tyre_life_HARD": [0.0] * 500,
            "compound_INTERMEDIATE": [0.0] * 500,
            "tyre_life_INTERMEDIATE": [0.0] * 500,
            "compound_WET": [0.0] * 500,
            "tyre_life_WET": [0.0] * 500,
        }
    )
    target = pd.Series([0.0] * 500)
    return fit_bayesian_pace_model(design, target, prior_scale=0.01, prior_rate=1e-6)


def test_stint_rejects_unknown_compound_or_nonpositive_laps() -> None:
    with pytest.raises(SimulatorError):
        Stint(compound="SLICK", lap_count=10)
    with pytest.raises(SimulatorError):
        Stint(compound="SOFT", lap_count=0)


def test_strategy_plan_requires_at_least_one_stint() -> None:
    with pytest.raises(SimulatorError):
        StrategyPlan(name="empty", stints=())


def test_strategy_plan_derives_total_laps_and_pit_stops() -> None:
    plan = StrategyPlan(name="1-stop", stints=(Stint("SOFT", 20), Stint("HARD", 30)))

    assert plan.total_laps == 50
    assert plan.pit_stop_count == 1


def test_simulate_race_is_deterministic_for_a_fixed_seed() -> None:
    posterior = _near_zero_posterior()
    strategy = StrategyPlan(name="1-stop", stints=(Stint("SOFT", 20), Stint("HARD", 30)))

    first = simulate_race(
        strategy,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        rng=np.random.default_rng(3),
    )
    second = simulate_race(
        strategy,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        rng=np.random.default_rng(3),
    )

    assert first == second


def test_extra_pit_stop_costs_approximately_one_pit_loss() -> None:
    posterior = _near_zero_posterior()
    one_stop = StrategyPlan(name="1-stop", stints=(Stint("SOFT", 25), Stint("HARD", 25)))
    two_stop = StrategyPlan(
        name="2-stop", stints=(Stint("SOFT", 17), Stint("SOFT", 17), Stint("HARD", 16))
    )

    result_one = simulate_race(
        one_stop,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        rng=np.random.default_rng(1),
    )
    result_two = simulate_race(
        two_stop,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        rng=np.random.default_rng(1),
    )

    # With near-zero pace noise and a near-zero degradation slope, the only
    # material difference between a 1-stop and a 2-stop plan of the same
    # total lap count is the extra pit stop.
    assert result_two.total_race_time_seconds - result_one.total_race_time_seconds == pytest.approx(
        20.0, abs=0.5
    )


def test_safety_car_laps_use_the_declared_multiplier_not_the_pace_model() -> None:
    posterior = _near_zero_posterior()
    strategy = StrategyPlan(name="no-stop", stints=(Stint("SOFT", 10),))
    scenario = SafetyCarScenario(
        episode_lap_probability=1.0, duration_laps_options=(10,), pace_multiplier=1.5
    )

    result = simulate_race(
        strategy,
        posterior,
        driver_baseline_seconds=100.0,
        pit_loss_seconds=20.0,
        rng=np.random.default_rng(0),
        safety_car_scenario=scenario,
    )

    # Every lap is under Safety Car at multiplier 1.5 with no pit stop.
    assert result.total_race_time_seconds == pytest.approx(10 * 100.0 * 1.5, rel=1e-6)
    assert result.safety_car_lap_count == 10


def test_simulate_race_rejects_invalid_configuration() -> None:
    posterior = _near_zero_posterior()
    strategy = StrategyPlan(name="1-stop", stints=(Stint("SOFT", 10),))

    with pytest.raises(SimulatorError):
        simulate_race(
            strategy,
            posterior,
            driver_baseline_seconds=90.0,
            pit_loss_seconds=-1.0,
            rng=np.random.default_rng(0),
        )
    with pytest.raises(SimulatorError):
        simulate_race(
            strategy,
            posterior,
            driver_baseline_seconds=90.0,
            pit_loss_seconds=10.0,
            rng=np.random.default_rng(0),
            safety_car_pit_loss_discount=1.5,
        )


def test_run_monte_carlo_is_reproducible_and_shaped_correctly() -> None:
    posterior = _near_zero_posterior()
    strategies = (
        StrategyPlan(name="1-stop", stints=(Stint("SOFT", 25), Stint("HARD", 25))),
        StrategyPlan(
            name="2-stop", stints=(Stint("SOFT", 17), Stint("SOFT", 17), Stint("HARD", 16))
        ),
    )

    first = run_monte_carlo(
        strategies,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        n_simulations=25,
        seed=42,
    )
    second = run_monte_carlo(
        strategies,
        posterior,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        n_simulations=25,
        seed=42,
    )

    assert len(first) == 25 * len(strategies)
    pd.testing.assert_frame_equal(first, second)


def test_run_monte_carlo_rejects_invalid_configuration() -> None:
    posterior = _near_zero_posterior()
    strategy = StrategyPlan(name="1-stop", stints=(Stint("SOFT", 10),))

    with pytest.raises(SimulatorError):
        run_monte_carlo(
            (),
            posterior,
            driver_baseline_seconds=90.0,
            pit_loss_seconds=10.0,
            n_simulations=10,
            seed=1,
        )
    with pytest.raises(SimulatorError):
        run_monte_carlo(
            (strategy,),
            posterior,
            driver_baseline_seconds=90.0,
            pit_loss_seconds=10.0,
            n_simulations=0,
            seed=1,
        )


def test_summarize_simulations_computes_paired_regret_and_win_rate() -> None:
    results = pd.DataFrame(
        {
            "draw_index": [0, 0, 1, 1],
            "strategy_name": ["A", "B", "A", "B"],
            "total_race_time_seconds": [100.0, 105.0, 110.0, 108.0],
            "pit_stop_count": [1, 2, 1, 2],
            "safety_car_lap_count": [0, 0, 3, 3],
        }
    )

    summary = summarize_simulations(results).set_index("strategy_name")

    assert summary.loc["A", "mean_regret_seconds"] == pytest.approx((0 + 2) / 2)
    assert summary.loc["B", "mean_regret_seconds"] == pytest.approx((5 + 0) / 2)
    assert summary.loc["A", "win_rate"] == pytest.approx(0.5)
    assert summary.loc["B", "win_rate"] == pytest.approx(0.5)


def test_summarize_simulations_rejects_empty_results() -> None:
    with pytest.raises(SimulatorError):
        summarize_simulations(
            pd.DataFrame(columns=["draw_index", "strategy_name", "total_race_time_seconds"])
        )
