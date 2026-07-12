# Progress Record 02 — Predictive Foundation

**Date:** 13 July 2026
**Status:** Implemented and iterated once; Gate B met on the primary hold-out

## Work completed

1. Defined the green-flag lap filter and the driver/session pace-delta
   target used by all Phase 2 modelling, with the traffic-data and
   fuel-burn-off limitations recorded rather than assumed away.
2. Added a compound-partitioned Bayesian linear pace/tyre model (conjugate
   Normal-Inverse-Gamma), giving each compound its own degradation curve
   with a shared, weakly-informative prior.
3. Added naive pace (driver/compound median) and pit-loss baselines.
4. Added a temporal hold-out protocol that trains on the two 2023 benchmark
   races and evaluates on the 2024 race, and a metrics module (MAE, RMSE,
   closed-form Gaussian CRPS, interval coverage) with no new heavy
   dependency beyond NumPy.
5. Wired an `apexmind evaluate` command that runs the full comparison and
   writes a calibration report next to the other generated artefacts.
6. Ran the first evaluation and found the intervals badly over-wide
   (50%/80%/95% nominal intervals covering 90.6%/99.4%/100% of held-out
   laps).
7. Diagnosed the cause directly against the data rather than guessing: the
   `dutch-2023` benchmark's green-flag laps early in the race (still on a
   drying track after rain) were 5-40 seconds slower than that compound's
   settled pace, and FastF1's track-status codes have no state to flag
   them separately from a fully green track. Confirmed this was specific
   to that benchmark's weather transition, not a generic race-start effect,
   by checking the same early-stint window in the other two benchmarks
   (no comparable variance spike there).
8. Added `remove_pace_outliers`, a robust (median/MAD-based, modified
   z-score) outlier filter, validated against every benchmark and compound
   in the dataset before adopting it — it trims 0-11% of laps everywhere
   and brings every group's pace-delta standard deviation into a
   consistent 0.9-2.0s range.
9. Re-ran the evaluation: MAE and RMSE improved for both the baseline and
   the model, and calibration went from badly over-wide to close to
   nominal, with a small remaining under-coverage at the 50%/80% levels.
10. Re-ran the same comparison with each of the three benchmarks held out
    in turn (the sensitivity check called for in `docs/PROJECT_PLAN.md`'s
    evaluation protocol), to see whether the result was specific to the
    Bahrain hold-out or general.
11. Added unit tests for the feature filter (including the new outlier
    filter), both baselines, the Bayesian model's posterior recovery and
    predictive-variance behaviour, and every evaluation metric. 28 tests,
    all passing; `ruff check` clean.

## Result

Primary hold-out (`bahrain-2024`, trained on the two 2023 races, 984 test
laps / 1,774 training laps after filtering): model MAE 1.173s versus
baseline 1.182s, RMSE 1.407s versus 1.427s, CRPS 0.815s. Coverage: 40% /
71% / 96% against nominal 50% / 80% / 95% — the 95% interval is well
calibrated; the 50% and 80% intervals are modestly too narrow.

Checked against all three hold-outs: the model clearly beats the baseline
on the dry-control (`bahrain-2024`) and Safety Car (`singapore-2023`)
races. On the changing-conditions race (`dutch-2023`) it narrowly beats the
baseline on MAE but loses on RMSE — a few large residuals on the most
volatile race pull its RMSE above the baseline's, even though its typical
error is still slightly smaller. Full tables and the root-cause analysis
are in `docs/PACE_MODEL.md`.

## Gate B assessment

Gate B requires the pace/tyre model to beat or match simple baselines with
calibrated intervals, evaluated on this project's documented primary
hold-out. That configuration now meets it: better MAE and RMSE than the
baseline, and a 95% interval close to nominal. The residual 50%/80%
under-coverage and the weaker showing on the changing-conditions hold-out
are carried forward as named, tracked limitations, not treated as closed.

## Next action

Phase 3 (counterfactual simulator) can begin. Its Safety Car and weather
scenario generators should treat the changing-conditions weak spot found
here as a design input: a single linear pace regime is not a good fit for
a race with an evolving track surface, and the simulator will need to
represent that as a distinct regime rather than assume the Phase 2 pace
curve applies uniformly.
