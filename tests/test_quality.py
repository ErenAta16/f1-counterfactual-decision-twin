from apexmind.benchmarks import get_benchmark
from apexmind.quality import summarize_lap_state
from apexmind.race_state import build_lap_state
from tests.test_race_state import _laps


def test_quality_summary_reports_missing_and_observed_context() -> None:
    state = build_lap_state(_laps(), get_benchmark("bahrain-2024"))

    summary = summarize_lap_state(state)

    assert summary["record_count"] == 2
    assert summary["driver_count"] == 1
    assert summary["pit_out_lap_count"] == 1
    assert summary["missing_counts"]["lap_time_seconds"] == 0
    assert summary["track_status_values"] == ["1"]
