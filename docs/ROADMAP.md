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

**Status:** Complete for v1 scope; Gate B met on the primary hold-out, with tracked limitations

**Target:** Weeks 3–4

- [x] Implement naive pace and pit baselines
- [x] Build probabilistic tyre/pace model
- [x] Separate clean-air, traffic, and weather effects (green-flag filter and compound-based weather proxy; see documented limits in `docs/PACE_MODEL.md`)
- [x] Establish a temporal hold-out protocol
- [x] Publish calibration and error report

**Exit criterion:** confidence intervals are calibrated and performance is not worse than the best simple baseline. **Result:** after diagnosing and fixing a data issue (damp-track laps misread as normal green-flag pace, see `docs/PACE_MODEL.md`), the model beats the naive baseline on MAE/RMSE and its 95% interval is close to nominal, with a modest, documented under-coverage gap at the 50%/80% levels and a weaker result on the changing-conditions hold-out. Treated as meeting the exit criterion well enough to proceed; the residual gaps carry forward as named risks for Phase 3.

## Phase 3 — Counterfactual simulator

**Status:** Complete for v1 scope; Gate C met, with named simplifications

**Target:** Weeks 5–6

- [x] Model pit loss and traffic interaction (pit loss from Phase 2's baseline; single-car scope only, no on-track traffic/overtaking model — see `docs/SIMULATOR.md`)
- [x] Implement Safety Car and weather scenario generators (Safety Car: real episode extraction plus a declared scenario generator; weather remains the Phase 2 compound-choice proxy, not a separate generator)
- [x] Simulate rival policy variants (via example candidate strategies compared under shared race conditions, not a multi-car field simulation — see scope note in `docs/SIMULATOR.md`)
- [x] Add energy/aero sensitivity scenarios as declared assumptions
- [x] Run replay and stress-test notebooks (substituted with a seeded CLI command plus a pytest determinism/plausibility suite; no notebook tooling exists elsewhere in this project — see `docs/SIMULATOR.md`)

**Exit criterion:** simulation behaviours are plausible, inspectable, and reproducible across fixed seeds. **Result:** reproducibility verified directly (two separate process runs, same seed, bit-for-bit identical output); plausibility checked against synthetic ground truth and real race distances. Full detail in `docs/SIMULATOR.md`.

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
