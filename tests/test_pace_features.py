import numpy as np
import pandas as pd
import pytest

from apexmind.pace_features import (
    PaceFeatureError,
    add_pace_delta,
    add_race_progress,
    build_pace_design_matrix,
    exclude_safety_car_restart_laps,
    remove_pace_outliers,
    select_green_flag_laps,
)
from apexmind.pace_model import fit_bayesian_pace_model


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
                lap_number=lap,
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
            lap_number=7,
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
            lap_number=8,
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
                lap_number=lap,
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


def test_add_race_progress_is_lap_number_over_session_total() -> None:
    green = select_green_flag_laps(_state())

    with_progress = add_race_progress(green, session_total_laps=10)

    assert (with_progress["race_progress"] == with_progress["lap_number"] / 10).all()


def test_add_race_progress_rejects_nonpositive_total_laps() -> None:
    green = select_green_flag_laps(_state())

    with pytest.raises(PaceFeatureError):
        add_race_progress(green, session_total_laps=0)


def test_build_pace_design_matrix_partitions_by_compound() -> None:
    green = select_green_flag_laps(_state())
    with_delta = add_race_progress(add_pace_delta(green), session_total_laps=8)

    design, target, feature_names = build_pace_design_matrix(with_delta)

    # 5 compounds x (indicator, tyre-life slope, race-progress slope)
    assert len(feature_names) == 15
    assert design["compound_SOFT"].sum() == len(with_delta)
    assert design["compound_HARD"].sum() == 0
    assert (design["tyre_life_SOFT"] == with_delta["tyre_life"].to_numpy()).all()
    assert (design["race_progress_SOFT"] == with_delta["lap_number"].to_numpy() / 8).all()
    assert (design["race_progress_HARD"] == 0).all()  # no HARD laps in this fixture
    assert len(target) == len(with_delta)


def test_build_pace_design_matrix_requires_race_progress_column() -> None:
    green = select_green_flag_laps(_state())
    with_delta = add_pace_delta(green)  # no add_race_progress call

    with pytest.raises(PaceFeatureError):
        build_pace_design_matrix(with_delta)


def _laps_with_one_outlier() -> pd.DataFrame:
    rows = []
    for driver, base in (("AAA", 90.0), ("BBB", 90.2), ("CCC", 89.8)):
        for lap in range(1, 9):
            rows.append(
                dict(
                    benchmark_id="bahrain-2024",
                    session_name="Race",
                    driver=driver,
                    track_status="1",
                    is_pit_in_lap=False,
                    is_pit_out_lap=False,
                    is_accurate=True,
                    is_deleted=False,
                    lap_time_seconds=base + (lap % 3) * 0.05,
                    tyre_life=float(lap),
                    compound="SOFT",
                )
            )
    # One lap far outside the settled pace, e.g. a damp-track lap that
    # nonetheless carries a green track-status flag.
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
            lap_time_seconds=130.0,
            tyre_life=9.0,
            compound="SOFT",
        )
    )
    return pd.DataFrame(rows)


def test_remove_pace_outliers_drops_extreme_lap_but_keeps_settled_pace() -> None:
    with_delta = add_pace_delta(select_green_flag_laps(_laps_with_one_outlier()))

    filtered = remove_pace_outliers(with_delta)

    assert len(filtered) == len(with_delta) - 1
    assert filtered["pace_delta_seconds"].max() < 5.0
    assert "compound" in filtered.columns
    assert "benchmark_id" in filtered.columns


def test_remove_pace_outliers_keeps_identical_laps_when_mad_is_zero() -> None:
    identical = pd.DataFrame(
        {
            "benchmark_id": ["bahrain-2024"] * 5,
            "session_name": ["Race"] * 5,
            "driver": ["AAA"] * 5,
            "compound": ["SOFT"] * 5,
            "pace_delta_seconds": [1.0, 1.0, 1.0, 1.0, 1.0],
        }
    )

    filtered = remove_pace_outliers(identical)

    assert len(filtered) == 5


def test_race_progress_separates_fuel_effect_from_tyre_wear() -> None:
    # Reproduces, on synthetic data with a known answer, the exact failure
    # found during Phase 4 development (docs/DECISION_ENGINE.md): a pure
    # fuel-burn effect (pace improves as the race goes on, independent of
    # tyre age) gets misattributed to a spuriously negative tyre-life
    # coefficient when race_progress is absent from the design, because
    # both correlate with lap number. Many stints starting at different,
    # randomised points in the race -- as real strategies do -- give the
    # pooled sample enough variation in "tyre life vs. how far into the
    # race" to identify the two effects separately once race_progress is
    # included as its own column.
    rng = np.random.default_rng(3)
    total_laps = 60
    stint_length = 12
    true_fuel_effect = -3.0  # seconds faster at race end than race start
    true_tyre_effect = 0.0  # no real degradation in this synthetic world

    rows = []
    for _ in range(40):
        stint_start = int(rng.integers(1, total_laps - stint_length + 1))
        for offset in range(stint_length):
            lap_number = stint_start + offset
            tyre_life = float(offset + 1)
            race_progress = lap_number / total_laps
            pace_delta = (
                true_fuel_effect * race_progress
                + true_tyre_effect * tyre_life
                + rng.normal(scale=0.05)
            )
            rows.append(
                {
                    "compound": "SOFT",
                    "tyre_life": tyre_life,
                    "lap_number": lap_number,
                    "pace_delta_seconds": pace_delta,
                }
            )
    laps = pd.DataFrame(rows)

    with_progress = add_race_progress(laps, session_total_laps=total_laps)
    design_with, target, _ = build_pace_design_matrix(with_progress)
    posterior_with = fit_bayesian_pace_model(design_with, target)

    # The old feature layout, to show the failure this test is named for
    # actually occurs on this data rather than being a hypothetical.
    race_progress_columns = [c for c in design_with.columns if c.startswith("race_progress_")]
    design_without = design_with.drop(columns=race_progress_columns)
    posterior_without = fit_bayesian_pace_model(design_without, target)

    coeffs_with = dict(
        zip(posterior_with.feature_names, posterior_with.coefficient_mean, strict=True)
    )
    coeffs_without = dict(
        zip(posterior_without.feature_names, posterior_without.coefficient_mean, strict=True)
    )

    # Without the fuel term, the tyre-life coefficient absorbs the fuel
    # effect and comes out spuriously negative -- the real bug, reproduced.
    assert coeffs_without["tyre_life_SOFT"] < -0.03

    # With it, the tyre-life coefficient is recovered close to its true
    # value of zero, and the fuel effect is recovered close to -3.0.
    assert coeffs_with["tyre_life_SOFT"] == pytest.approx(true_tyre_effect, abs=0.05)
    assert coeffs_with["race_progress_SOFT"] == pytest.approx(true_fuel_effect, abs=0.3)


