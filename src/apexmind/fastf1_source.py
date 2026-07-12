"""FastF1 ingestion adapter used during the data-fidelity stage."""

from __future__ import annotations

from typing import Any

from apexmind.benchmarks import BenchmarkRace
from apexmind.paths import DataPaths


def load_race(benchmark: BenchmarkRace, paths: DataPaths) -> Any:
    """Load only the race data required for the v1 replay state.

    Telemetry is intentionally disabled. The first research gate needs timing, tyres,
    weather, track status, and race-control data; loading car telemetry before that
    gate adds time and data-volume risk without improving its acceptance criteria.
    """

    import fastf1

    paths.create()
    fastf1.Cache.enable_cache(str(paths.fastf1_cache))
    session = fastf1.get_session(benchmark.year, benchmark.event_name, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=True)
    return session
