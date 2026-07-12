# ApexMind: F1 Counterfactual Decision Twin

An offline research laboratory for analysing Formula 1 strategy decisions from public data. At a decision point, ApexMind compares counterfactual options such as *pit now*, *extend the stint*, and *protect track position* under explicit assumptions, uncertainty, and FIA-rule constraints.

> Status: **Planning / research protocol approved**

## The honest boundary

This is not a live pit-wall tool and it does not claim access to team telemetry. Public data does not expose a car's true battery state, power-unit maps, tyre temperatures, or active-aero state. ApexMind labels every input as **observed**, **inferred**, or **simulated** and reports conditional rather than absolute recommendations.

## Why this project

The 2026 F1 regulations place greater emphasis on energy management and active aerodynamics. The project will combine public race timing and telemetry with a probabilistic tyre/pace model, a Monte Carlo race simulator, constrained optimisation, and evidence-grounded natural-language explanations.

## Repository map

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — scope, architecture, risks, and evaluation protocol
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — gated delivery plan and backlog
- [`docs/progress/00-inception.md`](docs/progress/00-inception.md) — initial project record

## Near-term milestone

Build a reproducible replay of three historical races, then validate a baseline tyre-and-pace model before introducing any strategy optimiser or LLM component.

The initial data-fidelity work, benchmark rationale, source caveats, and the normalised lap-state schema are recorded in [`docs/DATA_FOUNDATION.md`](docs/DATA_FOUNDATION.md).

The pace/tyre model, its baselines, and its current calibration gap are recorded in [`docs/PACE_MODEL.md`](docs/PACE_MODEL.md).

The counterfactual race simulator, its declared Safety Car scenario, and its scope limits are recorded in [`docs/SIMULATOR.md`](docs/SIMULATOR.md).

## Data and attribution

The initial research data sources are OpenF1, FastF1, and publicly available FIA regulations. Use is offline and research-oriented; source terms must be re-checked before any public deployment or commercial use. The project is independent and has no affiliation with Formula 1, the FIA, Aston Martin Aramco Formula One Team, or Cohere.

## Licence

No licence has been selected yet. The repository is private while the research protocol, data permissions, and release scope are being established.
