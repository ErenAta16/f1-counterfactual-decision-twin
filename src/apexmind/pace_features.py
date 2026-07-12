"""Turn the observed lap-state table into modelling features for pace and tyre analysis.

This module makes two deliberately narrow claims, both documented in
``docs/PACE_MODEL.md``:

1. "Green-flag" here means laps run under a normal (track-status ``1``) racing
   condition, off the in/out lap, marked accurate and not deleted by the
   provider. It is a regime filter, not a claim about inter-car spacing: the
   ingested schema has no gap-to-car-ahead field, so true clean-air pace
   (free of following-car dirty air) cannot yet be isolated from this data.
2. The modelling target is each lap's pace relative to that driver's own
   session baseline, not the raw lap time. Raw lap time is dominated by
   circuit length and layout, which would otherwise swamp the tyre signal
   when a model trained on one circuit is evaluated on another.
"""

from __future__ import annotations

import pandas as pd

GREEN_FLAG_TRACK_STATUS = "1"
MINIMUM_GREEN_FLAG_LAPS = 5
BASELINE_PERCENTILE = 0.10

COMPOUND_CATEGORIES: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")


class PaceFeatureError(ValueError):
    """Raised when lap-state data cannot support the pace-modelling contract."""


def select_green_flag_laps(state: pd.DataFrame) -> pd.DataFrame:
    """Return the subset of laps eligible for pace/tyre modelling.

    Excludes pit in/out laps, deleted laps, provider-flagged inaccurate laps,
    laps without a recorded time, and laps run outside a normal green-flag
    track status (Safety Car, VSC, red flag, and similar interruptions are
    a separate regime that this phase does not model).
    """

    if state.empty:
        raise PaceFeatureError("Lap-state table is empty.")

    mask = (
        (state["track_status"] == GREEN_FLAG_TRACK_STATUS)
        & (~state["is_pit_in_lap"])
        & (~state["is_pit_out_lap"])
        & (state["is_accurate"].fillna(False))
        & (~state["is_deleted"].fillna(False))
        & state["lap_time_seconds"].notna()
        & state["tyre_life"].notna()
        & state["compound"].notna()
    )
    return state.loc[mask].copy()


def add_pace_delta(green_flag_laps: pd.DataFrame) -> pd.DataFrame:
    """Add a ``pace_delta_seconds`` column relative to each driver's session baseline.

    The baseline is the 10th percentile of a driver's own green-flag lap times
    in that session: a robust proxy for their near-best pace that is far less
    sensitive to a couple of unusually fast or slow laps than the minimum or
    the mean. A driver with fewer than ``MINIMUM_GREEN_FLAG_LAPS`` green-flag
    laps in a session is dropped; a percentile computed from a handful of
    laps is not a trustworthy reference point.

    This delta still mixes tyre degradation with fuel burn-off, since both
    correlate with lap number and the source data carries no fuel-load
    signal. ``docs/PACE_MODEL.md`` records this as an open limitation rather
    than an implicit assumption.
    """

    grouped = green_flag_laps.groupby(["benchmark_id", "session_name", "driver"])
    counts = grouped["lap_time_seconds"].transform("count")
    eligible = green_flag_laps.loc[counts >= MINIMUM_GREEN_FLAG_LAPS].copy()
    if eligible.empty:
        raise PaceFeatureError(
            f"No driver has at least {MINIMUM_GREEN_FLAG_LAPS} green-flag laps; "
            "cannot establish a pace baseline."
        )
    baseline = eligible.groupby(["benchmark_id", "session_name", "driver"])[
        "lap_time_seconds"
    ].transform(lambda values: values.quantile(BASELINE_PERCENTILE))
    eligible["pace_baseline_seconds"] = baseline
    eligible["pace_delta_seconds"] = eligible["lap_time_seconds"] - baseline
    return eligible


def build_pace_design_matrix(
    laps_with_delta: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, tuple[str, ...]]:
    """Build a compound-partitioned design matrix for the Bayesian pace model.

    Each compound in ``COMPOUND_CATEGORIES`` gets its own intercept-style
    indicator column and its own tyre-life slope column. This lets the model
    learn a separate degradation curve per compound while a shared,
    weakly-informative prior shrinks compounds with little or no supporting
    data (for example WET in a mostly dry benchmark set) back toward "no
    offset, no degradation" instead of extrapolating from nothing.
    """

    if laps_with_delta.empty:
        raise PaceFeatureError("Cannot build a design matrix from an empty table.")

    feature_columns: dict[str, pd.Series] = {}
    for compound in COMPOUND_CATEGORIES:
        indicator = (laps_with_delta["compound"] == compound).astype(float)
        feature_columns[f"compound_{compound}"] = indicator
        feature_columns[f"tyre_life_{compound}"] = indicator * laps_with_delta["tyre_life"]

    feature_names = tuple(feature_columns.keys())
    design = pd.DataFrame(feature_columns, index=laps_with_delta.index)
    target = laps_with_delta["pace_delta_seconds"]
    return design, target, feature_names
