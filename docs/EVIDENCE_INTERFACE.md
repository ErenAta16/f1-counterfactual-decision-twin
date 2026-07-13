# Evidence Interface — Phase 5 Research Record (in progress)

**Status:** Core evidence-grounded explanation pipeline implemented and
verified against the real Cohere API on all three benchmarks; the
roadmap's replay interface and technical report are not started

## Purpose

Phase 5 is where this project introduces its first and only language
model, and `docs/PROJECT_PLAN.md` (Section 4) drew the boundary before
any code existed: "The LLM/SLM sits only in the last layer. It may
summarise validated calculations and retrieve cited rules; it must not
directly choose a strategy or invent numerical inputs." This record
covers the part of Phase 5 built so far: turning a Phase 4 decision
report into a natural-language explanation that cites its evidence,
built so that boundary is enforced by code, not by asking a model
nicely.

## Model choice

Two models were compared using Vectara's hallucination/faithfulness
leaderboard (a continuously updated, third-party benchmark of exactly
this kind of task — RAG summarisation faithfulness) before committing to
one: Cohere's `command-r-plus-08-2024` (6.9% measured hallucination rate)
and Cohere's newer `command-a-03-2025` (9.3%). Command R+ was chosen
specifically *because* it measured better on this metric than Cohere's
own newer, larger model — a reminder that "newer and bigger" is not the
same claim as "more faithful," and this project checked rather than
assumed. Command R+ also natively supports the two API features this
phase depends on: grounded `documents` with returned citation spans, and
`strict_tools`/structured-output schema enforcement (not yet used by this
first slice, reserved for future tool-calling work in this phase).

Faster/cheaper models from other providers (reported around 3-3.5% on
the same leaderboard) were considered and are not ruled out for later,
but were not adopted for this first slice: their leaderboard advantage is
measured on pure summarisation faithfulness, not on the harder,
less-benchmarked task this phase actually needs — synthesising several
numeric sources into coherent prose while still citing each claim
correctly. `src/apexmind/evidence_interface.py`'s `CohereClient` is a
small, swappable class specifically so this choice is not a one-way
door.

## Architecture: the model is not the safety mechanism

The evidence-and-citation boundary in `docs/PROJECT_PLAN.md` is enforced
in `src/apexmind/evidence_interface.py` at the code level, in two ways
that do not depend on which model is used:

1. **Closed evidence set.** `build_decision_evidence` assembles every
   number and every regulation excerpt the model is allowed to discuss
   directly from a Phase 4 decision report (`apexmind decide`) and
   `apexmind.regulations`. The model is never asked an open question; it
   is given a fixed set of documents and asked to explain them. It
   cannot introduce a number that was not already in that report.
2. **Code-level abstention.** `generate_explanation` raises
   `AbstentionError` and refuses to call the model at all if the evidence
   set is empty — verified directly in
   `tests/test_evidence_interface.py` with a fake client that fails the
   test if it is ever invoked. This is Gate E's "explicitly abstains"
   requirement (`docs/PROJECT_PLAN.md`, Section 9) implemented as a
   guard clause, not a prompt instruction the model could ignore.

A third check runs on the way *out*: every citation Cohere returns names
a `sources[].id`; `generate_explanation` drops any citation whose id is
not one of the evidence items actually supplied, rather than trusting
that the model only ever names real sources.

## Evidence classification

Every `EvidenceItem` is tagged with this project's own three-way evidence
class from `docs/PROJECT_PLAN.md` Section 3 — `observed`, `inferred`, or
`simulated` — reusing that vocabulary rather than inventing a parallel
one:

| Evidence item | Class | Why |
|---|---|---|
| The FIA regulation text | observed | A direct, sourced quote (`docs/regulations/tyre-compound-rule.md`) |
| Driver pace baseline, pit-stop loss | observed | Descriptive statistics computed directly from ingested lap data |
| The optimiser's chosen strategy | inferred | Output of a search over a fitted model's posterior mean |
| Monte Carlo summary, baseline comparisons | inferred | Sampled from the pace model's posterior predictive distribution |
| The Safety Car scenario | simulated | A declared, not statistically fitted, assumption (`docs/SIMULATOR.md`) |

`EvidenceItem.__post_init__` rejects any other class outright — this is
a closed set, not a suggestion.

## A real bug found running against the live API

Cohere's API rejected the first real request with `document id contains
whitespace for document index 4`: a baseline name like `"1-stop
(medium/hard)"` was being used directly as a document id. This was not
caught by the unit tests, because they exercise the request-building
logic against a fake client that never validates id format the way the
real API does — a reminder that a mocked test proves the code *shape* is
right, not that a third-party API will accept it. Fixed with a small
`_slugify` helper that turns display names into safe ids while keeping
the human-readable name in a separate `title` field for the model and
the printed evidence ledger.

## Result: real runs against all three benchmarks

`apexmind explain` was run against the real decision reports for all
three benchmarks. All three produced a coherent, multi-paragraph
explanation with every sentence backed by a citation to a real evidence
item:

| Benchmark | Evidence items | Citations returned | Uncited evidence |
|---|---:|---:|---|
| `bahrain-2024` | 7 | 15 | `race_reference` |
| `singapore-2023` | 7 | 15 | none |
| `dutch-2023` | 7 | 12 | `race_reference` |

Every citation's source id matched a real evidence item in all three
runs — the post-hoc filter in `generate_explanation` never had anything
to drop on real traffic, though it stays in place because a mocked test
proved it is needed in principle (a citation naming an unknown source is
possible, even if it did not occur in these three runs). `race_reference`
(the driver pace baseline and pit-loss figures) went uncited on two of
three runs: the model did not spontaneously bring in those figures
unless the question specifically asked for them. This is not a defect —
the evidence was correctly available, just not judged relevant to the
question asked — but it is a concrete, measured example of the gap
between "evidence supplied" and "evidence used," worth tracking as this
phase's explanation-quality tests get built out further.

The model also correctly reproduced this project's observed/inferred/
simulated distinction in its own prose without being asked to use those
exact words, for example: "This is a simulated assumption, not an
observed or inferred fact about this specific race" — evidence that the
evidence-item text (which does use that language) is actually shaping
the generated explanation rather than being ignored.

## What is not done yet

This record covers roadmap items "add evidence and assumption ledger"
and "implement regulation retrieval with citations," plus the abstention
half of "explanation quality tests and abstention behaviour." Not yet
built: automated explanation-quality tests beyond the citation-validity
and abstention checks already in `tests/test_evidence_interface.py`
(for example, a check that every *load-bearing number* in the report
gets cited, not just that citations that exist are valid), a minimal
replay interface, and the technical report and reproducibility guide the
roadmap calls for. Phase 5 is in progress, not complete.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe explain --reference-benchmark bahrain-2024 --data-dir D:\apexmind-data
```

Requires a decision report already written by `apexmind decide`, and a
`COHERE_API_KEY` environment variable (or a local `.env`, copied from
`.env.example` — both are git-ignored; the key is never committed).
Writes `explanation/explanation-<benchmark>.json` under the data
directory; nothing under the data directory belongs in Git.
