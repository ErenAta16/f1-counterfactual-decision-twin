# Progress Record 02 — Predictive Foundation

**Date:** 13 July 2026
**Status:** Implemented; Gate B not yet satisfied

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
6. Added unit tests for the feature filter, both baselines, the Bayesian
   model's posterior recovery and predictive-variance behaviour, and every
   evaluation metric, including known closed-form and reference-quantile
   checks.

## Result

Evaluated with Bahrain 2024 held out and both 2023 races as training data
(988 test laps, 1,822 training laps): the model's MAE (1.323s) and RMSE
(1.725s) both beat the naive baseline (1.404s / 2.137s). Its predictive
intervals are not calibrated — 50%, 80%, and 95% nominal intervals covered
90.6%, 99.4%, and 100.0% of held-out laps respectively, because residual
noise is currently pooled across benchmarks with very different variance
(the wet, red-flagged Dutch race inflates the shared noise term relative to
the calmer Bahrain test race). Full detail and candidate fixes are recorded
in `docs/DATA_FOUNDATION.md`'s sibling record, `docs/PACE_MODEL.md`.

## Gate B assessment

Gate B requires the pace/tyre model to beat or match simple baselines with
calibrated intervals. Point accuracy passes; calibration does not. Per this
project's own gated-roadmap rule, that is a real blocker, not a rounding
error, and Phase 3 should not begin until it is addressed or consciously
accepted with a documented justification.

## Next action

Address the pooled-noise calibration gap (see `docs/PACE_MODEL.md` for
candidate approaches), then re-run `apexmind evaluate` before deciding
whether Gate B is met and Phase 3 can begin.
