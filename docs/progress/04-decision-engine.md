# Progress Record 04 — Constrained Decision Engine

**Date:** 13 July 2026
**Status:** Implemented; Gate D met numerically on all three benchmarks, with a named caveat on the winning plan's shape

## Work completed

1. Retrieved the FIA 2026 Formula 1 Sporting Regulations, Section B,
   Issue 07 (25 June 2026) directly from the FIA — the exact document
   `docs/DATA_FOUNDATION.md` named as this project's rule source before
   any rule was encoded — and located Article B6.3.6, the mandatory
   dry-weather tyre-compound rule. Recorded the quoted article text,
   retrieval URL and date, and a SHA-256 hash of the retrieved PDF in
   `docs/regulations/tyre-compound-rule.md`, along with an explicit note
   on the one sub-clause (the per-Grand-Prix mandatory specification) this
   project's schema cannot check.
2. Added `src/apexmind/regulations.py`: `strategy_compound_violations` and
   `is_legal_strategy`, checking a `StrategyPlan` against Article B6.3.6.
3. Added `src/apexmind/decision_engine.py`: `optimise_strategies`, an
   exact dynamic-programming search over the legal dry-compound strategy
   space, scored by the Phase 2 posterior mean pace delta. The legality
   filter runs inside the search rather than as a separate pass, so this
   module covers both the roadmap's "candidate-strategy generator" and
   "optimiser" items as one piece of work rather than two.
4. Found a real problem by running the first, unbounded version of the
   search against actual ingested data: it returned a legal but not
   credible plan (56 laps on `SOFT`, a 1-lap `HARD` stint as a technical
   pit stop). Diagnosed the cause directly — the fitted `tyre_life_SOFT`
   coefficient is slightly negative (-0.0154 s/lap), the tyre-age/fuel
   -burn confound `docs/PACE_MODEL.md` had already named as an open
   limitation, and the unbounded search extrapolated it across a stint 7
   laps longer than anything in the training data (max observed: 49
   laps). Fixed it with a `max_stint_laps` parameter, computed from the
   actual training data rather than a hard-coded constant, and confirmed
   the same cap-riding pattern (a `SOFT` stint pinned to exactly 49 laps)
   recurs on all three benchmarks — a systematic model property worth
   documenting, not a one-off fluke.
5. Added `paired_mean_difference_ci` to `src/apexmind/evaluation.py`: a
   normal-approximation confidence interval for a paired mean difference,
   built for the common-random-numbers draws `run_monte_carlo` already
   produces, used to check Gate D's "statistically supported advantage"
   requirement rather than eyeballing the mean.
6. Wired an `apexmind decide` command: fits the pace model on every
   available benchmark (matching `simulate`'s approach), runs the
   optimiser, runs the winning plan against both Phase 3 example
   baselines through the full stochastic Monte Carlo simulator, computes
   the paired confidence interval against each baseline, and writes a
   report.
7. Added a `decision_reports` storage location to `DataPaths` alongside
   the existing `simulation_reports` and `evaluation_reports`.
8. Added 13 new unit tests (5 for `regulations`, 5 for `decision_engine`,
   3 for the new `evaluation` helper) covering: the compound rule on
   legal, illegal, and wet-weather-exempt strategies; the DP finding the
   minimum-stop legal solution under flat pace, correctly trading off
   between two compounds with different degradation under a forced
   two-compound search, and raising on an unsatisfiable race distance and
   invalid configuration; and the confidence-interval helper detecting a
   real paired shift, correctly failing to find one in i.i.d. noise, and
   rejecting malformed input. Two bugs were caught by these tests before
   merge: a missing trailing comma silently turned a one-element
   violation tuple into a bare string (`len()` counted characters, not
   findings), and two DP candidates with the same compound sequence but
   different lap splits could collide under the same strategy name, which
   would have silently merged their results under
   `summarize_simulations`' name-based grouping. 60 tests total in the
   project, all passing; `ruff check` clean.
9. Ran `apexmind decide` against real ingested data for all three
   benchmarks. On every one, the optimiser's plan is legal, beats both
   fixed baselines with a 95% confidence interval that excludes zero, and
   two independent process runs with the same seed produced byte
   -identical output.

## Result

See `docs/DECISION_ENGINE.md` for the full write-up, including the
per-benchmark comparison table and an explicit discussion of what the
optimiser's chosen plan does and does not prove, given where its
underlying pace model is confounded.

## Gate D assessment

Gate D requires "no illegal strategies and a statistically supported
advantage in the defined simulation benchmark." No illegal strategy can
leave the search by construction, and the statistical advantage holds with
95% confidence on all three benchmarks. Numerically, the gate is met. The
important caveat, recorded rather than smoothed over: the specific shape
of the winning plan (a near-maximum-length single `SOFT` stint) is a
traceable consequence of Phase 2's already-documented tyre-age/fuel-burn
confound, not new evidence about tyre behaviour. This is carried forward
as a named, tracked risk, the same way Phase 2's calibration gap and
Phase 3's single-car scope were carried forward rather than closed.

## Next action

Phase 5 (evidence interface) can begin. It should present the Article
B6.3.6 check and the optimiser's reasoning as visible, cited evidence
—exactly the kind of claim this phase's evidence-and-assumption ledger is
for — rather than only a final number. It should also treat the pace
-model confound named here as a candidate for the evidence ledger's
"named limitation" category when explaining any strategy recommendation
that leans on a long single stint. Separating tyre degradation from fuel
burn-off (deferred in Phase 2 for lack of a fuel-load signal) remains the
most direct fix and is not yet scheduled.
