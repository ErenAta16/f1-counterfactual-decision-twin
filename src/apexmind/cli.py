"""Command-line entry points for reproducible data-fidelity work."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from apexmind.benchmarks import BENCHMARK_RACES, get_benchmark
from apexmind.context import build_race_control_events, build_weather_observations
from apexmind.fastf1_source import load_race
from apexmind.manifest import write_manifest
from apexmind.paths import DataPaths, default_data_root
from apexmind.quality import write_quality_report
from apexmind.race_state import build_lap_state, validate_lap_state


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ApexMind data-fidelity tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest = subparsers.add_parser("ingest", help="create normalised lap-state artefacts")
    ingest.add_argument(
        "--benchmark",
        choices=["all", *(benchmark.identifier for benchmark in BENCHMARK_RACES)],
        default="all",
        help="benchmark race to ingest (default: all)",
    )
    ingest.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root for cache and generated data",
    )
    return parser


def _selected_benchmarks(identifier: str):
    if identifier == "all":
        return BENCHMARK_RACES
    return (get_benchmark(identifier),)


def _ingest(benchmark_id: str, data_dir: Path) -> int:
    import fastf1

    paths = DataPaths.from_root(data_dir)
    paths.create()
    for benchmark in _selected_benchmarks(benchmark_id):
        session = load_race(benchmark, paths)
        state = build_lap_state(session.laps, benchmark, session_name=session.name)
        validate_lap_state(state)
        race_control = build_race_control_events(session.race_control_messages, benchmark)
        weather = build_weather_observations(session.weather_data, benchmark)

        lap_state_path = paths.processed / f"{benchmark.identifier}-lap-state.parquet"
        race_control_path = paths.processed / f"{benchmark.identifier}-race-control.parquet"
        weather_path = paths.processed / f"{benchmark.identifier}-weather.parquet"
        state.to_parquet(lap_state_path, index=False)
        race_control.to_parquet(race_control_path, index=False)
        weather.to_parquet(weather_path, index=False)
        quality_path = paths.quality_reports / f"{benchmark.identifier}-lap-state.json"
        write_quality_report(quality_path, state)
        write_manifest(
            paths.manifests / f"{benchmark.identifier}-lap-state.json",
            benchmark=benchmark,
            artifact_paths={
                "lap_state": lap_state_path,
                "race_control": race_control_path,
                "weather": weather_path,
                "quality_report": quality_path,
            },
            fastf1_version=fastf1.__version__,
            record_counts={
                "lap_state": len(state),
                "race_control": len(race_control),
                "weather": len(weather),
            },
        )
        print(
            f"Wrote {len(state)} lap-state, {len(race_control)} race-control, "
            f"and {len(weather)} weather rows for {benchmark.identifier}."
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ApexMind command-line interface."""

    args = _parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.benchmark, args.data_dir)
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
