"""Naive pace and pit-loss baselines that a real model must beat to be worth using."""

from __future__ import annotations

import pandas as pd


class BaselineError(ValueError):
    """Raised when a baseline cannot be computed from the supplied data."""


def naive_driver_compound_baseline(train_laps: pd.DataFrame, test_laps: pd.DataFrame) -> pd.Series:
    """Predict each test lap's pace delta as the median seen for that driver and compound.

    Falls back to the compound-wide median, then the train-wide median, when
    a driver/compound combination in the test set has no matching training
    rows. This is deliberately simple: a per-driver, per-compound median with
    no tyre-age term at all. A pace model earns its complexity only if it
    beats this.
    """

    if train_laps.empty:
        raise BaselineError("Cannot build a baseline from an empty training set.")

    by_driver_compound = train_laps.groupby(["driver", "compound"])["pace_delta_seconds"].median()
    by_compound = train_laps.groupby("compound")["pace_delta_seconds"].median()
    overall = train_laps["pace_delta_seconds"].median()

    def _predict(row: pd.Series) -> float:
        key = (row["driver"], row["compound"])
        if key in by_driver_compound.index:
            return float(by_driver_compound.loc[key])
        if row["compound"] in by_compound.index:
            return float(by_compound.loc[row["compound"]])
        return float(overall)

    return test_laps.apply(_predict, axis=1)


def estimate_pit_loss(state: pd.DataFrame) -> pd.DataFrame:
    """Estimate total time lost to a pit stop, per benchmark.

    For each pit event, compares the in-lap and out-lap times against the
    driver's median green-flag lap time in that session, then reports the
    median of that excess across all pit events in a benchmark. This is a
    descriptive statistic, not a model: it does not separate pit-lane transit
    time from the driver's in/out-lap pace loss, and it is a starting
    reference for Phase 3's pit-loss model rather than a finished one.
    """

    required = {"benchmark_id", "session_name", "driver", "lap_time_seconds", "track_status"}
    missing = required.difference(state.columns)
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise BaselineError(f"Lap-state table is missing required columns: {missing_names}.")

    green_flag = state[
        (state["track_status"] == "1")
        & (~state["is_pit_in_lap"])
        & (~state["is_pit_out_lap"])
        & (state["is_accurate"].fillna(False))
        & (~state["is_deleted"].fillna(False))
        & state["lap_time_seconds"].notna()
    ]
    driver_reference = green_flag.groupby(["benchmark_id", "session_name", "driver"])[
        "lap_time_seconds"
    ].median()

    pit_laps = state[
        (state["is_pit_in_lap"] | state["is_pit_out_lap"]) & state["lap_time_seconds"].notna()
    ].copy()
    if pit_laps.empty:
        raise BaselineError("No pit in/out laps found; cannot estimate pit loss.")

    def _excess(row: pd.Series) -> float | None:
        key = (row["benchmark_id"], row["session_name"], row["driver"])
        reference = driver_reference.get(key)
        if reference is None:
            return None
        return float(row["lap_time_seconds"] - reference)

    pit_laps["excess_seconds"] = pit_laps.apply(_excess, axis=1)
    pit_laps = pit_laps.dropna(subset=["excess_seconds"])

    summary = (
        pit_laps.groupby("benchmark_id")
        .agg(
            pit_event_lap_count=("excess_seconds", "count"),
            median_excess_seconds_per_lap=("excess_seconds", "median"),
        )
        .reset_index()
    )
    # A pit event contributes one in-lap and one out-lap; the loss attributed
    # to the stop is the sum of both laps' excess over the reference pace.
    summary["estimated_pit_loss_seconds"] = summary["median_excess_seconds_per_lap"] * 2
    return summary.drop(columns="median_excess_seconds_per_lap")
