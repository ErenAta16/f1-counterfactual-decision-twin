"""Normalise race-control and weather context without merging it into lap evidence."""

from __future__ import annotations

import pandas as pd

from apexmind.benchmarks import BenchmarkRace


class ContextError(ValueError):
    """Raised when source context cannot satisfy the v1 replay contract."""


RACE_CONTROL_COLUMNS = (
    "benchmark_id",
    "event_year",
    "event_name",
    "event_time",
    "category",
    "message",
    "status",
    "flag",
    "scope",
    "sector",
    "racing_number",
    "lap",
)

WEATHER_COLUMNS = (
    "benchmark_id",
    "event_year",
    "event_name",
    "observation_seconds",
    "air_temperature_c",
    "humidity_percent",
    "pressure_mbar",
    "rainfall",
    "track_temperature_c",
    "wind_direction_degrees",
    "wind_speed_mps",
)


def _require_columns(frame: pd.DataFrame, required: set[str], context_name: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ContextError(f"{context_name} is missing required columns: {', '.join(missing)}.")
    if frame.empty:
        raise ContextError(f"{context_name} is empty.")


def build_race_control_events(
    messages: pd.DataFrame, benchmark: BenchmarkRace
) -> pd.DataFrame:
    """Return race-control messages as separate, provider-faithful event evidence."""

    _require_columns(
        messages,
        {"Time", "Category", "Message", "Status", "Flag", "Scope", "Sector", "RacingNumber", "Lap"},
        "Race-control messages",
    )
    events = pd.DataFrame(
        {
            "benchmark_id": benchmark.identifier,
            "event_year": benchmark.year,
            "event_name": benchmark.event_name,
            "event_time": pd.to_datetime(messages["Time"], errors="coerce"),
            "category": messages["Category"].astype("string"),
            "message": messages["Message"].astype("string"),
            "status": messages["Status"].astype("string"),
            "flag": messages["Flag"].astype("string"),
            "scope": messages["Scope"].astype("string"),
            "sector": pd.to_numeric(messages["Sector"], errors="coerce"),
            "racing_number": messages["RacingNumber"].astype("string"),
            "lap": pd.to_numeric(messages["Lap"], errors="coerce"),
        }
    )
    return events.loc[:, RACE_CONTROL_COLUMNS].sort_values("event_time", kind="stable").reset_index(
        drop=True
    )


def build_weather_observations(weather: pd.DataFrame, benchmark: BenchmarkRace) -> pd.DataFrame:
    """Return provider weather readings without falsely aligning them to individual laps."""

    _require_columns(
        weather,
        {
            "Time",
            "AirTemp",
            "Humidity",
            "Pressure",
            "Rainfall",
            "TrackTemp",
            "WindDirection",
            "WindSpeed",
        },
        "Weather data",
    )
    observation_seconds = pd.to_timedelta(weather["Time"], errors="coerce").dt.total_seconds()
    observations = pd.DataFrame(
        {
            "benchmark_id": benchmark.identifier,
            "event_year": benchmark.year,
            "event_name": benchmark.event_name,
            "observation_seconds": observation_seconds,
            "air_temperature_c": pd.to_numeric(weather["AirTemp"], errors="coerce"),
            "humidity_percent": pd.to_numeric(weather["Humidity"], errors="coerce"),
            "pressure_mbar": pd.to_numeric(weather["Pressure"], errors="coerce"),
            "rainfall": weather["Rainfall"].astype("boolean"),
            "track_temperature_c": pd.to_numeric(weather["TrackTemp"], errors="coerce"),
            "wind_direction_degrees": pd.to_numeric(weather["WindDirection"], errors="coerce"),
            "wind_speed_mps": pd.to_numeric(weather["WindSpeed"], errors="coerce"),
        }
    )
    return observations.loc[:, WEATHER_COLUMNS].sort_values(
        "observation_seconds", kind="stable"
    ).reset_index(drop=True)
