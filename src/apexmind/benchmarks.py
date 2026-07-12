"""Benchmark races used to validate the data-fidelity stage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkRace:
    """A deliberately chosen race condition for replay validation."""

    identifier: str
    year: int
    event_name: str
    condition_class: str
    rationale: str


BENCHMARK_RACES: tuple[BenchmarkRace, ...] = (
    BenchmarkRace(
        identifier="bahrain-2024",
        year=2024,
        event_name="Bahrain",
        condition_class="dry-control",
        rationale=(
            "A dry-condition control candidate for validating the standard lap, "
            "stint, and pit flow."
        ),
    ),
    BenchmarkRace(
        identifier="singapore-2023",
        year=2023,
        event_name="Singapore",
        condition_class="safety-car",
        rationale="A Safety Car case for validating neutralisation and pit-window state changes.",
    ),
    BenchmarkRace(
        identifier="dutch-2023",
        year=2023,
        event_name="Netherlands",
        condition_class="changing-conditions",
        rationale=(
            "A wet and interrupted-race case for validating weather, tyre, VSC, "
            "and red-flag evidence."
        ),
    ),
)


def get_benchmark(identifier: str) -> BenchmarkRace:
    """Return a benchmark race by its stable identifier."""

    for benchmark in BENCHMARK_RACES:
        if benchmark.identifier == identifier:
            return benchmark
    available = ", ".join(benchmark.identifier for benchmark in BENCHMARK_RACES)
    raise ValueError(f"Unknown benchmark '{identifier}'. Available benchmarks: {available}.")
