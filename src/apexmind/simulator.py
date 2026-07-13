"""A Monte Carlo counterfactual race simulator built on the Phase 2 pace model.

This is a single-car strategy simulator: it estimates how long one car takes
to complete a race under a candidate strategy (a sequence of tyre stints),
using the Phase 2 pace model for green-flag pace, the Phase 2 pit-loss
baseline for stop cost, and a declared Safety Car scenario. It does not
model other cars' positions, gaps, or overtaking, because the ingested
schema (Phase 1) has no gap-to-car-ahead field to validate that against.
Comparing strategies by total race time is the honest scope for v1; a
position-and-gap model is future work, not an implicit claim made here.

Reproducibility: every simulation is driven by an explicit
``numpy.random.SeedSequence``-derived generator, never by unseeded global
randomness, so a given seed always reproduces the same result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from apexmind.pace_features import COMPOUND_CATEGORIES, build_pace_feature_matrix
from apexmind.pace_model import PacePosterior, predict
from apexmind.safety_car import SafetyCarScenario, sample_safety_car_laps


class SimulatorError(ValueError):
    """Raised when a strategy or simulation configuration is invalid."""


@dataclass(frozen=True)
class Stint:
    """One tyre stint: a compound driven for a planned number of laps."""

    compound: str
    lap_count: int

    def __post_init__(self) -> None:
        if self.compound not in COMPOUND_CATEGORIES:
            raise SimulatorError(f"Unknown compound '{self.compound}'.")
        if self.lap_count <= 0:
            raise SimulatorError("lap_count must be positive.")


@dataclass(frozen=True)
class StrategyPlan:
    """A full-race candidate strategy: a named sequence of stints."""

    name: str
    stints: tuple[Stint, ...]

    def __post_init__(self) -> None:
        if not self.stints:
            raise SimulatorError("A strategy must have at least one stint.")

    @property
    def total_laps(self) -> int:
        return sum(stint.lap_count for stint in self.stints)

    @property
    def pit_stop_count(self) -> int:
        return len(self.stints) - 1


@dataclass(frozen=True)
class RaceSimulationResult:
    """The outcome of one Monte Carlo draw of one strategy."""

    strategy_name: str
    total_race_time_seconds: float
    pit_stop_count: int
    safety_car_lap_count: int


def _lap_plan(strategy: StrategyPlan) -> pd.DataFrame:
    """Expand a strategy into one row per lap: lap number, compound, tyre life."""

    rows = []
    lap_number = 1
    for stint in strategy.stints:
        for tyre_life in range(1, stint.lap_count + 1):
            rows.append(
                {"lap_number": lap_number, "compound": stint.compound, "tyre_life": tyre_life}
            )
            lap_number += 1
    return pd.DataFrame(rows)


def _pit_in_laps(strategy: StrategyPlan) -> set[int]:
    """Lap numbers on which a pit stop concludes this stint (all but the last)."""

    laps: set[int] = set()
    cumulative = 0
    for stint in strategy.stints[:-1]:
        cumulative += stint.lap_count
        laps.add(cumulative)
    return laps


def simulate_race(
    strategy: StrategyPlan,
    posterior: PacePosterior,
    *,
    driver_baseline_seconds: float,
    pit_loss_seconds: float,
    rng: np.random.Generator,
    safety_car_scenario: SafetyCarScenario | None = None,
    safety_car_pit_loss_discount: float = 0.5,
    energy_scenario_seconds_per_lap: float = 0.0,
) -> RaceSimulationResult:
    """Run one Monte Carlo draw of ``strategy`` and return its total race time.

    ``driver_baseline_seconds`` is the reference pace the Phase 2 model's
    predictions are relative to (see ``docs/PACE_MODEL.md``): in practice a
    value informed by practice or qualifying pace on the day, supplied by
    the caller rather than invented here.

    Laps under a sampled Safety Car/VSC period do not use the green-flag
    pace model at all, since that model was deliberately fit only on
    green-flag laps (`docs/PACE_MODEL.md`); using it to predict caution-lap
    pace would apply it well outside the data it was estimated from.
    Instead a caution lap costs ``driver_baseline_seconds *
    (scenario.pace_multiplier - 1)`` in addition to the baseline, and a pit
    stop taken during a caution lap is discounted by
    ``safety_car_pit_loss_discount`` (default a declared 50%, reflecting
    the well-known real-world effect of a slowed field reducing the relative
    cost of a stop) rather than measured from data — this benchmark set
    does not contain enough caution-period pit stops to estimate that
    discount empirically.

    ``energy_scenario_seconds_per_lap`` is a flat, declared per-lap pace
    adjustment for a simulated energy/aero availability scenario
    (`docs/PROJECT_PLAN.md`, Section 6.5): a sensitivity-analysis input, not
    an inference from data.
    """

    if pit_loss_seconds < 0:
        raise SimulatorError("pit_loss_seconds must not be negative.")
    if not 0 <= safety_car_pit_loss_discount <= 1:
        raise SimulatorError("safety_car_pit_loss_discount must be between 0 and 1.")

    plan = _lap_plan(strategy)
    race_progress = plan["lap_number"] / strategy.total_laps
    design = build_pace_feature_matrix(plan["compound"], plan["tyre_life"], race_progress)
    mean, variance = predict(posterior, design)
    sampled_delta = rng.normal(loc=mean, scale=np.sqrt(variance))

    safety_car_laps: frozenset[int] = frozenset()
    if safety_car_scenario is not None:
        safety_car_laps = sample_safety_car_laps(strategy.total_laps, safety_car_scenario, rng)

    pit_in_laps = _pit_in_laps(strategy)
    total_time = 0.0
    for row_index, lap_number in enumerate(plan["lap_number"]):
        if lap_number in safety_car_laps:
            lap_time = driver_baseline_seconds * safety_car_scenario.pace_multiplier
        else:
            lap_time = (
                driver_baseline_seconds + sampled_delta[row_index] + energy_scenario_seconds_per_lap
            )

        if lap_number in pit_in_laps:
            discount = safety_car_pit_loss_discount if lap_number in safety_car_laps else 0.0
            lap_time += pit_loss_seconds * (1.0 - discount)

        total_time += lap_time

    return RaceSimulationResult(
        strategy_name=strategy.name,
        total_race_time_seconds=total_time,
        pit_stop_count=strategy.pit_stop_count,
        safety_car_lap_count=len(safety_car_laps),
    )


def run_monte_carlo(
    strategies: tuple[StrategyPlan, ...],
    posterior: PacePosterior,
    *,
    driver_baseline_seconds: float,
    pit_loss_seconds: float,
    n_simulations: int,
    seed: int,
    safety_car_scenario: SafetyCarScenario | None = None,
    energy_scenario_seconds_per_lap: float = 0.0,
) -> pd.DataFrame:
    """Run every strategy through the same sequence of simulated race conditions.

    Each simulated race index shares one Safety Car draw across every
    strategy (common random numbers): the question this answers is "under
    the same race conditions, which strategy comes out ahead", not "what is
    each strategy's unconditional average" against independently drawn
    conditions. Pace noise is still sampled independently per strategy,
    since different strategies drive different tyre-life sequences and
    lap-for-lap noise alignment across them would not be meaningful.

    Every child random stream is derived from ``seed`` through
    ``numpy.random.SeedSequence``, so the full result set is reproducible.
    """

    if not strategies:
        raise SimulatorError("At least one strategy is required.")
    if n_simulations <= 0:
        raise SimulatorError("n_simulations must be positive.")

    root = np.random.SeedSequence(seed)
    draw_seeds = root.spawn(n_simulations)

    rows = []
    for draw_index, draw_seed in enumerate(draw_seeds):
        child_seeds = draw_seed.spawn(1 + len(strategies))
        safety_car_rng = np.random.default_rng(child_seeds[0])
        # A single shared Safety Car draw for this race index, reused for
        # every strategy so all strategies face the same simulated race.
        shared_safety_car_laps = (
            sample_safety_car_laps(
                max(strategy.total_laps for strategy in strategies),
                safety_car_scenario,
                safety_car_rng,
            )
            if safety_car_scenario is not None
            else frozenset()
        )
        for strategy, strategy_seed in zip(strategies, child_seeds[1:], strict=True):
            pace_rng = np.random.default_rng(strategy_seed)
            result = _simulate_with_fixed_safety_car(
                strategy,
                posterior,
                driver_baseline_seconds=driver_baseline_seconds,
                pit_loss_seconds=pit_loss_seconds,
                rng=pace_rng,
                safety_car_laps=shared_safety_car_laps,
                safety_car_scenario=safety_car_scenario,
                energy_scenario_seconds_per_lap=energy_scenario_seconds_per_lap,
            )
            rows.append(
                {
                    "draw_index": draw_index,
                    "strategy_name": result.strategy_name,
                    "total_race_time_seconds": result.total_race_time_seconds,
                    "pit_stop_count": result.pit_stop_count,
                    "safety_car_lap_count": result.safety_car_lap_count,
                }
            )

    return pd.DataFrame(rows)


def _simulate_with_fixed_safety_car(
    strategy: StrategyPlan,
    posterior: PacePosterior,
    *,
    driver_baseline_seconds: float,
    pit_loss_seconds: float,
    rng: np.random.Generator,
    safety_car_laps: frozenset[int],
    safety_car_scenario: SafetyCarScenario | None,
    energy_scenario_seconds_per_lap: float,
    safety_car_pit_loss_discount: float = 0.5,
) -> RaceSimulationResult:
    """Same lap-time model as ``simulate_race``, but with a pre-drawn Safety Car set.

    Kept private: this is the shared-race-conditions building block used by
    ``run_monte_carlo``. ``simulate_race`` is the public, single-strategy
    entry point for callers who do not need the paired-comparison structure.
    """

    plan = _lap_plan(strategy)
    race_progress = plan["lap_number"] / strategy.total_laps
    design = build_pace_feature_matrix(plan["compound"], plan["tyre_life"], race_progress)
    mean, variance = predict(posterior, design)
    sampled_delta = rng.normal(loc=mean, scale=np.sqrt(variance))

    relevant_safety_car_laps = {lap for lap in safety_car_laps if lap <= strategy.total_laps}
    pit_in_laps = _pit_in_laps(strategy)
    total_time = 0.0
    for row_index, lap_number in enumerate(plan["lap_number"]):
        if lap_number in relevant_safety_car_laps:
            lap_time = driver_baseline_seconds * safety_car_scenario.pace_multiplier
        else:
            lap_time = (
                driver_baseline_seconds + sampled_delta[row_index] + energy_scenario_seconds_per_lap
            )

        if lap_number in pit_in_laps:
            discount = (
                safety_car_pit_loss_discount if lap_number in relevant_safety_car_laps else 0.0
            )
            lap_time += pit_loss_seconds * (1.0 - discount)

        total_time += lap_time

    return RaceSimulationResult(
        strategy_name=strategy.name,
        total_race_time_seconds=total_time,
        pit_stop_count=strategy.pit_stop_count,
        safety_car_lap_count=len(relevant_safety_car_laps),
    )


def summarize_simulations(results: pd.DataFrame) -> pd.DataFrame:
    """Summarize Monte Carlo draws per strategy, including dynamic regret.

    Regret for a draw is that strategy's time minus the best (lowest) time
    among all strategies in the *same* draw index — the paired comparison
    ``run_monte_carlo`` was structured to support. Mean regret close to
    zero means a strategy is consistently competitive; a high mean regret
    means it is reliably beaten by some other candidate under the same
    conditions.
    """

    required = {"draw_index", "strategy_name", "total_race_time_seconds"}
    missing = required.difference(results.columns)
    if missing:
        raise SimulatorError(f"Results table is missing columns: {', '.join(sorted(missing))}.")
    if results.empty:
        raise SimulatorError("Cannot summarize an empty results table.")

    best_per_draw = results.groupby("draw_index")["total_race_time_seconds"].transform("min")
    with_regret = results.assign(regret_seconds=results["total_race_time_seconds"] - best_per_draw)

    summary = with_regret.groupby("strategy_name").agg(
        mean_total_race_time_seconds=("total_race_time_seconds", "mean"),
        p10_total_race_time_seconds=("total_race_time_seconds", lambda s: s.quantile(0.10)),
        p50_total_race_time_seconds=("total_race_time_seconds", lambda s: s.quantile(0.50)),
        p90_total_race_time_seconds=("total_race_time_seconds", lambda s: s.quantile(0.90)),
        mean_regret_seconds=("regret_seconds", "mean"),
        win_rate=("regret_seconds", lambda s: float((s == 0).mean())),
    )
    return summary.reset_index().sort_values("mean_total_race_time_seconds")
