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


OUTLIER_MODIFIED_Z_THRESHOLD = 3.5


def remove_pace_outliers(
    laps_with_delta: pd.DataFrame, *, threshold: float = OUTLIER_MODIFIED_Z_THRESHOLD
) -> pd.DataFrame:
    """Drop laps whose pace delta is a robust statistical outlier in its own group.

    Uses the modified z-score (Iglewicz and Hoaglin, 1993):
    ``0.6745 * (x - median) / MAD``, with the conventional threshold of 3.5,
    grouped by (benchmark, session, compound). Grouping by compound rather
    than by individual driver is deliberate: a single driver rarely has
    enough green-flag laps on one compound in one session for a stable
    median and MAD.

    This step exists because of a concrete finding, not a generic hygiene
    pass. Green-flag laps (track status "1") early in the Dutch GP 2023
    benchmark, run while the track was still drying after rain, are 5 to 40
    seconds slower than that compound's settled pace, even though FastF1's
    track-status codes have no separate "damp/evolving" state to flag them.
    Left in, they inflated that benchmark's SOFT-compound pace variance from
    roughly 1.1s to 6.7s of standard deviation and were the direct cause of
    the over-wide, uncalibrated predictive intervals in the first Phase 2
    evaluation (see ``docs/PACE_MODEL.md``). The same threshold applied to
    every other benchmark and compound in this project removes a comparably
    small share of laps (0-11%), which is why it is used here rather than a
    benchmark-specific rule.
    """

    group_columns = ["benchmark_id", "session_name", "compound"]
    grouped = laps_with_delta.groupby(group_columns)["pace_delta_seconds"]
    median = grouped.transform("median")
    absolute_deviation = (laps_with_delta["pace_delta_seconds"] - median).abs()
    mad = absolute_deviation.groupby(
        [laps_with_delta[column] for column in group_columns]
    ).transform("median")

    # A zero MAD means every lap in the group already has the same pace
    # delta; there is nothing to flag as an outlier, so those rows are kept
    # rather than divided by zero.
    modified_z = 0.6745 * (laps_with_delta["pace_delta_seconds"] - median) / mad.replace(0, pd.NA)
    keep = modified_z.abs().le(threshold).fillna(False) | mad.eq(0)
    return laps_with_delta.loc[keep].reset_index(drop=True)
