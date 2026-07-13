"""Phase 5 evidence interface: turn a Phase 4 decision report into a cited explanation.

This is the only layer in the project that calls an external language
model, and it is deliberately constrained to match `docs/PROJECT_PLAN.md`'s
evidence contract (Section 3) and its explicit boundary on what an LLM may
do here: "It may summarise validated calculations and retrieve cited
rules; it must not directly choose a strategy or invent numerical inputs."
Two things enforce that boundary in code, not just by asking the model
nicely:

1. Every number and every regulation excerpt the model can talk about is
   assembled here, in Python, from data this project already validated —
   the Phase 4 decision report (`apexmind decide`) and
   `apexmind.regulations`. The model never sees or is asked to produce a
   number that did not already exist in that report.
2. If there is no evidence to explain, `generate_explanation` refuses
   before making an API call at all. Abstention is a code-level guard,
   not something left to the model's own judgement — the closed-loop
   version of Gate E ("every answer is evidence-backed or explicitly
   abstains", `docs/PROJECT_PLAN.md`, Section 9).

Every evidence item is tagged with this project's three-way evidence
class (`docs/PROJECT_PLAN.md`, Section 3: observed / inferred /
simulated), reusing that exact vocabulary rather than inventing a new one,
so a reader of the explanation output can see which kind of claim they
are reading, not just what it says.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "command-r-plus-08-2024"
CHAT_ENDPOINT = "https://api.cohere.com/v2/chat"
EVIDENCE_CLASSES = frozenset({"observed", "inferred", "simulated"})


class EvidenceInterfaceError(ValueError):
    """Raised when evidence cannot be assembled or an explanation cannot be produced."""


class CohereConfigError(EvidenceInterfaceError):
    """Raised when no Cohere API key is available."""


class AbstentionError(EvidenceInterfaceError):
    """Raised when there is no evidence to explain; the code refuses to call the model at all."""


@dataclass(frozen=True)
class EvidenceItem:
    """One piece of evidence, tagged with this project's evidence-contract class."""

    id: str
    title: str
    text: str
    evidence_class: str  # "observed", "inferred", or "simulated"

    def __post_init__(self) -> None:
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise EvidenceInterfaceError(
                f"Unknown evidence_class '{self.evidence_class}' for evidence item '{self.id}'."
            )


@dataclass(frozen=True)
class Citation:
    """One citation span in a generated explanation, linked back to evidence item ids."""

    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExplanationResult:
    """A generated explanation and the evidence it actually cited."""

    text: str
    citations: tuple[Citation, ...]

    @property
    def cited_evidence_ids(self) -> frozenset[str]:
        return frozenset(id_ for citation in self.citations for id_ in citation.evidence_ids)


def _slugify(text: str) -> str:
    """Turn arbitrary text into a document id Cohere's API will accept.

    Found the hard way, against the real API rather than a guess: a
    baseline name like ``"1-stop (medium/hard)"`` used directly as a
    document id was rejected with "document id contains whitespace".
    Evidence item ids are internal identifiers, not display text — the
    human-readable name stays in ``title``.
    """

    return "".join(char if char.isalnum() else "_" for char in text).strip("_").lower()


