import pandas as pd
import pytest

from apexmind.pace_features import (
    PaceFeatureError,
    add_pace_delta,
    build_pace_design_matrix,
    select_green_flag_laps,
)


def _state() -> pd.DataFrame:
    # Driver AAA: 6 green-flag laps (eligible), one pit-out lap (excluded),
    # one inaccurate lap (excluded). Driver BBB: only 2 green-flag laps
    # (below the minimum, excluded from the pace-delta baseline).
    rows = []
    for lap in range(1, 7):
        rows.append(
            dict(
                benchmark_id="bahrain-2024",
                session_name="Race",
                driver="AAA",
                track_status="1",
                is_pit_in_lap=False,
                is_pit_out_lap=False,
                is_accurate=True,
                is_deleted=False,
                lap_time_seconds=90.0 + lap * 0.1,
                tyre_life=float(lap),
                compound="SOFT",
            )
        )
    rows.append(
        dict(
            benchmark_id="bahrain-2024",
            session_name="Race",
            driver="AAA",
            track_status="1",
            is_pit_in_lap=True,
            is_pit_out_lap=False,
            is_accurate=True,
            is_deleted=False,
            lap_time_seconds=115.0,
            tyre_life=7.0,
            compound="SOFT",
        )
    )
    rows.append(
        dict(
            benchmark_id="bahrain-2024",
            session_name="Race",
            driver="AAA",
            track_status="1",
            is_pit_in_lap=False,
            is_pit_out_lap=False,
            is_accurate=False,
            is_deleted=False,
            lap_time_seconds=99.0,
            tyre_life=8.0,
            compound="SOFT",
        )
    )
    for lap in range(1, 3):
        rows.append(
            dict(
                benchmark_id="bahrain-2024",
                session_name="Race",
                driver="BBB",
                track_status="1",
                is_pit_in_lap=False,
                is_pit_out_lap=False,
                is_accurate=True,
                is_deleted=False,
                lap_time_seconds=91.0 + lap * 0.1,
                tyre_life=float(lap),
                compound="HARD",
            )
        )
    return pd.DataFrame(rows)


def test_select_green_flag_laps_excludes_pit_and_inaccurate_laps() -> None:
    green = select_green_flag_laps(_state())

    assert len(green) == 8  # 6 AAA + 2 BBB; pit-in and inaccurate laps dropped
    assert not green["is_pit_in_lap"].any()
    assert green["is_accurate"].all()


def test_add_pace_delta_drops_drivers_below_minimum_laps() -> None:
    green = select_green_flag_laps(_state())

    with_delta = add_pace_delta(green)

    assert set(with_delta["driver"].unique()) == {"AAA"}
    assert "pace_baseline_seconds" in with_delta.columns
    assert with_delta["pace_delta_seconds"].abs().max() < 1.0


def test_add_pace_delta_requires_some_eligible_driver() -> None:
    green = select_green_flag_laps(_state())
    only_bbb = green[green["driver"] == "BBB"]

    with pytest.raises(PaceFeatureError):
        add_pace_delta(only_bbb)


def test_build_pace_design_matrix_partitions_by_compound() -> None:
    green = select_green_flag_laps(_state())
    with_delta = add_pace_delta(green)

    design, target, feature_names = build_pace_design_matrix(with_delta)

    assert len(feature_names) == 10  # 5 compounds x (indicator, tyre-life slope)
    assert design["compound_SOFT"].sum() == len(with_delta)
    assert design["compound_HARD"].sum() == 0
    assert (design["tyre_life_SOFT"] == with_delta["tyre_life"].to_numpy()).all()
    assert len(target) == len(with_delta)
