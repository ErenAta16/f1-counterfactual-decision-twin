from typing import Any

import pytest

from apexmind.evidence_interface import (
    AbstentionError,
    Citation,
    CohereConfigError,
    EvidenceInterfaceError,
    EvidenceItem,
    ExplanationResult,
    assess_explanation_coverage,
    build_decision_evidence,
    generate_explanation,
    load_cohere_api_key,
)


class _RefusingClient:
    """A fake client that fails the test if it is ever called."""

    def chat(self, *, question: str, documents: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        raise AssertionError("chat() must not be called when there is no evidence.")


class _FakeCohereClient:
    """A fake client returning a canned response shaped like the real v2/chat API."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.last_call: dict[str, Any] | None = None

    def chat(self, *, question: str, documents: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        self.last_call = {"question": question, "documents": documents}
        return self._response


def _sample_decision_report() -> dict[str, Any]:
    return {
        "reference_benchmark_id": "bahrain-2024",
        "total_laps": 57,
        "driver_baseline_seconds": 95.37,
        "pit_loss_seconds": 35.107,
        "max_stint_laps": 49,
        "regulation": {
            "document": (
                "FIA 2026 Formula 1 Sporting Regulations, Section B: Sporting, Issue 07, "
                "25 June 2026"
            ),
            "article": "B6.3.6",
        },
        "optimiser_candidates": [
            {
                "name": "optimiser (medium20/soft37)",
                "stints": [
                    {"compound": "MEDIUM", "lap_count": 20},
                    {"compound": "SOFT", "lap_count": 37},
                ],
            }
        ],
        "chosen_strategy": "optimiser (medium20/soft37)",
        "monte_carlo_summary": [
            {
                "strategy_name": "optimiser (medium20/soft37)",
                "mean_total_race_time_seconds": 5624.9,
                "mean_regret_seconds": 0.78,
                "win_rate": 0.8807,
            },
            {
                "strategy_name": "1-stop (medium/hard)",
                "mean_total_race_time_seconds": 5638.7,
                "mean_regret_seconds": 14.52,
                "win_rate": 0.1177,
            },
        ],
        "comparisons_vs_baselines": [
            {
                "baseline_name": "1-stop (medium/hard)",
                "mean_advantage_seconds": 13.74,
                "95pct_ci_lower_seconds": 13.31,
                "95pct_ci_upper_seconds": 14.17,
                "statistically_supported_advantage": True,
            },
            {
                "baseline_name": "2-stop (soft/soft/hard)",
                "mean_advantage_seconds": 37.76,
                "95pct_ci_lower_seconds": 37.35,
                "95pct_ci_upper_seconds": 38.17,
                "statistically_supported_advantage": True,
            },
        ],
    }


def test_build_decision_evidence_tags_every_item_with_a_valid_class() -> None:
    evidence = build_decision_evidence(_sample_decision_report())

    by_id = {item.id: item for item in evidence}
    assert by_id["regulation"].evidence_class == "observed"
    assert by_id["race_reference"].evidence_class == "observed"
    assert by_id["chosen_strategy"].evidence_class == "inferred"
    assert by_id["monte_carlo_summary"].evidence_class == "inferred"
    assert by_id["comparison_1_stop__medium_hard"].evidence_class == "inferred"
    assert by_id["safety_car_scenario"].evidence_class == "simulated"
    # Every number quoted in the evidence text traces back to the report,
    # not to a value this function invented.
    assert "13.74" in by_id["comparison_1_stop__medium_hard"].text


def test_evidence_item_rejects_unknown_evidence_class() -> None:
    with pytest.raises(EvidenceInterfaceError):
        EvidenceItem(id="x", title="x", text="x", evidence_class="guessed")


def test_generate_explanation_abstains_on_empty_evidence_without_calling_the_model() -> None:
    with pytest.raises(AbstentionError):
        generate_explanation((), "Why this strategy?", _RefusingClient())


def test_generate_explanation_parses_citations_and_drops_unknown_sources() -> None:
    evidence = (
        EvidenceItem(
            id="reg", title="Rule", text="Two compounds required.", evidence_class="observed"
        ),
    )
    canned_response = {
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Two compounds are required by the rule."}],
            "citations": [
                {
                    "text": "Two compounds are required",
                    "sources": [{"type": "document", "id": "reg"}],
                },
                {
                    # A citation pointing at a source id the caller never
                    # supplied -- must be dropped, not trusted.
                    "text": "an unrelated claim",
                    "sources": [{"type": "document", "id": "not_in_evidence"}],
                },
            ],
        }
    }
    client = _FakeCohereClient(canned_response)

    result = generate_explanation(evidence, "What does the rule require?", client)

    assert result.text == "Two compounds are required by the rule."
    assert len(result.citations) == 1
    assert result.citations[0].evidence_ids == ("reg",)
    assert result.cited_evidence_ids == frozenset({"reg"})
    # The evidence actually reached the client as grounding documents.
    assert client.last_call["documents"][0]["id"] == "reg"


def test_generate_explanation_returns_no_citations_when_model_cites_nothing() -> None:
    evidence = (EvidenceItem(id="reg", title="Rule", text="text", evidence_class="observed"),)
    canned_response = {
        "message": {
            "content": [{"type": "text", "text": "An uncited answer."}],
            "citations": [],
        }
    }

    result = generate_explanation(evidence, "question", _FakeCohereClient(canned_response))

    assert result.text == "An uncited answer."
    assert result.citations == ()


def test_load_cohere_api_key_prefers_the_environment_variable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "from-env")
    # An .env file that would return a different key if actually read --
    # proves the environment variable takes precedence rather than being
    # a coincidence of this key not existing in the file.
    env_file = tmp_path / ".env"
    env_file.write_text("COHERE_API_KEY=from-dotenv\n", encoding="utf-8")

    assert load_cohere_api_key(env_path=env_file) == "from-env"


def test_load_cohere_api_key_falls_back_to_dotenv_file(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nCOHERE_API_KEY=from-dotenv\n", encoding="utf-8")

    assert load_cohere_api_key(env_path=env_file) == "from-dotenv"


def test_load_cohere_api_key_raises_when_nothing_is_configured(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)

    with pytest.raises(CohereConfigError):
        load_cohere_api_key(env_path=tmp_path / "does-not-exist.env")


def test_assess_explanation_coverage_flags_missing_safety_critical_citation() -> None:
    evidence = (
        EvidenceItem(id="regulation", title="Rule", text="text", evidence_class="observed"),
        EvidenceItem(id="chosen_strategy", title="Plan", text="text", evidence_class="inferred"),
        EvidenceItem(id="race_reference", title="Ref", text="text", evidence_class="observed"),
    )
    # Cites an unrelated item but never the rule or the strategy itself.
    result = ExplanationResult(
        text="An explanation that never mentions legality or the plan.",
        citations=(Citation(text="...", evidence_ids=("race_reference",)),),
    )

    missing = assess_explanation_coverage(evidence, result)

    assert missing == ("chosen_strategy", "regulation")


def test_assess_explanation_coverage_passes_when_both_are_cited() -> None:
    evidence = (
        EvidenceItem(id="regulation", title="Rule", text="text", evidence_class="observed"),
        EvidenceItem(id="chosen_strategy", title="Plan", text="text", evidence_class="inferred"),
    )
    result = ExplanationResult(
        text="Legal because of the rule; the plan is X.",
        citations=(
            Citation(text="a", evidence_ids=("regulation",)),
            Citation(text="b", evidence_ids=("chosen_strategy",)),
        ),
    )

    assert assess_explanation_coverage(evidence, result) == ()


def test_assess_explanation_coverage_only_flags_required_ids_present_in_evidence() -> None:
    # "regulation" is never in this evidence set (not this project's real
    # usage, but a valid input) -- there is nothing to demand a citation
    # for, so only the present-but-uncited "chosen_strategy" is flagged.
    evidence = (
        EvidenceItem(id="chosen_strategy", title="Plan", text="t", evidence_class="inferred"),
    )
    result = ExplanationResult(text="uncited", citations=())

    assert assess_explanation_coverage(evidence, result) == ("chosen_strategy",)
