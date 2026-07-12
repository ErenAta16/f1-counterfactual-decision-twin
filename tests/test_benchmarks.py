from apexmind.benchmarks import BENCHMARK_RACES, get_benchmark


def test_benchmarks_have_unique_identifiers() -> None:
    identifiers = [benchmark.identifier for benchmark in BENCHMARK_RACES]
    assert len(identifiers) == len(set(identifiers))


def test_known_benchmark_is_resolved() -> None:
    benchmark = get_benchmark("singapore-2023")

    assert benchmark.year == 2023
    assert benchmark.condition_class == "safety-car"
