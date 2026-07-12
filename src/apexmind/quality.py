"""Data-quality summaries for replay artefacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from apexmind.race_state import RACE_STATE_COLUMNS


def summarize_lap_state(state: pd.DataFrame) -> dict[str, object]:
    """Return quality facts without repairing or excluding source evidence."""

    missing_counts = {
        column: int(state[column].isna().sum())
        for column in ("lap_time_seconds", "tyre_life", "position", "track_status")
    }
    return {
        "schema_columns": list(RACE_STATE_COLUMNS),
        "record_count": len(state),
        "driver_count": int(state["driver"].nunique(dropna=True)),
        "lap_number_range": {
            "minimum": float(state["lap_number"].min()),
            "maximum": float(state["lap_number"].max()),
        },
        "missing_counts": missing_counts,
        "pit_in_lap_count": int(state["is_pit_in_lap"].sum()),
        "pit_out_lap_count": int(state["is_pit_out_lap"].sum()),
        "deleted_lap_count": int(state["is_deleted"].fillna(False).sum()),
        "inaccurate_lap_count": int((~state["is_accurate"].fillna(False)).sum()),
        "track_status_values": sorted(state["track_status"].dropna().unique().tolist()),
    }


def write_quality_report(path: Path, state: pd.DataFrame) -> None:
    """Write the summary as a portable JSON record alongside a replay artefact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summarize_lap_state(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
