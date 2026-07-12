"""Provenance records for generated research artefacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from apexmind.benchmarks import BenchmarkRace


def write_manifest(
    path: Path,
    *,
    benchmark: BenchmarkRace,
    artifact_paths: Mapping[str, Path],
    fastf1_version: str,
    record_counts: Mapping[str, int],
) -> None:
    """Write an auditable record next to a generated replay artefact."""

    payload = {
        "artifact": "lap-state",
        "benchmark": {
            "identifier": benchmark.identifier,
            "year": benchmark.year,
            "event_name": benchmark.event_name,
            "condition_class": benchmark.condition_class,
        },
        "provider": {
            "name": "FastF1",
            "version": fastf1_version,
            "documentation": "https://docs.fastf1.dev/data_reference/index.html",
        },
        "record_counts": dict(record_counts),
        "artifact_paths": {name: str(output_path) for name, output_path in artifact_paths.items()},
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
