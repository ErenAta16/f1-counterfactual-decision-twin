# Progress Record 05 — Fuel/Tyre Confound Root-Cause Fix

**Date:** 13 July 2026
**Status:** Fixed and verified against real data; two distinct bugs found and resolved

## Why this record exists

`docs/progress/04-decision-engine.md` shipped Phase 4 with a documented,
named limitation: the decision engine's optimiser had found and exploited
a pace-model confound between tyre wear and fuel burn-off, and the fix at
the time was a safety bound (`max_stint_laps`) rather than a fix to the
model itself. This record covers the follow-up work that replaced the
bound with an actual root-cause fix, found and resolved a second, related
bug along the way, and re-verified every affected number against real
ingested data before committing.

## Work completed

1. Added `add_race_progress` to `src/apexmind/pace_features.py`: a
   `race_progress` column (`lap_number / session_total_laps`) whose
   defining property is that it does not reset at a pit stop, unlike
   `tyre_life`. That structural difference is what lets a linear model
   attribute a car's "gets faster over the race" behaviour to fuel
   burn-off instead of folding it into the tyre-degradation slope.
2. First attempt: added `race_progress` as a single column shared across
   every compound. Verified this measurably fixed the original problem —
   `tyre_life_SOFT`'s coefficient moved from -0.0154 to positive, and
   `bahrain-2024`/`singapore-2023` MAE improved 30-38% — with a synthetic
   test proving the mechanism
   (`test_race_progress_separates_fuel_effect_from_tyre_wear`) before
   trusting the real-data result.
3. Found a second real bug by checking robustness across all three
   hold-outs rather than stopping at the first improved number:
   `dutch-2023`'s MAE got *worse* (2.652 &rarr; 3.049) with the shared
   column. Diagnosed by inspecting the worst individual residuals
   directly rather than guessing — every one of the largest errors was an
   `INTERMEDIATE`-compound lap at race progress &asymp;0.93, where a
   fuel-burn slope estimated entirely from `bahrain-2024` and
   `singapore-2023` (both fully dry, zero `INTERMEDIATE` laps between
   them) was being extrapolated onto a compound it had never been fit on.
4. Fixed the second bug the same way every other coefficient in this model
   already handles missing evidence: made `race_progress` per-compound
   (`race_progress_SOFT`, `race_progress_MEDIUM`, ...) instead of shared,
   so a compound with no supporting laps shrinks its fuel effect to the
   prior's zero instead of inheriting another compound's slope. Added a
   second synthetic test proving this specific mechanism
   (`test_race_progress_does_not_leak_across_compounds_with_no_shared_evidence`)
   before re-checking real data.
5. Updated `src/apexmind/simulator.py` and `src/apexmind/decision_engine.py`
   to compute and pass `race_progress` through to the pace model. The
   decision engine's dynamic program required a real structural change,
   not just a plumbing change: pace can no longer be precomputed once as
   a function of tyre life alone, since it now also depends on the
   absolute lap (race progress resets tyre life does not), so the DP now
   recomputes the relevant pace table once per lap of the search instead
   of once for the whole race.
6. Updated `src/apexmind/cli.py`'s `_evaluate` and `_reference_race_stats`
   (shared by `simulate` and `decide`) to call `add_race_progress` per
   benchmark, using that benchmark's actual total lap count.
7. Updated 6 existing tests whose synthetic posteriors needed a
   `race_progress` (later `race_progress_<compound>`) column to keep
   matching the model's real feature layout, and added 5 new tests: two
   proving the confound and its fix on synthetic data with a known
   answer, one proving the fuel effect reaches `simulate_race`'s lap-time
   arithmetic, and two on the `add_race_progress` function itself. 66
   tests total, all passing; `ruff check` clean.
8. Re-ran `apexmind evaluate` and `apexmind decide` against real ingested
   data for all three benchmarks at every stage of this fix (original,
   shared-column, per-compound) rather than trusting the design reasoning
   alone, and only proceeded past each stage once the real numbers
   supported it.

## Result

Full numbers, including the before/shared/per-compound comparison table
and the honest discussion of what improved and what did not, are in
`docs/PACE_MODEL.md`'s "Second iteration" section and
`docs/DECISION_ENGINE.md`'s updated failure/result sections. Summary:

- `bahrain-2024` (this project's primary hold-out): MAE improved from
  1.173s to 0.642s against the model at the end of Phase 2 (baseline:
  1.182s) — roughly halving the error.
- `singapore-2023`: MAE improved from 1.183s to 1.115s, still clearly
  ahead of baseline (1.317s), though its interval calibration got
  measurably worse in the process — a real cost, not smoothed over.
- `dutch-2023`: the shared-column version's regression (MAE 13% worse
  than baseline) is repaired to statistically indistinguishable from
  baseline (2.691s vs. 2.688s), though RMSE there is still worse than
  baseline, continuing a difficulty this hold-out already had before any
  of this work.
- The decision engine's optimiser no longer needs its `max_stint_laps`
  safety bound to produce a credible answer on two of the three
  benchmarks (`bahrain-2024`: `MEDIUM×20/SOFT×37`; `singapore-2023`:
  `MEDIUM×21/SOFT×41`); `dutch-2023`'s plan (`MEDIUM×24/SOFT×48`) sits
  one lap under the bound, named as still the closest call of the three.

## Gate reassessment

This work does not reopen Gate B or Gate D's pass/fail status — both were
already assessed as met, with named limitations, before this fix began.
What changes is the content of those named limitations: the fuel/tyre
confound is resolved rather than merely contained, `singapore-2023`'s
calibration regression is a new item added to the tracked list, and
`dutch-2023`'s known difficulty is narrowed (MAE fixed, RMSE still open)
rather than eliminated. `docs/PACE_MODEL.md` and `docs/DECISION_ENGINE.md`
carry the current, authoritative version of each of these; this record is
the history of how they got there.

## Next action

Two items are now well-defined enough to be worth scheduling explicitly,
rather than left as generic "future work": `singapore-2023`'s calibration
regression (worth checking whether a heavier-tailed likelihood, already
named in `docs/PACE_MODEL.md` as an unimplemented refinement, addresses
both this and the pre-existing 50%/80% under-coverage at once), and
`dutch-2023`'s remaining RMSE gap (worth checking whether it is still
driven by a small number of large residuals, the same shape of problem
`remove_pace_outliers` was built to fix earlier in Phase 2). Neither
blocks Phase 5.
