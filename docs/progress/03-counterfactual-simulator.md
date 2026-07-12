# Progress Record 03 — Counterfactual Simulator

**Date:** 13 July 2026
**Status:** Implemented; Gate C met for v1 scope

## Work completed

1. Added `extract_safety_car_episodes`, which parses the real, already
   -ingested race-control evidence into Safety Car/VSC episodes. Validated
   directly against all three benchmarks: correctly finds zero episodes in
   the dry-control `bahrain-2024`, two episodes in `singapore-2023` (SC
   laps 20-22, VSC laps 44-45), and two in `dutch-2023` (SC laps 16-21, and
   a VSC that never closes because a red flag interrupts it, correctly
   falling back to the last recorded lap).
2. Added `SafetyCarScenario`, a declared (not statistically fit) Monte
   Carlo scenario generator, with its pace multiplier grounded in a real
   check of caution-lap pace against green-flag pace across the two
   benchmarks that had incidents (roughly 35-50% slower).
3. Added the `simulator` module: `Stint`/`StrategyPlan` to describe a
   candidate strategy, `simulate_race` for one Monte Carlo draw,
   `run_monte_carlo` to run every candidate strategy through the same
   sequence of simulated race conditions (shared Safety Car draw per race
   index, independent pace noise per strategy), and
   `summarize_simulations` to report mean/percentile race time and dynamic
   regret per strategy.
4. Wired an `apexmind simulate` command that fits the pace model on every
   available benchmark, estimates pit loss and a driver pace baseline from
   a chosen reference benchmark, runs the comparison, prints the observed
   real Safety Car episodes for context, and writes a report.
5. Added 19 new unit tests (8 for `safety_car`, 11 for `simulator`)
   covering: real-shaped episode extraction and its red-flag fallback,
   scenario sampling determinism and bounds, strategy/stint validation,
   deterministic pit-loss arithmetic on near-zero-noise synthetic data,
   Safety Car laps correctly bypassing the pace model, Monte Carlo
   reproducibility and shape, and regret/win-rate computation on a
   hand-worked example. 47 tests total in the project, all passing;
   `ruff check` clean.
6. Ran `apexmind simulate` against real ingested data for all three
   benchmarks and confirmed: simulated race times land in a plausible
   range for each circuit's actual distance, the 1-stop example strategy
   wins the large majority of draws with near-zero mean regret, the 2-stop
   example strategy's mean regret sits close to one pit loss (as expected
   given the current pace model's modest degradation slopes), and running
   the same command twice with the same seed produces bit-for-bit
   identical output.

## Result

See `docs/SIMULATOR.md` for the full write-up, including the specific
numbers from the `bahrain-2024` reference run and every declared-versus
-observed assumption the simulator depends on.

## Gate C assessment

Gate C requires simulation behaviours to be plausible, inspectable, and
reproducible across fixed seeds. Reproducibility is directly demonstrated,
not assumed. Plausibility is checked against both synthetic ground truth
(unit tests) and real historical race distances. Every simulated (as
opposed to observed) parameter is named and printed rather than buried,
which is what "inspectable" means in this project's evidence contract.
The single-car, no-overtaking scope and every declared scenario parameter
are recorded as named limitations, not hidden.

## Next action

Phase 4 (constrained decision engine) can begin. It should treat the
example strategies used here as illustrative only: a real candidate
-strategy generator with FIA-rule checks is Phase 4's job, not this one's.
It should also revisit the Safety Car pit-loss discount and pace
multiplier as soon as more benchmark races are available, since both are
currently declared placeholders rather than fitted values.
