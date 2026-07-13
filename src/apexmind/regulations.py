"""FIA sporting-regulation constraints relevant to strategy legality.

`docs/DATA_FOUNDATION.md` recorded this project's rule source before any
rule was encoded: the FIA 2026 Formula 1 Sporting Regulations, Section B,
Issue 07 (25 June 2026). This module encodes exactly one rule from that
document, Article B6.3.6, the mandatory dry-weather tyre-compound rule —
because it is the only sporting rule this project's strategy representation
(a named sequence of compound/lap-count stints) can actually verify. Other
rules in that document depend on state this project does not have, such as
a per-Grand-Prix mandatory-specification designation or pit-lane speed
traces; encoding a rule this project cannot check against real evidence
would misrepresent what "legal" means here.

The quoted rule text, retrieval date, and a SHA-256 hash of the retrieved
regulation document are recorded in
`docs/regulations/tyre-compound-rule.md`, along with an explicit note on
the sub-clause this module does not check.
"""

from __future__ import annotations

from dataclasses import dataclass

from apexmind.simulator import StrategyPlan

DRY_COMPOUNDS: frozenset[str] = frozenset({"SOFT", "MEDIUM", "HARD"})
WET_WEATHER_COMPOUNDS: frozenset[str] = frozenset({"INTERMEDIATE", "WET"})


@dataclass(frozen=True)
class RegulationSource:
    """Provenance for one encoded regulation, matching this project's evidence contract."""

    document: str
    article: str
    quoted_text: str
    retrieved_url: str
    retrieved_date: str


TYRE_COMPOUND_RULE = RegulationSource(
    document="FIA 2026 Formula 1 Sporting Regulations, Section B: Sporting, Issue 07, 25 June 2026",
    article="B6.3.6",
    quoted_text=(
        "Unless they have used intermediate or wet-weather tyres during the Race, each "
        "driver must use at least two (2) different specifications of dry-weather tyres "
        "during the Race, at least one (1) of which must be a mandatory dry-weather Race "
        "tyre specification (Article B6.1.2)."
    ),
    retrieved_url=(
        "https://www.fia.com/system/files/documents/"
        "fia_2026_f1_regulations_-_section_b_sporting_-_iss_07_-_2026-06-25.pdf"
    ),
    retrieved_date="2026-07-13",
)


def strategy_compound_violations(strategy: StrategyPlan) -> tuple[str, ...]:
    """Check ``strategy`` against Article B6.3.6; an empty tuple means it is legal.

    Only the "two different dry-weather specifications, unless wet tyres
    were used" clause is checked. The "at least one mandatory Race
    specification" sub-clause is a named, deliberate scope gap — see
    `docs/regulations/tyre-compound-rule.md` for why.
    """

    compounds_used = {stint.compound for stint in strategy.stints}
    if compounds_used & WET_WEATHER_COMPOUNDS:
        return ()

    dry_used = compounds_used & DRY_COMPOUNDS
    if len(dry_used) < 2:
        used_description = ", ".join(sorted(dry_used)) if dry_used else "no dry-weather compounds"
        return (
            f"Article B6.3.6: strategy '{strategy.name}' uses only {used_description}; "
            "at least two different dry-weather specifications are required unless "
            "intermediate or wet-weather tyres were used during the race.",
        )
    return ()


def is_legal_strategy(strategy: StrategyPlan) -> bool:
    """Return whether ``strategy`` passes every encoded regulation check."""

    return not strategy_compound_violations(strategy)
