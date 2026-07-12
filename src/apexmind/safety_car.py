"""Safety Car / VSC episode extraction and a declared scenario generator for simulation.

Episode extraction (``extract_safety_car_episodes``) reads only what is
already recorded as evidence in the Phase 1 race-control table: it is an
**observed** transformation, no different in kind from the rest of Phase 1.
The scenario generator below it (``SafetyCarScenario``,
``sample_safety_car_laps``) is a different thing entirely: a **simulated**
assumption in this project's evidence contract (`docs/PROJECT_PLAN.md`,
Section 3). Only three benchmark races exist, and only two of them contain
any Safety Car or VSC event, which is nowhere near enough to fit a
statistically reliable deployment-rate model. The scenario defaults are
order-of-magnitude estimates informed by the observed episodes, documented
in `docs/SIMULATOR.md`, and are meant to be varied explicitly rather than
trusted as a calibrated probability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


class SafetyCarError(ValueError):
    """Raised when race-control evidence cannot support safety-car extraction."""


DEPLOY_MESSAGES = {
    "SAFETY CAR DEPLOYED": "SC",
    "VIRTUAL SAFETY CAR DEPLOYED": "VSC",
}
END_MESSAGES = {
    "SAFETY CAR IN THIS LAP": "SC",
    "VIRTUAL SAFETY CAR ENDING": "VSC",
}


@dataclass(frozen=True)
class SafetyCarEpisode:
    """One continuous Safety Car or Virtual Safety Car period, in race laps."""

    episode_type: str  # "SC" or "VSC"
    start_lap: int
    end_lap: int  # inclusive

    @property
    def duration_laps(self) -> int:
        return self.end_lap - self.start_lap + 1


def extract_safety_car_episodes(race_control: pd.DataFrame) -> tuple[SafetyCarEpisode, ...]:
    """Pair deployment and ending race-control messages into episodes.

    Matches a documented deployment message to the next ending message of
    the same type, in event-time order. A deployment with no matching
    ending message before the data ends (for example because the race also
    had a red flag, as in the Dutch GP 2023 benchmark) is closed at the
    last lap present in ``race_control``; this fallback is visible to a
    reviewer by comparing the resulting ``end_lap`` against the recorded
    chequered-flag lap for that benchmark.
    """

    required = {"event_time", "category", "message", "lap"}
    missing = required.difference(race_control.columns)
    if missing:
        raise SafetyCarError(
            f"Race-control table is missing columns: {', '.join(sorted(missing))}."
        )
    if race_control.empty:
        raise SafetyCarError("Race-control table is empty.")

    ordered = race_control.sort_values("event_time")
    episodes: list[SafetyCarEpisode] = []
    open_deploys: dict[str, int] = {}
    lap_values = ordered["lap"].dropna()
    if lap_values.empty:
        raise SafetyCarError("Race-control table has no rows with a recorded lap.")
    last_lap = int(lap_values.max())

    for _, row in ordered.iterrows():
        if pd.isna(row["lap"]):
            continue
        message = str(row["message"]).strip().upper()
        lap = int(row["lap"])
        if message in DEPLOY_MESSAGES:
            episode_type = DEPLOY_MESSAGES[message]
            open_deploys.setdefault(episode_type, lap)
        elif message in END_MESSAGES:
            episode_type = END_MESSAGES[message]
            start_lap = open_deploys.pop(episode_type, None)
            if start_lap is not None:
                episodes.append(SafetyCarEpisode(episode_type, start_lap, lap))

    for episode_type, start_lap in open_deploys.items():
        episodes.append(SafetyCarEpisode(episode_type, start_lap, last_lap))

    return tuple(sorted(episodes, key=lambda episode: episode.start_lap))


DEFAULT_EPISODE_LAP_PROBABILITY = 0.02
DEFAULT_DURATION_LAPS_OPTIONS: tuple[int, ...] = (2, 3, 4, 5)
DEFAULT_PACE_MULTIPLIER = 1.4


@dataclass(frozen=True)
class SafetyCarScenario:
    """A declared, illustrative Safety Car / VSC scenario for Monte Carlo simulation.

    ``pace_multiplier`` (default 1.4) is a rough empirical anchor, not a fit:
    real green-flag-versus-caution lap times in the two benchmarks that had
    incidents show roughly 35-50% slower laps under a pure Safety Car status
    code. ``episode_lap_probability`` and ``duration_laps_options`` are
    order-of-magnitude placeholders informed by, but not statistically
    estimated from, the two observed episodes in this benchmark set.
    """

    episode_lap_probability: float = DEFAULT_EPISODE_LAP_PROBABILITY
    duration_laps_options: tuple[int, ...] = DEFAULT_DURATION_LAPS_OPTIONS
    pace_multiplier: float = DEFAULT_PACE_MULTIPLIER


def sample_safety_car_laps(
    total_laps: int, scenario: SafetyCarScenario, rng: np.random.Generator
) -> frozenset[int]:
    """Draw the set of laps under Safety Car/VSC conditions for one simulated race.

    At most one episode is drawn per simulated race. Real races can have
    more than one (Singapore 2023 had two), but modelling the arrival
    process of multiple episodes from a two-race sample would overstate
    what this data can support; a single-episode-per-race model is the
    declared, documented simplification for this v1 scenario generator.
    """

    if total_laps <= 0:
        raise SafetyCarError("total_laps must be positive.")
    if not 0 <= scenario.episode_lap_probability <= 1:
        raise SafetyCarError("episode_lap_probability must be between 0 and 1.")

    deployed = rng.random(total_laps) < scenario.episode_lap_probability
    deployment_laps = np.flatnonzero(deployed)
    if deployment_laps.size == 0:
        return frozenset()

    start_lap = int(deployment_laps[0]) + 1  # laps are 1-indexed
    duration = int(rng.choice(scenario.duration_laps_options))
    end_lap = min(start_lap + duration - 1, total_laps)
    return frozenset(range(start_lap, end_lap + 1))
