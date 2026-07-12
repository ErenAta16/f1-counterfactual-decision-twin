# Roadmap

This roadmap is intentionally gated. A later stage does not start merely because its calendar date has arrived.

## Phase 0 — Research foundation

**Status:** Complete with documented provider exceptions

- [x] Define the v1 research boundary and non-goals
- [x] Define observed, inferred, and simulated evidence classes
- [x] Document risks, safeguards, and success metrics
- [x] Create a private source-control home

## Phase 1 — Data fidelity

**Target:** Weeks 1–2

- [x] Select one dry, one Safety Car, and one changing-condition historical race
- [x] Create source and schema registry
- [x] Implement reproducible ingestion and local cache configuration
- [x] Build a per-lap race-state table
- [x] Download and replay tyre, stint, pit, position, and race-control timelines
- [x] Define data-quality tests and missing-data policy

**Exit criterion:** the three selected race replays are independently inspectable and match published session data within documented tolerances.

## Phase 2 — Predictive foundation

**Status:** Implemented; exit criterion not yet met (Gate B blocked on calibration)

**Target:** Weeks 3–4

- [x] Implement naive pace and pit baselines
- [x] Build probabilistic tyre/pace model
- [x] Separate clean-air, traffic, and weather effects (green-flag filter and compound-based weather proxy; see documented limits in `docs/PACE_MODEL.md`)
- [x] Establish a temporal hold-out protocol
- [x] Publish calibration and error report

**Exit criterion:** confidence intervals are calibrated and performance is not worse than the best simple baseline. **Current result:** the model beats the naive baseline on MAE/RMSE but its predictive intervals are over-wide (50% nominal interval covers 90.6% of held-out laps). Root cause and candidate fixes are recorded in `docs/PACE_MODEL.md`; Phase 3 should wait until this is resolved or consciously accepted.

## Phase 3 — Counterfactual simulator

**Target:** Weeks 5–6

- [ ] Model pit loss and traffic interaction
- [ ] Implement Safety Car and weather scenario generators
- [ ] Simulate rival policy variants
- [ ] Add energy/aero sensitivity scenarios as declared assumptions
- [ ] Run replay and stress-test notebooks

**Exit criterion:** simulation behaviours are plausible, inspectable, and reproducible across fixed seeds.

## Phase 4 — Constrained decision engine

**Target:** Weeks 7–8

- [ ] Implement legal candidate-strategy generator
- [ ] Encode relevant FIA constraints with rule-version metadata
- [ ] Add beam search or dynamic programming optimiser
- [ ] Compare expected performance and regret to baselines
- [ ] Decide whether Gate D supports continuation

**Exit criterion:** no illegal strategies and a statistically supported advantage in the defined simulation benchmark.

## Phase 5 — Evidence interface

**Target:** Weeks 9–10

- [ ] Add evidence and assumption ledger to every recommendation
- [ ] Implement regulation retrieval with citations
- [ ] Add explanation quality tests and abstention behaviour
- [ ] Build a minimal replay interface
- [ ] Publish a technical report and reproducibility guide

**Exit criterion:** an independent reviewer can reproduce a demo decision and trace every claim to data, a model output, or an explicit assumption.

## Deferred backlog

- [ ] 2026-specific calibration after enough comparable observations exist
- [ ] Vision-assisted event tagging
- [ ] Reinforcement-learning policy research
- [ ] Secure private-data adapter, subject to explicit data-governance approval
- [ ] Live telemetry mode, subject to licensing and safety review
