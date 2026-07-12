# Pace and Tyre Model — Phase 2 Research Record

**Status:** Implemented and iterated once; exit criterion met for the primary hold-out, with a documented residual gap on the hardest condition class

## Purpose

Phase 2 turns the Phase 1 lap-state evidence into a first pace/tyre model:
predict a driver's pace as a function of tyre compound and tyre age, with an
honest uncertainty interval, and check whether that model is worth using at
all by comparing it against a naive baseline on a race it never trained on.

## Scope decisions and their limits

- **"Green-flag", not "clean-air".** The ingested schema (Phase 1) has no
  gap-to-car-ahead field, so this phase cannot isolate true traffic-free
  pace. "Green-flag" here means track status `1`, off the in/out lap,
  provider-flagged accurate, not deleted. Safety Car, VSC, and red-flag laps
  are excluded from the model rather than misrepresented as normal pace.
- **Modelling target is a pace delta, not raw lap time.** Raw lap time is
  dominated by circuit length and layout. A model trained on Singapore and
  the Dutch circuit and evaluated on Bahrain would otherwise be fit mostly to
  which track it saw, not to tyre behaviour. Every lap's target is instead
  `lap_time_seconds - driver_session_baseline`, where the baseline is the
  10th percentile of that driver's own green-flag lap times in that session.
- **Tyre age and fuel burn-off are confounded.** Both correlate with lap
  number, and the source data carries no fuel-load signal. The `tyre_life`
  coefficient in this model should be read as "pace change per lap of tyre
  age and race progress combined," not as an isolated tyre-degradation rate.
- **Weather is captured only indirectly, through compound choice.** Directly
  joining the separate weather table to individual laps requires
  reconstructing an approximate cumulative session time per lap (summing lap
  times, which is itself an approximation once pit stops and Safety Car
  laps are involved). That join is deferred rather than built on a shaky
  time-alignment assumption; a driver's choice of intermediate or wet tyres
  is used as a proxy for wet conditions in the meantime.
- **A robust outlier filter removes laps run on an evolving track surface.**
  See "Calibration fix" below: green-flag laps early in a session that was
  still drying after rain behave nothing like settled tyre-degradation
  laps, and FastF1's track-status codes have no state to flag them
  separately. `remove_pace_outliers` drops laps whose pace delta is a
  robust statistical outlier (modified z-score, threshold 3.5) within its
  own benchmark/session/compound group.

## Model

