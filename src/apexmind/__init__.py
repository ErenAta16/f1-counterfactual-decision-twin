"""ApexMind research toolkit.

A curated public surface for notebook and library use, so callers do not
need to know which internal module a function lives in. This mirrors the
five phases described in ``docs/PROJECT_PLAN.md``: benchmarks -> pace model
-> simulator -> decision engine -> evidence interface.

    from apexmind import get_benchmark, fit_bayesian_pace_model, optimise_strategies

The CLI (``apexmind.cli``) and internal modules remain available for
anything not re-exported here.
"""

from apexmind.benchmarks import BenchmarkRace, get_benchmark
from apexmind.decision_engine import DecisionEngineError, optimise_strategies
from apexmind.evidence_interface import (
    Citation,
    EvidenceInterfaceError,
    EvidenceItem,
    ExplanationResult,
    assess_explanation_coverage,
    build_decision_evidence,
    generate_explanation,
)
from apexmind.pace_model import PaceModelError, PacePosterior, fit_bayesian_pace_model, predict
from apexmind.replay import build_replay_html
from apexmind.simulator import (
    RaceSimulationResult,
    SimulatorError,
    Stint,
    StrategyPlan,
    run_monte_carlo,
    simulate_race,
    summarize_simulations,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # benchmarks
    "BenchmarkRace",
    "get_benchmark",
    # pace model
    "PaceModelError",
    "PacePosterior",
    "fit_bayesian_pace_model",
    "predict",
    # simulator
    "RaceSimulationResult",
    "SimulatorError",
    "Stint",
    "StrategyPlan",
    "run_monte_carlo",
    "simulate_race",
    "summarize_simulations",
    # decision engine
    "DecisionEngineError",
    "optimise_strategies",
    # evidence interface
    "Citation",
    "EvidenceInterfaceError",
    "EvidenceItem",
    "ExplanationResult",
    "assess_explanation_coverage",
    "build_decision_evidence",
    "generate_explanation",
    # replay
    "build_replay_html",
]
