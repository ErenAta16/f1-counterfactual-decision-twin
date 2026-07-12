"""Command-line entry points for reproducible data-fidelity and evaluation work."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from apexmind.baselines import estimate_pit_loss, naive_driver_compound_baseline
from apexmind.benchmarks import BENCHMARK_RACES, get_benchmark
from apexmind.context import build_race_control_events, build_weather_observations
from apexmind.evaluation import (
    gaussian_crps,
    interval_coverage,
    mean_absolute_error,
    root_mean_squared_error,
    temporal_holdout_split,
    write_calibration_report,
)
from apexmind.fastf1_source import load_race
from apexmind.manifest import write_manifest
from apexmind.pace_features import (
    add_pace_delta,
    build_pace_design_matrix,
    remove_pace_outliers,
    select_green_flag_laps,
)
from apexmind.pace_model import fit_bayesian_pace_model, predict
from apexmind.paths import DataPaths, default_data_root
from apexmind.quality import write_quality_report
from apexmind.race_state import build_lap_state, validate_lap_state

# The 2023 races are the training history; the 2024 race is the unseen
# "future" hold-out. See docs/PACE_MODEL.md for the rationale.
DEFAULT_HOLDOUT_BENCHMARK = "bahrain-2024"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ApexMind data-fidelity and evaluation tools")
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

    evaluate = subparsers.add_parser(
        "evaluate", help="fit the Phase 2 pace model and report calibration against a hold-out race"
    )
    evaluate.add_argument(
        "--holdout",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark race to hold out as the test set (default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    evaluate.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root containing previously ingested lap-state artefacts",
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


def _load_lap_state(paths: DataPaths, benchmark_id: str) -> pd.DataFrame:
    lap_state_path = paths.processed / f"{benchmark_id}-lap-state.parquet"
    if not lap_state_path.exists():
        raise SystemExit(
            f"No ingested lap-state file for '{benchmark_id}' at {lap_state_path}. "
            "Run 'apexmind ingest' first."
        )
    return pd.read_parquet(lap_state_path)


def _evaluate(holdout_benchmark_id: str, data_dir: Path) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    all_states = {
        benchmark.identifier: _load_lap_state(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    full_state = pd.concat(all_states.values(), ignore_index=True)
    pit_loss = estimate_pit_loss(full_state)
    print("Naive pit-loss estimate per benchmark (descriptive, not yet a model):")
    print(pit_loss.to_string(index=False))

    laps_with_delta = {
        benchmark_id: remove_pace_outliers(add_pace_delta(select_green_flag_laps(state)))
        for benchmark_id, state in all_states.items()
    }
    train_laps, test_laps = temporal_holdout_split(
        laps_with_delta, holdout_benchmark_id=holdout_benchmark_id
    )
    train_benchmark_ids = tuple(sorted(set(train_laps["benchmark_id"])))

    train_design, train_target, _ = build_pace_design_matrix(train_laps)
    test_design, test_target, _ = build_pace_design_matrix(test_laps)

    posterior = fit_bayesian_pace_model(train_design, train_target)
    model_mean, model_variance = predict(posterior, test_design)

    baseline_pred = naive_driver_compound_baseline(train_laps, test_laps).to_numpy()

    baseline_metrics = {
        "mae": mean_absolute_error(test_target.to_numpy(), baseline_pred),
        "rmse": root_mean_squared_error(test_target.to_numpy(), baseline_pred),
    }
    model_metrics = {
        "mae": mean_absolute_error(test_target.to_numpy(), model_mean),
        "rmse": root_mean_squared_error(test_target.to_numpy(), model_mean),
        "crps": gaussian_crps(test_target.to_numpy(), model_mean, model_variance),
    }
    coverage = {
        f"{int(level * 100)}pct": interval_coverage(
            test_target.to_numpy(), model_mean, model_variance, confidence=level
        )
        for level in (0.5, 0.8, 0.95)
    }

    report_path = paths.evaluation_reports / f"pace-model-holdout-{holdout_benchmark_id}.json"
    write_calibration_report(
        report_path,
        holdout_benchmark_id=holdout_benchmark_id,
        train_benchmark_ids=train_benchmark_ids,
        train_row_count=len(train_laps),
        test_row_count=len(test_laps),
        baseline_metrics=baseline_metrics,
        model_metrics=model_metrics,
        coverage=coverage,
    )

    print(
        f"\nTemporal hold-out: trained on {train_benchmark_ids}, "
        f"tested on '{holdout_benchmark_id}'."
    )
    print(f"Baseline MAE={baseline_metrics['mae']:.3f}s RMSE={baseline_metrics['rmse']:.3f}s")
    print(
        f"Model    MAE={model_metrics['mae']:.3f}s RMSE={model_metrics['rmse']:.3f}s "
        f"CRPS={model_metrics['crps']:.3f}s"
    )
    print(f"Coverage (nominal -> observed): {coverage}")
    print(f"Report written to {report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ApexMind command-line interface."""

    args = _parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.benchmark, args.data_dir)
    if args.command == "evaluate":
        return _evaluate(args.holdout, args.data_dir)
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
