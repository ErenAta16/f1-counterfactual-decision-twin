"""Command-line entry points for reproducible data-fidelity and evaluation work."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from apexmind.baselines import estimate_pit_loss, naive_driver_compound_baseline
from apexmind.benchmarks import BENCHMARK_RACES, get_benchmark
from apexmind.context import build_race_control_events, build_weather_observations
from apexmind.decision_engine import SEARCH_COMPOUNDS, optimise_strategies
from apexmind.evaluation import (
    gaussian_crps,
    interval_coverage,
    mean_absolute_error,
    metrics_by_compound_class,
    paired_mean_difference_ci,
    root_mean_squared_error,
    temporal_holdout_split,
    write_calibration_report,
)
from apexmind.evidence_interface import (
    CohereClient,
    assess_explanation_coverage,
    build_decision_evidence,
    generate_explanation,
    load_cohere_api_key,
)
from apexmind.fastf1_source import load_race
from apexmind.manifest import write_manifest
from apexmind.pace_features import (
    add_pace_delta,
    add_race_progress,
    build_pace_design_matrix,
    exclude_safety_car_restart_laps,
    remove_pace_outliers,
    select_green_flag_laps,
)
from apexmind.pace_model import fit_bayesian_pace_model, predict
from apexmind.paths import DataPaths, default_data_root
from apexmind.quality import write_quality_report
from apexmind.race_state import build_lap_state, validate_lap_state
from apexmind.regulations import TYRE_COMPOUND_RULE, is_legal_strategy
from apexmind.replay import build_replay_html, stints_to_segments
from apexmind.safety_car import SafetyCarScenario, extract_safety_car_episodes
from apexmind.simulator import Stint, StrategyPlan, run_monte_carlo, summarize_simulations

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

    simulate = subparsers.add_parser(
        "simulate",
        help="run a Monte Carlo comparison of example candidate strategies for one benchmark",
    )
    simulate.add_argument(
        "--reference-benchmark",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark whose lap count, pace baseline, and pit loss anchor the simulated race "
        f"(default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    simulate.add_argument(
        "--n-simulations",
        type=int,
        default=2000,
        help="number of Monte Carlo draws per strategy (default: 2000)",
    )
    simulate.add_argument(
        "--seed", type=int, default=0, help="random seed for reproducibility (default: 0)"
    )
    simulate.add_argument(
        "--no-safety-car",
        action="store_true",
        help="disable the declared Safety Car scenario and simulate green-flag conditions only",
    )
    simulate.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root containing previously ingested lap-state artefacts",
    )

    decide = subparsers.add_parser(
        "decide",
        help="search legal candidate strategies and compare the best one to fixed baselines",
    )
    decide.add_argument(
        "--reference-benchmark",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark whose lap count, pace baseline, and pit loss anchor the search "
        f"(default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    decide.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="number of distinct legal candidates the optimiser reports (default: 3)",
    )
    decide.add_argument(
        "--n-simulations",
        type=int,
        default=2000,
        help="number of Monte Carlo draws per strategy for the comparison stage (default: 2000)",
    )
    decide.add_argument(
        "--seed", type=int, default=0, help="random seed for reproducibility (default: 0)"
    )
    decide.add_argument(
        "--no-safety-car",
        action="store_true",
        help="disable the declared Safety Car scenario in the comparison stage",
    )
    decide.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root containing previously ingested lap-state artefacts",
    )

    explain = subparsers.add_parser(
        "explain",
        help="generate a cited, evidence-grounded explanation of a 'decide' report",
    )
    explain.add_argument(
        "--reference-benchmark",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark whose decision report to explain (default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    explain.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root containing a previously written decision report",
    )

    replay = subparsers.add_parser(
        "replay",
        help="render a single-file HTML replay: real track status, chosen strategy, and evidence",
    )
    replay.add_argument(
        "--reference-benchmark",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark to render (default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    replay.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_root(),
        help="local, untracked root containing previously written decision/explanation reports",
    )

    plot = subparsers.add_parser(
        "plot",
        help="render tyre-degradation, calibration-reliability, and Monte Carlo PNGs "
        "(requires the 'viz' extra)",
    )
    plot.add_argument(
        "--reference-benchmark",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help="benchmark for the tyre-degradation and Monte Carlo charts "
        f"(default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    plot.add_argument(
        "--holdout",
        choices=[benchmark.identifier for benchmark in BENCHMARK_RACES],
        default=DEFAULT_HOLDOUT_BENCHMARK,
        help=f"benchmark held out for the calibration chart (default: {DEFAULT_HOLDOUT_BENCHMARK})",
    )
    plot.add_argument(
        "--n-simulations",
        type=int,
        default=2000,
        help="number of Monte Carlo draws per strategy for the outcomes chart (default: 2000)",
    )
    plot.add_argument(
        "--seed", type=int, default=0, help="random seed for reproducibility (default: 0)"
    )
    plot.add_argument(
        "--no-safety-car",
        action="store_true",
        help="disable the declared Safety Car scenario in the Monte Carlo outcomes chart",
    )
    plot.add_argument(
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


def _load_race_control(paths: DataPaths, benchmark_id: str) -> pd.DataFrame:
    race_control_path = paths.processed / f"{benchmark_id}-race-control.parquet"
    if not race_control_path.exists():
        raise SystemExit(
            f"No ingested race-control file for '{benchmark_id}' at {race_control_path}. "
            "Run 'apexmind ingest' first."
        )
    return pd.read_parquet(race_control_path)


def _evaluate(holdout_benchmark_id: str, data_dir: Path) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    all_states = {
        benchmark.identifier: _load_lap_state(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    all_race_control = {
        benchmark.identifier: _load_race_control(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    full_state = pd.concat(all_states.values(), ignore_index=True)
    pit_loss = estimate_pit_loss(full_state)
    print("Naive pit-loss estimate per benchmark (descriptive, not yet a model):")
    print(pit_loss.to_string(index=False))

    laps_with_delta = {
        benchmark_id: remove_pace_outliers(
            add_race_progress(
                add_pace_delta(
                    exclude_safety_car_restart_laps(
                        select_green_flag_laps(state), all_race_control[benchmark_id]
                    )
                ),
                session_total_laps=int(state["lap_number"].max()),
            )
        )
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
    baseline_by_class = metrics_by_compound_class(
        test_laps["compound"], test_target.to_numpy(), baseline_pred
    )
    model_by_class = metrics_by_compound_class(
        test_laps["compound"], test_target.to_numpy(), model_mean
    )

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
        baseline_metrics_by_compound_class=baseline_by_class,
        model_metrics_by_compound_class=model_by_class,
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
    print("\nBy compound class (a pooled metric can hide a split result):")
    for class_label in sorted(set(baseline_by_class) | set(model_by_class)):
        b = baseline_by_class.get(class_label)
        m = model_by_class.get(class_label)
        if b is None or m is None:
            continue
        print(
            f"  {class_label:>20} (n={b['row_count']}): "
            f"baseline MAE={b['mae']:.3f}s RMSE={b['rmse']:.3f}s | "
            f"model MAE={m['mae']:.3f}s RMSE={m['rmse']:.3f}s"
        )
    print(f"Report written to {report_path}")
    return 0


# Two example candidate strategies for the simulate command. This is a
# deliberately small, fixed demonstration set, not a strategy generator:
# Phase 4 is where a real candidate-strategy search belongs
# (docs/PROJECT_PLAN.md, Section 6.4). Stint lengths are re-scaled to each
# reference benchmark's actual lap count at runtime.
def _example_strategies(total_laps: int) -> tuple[StrategyPlan, ...]:
    one_stop_split = total_laps // 2
    two_stop_first = total_laps // 3
    two_stop_second = total_laps // 3
    two_stop_third = total_laps - two_stop_first - two_stop_second
    return (
        StrategyPlan(
            name="1-stop (medium/hard)",
            stints=(
                Stint("MEDIUM", one_stop_split),
                Stint("HARD", total_laps - one_stop_split),
            ),
        ),
        StrategyPlan(
            name="2-stop (soft/soft/hard)",
            stints=(
                Stint("SOFT", two_stop_first),
                Stint("SOFT", two_stop_second),
                Stint("HARD", two_stop_third),
            ),
        ),
    )


class _ReferenceRaceStats(NamedTuple):
    posterior: object
    driver_baseline_seconds: float
    total_laps: int
    pit_loss_seconds: float
    max_observed_tyre_life: int


def _reference_race_stats(
    all_states: dict[str, pd.DataFrame],
    all_race_control: dict[str, pd.DataFrame],
    full_state: pd.DataFrame,
    reference_benchmark_id: str,
) -> _ReferenceRaceStats:
    """Fit the pace model on every available benchmark and derive one race's reference figures.

    Shared by `simulate` and `decide`: neither command is measuring
    generalisation the way the Phase 2 evaluation does, so there is no
    reason to hold a benchmark out here.
    """

    laps_with_delta = pd.concat(
        [
            remove_pace_outliers(
                add_race_progress(
                    add_pace_delta(
                        exclude_safety_car_restart_laps(
                            select_green_flag_laps(state), all_race_control[benchmark_id]
                        )
                    ),
                    session_total_laps=int(state["lap_number"].max()),
                )
            )
            for benchmark_id, state in all_states.items()
        ],
        ignore_index=True,
    )
    design, target, _ = build_pace_design_matrix(laps_with_delta)
    posterior = fit_bayesian_pace_model(design, target)

    reference_state = all_states[reference_benchmark_id]
    reference_laps = laps_with_delta[laps_with_delta["benchmark_id"] == reference_benchmark_id]
    driver_baseline_seconds = float(reference_laps["pace_baseline_seconds"].median())
    total_laps = int(reference_state["lap_number"].max())

    pit_loss_table = estimate_pit_loss(full_state)
    pit_loss_row = pit_loss_table.loc[pit_loss_table["benchmark_id"] == reference_benchmark_id]
    if pit_loss_row.empty:
        raise SystemExit(f"No pit-loss estimate available for '{reference_benchmark_id}'.")
    pit_loss_seconds = float(pit_loss_row["estimated_pit_loss_seconds"].iloc[0])
    max_observed_tyre_life = int(laps_with_delta["tyre_life"].max())

    return _ReferenceRaceStats(
        posterior, driver_baseline_seconds, total_laps, pit_loss_seconds, max_observed_tyre_life
    )


def _simulate(
    reference_benchmark_id: str, n_simulations: int, seed: int, use_safety_car: bool, data_dir: Path
) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    all_states = {
        benchmark.identifier: _load_lap_state(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    all_race_control = {
        benchmark.identifier: _load_race_control(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    full_state = pd.concat(all_states.values(), ignore_index=True)

    stats = _reference_race_stats(all_states, all_race_control, full_state, reference_benchmark_id)
    total_laps = stats.total_laps

    safety_car_scenario: SafetyCarScenario | None = None
    observed_episodes = extract_safety_car_episodes(
        pd.read_parquet(paths.processed / f"{reference_benchmark_id}-race-control.parquet")
    )
    if use_safety_car:
        safety_car_scenario = SafetyCarScenario()

    strategies = _example_strategies(total_laps)
    results = run_monte_carlo(
        strategies,
        stats.posterior,
        driver_baseline_seconds=stats.driver_baseline_seconds,
        pit_loss_seconds=stats.pit_loss_seconds,
        n_simulations=n_simulations,
        seed=seed,
        safety_car_scenario=safety_car_scenario,
    )
    summary = summarize_simulations(results)

    report_path = paths.simulation_reports / f"strategy-comparison-{reference_benchmark_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(summary.to_json(orient="records", indent=2) + "\n", encoding="utf-8")

    print(f"Reference benchmark: {reference_benchmark_id} ({total_laps} laps)")
    print(
        f"Driver pace baseline: {stats.driver_baseline_seconds:.3f}s/lap; "
        f"pit loss: {stats.pit_loss_seconds:.3f}s"
    )
    print(f"Observed Safety Car/VSC episodes in this race: {observed_episodes}")
    safety_car_label = "declared default" if use_safety_car else "disabled (green-flag only)"
    print(f"Safety Car scenario: {safety_car_label}")
    print(summary.to_string(index=False))
    print(f"Report written to {report_path}")
    return 0


def _decide(
    reference_benchmark_id: str,
    top_k: int,
    n_simulations: int,
    seed: int,
    use_safety_car: bool,
    data_dir: Path,
) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    all_states = {
        benchmark.identifier: _load_lap_state(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    all_race_control = {
        benchmark.identifier: _load_race_control(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    full_state = pd.concat(all_states.values(), ignore_index=True)

    stats = _reference_race_stats(all_states, all_race_control, full_state, reference_benchmark_id)
    total_laps = stats.total_laps

    candidates = optimise_strategies(
        stats.posterior,
        total_laps=total_laps,
        driver_baseline_seconds=stats.driver_baseline_seconds,
        pit_loss_seconds=stats.pit_loss_seconds,
        top_k=top_k,
        max_stint_laps=stats.max_observed_tyre_life,
    )
    chosen = candidates[0]

    baselines = _example_strategies(total_laps)
    illegal_baselines = [b.name for b in baselines if not is_legal_strategy(b)]

    safety_car_scenario = SafetyCarScenario() if use_safety_car else None
    comparison_strategies = (chosen, *baselines)
    results = run_monte_carlo(
        comparison_strategies,
        stats.posterior,
        driver_baseline_seconds=stats.driver_baseline_seconds,
        pit_loss_seconds=stats.pit_loss_seconds,
        n_simulations=n_simulations,
        seed=seed,
        safety_car_scenario=safety_car_scenario,
    )
    summary = summarize_simulations(results)

    pivoted = results.pivot(
        index="draw_index", columns="strategy_name", values="total_race_time_seconds"
    )
    comparisons = []
    for baseline in baselines:
        mean_difference, lower, upper = paired_mean_difference_ci(
            pivoted[baseline.name].to_numpy(), pivoted[chosen.name].to_numpy()
        )
        comparisons.append(
            {
                "baseline_name": baseline.name,
                "mean_advantage_seconds": mean_difference,
                "95pct_ci_lower_seconds": lower,
                "95pct_ci_upper_seconds": upper,
                "statistically_supported_advantage": lower > 0,
            }
        )

    report_path = paths.decision_reports / f"decision-{reference_benchmark_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "reference_benchmark_id": reference_benchmark_id,
        "total_laps": total_laps,
        "driver_baseline_seconds": stats.driver_baseline_seconds,
        "pit_loss_seconds": stats.pit_loss_seconds,
        "max_stint_laps": stats.max_observed_tyre_life,
        "regulation": {
            "document": TYRE_COMPOUND_RULE.document,
            "article": TYRE_COMPOUND_RULE.article,
        },
        "optimiser_candidates": [
            {
                "name": plan.name,
                "stints": [
                    {"compound": stint.compound, "lap_count": stint.lap_count}
                    for stint in plan.stints
                ],
            }
            for plan in candidates
        ],
        "chosen_strategy": chosen.name,
        "monte_carlo_summary": json.loads(summary.to_json(orient="records")),
        "comparisons_vs_baselines": comparisons,
    }
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    print(f"Reference benchmark: {reference_benchmark_id} ({total_laps} laps)")
    print(
        f"Driver pace baseline: {stats.driver_baseline_seconds:.3f}s/lap; "
        f"pit loss: {stats.pit_loss_seconds:.3f}s"
    )
    print(f"Encoded rule: {TYRE_COMPOUND_RULE.document}, Article {TYRE_COMPOUND_RULE.article}")
    if illegal_baselines:
        print(f"WARNING: baseline strategies failing the compound rule: {illegal_baselines}")
    else:
        print("All baseline strategies pass the compound rule (both use two compounds).")
    print(
        f"\nOptimiser searched dry compounds {SEARCH_COMPOUNDS} by exact dynamic programming "
        f"(max {stats.max_observed_tyre_life} laps per stint, the longest observed in training)."
    )
    print(f"Top {len(candidates)} legal candidates (expected time, posterior mean, no Safety Car):")
    for rank, plan in enumerate(candidates, start=1):
        stint_desc = ", ".join(f"{s.compound}x{s.lap_count}" for s in plan.stints)
        print(f"  {rank}. {plan.name}: {stint_desc}")
    print(f"\nMonte Carlo comparison ({n_simulations} draws, seed={seed}):")
    print(summary.to_string(index=False))
    print("\nPaired comparison vs each baseline (positive = optimiser faster, 95% CI):")
    for comparison in comparisons:
        supported = "yes" if comparison["statistically_supported_advantage"] else "no"
        lower = comparison["95pct_ci_lower_seconds"]
        upper = comparison["95pct_ci_upper_seconds"]
        print(
            f"  vs {comparison['baseline_name']}: "
            f"{comparison['mean_advantage_seconds']:+.3f}s [{lower:+.3f}, {upper:+.3f}] "
            f"statistically supported: {supported}"
        )
    print(f"Report written to {report_path}")
    return 0


QUESTION_TEMPLATE = (
    "Explain why the '{chosen_strategy}' strategy was chosen for {benchmark}. "
    "Cover: what the FIA rule requires and why the strategy is legal, the pace "
    "and Monte Carlo evidence behind the choice, how it compares to the baseline "
    "strategies, and which parts of the answer are simulated assumptions rather "
    "than observed or inferred facts. Cite the specific evidence for every claim."
)


def _explain(reference_benchmark_id: str, data_dir: Path) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    decision_report_path = paths.decision_reports / f"decision-{reference_benchmark_id}.json"
    if not decision_report_path.exists():
        raise SystemExit(
            f"No decision report for '{reference_benchmark_id}' at {decision_report_path}. "
            "Run 'apexmind decide' first."
        )
    decision_report = json.loads(decision_report_path.read_text(encoding="utf-8"))

    evidence = build_decision_evidence(decision_report)
    api_key = load_cohere_api_key()
    client = CohereClient(api_key)
    question = QUESTION_TEMPLATE.format(
        chosen_strategy=decision_report["chosen_strategy"],
        benchmark=reference_benchmark_id,
    )
    result = generate_explanation(evidence, question, client)
    missing_required = assess_explanation_coverage(evidence, result)

    report_path = paths.explanation_reports / f"explanation-{reference_benchmark_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "reference_benchmark_id": reference_benchmark_id,
        "question": question,
        "evidence": [
            {"id": item.id, "title": item.title, "evidence_class": item.evidence_class}
            for item in evidence
        ],
        "explanation": result.text,
        "citations": [
            {"text": citation.text, "evidence_ids": list(citation.evidence_ids)}
            for citation in result.citations
        ],
        "cited_evidence_ids": sorted(result.cited_evidence_ids),
        "uncited_evidence_ids": sorted({item.id for item in evidence} - result.cited_evidence_ids),
        "missing_required_evidence_ids": list(missing_required),
    }
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    print(f"Reference benchmark: {reference_benchmark_id}")
    print(f"\nEvidence ledger ({len(evidence)} items):")
    for item in evidence:
        print(f"  [{item.evidence_class:>9}] {item.id}: {item.title}")
    print(f"\n{result.text}")
    print(f"\nCitations ({len(result.citations)}):")
    for citation in result.citations:
        print(f'  "{citation.text}" -> {", ".join(citation.evidence_ids)}')
    if report_payload["uncited_evidence_ids"]:
        print(f"\nEvidence provided but not cited: {report_payload['uncited_evidence_ids']}")
    if missing_required:
        print(
            f"\nWARNING: explanation did not cite safety-critical evidence: {missing_required}. "
            "Treat this explanation as incomplete."
        )
    print(f"\nReport written to {report_path}")
    return 0


def _replay(reference_benchmark_id: str, data_dir: Path) -> int:
    paths = DataPaths.from_root(data_dir)
    paths.create()

    decision_report_path = paths.decision_reports / f"decision-{reference_benchmark_id}.json"
    if not decision_report_path.exists():
        raise SystemExit(
            f"No decision report for '{reference_benchmark_id}' at {decision_report_path}. "
            "Run 'apexmind decide' first."
        )
    decision_report = json.loads(decision_report_path.read_text(encoding="utf-8"))
    evidence = build_decision_evidence(decision_report)

    explanation_report_path = (
        paths.explanation_reports / f"explanation-{reference_benchmark_id}.json"
    )
    if explanation_report_path.exists():
        explanation_report = json.loads(explanation_report_path.read_text(encoding="utf-8"))
        explanation_text = explanation_report["explanation"]
        citations = tuple(explanation_report["citations"])
    else:
        explanation_text = (
            "No explanation has been generated yet for this benchmark. "
            "Run 'apexmind explain' first to include a cited narrative here."
        )
        citations = ()

    race_control = pd.read_parquet(
        paths.processed / f"{reference_benchmark_id}-race-control.parquet"
    )
    safety_car_episodes = extract_safety_car_episodes(race_control)

    chosen_name = decision_report["chosen_strategy"]
    chosen_plan = next(
        candidate
        for candidate in decision_report["optimiser_candidates"]
        if candidate["name"] == chosen_name
    )
    chosen_segments = stints_to_segments(tuple(chosen_plan["stints"]))

    html = build_replay_html(
        benchmark_id=reference_benchmark_id,
        total_laps=decision_report["total_laps"],
        safety_car_episodes=safety_car_episodes,
        chosen_strategy_name=chosen_name,
        chosen_segments=chosen_segments,
        evidence=tuple(
            {"id": item.id, "title": item.title, "evidence_class": item.evidence_class}
            for item in evidence
        ),
        explanation_text=explanation_text,
        citations=citations,
    )

    report_path = paths.replay_reports / f"replay-{reference_benchmark_id}.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html, encoding="utf-8")

    print(f"Reference benchmark: {reference_benchmark_id}")
    print(f"Real Safety Car/VSC episodes: {safety_car_episodes}")
    print(f"Chosen strategy: {chosen_name}")
    if not explanation_report_path.exists():
        print("(no 'apexmind explain' report found; replay page has a placeholder explanation)")
    print(f"Replay page written to {report_path}")
    return 0


def _plot(
    reference_benchmark_id: str,
    holdout_benchmark_id: str,
    n_simulations: int,
    seed: int,
    use_safety_car: bool,
    data_dir: Path,
) -> int:
    try:
        from apexmind.viz import (
            plot_calibration_reliability,
            plot_monte_carlo_outcomes,
            plot_tyre_degradation,
        )
    except ImportError as error:
        raise SystemExit(str(error)) from error

    paths = DataPaths.from_root(data_dir)
    paths.create()

    all_states = {
        benchmark.identifier: _load_lap_state(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    all_race_control = {
        benchmark.identifier: _load_race_control(paths, benchmark.identifier)
        for benchmark in BENCHMARK_RACES
    }
    full_state = pd.concat(all_states.values(), ignore_index=True)
    written_paths: list[Path] = []

    stats = _reference_race_stats(all_states, all_race_control, full_state, reference_benchmark_id)

    # The dry slick compounds (SOFT/MEDIUM/HARD) have comparable support
    # across all three benchmarks; INTERMEDIATE/WET only have laps from
    # dutch-2023's rain-affected stints, so their predictive band widens
    # sharply past that benchmark's observed tyre life and dominates the
    # chart without adding a readable signal. Capping at a realistic
    # single-stint length keeps this the intended headline chart; the
    # function itself still accepts any compound/tyre-life combination
    # for a caller who wants the full picture (see apexmind.viz).
    tyre_ax = plot_tyre_degradation(
        stats.posterior,
        compounds=("SOFT", "MEDIUM", "HARD"),
        max_tyre_life=min(stats.max_observed_tyre_life, 35),
    )
    tyre_path = paths.plot_reports / f"{reference_benchmark_id}-tyre-degradation.png"
    tyre_ax.figure.savefig(tyre_path, dpi=150, bbox_inches="tight")
    written_paths.append(tyre_path)

    laps_with_delta = {
        benchmark_id: remove_pace_outliers(
            add_race_progress(
                add_pace_delta(
                    exclude_safety_car_restart_laps(
                        select_green_flag_laps(state), all_race_control[benchmark_id]
                    )
                ),
                session_total_laps=int(state["lap_number"].max()),
            )
        )
        for benchmark_id, state in all_states.items()
    }
    train_laps, test_laps = temporal_holdout_split(
        laps_with_delta, holdout_benchmark_id=holdout_benchmark_id
    )
    train_design, train_target, _ = build_pace_design_matrix(train_laps)
    test_design, test_target, _ = build_pace_design_matrix(test_laps)
    holdout_posterior = fit_bayesian_pace_model(train_design, train_target)
    test_mean, test_variance = predict(holdout_posterior, test_design)
    calibration_ax = plot_calibration_reliability(test_target.to_numpy(), test_mean, test_variance)
    calibration_path = paths.plot_reports / f"{holdout_benchmark_id}-calibration-reliability.png"
    calibration_ax.figure.savefig(calibration_path, dpi=150, bbox_inches="tight")
    written_paths.append(calibration_path)

    safety_car_scenario = SafetyCarScenario() if use_safety_car else None
    strategies = _example_strategies(stats.total_laps)
    mc_results = run_monte_carlo(
        strategies,
        stats.posterior,
        driver_baseline_seconds=stats.driver_baseline_seconds,
        pit_loss_seconds=stats.pit_loss_seconds,
        n_simulations=n_simulations,
        seed=seed,
        safety_car_scenario=safety_car_scenario,
    )
    mc_ax = plot_monte_carlo_outcomes(mc_results)
    mc_path = paths.plot_reports / f"{reference_benchmark_id}-monte-carlo-outcomes.png"
    mc_ax.figure.savefig(mc_path, dpi=150, bbox_inches="tight")
    written_paths.append(mc_path)

    for path in written_paths:
        print(f"Wrote {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ApexMind command-line interface."""

    args = _parser().parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.benchmark, args.data_dir)
    if args.command == "evaluate":
        return _evaluate(args.holdout, args.data_dir)
    if args.command == "simulate":
        return _simulate(
            args.reference_benchmark,
            args.n_simulations,
            args.seed,
            not args.no_safety_car,
            args.data_dir,
        )
    if args.command == "decide":
        return _decide(
            args.reference_benchmark,
            args.top_k,
            args.n_simulations,
            args.seed,
            not args.no_safety_car,
            args.data_dir,
        )
    if args.command == "explain":
        return _explain(args.reference_benchmark, args.data_dir)
    if args.command == "replay":
        return _replay(args.reference_benchmark, args.data_dir)
    if args.command == "plot":
        return _plot(
            args.reference_benchmark,
            args.holdout,
            args.n_simulations,
            args.seed,
            not args.no_safety_car,
            args.data_dir,
        )
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
