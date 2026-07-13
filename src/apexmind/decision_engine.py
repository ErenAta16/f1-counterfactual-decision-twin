"""Phase 4 constrained decision engine: legal candidate strategies ranked by expected race time.

This module searches the space of dry-weather pit strategies for one race
distance and finds the legal plan (Article B6.3.6, `apexmind.regulations`)
with the lowest *expected* total race time, using exact dynamic programming
rather than a heuristic search. The state space is small enough to make
this tractable: at most three dry compounds, at most one tyre life per lap
of the race, and eight possible "which compounds used so far" subsets. A
heuristic like beam search would risk discarding a state that looks
expensive now but turns out optimal later; exact DP over this state space
does not have that failure mode and costs nothing extra to compute.

The search is deliberately narrow in two ways, both consequences of
decisions already made in earlier phases:

1. **Dry compounds only.** `docs/PACE_MODEL.md` notes that `WET` has no
   supporting laps in this benchmark set, so the fitted model predicts no
   offset and no degradation for it — not because wet tyres are fast, but
   because there is nothing to estimate from. Searching wet-tyre strategies
   with that model would produce a confidently wrong answer, so the search
   space here is restricted to `SOFT`, `MEDIUM`, `HARD`.
2. **Deterministic planning, not the full posterior.** The DP scores each
   candidate lap by the posterior *mean* pace delta only. This is a
   real simplification: it optimises the expected outcome, not a
   risk-aware one, and it ignores the Safety Car scenario entirely (the
   green-flag pace model does not apply to caution laps in the first
   place — see `docs/SIMULATOR.md`). The `apexmind decide` command re-runs
   the winning plan and the fixed baseline plans through Phase 3's full
   stochastic Monte Carlo simulator afterwards, which does sample from the
   posterior and can include the declared Safety Car scenario, for the
   uncertainty-aware comparison this planning stage does not attempt.

An early, real run against this project's benchmark data surfaced a third
limit, which is why ``max_stint_laps`` exists below: the fitted pace model
gives ``SOFT`` a slightly *negative* tyre-life coefficient, a known
consequence of the tyre age / fuel burn-off confound `docs/PACE_MODEL.md`
already names ("the coefficient should be read as pace change per lap of
tyre age and race progress combined, not as an isolated tyre-degradation
rate"). An unbounded DP takes the posterior mean literally and happily
extrapolates that coefficient across an entire near-full-race stint, since
nothing in the search told it that laps 50-56 of a single stint are outside
anything the model was actually fit on (training data tops out at 49 laps
of observed tyre life). The result was a technically legal but not
credible plan: 56 laps on SOFT and a token 1-lap stint to satisfy Article
B6.3.6. ``optimise_strategies`` therefore refuses, by default, to plan a
stint longer than the longest stint actually observed in training —
extending the same "do not extrapolate a model past its evidence"
discipline `docs/SIMULATOR.md` already applies to Safety Car laps.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from apexmind.pace_features import build_pace_feature_matrix
from apexmind.pace_model import PacePosterior, predict
from apexmind.regulations import DRY_COMPOUNDS, is_legal_strategy
from apexmind.simulator import Stint, StrategyPlan

SEARCH_COMPOUNDS: tuple[str, ...] = tuple(sorted(DRY_COMPOUNDS))


class DecisionEngineError(ValueError):
    """Raised when the optimiser cannot search a race of the requested shape."""


def _pace_at_lap(
    posterior: PacePosterior, lap: int, total_laps: int, compounds: tuple[str, ...]
) -> dict[str, np.ndarray]:
    """Posterior-mean pace delta for each compound at tyre life 1..``total_laps``, at this lap.

    Pace now depends on two independent quantities that this function must
    not collapse into one: tyre life (which resets to 1 at every pit stop)
    and race progress (``lap / total_laps``, which does not reset — see
    ``add_race_progress`` in ``pace_features.py`` for why that distinction
    is what lets the fitted model separate tyre wear from fuel burn-off).
    Because every DP transition into a given lap shares the same race
    progress regardless of which state it came from, this is evaluated
    once per lap rather than once per (compound, tyre life) pair up front.
    """

    tyre_life = pd.Series(range(1, total_laps + 1))
    race_progress = pd.Series([lap / total_laps] * total_laps)
    table: dict[str, np.ndarray] = {}
    for compound in compounds:
        design = build_pace_feature_matrix(
            pd.Series([compound] * total_laps), tyre_life, race_progress
        )
        mean, _variance = predict(posterior, design)
        table[compound] = np.asarray(mean, dtype=float)
    return table


@dataclass(frozen=True)
class _DpState:
    """One reachable (compound, tyre life, compounds-used-so-far) combination at some lap."""

    compound: str
    tyre_life: int
    used: frozenset[str]


@dataclass(frozen=True)
class _DpEntry:
    cost: float
    parent: _DpState | None
    pit_stop: bool


def optimise_strategies(
    posterior: PacePosterior,
    *,
    total_laps: int,
    driver_baseline_seconds: float,
    pit_loss_seconds: float,
    top_k: int = 5,
    compounds: tuple[str, ...] = SEARCH_COMPOUNDS,
    max_stint_laps: int | None = None,
) -> tuple[StrategyPlan, ...]:
    """Search the legal, dry-compound strategy space and return the best plans found.

    ``max_stint_laps``, if given, caps how many laps any single stint may
    run before the DP is forced to consider a pit stop. This exists
    because of a concrete failure found while developing this module (see
    the module docstring): without a cap, the search extrapolates the
    fitted pace model's tyre-life coefficient across stint lengths far
    beyond anything it was fit on, which can produce a technically legal
    but not credible plan. Callers should pass the longest stint actually
    observed in the data the posterior was fit on, not an arbitrary number.

    Returns up to ``top_k`` distinct legal strategies (deduplicated by their
    compound/lap-count sequence), sorted by ascending expected total race
    time under the posterior mean. The first element is the optimiser's
    chosen plan. Raises `DecisionEngineError` if no legal strategy exists
    for this race distance (which would mean every candidate finished on a
    single dry compound — not possible once ``total_laps`` allows at least
    one pit stop, but checked rather than assumed).
    """

    if total_laps <= 0:
        raise DecisionEngineError("total_laps must be positive.")
    if pit_loss_seconds < 0:
        raise DecisionEngineError("pit_loss_seconds must not be negative.")
    if top_k <= 0:
        raise DecisionEngineError("top_k must be positive.")
    if not compounds:
        raise DecisionEngineError("At least one compound is required to search.")
    if max_stint_laps is not None and max_stint_laps <= 0:
        raise DecisionEngineError("max_stint_laps must be positive when given.")

    lap_one_pace = _pace_at_lap(posterior, 1, total_laps, compounds)
    frontier: dict[_DpState, _DpEntry] = {}
    for compound in compounds:
        state = _DpState(compound, 1, frozenset({compound}))
        cost = driver_baseline_seconds + float(lap_one_pace[compound][0])
        frontier[state] = _DpEntry(cost, None, False)
    history: list[dict[_DpState, _DpEntry]] = [frontier]

    for lap in range(2, total_laps + 1):
        next_frontier: dict[_DpState, _DpEntry] = {}
        # Every transition landing on this lap shares the same race
        # progress, so the per-compound pace table is looked up once per
        # lap, not once per (compound, tyre life) combination up front.
        pace_at_this_lap = _pace_at_lap(posterior, lap, total_laps, compounds)

        def _offer(
            state: _DpState,
            cost: float,
            parent: _DpState,
            pit_stop: bool,
            *,
            _frontier: dict[_DpState, _DpEntry] = next_frontier,
        ) -> None:
            existing = _frontier.get(state)
            if existing is None or cost < existing.cost:
                _frontier[state] = _DpEntry(cost, parent, pit_stop)

        for state, entry in frontier.items():
            new_tyre_life = state.tyre_life + 1
            if max_stint_laps is None or new_tyre_life <= max_stint_laps:
                stay_pace = float(pace_at_this_lap[state.compound][new_tyre_life - 1])
                stay_cost = entry.cost + driver_baseline_seconds + stay_pace
                _offer(_DpState(state.compound, new_tyre_life, state.used), stay_cost, state, False)

            for next_compound in compounds:
                pit_cost = (
                    entry.cost
                    + pit_loss_seconds
                    + driver_baseline_seconds
                    + float(pace_at_this_lap[next_compound][0])
                )
                _offer(
                    _DpState(next_compound, 1, state.used | {next_compound}),
                    pit_cost,
                    state,
                    True,
                )

        frontier = next_frontier
        history.append(frontier)

    finishers = sorted(
        ((state, entry.cost) for state, entry in frontier.items() if len(state.used) >= 2),
        key=lambda item: item[1],
    )
    if not finishers:
        raise DecisionEngineError(
            f"No legal strategy found across {total_laps} laps with compounds {compounds}: "
            "every reachable candidate used fewer than two dry-weather specifications."
        )

    plans: list[StrategyPlan] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    for state, _cost in finishers:
        stints = _backtrack(history, state)
        key = tuple((stint.compound, stint.lap_count) for stint in stints)
        if key in seen:
            continue
        seen.add(key)
        # The name must be injective in the stint sequence: two candidates
        # can share a compound sequence but differ in lap split (e.g.
        # HARD16/MEDIUM16 vs HARD15/MEDIUM17), and downstream Monte Carlo
        # aggregation (`summarize_simulations`) groups by strategy name, so
        # a collision here would silently merge two different strategies.
        stint_label = "/".join(f"{stint.compound.lower()}{stint.lap_count}" for stint in stints)
        name = f"optimiser ({stint_label})"
        plan = StrategyPlan(name=name, stints=stints)
        if not is_legal_strategy(plan):
            raise DecisionEngineError(f"Internal error: '{plan.name}' failed the legality check.")
        plans.append(plan)
        if len(plans) >= top_k:
            break

    return tuple(plans)


def _backtrack(history: list[dict[_DpState, _DpEntry]], final_state: _DpState) -> tuple[Stint, ...]:
    """Reconstruct the stint sequence that reaches ``final_state`` at the last lap."""

    lap_index = len(history) - 1
    state: _DpState | None = final_state
    lap_records: list[tuple[str, bool]] = []
    while lap_index >= 0:
        assert state is not None
        entry = history[lap_index][state]
        lap_records.append((state.compound, entry.pit_stop))
        state = entry.parent
        lap_index -= 1
    lap_records.reverse()

    stints: list[Stint] = []
    current_compound = lap_records[0][0]
    current_count = 1
    for compound, pit_stop in lap_records[1:]:
        if pit_stop:
            stints.append(Stint(current_compound, current_count))
            current_compound = compound
            current_count = 1
        else:
            current_count += 1
    stints.append(Stint(current_compound, current_count))
    return tuple(stints)
