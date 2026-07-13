"""Transform provider-specific timing rows into the initial ApexMind race-state table."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from apexmind.benchmarks import BenchmarkRace


class RaceStateError(ValueError):
    """Raised when source data cannot satisfy the replay-state contract."""


SOURCE_COLUMNS = frozenset(
    {
        "Driver",
        "DriverNumber",
        "LapTime",
        "LapNumber",
        "Stint",
        "PitInTime",
        "PitOutTime",
        "Sector1Time",
        "Sector2Time",
        "Sector3Time",
        "Compound",
        "TyreLife",
        "FreshTyre",
        "Team",
        "TrackStatus",
        "Position",
        "Deleted",
        "IsAccurate",
    }
)

RACE_STATE_COLUMNS = (
    "benchmark_id",
    "condition_class",
    "event_year",
    "event_name",
    "session_name",
    "driver",
    "driver_number",
    "team",
    "lap_number",
    "stint",
    "position",
    "compound",
    "tyre_life",
    "fresh_tyre",
    "lap_time_seconds",
    "sector_1_seconds",
    "sector_2_seconds",
    "sector_3_seconds",
    "is_pit_in_lap",
    "is_pit_out_lap",
    "track_status",
    "is_deleted",
    "is_accurate",
)


def _seconds(values: pd.Series) -> pd.Series:
    return pd.to_timedelta(values, errors="coerce").dt.total_seconds()


def _require_columns(laps: pd.DataFrame, required: Iterable[str] = SOURCE_COLUMNS) -> None:
    missing = sorted(set(required).difference(laps.columns))
    if missing:
        raise RaceStateError(f"Lap data is missing required columns: {', '.join(missing)}.")


def build_lap_state(
    laps: pd.DataFrame,
    benchmark: BenchmarkRace,
    *,
    session_name: str = "Race",
) -> pd.DataFrame:
    """Build one normalised row per driver and completed lap.

    This function preserves provider values rather than filling missing timings. A
    missing or deleted lap is evidence that must remain visible to downstream
    quality checks, not a value that should be silently imputed during ingestion.
    """

    _require_columns(laps)
    if laps.empty:
        raise RaceStateError("Lap data is empty; a replay state cannot be created.")

    state = pd.DataFrame(
        {
            "benchmark_id": benchmark.identifier,
            "condition_class": benchmark.condition_class,
            "event_year": benchmark.year,
            "event_name": benchmark.event_name,
            "session_name": session_name,
            "driver": laps["Driver"].astype("string"),
            "driver_number": laps["DriverNumber"].astype("string"),
            "team": laps["Team"].astype("string"),
            "lap_number": pd.to_numeric(laps["LapNumber"], errors="coerce"),
            "stint": pd.to_numeric(laps["Stint"], errors="coerce"),
            "position": pd.to_numeric(laps["Position"], errors="coerce"),
            "compound": laps["Compound"].astype("string"),
            "tyre_life": pd.to_numeric(laps["TyreLife"], errors="coerce"),
            "fresh_tyre": laps["FreshTyre"].astype("boolean"),
            "lap_time_seconds": _seconds(laps["LapTime"]),
            "sector_1_seconds": _seconds(laps["Sector1Time"]),
            "sector_2_seconds": _seconds(laps["Sector2Time"]),
            "sector_3_seconds": _seconds(laps["Sector3Time"]),
            "is_pit_in_lap": laps["PitInTime"].notna(),
            "is_pit_out_lap": laps["PitOutTime"].notna(),
            "track_status": laps["TrackStatus"].astype("string"),
            "is_deleted": laps["Deleted"].astype("boolean"),
            "is_accurate": laps["IsAccurate"].astype("boolean"),
        }
    )
    return (
        state.loc[:, RACE_STATE_COLUMNS]
        .sort_values(["driver", "lap_number"], kind="stable")
        .reset_index(drop=True)
    )


def validate_lap_state(state: pd.DataFrame) -> None:
    """Check the minimum invariants required before writing a replay artefact."""

    missing = sorted(set(RACE_STATE_COLUMNS).difference(state.columns))
    if missing:
        raise RaceStateError(f"Race state is missing required columns: {', '.join(missing)}.")
    if state.empty:
        raise RaceStateError("Race state is empty.")
    if state["driver"].isna().any() or state["lap_number"].isna().any():
        raise RaceStateError("Race state contains a missing driver or lap number.")
    if (state["lap_number"] <= 0).any():
        raise RaceStateError("Race state contains a non-positive lap number.")
    duplicates = state.duplicated(["driver", "lap_number"], keep=False)
    if duplicates.any():
        raise RaceStateError("Race state contains duplicate driver/lap pairs.")