def test_race_progress_does_not_leak_across_compounds_with_no_shared_evidence() -> None:
    # A second real bug found while validating the first fix, on real data
    # (docs/PACE_MODEL.md): a single *shared* race_progress term, estimated
    # only from dry-compound laps in two races with zero INTERMEDIATE laps
    # between them, was applied without shrinkage to INTERMEDIATE laps in
    # the third race's evaluation -- producing a large, confidently wrong
    # fuel-effect prediction for a compound the term was never fit on. A
    # per-compound race_progress column should behave like every other
    # per-compound term here: a compound with zero supporting laps shrinks
    # its fuel effect back toward the prior's zero rather than inheriting
    # another compound's slope.
    rng = np.random.default_rng(5)
    n = 300
    total_laps = 50
    lap_number = rng.integers(1, total_laps + 1, size=n)
    race_progress = lap_number / total_laps
    tyre_life = rng.integers(1, 20, size=n).astype(float)
    pace_delta = -4.0 * race_progress + rng.normal(scale=0.05, size=n)
    laps = pd.DataFrame(
        {
            "compound": ["SOFT"] * n,  # HARD never appears in this training set at all
            "tyre_life": tyre_life,
            "lap_number": lap_number,
            "pace_delta_seconds": pace_delta,
        }
    )

    with_progress = add_race_progress(laps, session_total_laps=total_laps)
    design, target, _ = build_pace_design_matrix(with_progress)
    posterior = fit_bayesian_pace_model(design, target)
    coeffs = dict(zip(posterior.feature_names, posterior.coefficient_mean, strict=True))

    assert coeffs["race_progress_SOFT"] == pytest.approx(-4.0, abs=0.3)
    assert coeffs["race_progress_HARD"] == pytest.approx(0.0, abs=0.2)


def _race_control(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["event_time"] = pd.to_datetime(frame["event_time"])
    return frame


def test_exclude_safety_car_restart_laps_drops_only_the_sc_restart_lap() -> None:
    # Real finding (docs/PACE_MODEL.md): the lap right after a Safety Car
    # peels off is green-flagged but not settled racing pace, because the
    # whole field is still bunched up from the rolling restart. A VSC
    # ending has no equivalent physical bunching, so it must not be
    # touched by this filter.
    green = pd.DataFrame(
        {
            "lap_number": [21, 22, 23, 24, 44, 45, 46],
            "compound": ["SOFT"] * 7,
            "tyre_life": [1, 2, 3, 4, 24, 25, 26],
        }
    )
    rc = _race_control(
        [
            dict(
                event_time="2023-01-01T00:00:00",
                category="SafetyCar",
                message="SAFETY CAR DEPLOYED",
                lap=19,
            ),
            dict(
                event_time="2023-01-01T00:02:00",
                category="SafetyCar",
                message="SAFETY CAR IN THIS LAP",
                lap=22,
            ),
            dict(
                event_time="2023-01-01T00:10:00",
                category="SafetyCar",
                message="VIRTUAL SAFETY CAR DEPLOYED",
                lap=44,
            ),
            dict(
                event_time="2023-01-01T00:11:00",
                category="SafetyCar",
                message="VIRTUAL SAFETY CAR ENDING",
                lap=45,
            ),
        ]
    )

    filtered = exclude_safety_car_restart_laps(green, rc)

    # Lap 23 (right after the SC ends on lap 22) is dropped; lap 46 (right
    # after the VSC ends on lap 45) is kept.
    assert sorted(filtered["lap_number"]) == [21, 22, 24, 44, 45, 46]


def _simple_green(lap_numbers: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "lap_number": lap_numbers,
            "compound": ["SOFT"] * len(lap_numbers),
            "tyre_life": list(range(1, len(lap_numbers) + 1)),
        }
    )


def test_exclude_safety_car_restart_laps_is_a_no_op_with_no_episodes() -> None:
    rc = _race_control(
        [
            dict(
                event_time="2024-01-01T00:00:00",
                category="Other",
                message="CHEQUERED FLAG",
                lap=57,
            ),
        ]
    )

    filtered = exclude_safety_car_restart_laps(_simple_green([1, 2, 3]), rc)

    assert sorted(filtered["lap_number"]) == [1, 2, 3]


def test_exclude_safety_car_restart_laps_handles_empty_race_control() -> None:
    empty_rc = pd.DataFrame(columns=["event_time", "category", "message", "lap"])

    filtered = exclude_safety_car_restart_laps(_simple_green([1, 2, 3]), empty_rc)

    assert sorted(filtered["lap_number"]) == [1, 2, 3]
