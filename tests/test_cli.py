"""Tests for argument parsing and command dispatch in apexmind.cli.

These deliberately stay away from real data, network calls, and the
Cohere API: they check that the parser accepts what the CLI's own help
text promises and that `main()` routes each command to the right handler
with the right arguments, using monkeypatched handlers rather than
running the real ones. The handlers themselves are exercised by real
`apexmind <command>` runs against live data as part of this project's
established verification practice, not by this file.
"""

from pathlib import Path

import pytest

from apexmind.benchmarks import BENCHMARK_RACES
from apexmind.cli import DEFAULT_HOLDOUT_BENCHMARK, _parser, main
from apexmind.paths import default_data_root

ALL_COMMANDS = ("ingest", "evaluate", "simulate", "decide", "explain", "replay", "plot")


def test_no_command_is_an_error() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args([])


def test_unknown_command_is_an_error() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["qualify"])


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_each_command_parses_with_no_extra_arguments(command: str) -> None:
    args = _parser().parse_args([command])
    assert args.command == command


def test_ingest_defaults_to_all_benchmarks_and_the_default_data_root() -> None:
    args = _parser().parse_args(["ingest"])
    assert args.benchmark == "all"
    assert args.data_dir == default_data_root()


def test_ingest_accepts_every_registered_benchmark_identifier() -> None:
    for benchmark in BENCHMARK_RACES:
        args = _parser().parse_args(["ingest", "--benchmark", benchmark.identifier])
        assert args.benchmark == benchmark.identifier


def test_ingest_rejects_an_unregistered_benchmark() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["ingest", "--benchmark", "monaco-1955"])


def test_evaluate_defaults_to_the_documented_primary_holdout() -> None:
    args = _parser().parse_args(["evaluate"])
    assert args.holdout == DEFAULT_HOLDOUT_BENCHMARK == "bahrain-2024"


def test_simulate_defaults() -> None:
    args = _parser().parse_args(["simulate"])
    assert args.reference_benchmark == DEFAULT_HOLDOUT_BENCHMARK
    assert args.n_simulations == 2000
    assert args.seed == 0
    assert args.no_safety_car is False


def test_simulate_no_safety_car_flag_and_custom_seed() -> None:
    args = _parser().parse_args(
        ["simulate", "--no-safety-car", "--seed", "7", "--n-simulations", "50"]
    )
    assert args.no_safety_car is True
    assert args.seed == 7
    assert args.n_simulations == 50


def test_decide_defaults() -> None:
    args = _parser().parse_args(["decide"])
    assert args.reference_benchmark == DEFAULT_HOLDOUT_BENCHMARK
    assert args.top_k == 3
    assert args.n_simulations == 2000
    assert args.seed == 0
    assert args.no_safety_car is False


@pytest.mark.parametrize("command", ["explain", "replay"])
def test_explain_and_replay_accept_reference_benchmark(command: str) -> None:
    args = _parser().parse_args([command, "--reference-benchmark", "dutch-2023"])
    assert args.reference_benchmark == "dutch-2023"


@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_every_command_accepts_a_custom_data_dir(tmp_path: Path, command: str) -> None:
    args = _parser().parse_args([command, "--data-dir", str(tmp_path)])
    assert args.data_dir == tmp_path


def test_main_dispatches_ingest_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._ingest",
        lambda benchmark_id, data_dir: calls.append((benchmark_id, data_dir)) or 0,
    )

    result = main(["ingest", "--benchmark", "singapore-2023"])

    assert result == 0
    assert calls == [("singapore-2023", default_data_root())]


def test_main_dispatches_evaluate_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._evaluate",
        lambda holdout_id, data_dir: calls.append((holdout_id, data_dir)) or 0,
    )

    result = main(["evaluate", "--holdout", "dutch-2023"])

    assert result == 0
    assert calls == [("dutch-2023", default_data_root())]


def test_main_dispatches_simulate_and_inverts_no_safety_car(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._simulate",
        lambda ref, n_sim, seed, use_sc, data_dir: (
            calls.append((ref, n_sim, seed, use_sc, data_dir)) or 0
        ),
    )

    main(["simulate", "--reference-benchmark", "bahrain-2024", "--no-safety-car"])

    # --no-safety-car is a "disable" flag on the CLI, but _simulate's
    # signature takes a "use it" boolean -- main() must invert it, and a
    # regression here would silently run the opposite scenario from what
    # the user asked for.
    assert calls == [("bahrain-2024", 2000, 0, False, default_data_root())]


def test_main_dispatches_simulate_with_safety_car_enabled_by_default(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._simulate",
        lambda ref, n_sim, seed, use_sc, data_dir: calls.append(use_sc) or 0,
    )

    main(["simulate"])

    assert calls == [True]


def test_main_dispatches_decide_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._decide",
        lambda ref, top_k, n_sim, seed, use_sc, data_dir: (
            calls.append((ref, top_k, n_sim, seed, use_sc, data_dir)) or 0
        ),
    )

    main(["decide", "--reference-benchmark", "singapore-2023", "--top-k", "5"])

    assert calls == [("singapore-2023", 5, 2000, 0, True, default_data_root())]


def test_main_dispatches_explain_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._explain",
        lambda ref, data_dir: calls.append((ref, data_dir)) or 0,
    )

    main(["explain", "--reference-benchmark", "dutch-2023"])

    assert calls == [("dutch-2023", default_data_root())]


def test_main_dispatches_replay_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._replay",
        lambda ref, data_dir: calls.append((ref, data_dir)) or 0,
    )

    main(["replay", "--reference-benchmark", "bahrain-2024"])

    assert calls == [("bahrain-2024", default_data_root())]


def test_plot_defaults_to_the_documented_primary_holdout_for_both_benchmarks() -> None:
    args = _parser().parse_args(["plot"])
    assert args.reference_benchmark == DEFAULT_HOLDOUT_BENCHMARK == "bahrain-2024"
    assert args.holdout == DEFAULT_HOLDOUT_BENCHMARK


def test_main_dispatches_plot_with_the_parsed_arguments(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._plot",
        lambda ref, holdout, n_sim, seed, use_sc, data_dir: (
            calls.append((ref, holdout, n_sim, seed, use_sc, data_dir)) or 0
        ),
    )

    main(["plot", "--reference-benchmark", "singapore-2023", "--holdout", "dutch-2023"])

    assert calls == [("singapore-2023", "dutch-2023", 2000, 0, True, default_data_root())]


def test_main_dispatches_plot_and_inverts_no_safety_car(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        "apexmind.cli._plot",
        lambda ref, holdout, n_sim, seed, use_sc, data_dir: (
            calls.append((ref, holdout, n_sim, seed, use_sc, data_dir)) or 0
        ),
    )

    main(["plot", "--no-safety-car"])

    assert calls == [
        (DEFAULT_HOLDOUT_BENCHMARK, DEFAULT_HOLDOUT_BENCHMARK, 2000, 0, False, default_data_root())
    ]
