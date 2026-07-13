import numpy as np
import pandas as pd
import pytest

from apexmind.decision_engine import DecisionEngineError, optimise_strategies
from apexmind.pace_model import fit_bayesian_pace_model
from apexmind.regulations import is_legal_strategy


def _flat_posterior():
    """A posterior whose predicted pace delta is (almost) zero for every compound and tyre life.

    Mirrors the pattern in tests/test_simulator.py: an all-zero target
    drives every coefficient's posterior mean to (almost) zero, including
    compounds whose design column is always zero here, since their
    contribution to both the prior and the likelihood is zero.
    """

    # Column order must match build_pace_feature_matrix exactly: compound,
    # tyre-life, race-progress, interleaved per compound.
    n = 500
    design = pd.DataFrame(
        {
            "compound_SOFT": [1.0] * n,
            "tyre_life_SOFT": list(range(1, n + 1)),
            "race_progress_SOFT": [0.0] * n,
            "compound_MEDIUM": [0.0] * n,
            "tyre_life_MEDIUM": [0.0] * n,
            "race_progress_MEDIUM": [0.0] * n,
            "compound_HARD": [0.0] * n,
            "tyre_life_HARD": [0.0] * n,
            "race_progress_HARD": [0.0] * n,
            "compound_INTERMEDIATE": [0.0] * n,
            "tyre_life_INTERMEDIATE": [0.0] * n,
            "race_progress_INTERMEDIATE": [0.0] * n,
            "compound_WET": [0.0] * n,
            "tyre_life_WET": [0.0] * n,
            "race_progress_WET": [0.0] * n,
        }
    )
    target = pd.Series([0.0] * n)
    return fit_bayesian_pace_model(design, target, prior_scale=0.01, prior_rate=1e-6)


def test_optimal_strategy_uses_exactly_one_pit_stop_when_pace_is_flat() -> None:
    posterior = _flat_posterior()

    candidates = optimise_strategies(
        posterior,
        total_laps=40,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        top_k=5,
    )

    assert candidates
    best = candidates[0]
    # With no degradation advantage to chase, every extra pit stop is pure
    # cost, so the legal optimum is the minimum needed to satisfy Article
    # B6.3.6: one stop, two stints.
    assert best.pit_stop_count == 1
    assert best.total_laps == 40


def test_every_candidate_is_legal_distinct_and_covers_the_full_race_distance() -> None:
    posterior = _flat_posterior()

    candidates = optimise_strategies(
        posterior,
        total_laps=32,
        driver_baseline_seconds=95.0,
        pit_loss_seconds=22.0,
        top_k=5,
    )

    assert len(candidates) <= 5
    names = [plan.name for plan in candidates]
    assert len(names) == len(set(names))
    for plan in candidates:
        assert is_legal_strategy(plan)
        assert plan.total_laps == 32


def test_optimiser_minimises_laps_on_the_more_degrading_compound() -> None:
    # HARD: no degradation. SOFT: steep degradation. Restricting the search
    # to exactly these two compounds forces a real trade-off: a
    # cost-minimising search should spend as few laps as legally possible
    # on SOFT rather than avoid it via some other, unmodelled compound.
    n = 400
    tyre_life = np.tile(np.arange(1, 51), n // 50)
    is_soft = np.tile([True] * 25 + [False] * 25, n // 50)
    design = pd.DataFrame(
        {
            "compound_SOFT": is_soft.astype(float),
            "tyre_life_SOFT": is_soft.astype(float) * tyre_life,
            "race_progress_SOFT": 0.0,
            "compound_MEDIUM": 0.0,
            "tyre_life_MEDIUM": 0.0,
            "race_progress_MEDIUM": 0.0,
            "compound_HARD": (~is_soft).astype(float),
            "tyre_life_HARD": (~is_soft).astype(float) * tyre_life,
            "race_progress_HARD": 0.0,
            "compound_INTERMEDIATE": 0.0,
            "tyre_life_INTERMEDIATE": 0.0,
            "race_progress_INTERMEDIATE": 0.0,
            "compound_WET": 0.0,
            "tyre_life_WET": 0.0,
            "race_progress_WET": 0.0,
        }
    )
    target = pd.Series(np.where(is_soft, 0.3 * tyre_life, 0.0))
    posterior = fit_bayesian_pace_model(design, target)

    candidates = optimise_strategies(
        posterior,
        total_laps=40,
        driver_baseline_seconds=90.0,
        pit_loss_seconds=20.0,
        top_k=1,
        compounds=("SOFT", "HARD"),
    )

    best = candidates[0]
    soft_laps = sum(stint.lap_count for stint in best.stints if stint.compound == "SOFT")
    hard_laps = sum(stint.lap_count for stint in best.stints if stint.compound == "HARD")
    assert soft_laps < hard_laps


def test_no_legal_strategy_for_a_race_too_short_to_pit() -> None:
    posterior = _flat_posterior()

    with pytest.raises(DecisionEngineError):
        optimise_strategies(
            posterior, total_laps=1, driver_baseline_seconds=90.0, pit_loss_seconds=20.0
        )


def test_optimise_strategies_rejects_invalid_configuration() -> None:
    posterior = _flat_posterior()

    with pytest.raises(DecisionEngineError):
        optimise_strategies(
            posterior, total_laps=0, driver_baseline_seconds=90.0, pit_loss_seconds=20.0
        )
    with pytest.raises(DecisionEngineError):
        optimise_strategies(
            posterior, total_laps=30, driver_baseline_seconds=90.0, pit_loss_seconds=-1.0
        )
    with pytest.raises(DecisionEngineError):
        optimise_strategies(
            posterior,
            total_laps=30,
            driver_baseline_seconds=90.0,
            pit_loss_seconds=20.0,
            top_k=0,
        )