def build_decision_evidence(decision_report: dict[str, Any]) -> tuple[EvidenceItem, ...]:
    """Turn a Phase 4 `apexmind decide` report into a tagged evidence set.

    Every field read here already exists in the decision report
    `apexmind decide` wrote (`src/apexmind/cli.py`); nothing is computed
    fresh, so this function cannot introduce a number the decision stage
    did not already validate.
    """

    items: list[EvidenceItem] = []

    regulation = decision_report["regulation"]
    items.append(
        EvidenceItem(
            id="regulation",
            title=f"{regulation['document']}, Article {regulation['article']}",
            text=(
                f"Article {regulation['article']} ({regulation['document']}): every "
                "strategy considered by the optimiser was checked against this rule "
                "and rejected if it failed. See docs/regulations/tyre-compound-rule.md "
                "for the quoted rule text and its source."
            ),
            evidence_class="observed",
        )
    )

    items.append(
        EvidenceItem(
            id="race_reference",
            title=f"Reference figures for {decision_report['reference_benchmark_id']}",
            text=(
                f"Reference benchmark: {decision_report['reference_benchmark_id']} "
                f"({decision_report['total_laps']} laps). Driver pace baseline: "
                f"{decision_report['driver_baseline_seconds']:.3f} seconds per lap. "
                f"Estimated pit-stop loss: {decision_report['pit_loss_seconds']:.3f} "
                "seconds. Both figures are descriptive statistics computed directly "
                "from ingested lap-state data, not model predictions."
            ),
            evidence_class="observed",
        )
    )

    chosen_name = decision_report["chosen_strategy"]
    chosen_plan = next(
        candidate
        for candidate in decision_report["optimiser_candidates"]
        if candidate["name"] == chosen_name
    )
    stint_desc = ", ".join(
        f"{stint['compound']} for {stint['lap_count']} laps" for stint in chosen_plan["stints"]
    )
    items.append(
        EvidenceItem(
            id="chosen_strategy",
            title="Optimiser's chosen strategy",
            text=(
                f"The dynamic-programming optimiser's top-ranked legal strategy is: "
                f"{stint_desc}. It was found by searching the legal strategy space and "
                "ranking candidates by expected race time under the fitted pace "
                "model's posterior mean; the pace model's fitted values are "
                "themselves an inference from observed lap data, with acknowledged "
                "limitations recorded in docs/PACE_MODEL.md."
            ),
            evidence_class="inferred",
        )
    )

    summary_row = next(
        row for row in decision_report["monte_carlo_summary"] if row["strategy_name"] == chosen_name
    )
    items.append(
        EvidenceItem(
            id="monte_carlo_summary",
            title="Monte Carlo simulation summary",
            text=(
                "Across the simulated draws, the chosen strategy's mean total race "
                f"time was {summary_row['mean_total_race_time_seconds']:.1f} seconds, "
                f"with mean regret {summary_row['mean_regret_seconds']:.2f} seconds "
                f"and a win rate of {summary_row['win_rate']:.1%}. These figures come "
                "from Phase 3's Monte Carlo simulator sampling from the pace model's "
                "posterior predictive distribution, not from a single deterministic "
                "calculation."
            ),
            evidence_class="inferred",
        )
    )

    for comparison in decision_report["comparisons_vs_baselines"]:
        supported = comparison["statistically_supported_advantage"]
        items.append(
            EvidenceItem(
                id=f"comparison_{_slugify(comparison['baseline_name'])}",
                title=f"Comparison vs {comparison['baseline_name']}",
                text=(
                    f"Versus the baseline strategy '{comparison['baseline_name']}', "
                    "the chosen strategy's mean advantage was "
                    f"{comparison['mean_advantage_seconds']:.2f} seconds, with a 95% "
                    "confidence interval of "
                    f"[{comparison['95pct_ci_lower_seconds']:.2f}, "
                    f"{comparison['95pct_ci_upper_seconds']:.2f}] seconds. This "
                    "advantage is "
                    f"{'statistically supported' if supported else 'not statistically supported'} "
                    "at the 95% level, computed from paired Monte Carlo draws under "
                    "common random numbers."
                ),
                evidence_class="inferred",
            )
        )

    items.append(
        EvidenceItem(
            id="safety_car_scenario",
            title="Safety Car scenario assumption",
            text=(
                "The Monte Carlo comparison includes a declared Safety Car scenario: "
                "episode probability, duration, and pace multiplier are illustrative "
                "assumptions informed by, but not statistically fitted to, two "
                "observed historical episodes (docs/SIMULATOR.md). This is a "
                "simulated assumption, not an observed or inferred fact about this "
                "specific race."
            ),
            evidence_class="simulated",
        )
    )

    return tuple(items)