A conjugate Bayesian linear regression, one intercept and one tyre-life
slope per compound (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`), fit
with a Normal-Inverse-Gamma prior. The prior is weakly informative
(coefficient standard deviation 5 seconds, centred on zero), so a compound
with no supporting laps in training — `WET` in this benchmark set — predicts
no offset and no degradation instead of extrapolating from nothing. The
posterior and posterior predictive distribution are both closed-form; no
sampling-based inference library is required for this stage. The predictive
distribution is technically Student-t, but with the lap counts available
here the degrees of freedom run into the hundreds, so it is well
approximated by a Normal distribution.

## Naive baselines

- **Pace baseline:** predict a lap's pace delta as the median seen for that
  driver and compound in training, falling back to a compound-wide median
  and then a training-wide median for unseen combinations.
- **Pit-loss baseline:** for each pit event, compare the in-lap and out-lap
  time against the driver's median green-flag pace in that session, then
  report the median of that excess, doubled, per benchmark. This is a
  descriptive statistic — it does not separate pit-lane transit time from
  in/out-lap pace loss — kept as a starting reference for Phase 3.

## Temporal hold-out protocol

Random or per-lap splitting would leak information, since laps in the same
stint are highly autocorrelated. The evaluation instead holds out one entire
benchmark race and trains only on the others. The default split trains on
the two 2023 races (Singapore, Dutch) and tests on the 2024 race (Bahrain):
training on the past to predict an unseen future race, matching how the
model would actually be used.

## First result (2026-07-13, holdout: `bahrain-2024`, before the calibration fix)

| Metric | Naive baseline | Bayesian pace model |
|---|---:|---:|
| MAE (s) | 1.404 | 1.323 |
| RMSE (s) | 2.137 | 1.725 |
| CRPS (s) | — | 1.214 |

The model beat the naive baseline on both MAE and RMSE, but its predictive
intervals were badly over-wide: the 50%, 80%, and 95% nominal intervals
covered 90.6%, 99.4%, and 100.0% of held-out laps.

### Root cause

Green-flag laps (track status `1`) early in the `dutch-2023` benchmark were
run while the track was still drying after rain. FastF1's track-status
codes have no distinct "damp/evolving" state, so these laps pass the
green-flag filter looking identical to a settled, dry racing lap, even
though some were 5 to 40 seconds slower than that compound's normal pace.
Inspecting the data directly (`docs/progress/02-predictive-foundation.md`
records the diagnostic session) showed this was concentrated in the first
lap of stint 1 through roughly lap 10 of that specific race, and the same
pattern did **not** appear in the equivalent early-stint laps of the other
two benchmarks — ruling out a generic "race start" effect and pointing at
`dutch-2023`'s actual weather transition. Left in, these laps inflated that
benchmark's SOFT-compound pace-delta standard deviation from about 1.1s to
6.7s, and the model's pooled noise term inherited that inflation for every
prediction, regardless of which race was being predicted.

## Calibration fix

`remove_pace_outliers` (`src/apexmind/pace_features.py`) drops laps whose
pace delta is a robust statistical outlier — modified z-score above 3.5,
computed with the median and MAD (median absolute deviation) rather than
the mean and standard deviation, so a handful of extreme laps cannot skew
the threshold that is used to exclude them. It is applied per
benchmark/session/compound group, not hand-tuned to `dutch-2023`: checked
against every benchmark and compound in this dataset, it removes 0-11% of
laps and brings every group's standard deviation into a consistent
0.9-2.0s range (`dutch-2023` SOFT: 6.7s to 1.1s; every other group changed
by a few hundredths to a few tenths of a second).

## Result after the fix (holdout: `bahrain-2024`)

| Metric | Naive baseline | Bayesian pace model |
|---|---:|---:|
| MAE (s) | 1.182 | 1.173 |
| RMSE (s) | 1.427 | 1.407 |
| CRPS (s) | — | 0.815 |

| Nominal interval | Observed coverage |
|---:|---:|
| 50% | 39.9% |
| 80% | 71.0% |
| 95% | 95.6% |

The 95% interval is now close to nominal. The 50% and 80% intervals are
modestly too narrow (under-coverage rather than the earlier severe
over-coverage) — the opposite failure mode, and a much smaller one. This
pattern (good tail coverage, tight-but-slightly-overconfident inner
quantiles) is consistent with residuals that are somewhat more
sharply-peaked than the model's Normal-likelihood assumption; a Student-t
or other heavy-tailed likelihood is the natural next refinement, not yet
implemented.

## Robustness across all three hold-outs

Re-running the same evaluation with each benchmark held out in turn (a
sensitivity check called for directly in `docs/PROJECT_PLAN.md`'s evaluation
protocol):

| Holdout | Condition class | Baseline MAE / RMSE | Model MAE / RMSE | Coverage 50/80/95% |
|---|---|---:|---:|---|
| `bahrain-2024` | dry control | 1.182 / 1.427 | 1.173 / 1.407 | 40% / 71% / 96% |
| `singapore-2023` | Safety Car | 1.317 / 1.599 | 1.183 / 1.464 | 38% / 71% / 92% |
| `dutch-2023` | changing conditions | 2.688 / 3.872 | 2.652 / 4.370 | 59% / 81% / 99% |

The model clearly beats the baseline on both metrics for the dry-control and
Safety Car hold-outs. On the changing-conditions hold-out it barely beats
the baseline on MAE and loses on RMSE — a handful of large errors on the
hardest, most volatile race pull its RMSE up, even though its typical
(median-driven MAE) error is still slightly better than the baseline's.
Its coverage is, on the other hand, the closest to nominal of the three.
This is read as an honest limitation rather than smoothed over: a linear,
single-regime pace model is a reasonable fit for calmer races and a weaker
one for a race with rain, a red flag, and tyre-compound transitions in it —
exactly the scenario Phase 3's scenario generators will need to represent
explicitly rather than assume away.

### Exit criterion assessment

Phase 2's exit criterion is "confidence intervals are calibrated and
performance is not worse than the best simple baseline," evaluated on this
project's primary, documented hold-out (`bahrain-2024`, training on the two
2023 races). On that configuration: the model beats the baseline on MAE and
RMSE, and its 95% interval is well calibrated with a modest, documented
under-coverage gap at the 50% and 80% levels. This is treated as meeting
the exit criterion well enough to proceed, with the residual calibration
gap and the changing-conditions weak spot both carried forward as named,
tracked limitations rather than closed questions.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe evaluate --holdout bahrain-2024 --data-dir D:\apexmind-data
```

Requires the three benchmarks to already be ingested (`apexmind ingest`).
Writes `evaluation/pace-model-holdout-<benchmark>.json` under the data
directory; nothing under the data directory belongs in Git.
