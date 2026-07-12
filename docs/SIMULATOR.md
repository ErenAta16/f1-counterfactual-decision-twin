# Counterfactual Race Simulator — Phase 3 Research Record

**Status:** Implemented for v1 scope; exit criterion met, with named simplifications

## Purpose

Phase 3 turns the Phase 2 pace model into a tool that can compare candidate
strategies: given a race length, a driver's pace baseline, and an estimated
pit loss, estimate the total race time each strategy is likely to produce,
with an honest uncertainty range, under both green-flag and Safety
Car-affected conditions.

## Scope decisions and their limits

- **Single-car, not multi-car.** The simulator estimates one car's total
  race time under a strategy. It does not model other cars' positions,
  gaps, or overtaking, because the Phase 1 schema has no gap-to-car-ahead
  field to validate a traffic/overtaking model against. Comparing
  strategies by total race time is the honest v1 scope; a
  position-and-gap model is future work, not an implicit claim made here.
- **Safety Car pace is a declared assumption, not a model output.** The
  Phase 2 pace model was deliberately fit only on green-flag laps
  (`docs/PACE_MODEL.md`); using it to predict a caution lap would apply it
  well outside the data it was estimated from. A caution lap instead costs
  `driver_baseline_seconds * pace_multiplier`, where `pace_multiplier`
  defaults to 1.4 — a rough anchor from a real check: laps recorded under a
  pure Safety Car track-status code were roughly 35-50% slower than
  green-flag pace in the two benchmarks that had one (see the `4`
  track-status rows checked directly against `singapore-2023` and
  `dutch-2023` in the Phase 3 development session). This is an
  order-of-magnitude anchor, not a fitted rate.
- **The Safety Car scenario generator is declared, not statistically fit.**
  Only three benchmark races exist, and only two contain a Safety Car or
  VSC event at all — nowhere near enough to fit a reliable per-lap
  deployment probability or duration distribution. `SafetyCarScenario`'s
  defaults (`episode_lap_probability=0.02`, one episode of 2-5 laps per
  simulated race) are illustrative, informed by but not estimated from the
  two observed episodes, and are meant to be varied explicitly for a
  sensitivity analysis rather than trusted as calibrated. Real historical
  episodes are still extracted from the actual race-control evidence
  (`extract_safety_car_episodes`) — that part is observed, not declared —
  and printed by `apexmind simulate` for context.
- **A pit stop taken during a Safety Car lap is discounted, not measured.**
  Real racing shows pit stops cost much less time when the field is
  already slowed under caution. This benchmark set does not contain enough
  caution-period pit stops to estimate that discount from data, so
  `safety_car_pit_loss_discount` (default 50%) is a declared placeholder,
  the same kind of assumption this project already uses for the
  energy/aero sensitivity layer (`docs/PROJECT_PLAN.md`, Section 6.5).
- **Energy/aero scenarios are a flat per-lap adjustment.** Consistent with
  the project's evidence contract, `energy_scenario_seconds_per_lap` is a
  sensitivity-analysis input a caller supplies explicitly; the simulator
  never infers it and never presents it as observed.

## Model

`simulate_race` draws one Monte Carlo race for a `StrategyPlan` (a named
sequence of `Stint`s, each a compound and a lap count). For each lap it
either samples a pace delta from the Phase 2 posterior predictive
distribution (green-flag laps) or applies the declared Safety Car pace
multiplier (caution laps), then adds pit loss on laps that conclude a
stint. `run_monte_carlo` runs every candidate strategy through the *same*
sequence of simulated race conditions — one shared Safety Car draw per
race index, common to every strategy in that index (common random
numbers), with independently sampled pace noise per strategy since
different strategies drive different tyre-life sequences. Every random
stream is derived from a `numpy.random.SeedSequence`, so a given seed
reproduces bit-for-bit identical results (verified directly, not just
assumed: two separate `apexmind simulate` process runs with the same seed
produced identical output).

`summarize_simulations` reports, per strategy, the mean and 10th/50th/90th
percentile of total race time, plus **dynamic regret**: each draw's time
minus the best time among all strategies in that same draw, averaged
(`docs/PROJECT_PLAN.md`, Section 7 names this exact metric). A strategy's
`win_rate` is the share of paired draws where it was the fastest option.

## Example result

`apexmind simulate --reference-benchmark bahrain-2024 --n-simulations 3000 --seed 42`,
comparing a 1-stop (medium/hard) plan against a 2-stop (soft/soft/hard)
plan of the same total lap count, with the declared Safety Car scenario
enabled:

| Strategy | Mean race time (s) | p10 / p50 / p90 (s) | Mean regret (s) | Win rate |
|---|---:|---|---:|---:|
| 1-stop (medium/hard) | 5643.2 | 5552.7 / 5648.9 / 5735.8 | 0.13 | 97.8% |
| 2-stop (soft/soft/hard) | 5673.9 | 5584.2 / 5679.0 / 5767.3 | 30.9 | 2.2% |

The 1-stop plan wins in the large majority of simulated draws, and its
mean regret (0.13s) is close to zero — consistent with it losing only when
a caution period happens to fall favourably for the 2-stop plan's pit
window. The 2-stop plan's mean regret (30.9s) sits close to one pit loss
(35.1s for this benchmark) minus a partial tyre-freshness benefit, which
is the expected relationship given the current pace model's still-modest
degradation slopes (`docs/PACE_MODEL.md`). The simulated mean race time
(~5643s, about 94 minutes for 57 laps) is in the right order of magnitude
for a real Bahrain Grand Prix finishing time — a coarse but useful
plausibility check, not a validation of precision.

## Reproducibility and stress-testing

The roadmap calls for "replay and stress-test notebooks." This project has
no notebook tooling anywhere else in it (Phase 1 and 2 are pure modules,
CLI commands, and pytest), and adding a Jupyter dependency for one phase
would be a new, undocumented tooling burden. The substitute used here is a
seeded, scriptable CLI command (`apexmind simulate`) plus a pytest suite
that directly checks determinism (same seed, identical output — including
an explicit two-process check, not only an in-process one), boundary
arithmetic (an extra pit stop costs approximately one pit loss when
degradation is negligible), and declared-scenario behaviour (every lap
under a forced Safety Car scenario costs exactly `baseline * multiplier`).
This is recorded here as a deliberate substitution, not a silently dropped
requirement.

## Exit criterion assessment

Phase 3's exit criterion is "simulation behaviours are plausible,
inspectable, and reproducible across fixed seeds." Reproducibility is
directly verified. Plausibility is checked two ways: unit tests on
synthetic data with known answers (an extra pit stop costs what it should;
a forced Safety Car scenario costs exactly what it should), and a real-data
run whose simulated race time lands in a sane range for an actual Grand
Prix distance. Every simulated-layer parameter (Safety Car frequency,
duration, pace multiplier, pit-loss discount, energy/aero adjustment) is
named, printed, and traceable to either a real check or an explicit
declaration — inspectable in the sense this project's evidence contract
requires. Treated as meeting the exit criterion for v1 scope.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe simulate --reference-benchmark bahrain-2024 --n-simulations 3000 --seed 42 --data-dir D:\apexmind-data
```

Requires the three benchmarks to already be ingested (`apexmind ingest`).
Writes `simulation/strategy-comparison-<benchmark>.json` under the data
directory; nothing under the data directory belongs in Git.
