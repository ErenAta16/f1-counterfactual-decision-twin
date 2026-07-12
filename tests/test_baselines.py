import pandas as pd
import pytest

from apexmind.baselines import BaselineError, estimate_pit_loss, naive_driver_compound_baseline


def test_naive_driver_compound_baseline_uses_median_with_fallback() -> None:
    train = pd.DataFrame(
        {
            "driver": ["AAA", "AAA", "AAA", "BBB"],
            "compound": ["SOFT", "SOFT", "HARD", "HARD"],
            "pace_delta_seconds": [1.0, 3.0, 5.0, 2.0],
        }
    )
    test = pd.DataFrame(
        {
            "driver": ["AAA", "AAA", "CCC"],
            "compound": ["SOFT", "HARD", "HARD"],
        }
    )

    predictions = naive_driver_compound_baseline(train, test)

    assert predictions.iloc[0] == 2.0  # median(1.0, 3.0) for AAA/SOFT
    assert predictions.iloc[1] == 5.0  # only one AAA/HARD row
    assert predictions.iloc[2] == 3.5  # compound-wide median for HARD (5.0, 2.0), unseen driver


def test_naive_driver_compound_baseline_rejects_empty_training_set() -> None:
    with pytest.raises(BaselineError):
        naive_driver_compound_baseline(pd.DataFrame(), pd.DataFrame({"driver": [], "compound": []}))


def _pit_state() -> pd.DataFrame:
    rows = [
        # Green-flag reference laps for AAA: median ~90.0
        *[
            dict(
                benchmark_id="bahrain-2024",
                session_name="Race",
                driver="AAA",
                track_status="1",
                is_pit_in_lap=False,
                is_pit_out_lap=False,
                is_accurate=True,
                is_deleted=False,
                lap_time_seconds=90.0,
            )
            for _ in range(5)
        ],
        dict(
            benchmark_id="bahrain-2024",
            session_name="Race",
            driver="AAA",
            track_status="1",
            is_pit_in_lap=True,
            is_pit_out_lap=False,
            is_accurate=True,
            is_deleted=False,
            lap_time_seconds=110.0,
        ),
        dict(
            benchmark_id="bahrain-2024",
            session_name="Race",
            driver="AAA",
            track_status="1",
            is_pit_in_lap=False,
            is_pit_out_lap=True,
            is_accurate=True,
            is_deleted=False,
            lap_time_seconds=112.0,
        ),
    ]
    return pd.DataFrame(rows)


def test_estimate_pit_loss_reports_excess_over_reference_pace() -> None:
    summary = estimate_pit_loss(_pit_state())

    assert summary.loc[0, "benchmark_id"] == "bahrain-2024"
    assert summary.loc[0, "pit_event_lap_count"] == 2
    # (110-90) and (112-90) -> median excess 21, doubled for the full stop
    assert summary.loc[0, "estimated_pit_loss_seconds"] == pytest.approx(42.0)


def test_estimate_pit_loss_requires_pit_laps() -> None:
    no_pit = _pit_state()
    no_pit = no_pit[~(no_pit["is_pit_in_lap"] | no_pit["is_pit_out_lap"])]

    with pytest.raises(BaselineError):
        estimate_pit_loss(no_pit)
