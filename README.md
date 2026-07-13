# ApexMind: F1 Counterfactual Decision Twin

[![Tests](https://github.com/ErenAta16/f1-counterfactual-decision-twin/actions/workflows/tests.yml/badge.svg)](https://github.com/ErenAta16/f1-counterfactual-decision-twin/actions/workflows/tests.yml)

An offline research laboratory for analysing Formula 1 strategy decisions from public data. At a decision point, ApexMind compares counterfactual options such as *pit now*, *extend the stint*, and *protect track position* under explicit assumptions, uncertainty, and FIA-rule constraints.

> Status: **Phases 0-5 implemented for v1 scope (data fidelity, predictive foundation, counterfactual simulator, constrained decision engine, evidence interface). See `docs/TECHNICAL_REPORT.md` for the consolidated results and an independent reproducibility checklist.**

## The honest boundary

This is not a live pit-wall tool and it does not claim access to team telemetry. Public data does not expose a car's true battery state, power-unit maps, tyre temperatures, or active-aero state. ApexMind labels every input as **observed**, **inferred**, or **simulated** and reports conditional rather than absolute recommendations.

## Why this project

The 2026 F1 regulations place greater emphasis on energy management and active aerodynamics. The project will combine public race timing and telemetry with a probabilistic tyre/pace model, a Monte Carlo race simulator, constrained optimisation, and evidence-grounded natural-language explanations.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q          # 116 tests, no network required

.\.venv\Scripts\apexmind.exe ingest --benchmark all --data-dir D:\apexmind-data
.\.venv\Scripts\apexmind.exe decide --reference-benchmark bahrain-2024 --data-dir D:\apexmind-data
```

`decide` is the fastest way to see the whole pipeline (pace model,
simulator, and legal-strategy search) produce a real result. Generating
a cited natural-language explanation of that result
(`apexmind explain`) additionally needs a Cohere API key — copy
`.env.example` to `.env` and fill it in, or set `COHERE_API_KEY` as an
environment variable; `.env` is git-ignored and the key is never
committed. The full command reference and a numbered, independently
reproducible verification checklist are in
[`docs/TECHNICAL_REPORT.md`](docs/TECHNICAL_REPORT.md).

## Repository map

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — scope, architecture, risks, and evaluation protocol
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — gated delivery plan and backlog
- [`docs/progress/00-inception.md`](docs/progress/00-inception.md) — initial project record

## Near-term milestone

Phases 1-5 are complete for v1 scope: a reproducible replay of three historical races, a validated tyre-and-pace model, a counterfactual race simulator, a constrained strategy optimiser with one encoded FIA regulation, and a cited, evidence-grounded explanation and replay interface verified against a real language model API. What remains open is named explicitly in `docs/TECHNICAL_REPORT.md` rather than implied to be finished.

The initial data-fidelity work, benchmark rationale, source caveats, and the normalised lap-state schema are recorded in [`docs/DATA_FOUNDATION.md`](docs/DATA_FOUNDATION.md).

The pace/tyre model, its baselines, and its current calibration gap are recorded in [`docs/PACE_MODEL.md`](docs/PACE_MODEL.md).

The counterfactual race simulator, its declared Safety Car scenario, and its scope limits are recorded in [`docs/SIMULATOR.md`](docs/SIMULATOR.md).

The constrained decision engine, its one encoded FIA regulation, and the pace-model limitation its optimiser surfaced are recorded in [`docs/DECISION_ENGINE.md`](docs/DECISION_ENGINE.md).

The evidence interface — cited, evidence-grounded explanation generation, its model choice, and what is still missing — is recorded in [`docs/EVIDENCE_INTERFACE.md`](docs/EVIDENCE_INTERFACE.md).

A consolidated summary of every phase, what is honestly still unresolved, and a step-by-step reproducibility checklist are in [`docs/TECHNICAL_REPORT.md`](docs/TECHNICAL_REPORT.md).

## Data and attribution

The initial research data sources are OpenF1, FastF1, and publicly available FIA regulations. Use is offline and research-oriented; source terms must be re-checked before any public deployment or commercial use. The project is independent and has no affiliation with Formula 1, the FIA, Aston Martin Aramco Formula One Team, or Cohere.

## Licence

No licence has been selected yet. The repository is private while the research protocol, data permissions, and release scope are being established.
