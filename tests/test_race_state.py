import pandas as pd
import pytest

from apexmind.benchmarks import get_benchmark
from apexmind.race_state import RaceStateError, build_lap_state, validate_lap_state


def _duration(seconds: float):
    return pd.to_timedelta(seconds, unit="s")


def _laps() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Driver": ["AAA", "AAA"],
            "DriverNumber": ["1", "1"],
            "LapTime": [_duration(91.2), _duration(90.8)],
            "LapNumber": [1.0, 2.0],
            "Stint": [1.0, 1.0],
            "PitInTime": [pd.NaT, pd.NaT],
            "PitOutTime": [_duration(1), pd.NaT],
            "Sector1Time": [_duration(30), _duration(29.8)],
            "Sector2Time": [_duration(31), _duration(30.8)],
            "Sector3Time": [_duration(30.2), _duration(30.2)],
            "Compound": ["MEDIUM", "MEDIUM"],
            "TyreLife": [1.0, 2.0],
            "FreshTyre": [True, True],
            "Team": ["Example", "Example"],
            "TrackStatus": ["1", "1"],
            "Position": [4.0, 3.0],
            "Deleted": [False, False],
            "IsAccurate": [False, True],
        }
    )


def test_build_lap_state_preserves_observed_and_quality_fields() -> None:
    state = build_lap_state(_laps(), get_benchmark("bahrain-2024"))

    validate_lap_state(state)

    assert list(state["lap_number"]) == [1.0, 2.0]
    assert list(state["lap_time_seconds"]) == [91.2, 90.8]
    assert state.loc[0, "is_pit_out_lap"]
    assert not state.loc[0, "is_accurate"]
    assert state.loc[1, "position"] == 3.0


def test_build_lap_state_rejects_missing_source_columns() -> None:
    laps = _laps().drop(columns="TrackStatus")

    with pytest.raises(RaceStateError, match="TrackStatus"):
        build_lap_state(laps, get_benchmark("bahrain-2024"))
