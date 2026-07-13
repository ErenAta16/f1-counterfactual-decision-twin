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

**Exit criterion:** confidence intervals are calibrated and performance is not worse than the best simple baseline. **Result:** after diagnosing and fixing a data issue (damp-track laps misread as normal green-flag pace, see `docs/PACE_MODEL.md`), the model beat the naive baseline on MAE/RMSE with a modest, documented calibration gap. A second root-cause fix during Phase 4 (`docs/progress/05-fuel-tyre-confound-fix.md`) separated a fuel-burn/tyre-wear confound the original fix had named but not resolved, roughly halving MAE on the primary hold-out; `docs/PACE_MODEL.md`'s "Second iteration" section has the full before/after numbers, including a calibration regression on `singapore-2023` this fix introduced and did not hide.

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

**Status:** Complete for v1 scope; Gate D met on all three benchmarks with credible, non-degenerate winning plans

**Target:** Weeks 7–8

- [x] Implement legal candidate-strategy generator (generation and ranking are one dynamic-programming search, not two passes — see `docs/DECISION_ENGINE.md`)
- [x] Encode relevant FIA constraints with rule-version metadata (Article B6.3.6, FIA 2026 Sporting Regulations Section B Issue 07; the one rule this project's strategy representation can verify — see `docs/regulations/tyre-compound-rule.md`)
- [x] Add beam search or dynamic programming optimiser (exact DP; the legal state space is small enough that an exact search costs nothing extra over a heuristic)
- [x] Compare expected performance and regret to baselines (statistically supported on all three benchmarks via a new paired confidence-interval check — see `docs/DECISION_ENGINE.md`)
- [x] Decide whether Gate D supports continuation

**Exit criterion:** no illegal strategies and a statistically supported advantage in the defined simulation benchmark. **Result:** met on all three benchmarks — every ranked candidate is legal by construction, and the optimiser's plan beats both fixed example baselines with a 95% confidence interval excluding zero. An unbounded first version of the search was found, during development, to exploit a known pace-model confound (tyre age vs. fuel burn-off, already named in `docs/PACE_MODEL.md`) by extrapolating a stint length far past the training data; an initial fix bounded stint length rather than the model, and the winning plan rode that bound on every benchmark. A follow-up root-cause fix (`docs/progress/05-fuel-tyre-confound-fix.md`) corrected the pace model itself; the optimiser's winning plans no longer touch the safety bound on two of the three benchmarks, and the third sits one lap under it — full detail, including what still doesn't fully resolve, in `docs/DECISION_ENGINE.md`.

## Phase 5 — Evidence interface

**Status:** Complete for v1 scope — evidence ledger, cited retrieval, code-level abstention, a minimal replay interface, and a technical report are all implemented and verified against real data; deeper claim-level faithfulness testing remains a named, tracked gap rather than a closed one

**Target:** Weeks 9–10

- [x] Add evidence and assumption ledger to every recommendation (`apexmind explain`; every item tagged observed/inferred/simulated — see `docs/EVIDENCE_INTERFACE.md`)
- [x] Implement regulation retrieval with citations (Article B6.3.6 from Phase 4, cited with real character-span citations from Cohere's grounded generation)
- [x] Add explanation quality tests and abstention behaviour (abstention: code refuses to call the model with no evidence, tested with a fake client that fails if invoked; citation validity: unknown source ids are dropped, not trusted; a coverage check flags if either safety-critical claim — legality or the chosen strategy — goes uncited. Broader, per-sentence faithfulness checking is not implemented.)
- [x] Build a minimal replay interface (`apexmind replay`; a single self-contained HTML file per benchmark showing the real track-status timeline, the chosen strategy overlaid on it, the evidence ledger, and the cited explanation — no server, no JS framework, matching this project's Phase 3 tooling discipline)
- [x] Publish a technical report and reproducibility guide (`docs/TECHNICAL_REPORT.md`)

**Exit criterion:** an independent reviewer can reproduce a demo decision and trace every claim to data, a model output, or an explicit assumption. **Result:** met for v1 scope. `docs/TECHNICAL_REPORT.md` gives a reviewer an explicit, numbered checklist to verify this directly (fresh clone through to opening a replay page in a browser), and every citation returned across real, live-API runs on all three benchmarks traced to a real evidence item computed from a Phase 4 decision report. A live-API bug (document ids containing whitespace) was found and fixed rather than only caught by mocked tests — recorded in `docs/EVIDENCE_INTERFACE.md`. What remains open, by design rather than oversight: per-sentence faithfulness testing beyond citation-validity and safety-critical-claim coverage.

## Deferred backlog

- [ ] 2026-specific calibration after enough comparable observations exist
- [ ] Vision-assisted event tagging
- [ ] Reinforcement-learning policy research
- [ ] Secure private-data adapter, subject to explicit data-governance approval
- [ ] Live telemetry mode, subject to licensing and safety review