def load_cohere_api_key(env_path: Path | None = None) -> str:
    """Read ``COHERE_API_KEY`` from the environment, falling back to a local ``.env`` file.

    Matches the credential policy already declared in `docs/PROJECT_PLAN.md`
    (Section 8): never commit a credential, read it from the environment.
    The ``.env`` fallback is a development convenience only — ``.env`` is
    git-ignored (see ``.gitignore``), and this function never writes one.
    ``env_path`` defaults to the repository root's ``.env``; tests pass an
    explicit path so this function's behaviour does not depend on whether
    a real ``.env`` happens to exist on the machine running it.
    """

    key = os.environ.get("COHERE_API_KEY")
    if key:
        return key

    if env_path is None:
        env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("COHERE_API_KEY="):
                value = stripped.split("=", 1)[1].strip()
                if value:
                    return value

    raise CohereConfigError(
        "No Cohere API key found. Set COHERE_API_KEY as an environment variable, "
        "or copy .env.example to .env and fill it in."
    )


class CohereClient:
    """A minimal client for Cohere's v2 chat endpoint, using only the standard library.

    This project's dependency list has stayed deliberately narrow (fastf1,
    pandas, pyarrow, numpy) through four phases; a single JSON POST
    request does not justify adding the full Cohere SDK as a fifth.
    """

    def __init__(
        self, api_key: str, *, model: str = DEFAULT_MODEL, timeout_seconds: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def chat(self, *, question: str, documents: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": question}],
            "documents": list(documents),
        }
        request = urllib.request.Request(
            CHAT_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise EvidenceInterfaceError(f"Cohere API error {error.code}: {body}") from error
        except urllib.error.URLError as error:
            raise EvidenceInterfaceError(
                f"Could not reach the Cohere API: {error.reason}"
            ) from error


def generate_explanation(
    evidence: tuple[EvidenceItem, ...], question: str, client: CohereClient
) -> ExplanationResult:
    """Generate a cited explanation grounded only in ``evidence``.

    Refuses before calling the model at all if there is no evidence to
    explain — see the module docstring for why this is a code-level
    guard rather than a prompt instruction.

    Citations whose source id is not one of ``evidence``'s ids are
    dropped rather than trusted: this project's evidence-item ids are the
    only ones the model was ever shown, so a citation pointing anywhere
    else is not something this function's caller asked for.
    """

    if not evidence:
        raise AbstentionError("No evidence available; refusing to generate an explanation.")

    documents = tuple(
        {"id": item.id, "data": {"title": item.title, "text": item.text}} for item in evidence
    )
    response = client.chat(question=question, documents=documents)

    message = response.get("message", {})
    content_blocks = message.get("content", [])
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")

    evidence_ids = {item.id for item in evidence}
    citations: list[Citation] = []
    for raw_citation in message.get("citations", []):
        cited_ids = tuple(
            source["id"]
            for source in raw_citation.get("sources", [])
            if source.get("type") == "document" and source.get("id") in evidence_ids
        )
        if cited_ids:
            citations.append(Citation(text=raw_citation.get("text", ""), evidence_ids=cited_ids))

    return ExplanationResult(text=text, citations=tuple(citations))


# The two claims a reader cannot afford to have silently dropped: which
# strategy is being recommended, and why it is legal. Everything else in
# the evidence set is supporting detail; these two are the safety-critical
# core Gate E ("every answer is evidence-backed or explicitly abstains")
# most needs to hold for.
REQUIRED_EVIDENCE_IDS: frozenset[str] = frozenset({"regulation", "chosen_strategy"})


def assess_explanation_coverage(
    evidence: tuple[EvidenceItem, ...], result: ExplanationResult
) -> tuple[str, ...]:
    """Return the ids of any safety-critical evidence item the explanation did not cite.

    This is a narrower, automatable stand-in for Gate E's full "every
    claim is evidence-backed" requirement: it does not check that every
    sentence in the output has a citation (that would need a human or a
    second model judging faithfulness), but it does mechanically catch
    the one failure this project cannot tolerate silently — an
    explanation that recommends a strategy without ever citing what makes
    it legal, or without saying what the strategy actually is. An empty
    tuple means both were covered.
    """

    available_ids = {item.id for item in evidence}
    required_present = REQUIRED_EVIDENCE_IDS & available_ids
    return tuple(sorted(required_present - result.cited_evidence_ids))
