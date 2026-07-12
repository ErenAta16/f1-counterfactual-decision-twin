import numpy as np
import pandas as pd
import pytest

from apexmind.safety_car import (
    SafetyCarError,
    SafetyCarScenario,
    extract_safety_car_episodes,
    sample_safety_car_laps,
)


def _race_control(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["event_time"] = pd.to_datetime(frame["event_time"])
    return frame


def test_extract_pairs_deploy_and_end_messages() -> None:
    rc = _race_control(
        [
            dict(
                event_time="2023-01-01T00:00:00",
                category="SafetyCar",
                message="SAFETY CAR DEPLOYED",
                lap=10,
            ),
            dict(
                event_time="2023-01-01T00:02:00",
                category="SafetyCar",
                message="SAFETY CAR IN THIS LAP",
                lap=12,
            ),
            dict(
                event_time="2023-01-01T00:05:00",
                category="SafetyCar",
                message="VIRTUAL SAFETY CAR DEPLOYED",
                lap=30,
            ),
            dict(
                event_time="2023-01-01T00:06:00",
                category="SafetyCar",
                message="VIRTUAL SAFETY CAR ENDING",
                lap=31,
            ),
        ]
    )

    episodes = extract_safety_car_episodes(rc)

    assert len(episodes) == 2
    sc, vsc = episodes
    assert (sc.episode_type, sc.start_lap, sc.end_lap, sc.duration_laps) == ("SC", 10, 12, 3)
    assert (vsc.episode_type, vsc.start_lap, vsc.end_lap, vsc.duration_laps) == ("VSC", 30, 31, 2)


def test_extract_closes_an_unmatched_deployment_at_the_last_lap() -> None:
    rc = _race_control(
        [
            dict(
                event_time="2023-01-01T00:00:00",
                category="SafetyCar",
                message="VIRTUAL SAFETY CAR DEPLOYED",
                lap=64,
            ),
            dict(event_time="2023-01-01T00:01:00", category="Flag", message="RED FLAG", lap=64),
            dict(
                event_time="2023-01-01T00:30:00", category="Flag", message="CHEQUERED FLAG", lap=72
            ),
        ]
    )

    episodes = extract_safety_car_episodes(rc)

    assert len(episodes) == 1
    assert episodes[0].episode_type == "VSC"
    assert episodes[0].start_lap == 64
    assert episodes[0].end_lap == 72


def test_extract_returns_empty_for_a_race_with_no_incidents() -> None:
    rc = _race_control(
        [dict(event_time="2023-01-01T00:00:00", category="Flag", message="CHEQUERED FLAG", lap=57)]
    )

    assert extract_safety_car_episodes(rc) == ()


def test_extract_rejects_empty_table() -> None:
    with pytest.raises(SafetyCarError):
        extract_safety_car_episodes(
            pd.DataFrame(columns=["event_time", "category", "message", "lap"])
        )


def test_sample_safety_car_laps_is_reproducible_with_a_fixed_seed() -> None:
    scenario = SafetyCarScenario(episode_lap_probability=0.3, duration_laps_options=(3,))

    first = sample_safety_car_laps(50, scenario, np.random.default_rng(7))
    second = sample_safety_car_laps(50, scenario, np.random.default_rng(7))

    assert first == second


def test_sample_safety_car_laps_respects_total_laps_bound() -> None:
    scenario = SafetyCarScenario(episode_lap_probability=1.0, duration_laps_options=(10,))

    laps = sample_safety_car_laps(5, scenario, np.random.default_rng(0))

    assert laps
    assert max(laps) <= 5
    assert min(laps) >= 1


def test_sample_safety_car_laps_can_return_no_episode() -> None:
    scenario = SafetyCarScenario(episode_lap_probability=0.0)

    laps = sample_safety_car_laps(50, scenario, np.random.default_rng(0))

    assert laps == frozenset()


def test_sample_safety_car_laps_rejects_invalid_inputs() -> None:
    with pytest.raises(SafetyCarError):
        sample_safety_car_laps(0, SafetyCarScenario(), np.random.default_rng(0))
    with pytest.raises(SafetyCarError):
        sample_safety_car_laps(
            10, SafetyCarScenario(episode_lap_probability=1.5), np.random.default_rng(0)
        )
