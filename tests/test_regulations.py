from apexmind.regulations import is_legal_strategy, strategy_compound_violations
from apexmind.simulator import Stint, StrategyPlan


def test_two_different_dry_compounds_is_legal() -> None:
    plan = StrategyPlan(name="1-stop", stints=(Stint("MEDIUM", 25), Stint("HARD", 25)))

    assert strategy_compound_violations(plan) == ()
    assert is_legal_strategy(plan)


def test_single_dry_compound_is_illegal() -> None:
    plan = StrategyPlan(name="no-stop", stints=(Stint("HARD", 50),))

    violations = strategy_compound_violations(plan)

    assert len(violations) == 1
    assert "B6.3.6" in violations[0]
    assert not is_legal_strategy(plan)


def test_repeated_single_compound_across_stops_is_still_illegal() -> None:
    # Two stints, but the same specification both times: still only one
    # dry-weather specification used, which is exactly what Article B6.3.6
    # requires two of.
    plan = StrategyPlan(name="fresh-hards", stints=(Stint("HARD", 25), Stint("HARD", 25)))

    assert not is_legal_strategy(plan)


def test_wet_weather_stint_exempts_the_two_compound_requirement() -> None:
    plan = StrategyPlan(name="wet-race", stints=(Stint("INTERMEDIATE", 30), Stint("HARD", 20)))

    assert is_legal_strategy(plan)


def test_all_wet_is_legal_with_no_dry_compound_at_all() -> None:
    plan = StrategyPlan(name="fully-wet", stints=(Stint("WET", 40),))

    assert is_legal_strategy(plan)
