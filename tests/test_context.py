import pandas as pd

from apexmind.benchmarks import get_benchmark
from apexmind.context import build_race_control_events, build_weather_observations


def test_race_control_events_preserve_message_evidence() -> None:
    messages = pd.DataFrame(
        {
            "Time": ["2023-09-17T11:10:01"],
            "Category": ["Flag"],
            "Message": ["GREEN LIGHT - PIT EXIT OPEN"],
            "Status": [None],
            "Flag": ["GREEN"],
            "Scope": ["Track"],
            "Sector": [None],
            "RacingNumber": [None],
            "Lap": [1],
        }
    )

    events = build_race_control_events(messages, get_benchmark("singapore-2023"))

    assert events.loc[0, "message"] == "GREEN LIGHT - PIT EXIT OPEN"
    assert events.loc[0, "lap"] == 1


def test_weather_observations_keep_session_time_separate_from_laps() -> None:
    weather = pd.DataFrame(
        {
            "Time": [pd.to_timedelta(30, unit="s")],
            "AirTemp": [30.0],
            "Humidity": [68.0],
            "Pressure": [1008.0],
            "Rainfall": [False],
            "TrackTemp": [38.3],
            "WindDirection": [106],
            "WindSpeed": [0.8],
        }
    )

    observations = build_weather_observations(weather, get_benchmark("singapore-2023"))

    assert observations.loc[0, "observation_seconds"] == 30.0
    assert not observations.loc[0, "rainfall"]
