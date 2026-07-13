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

## Second iteration: separating fuel burn-off from tyre wear

Everything above describes the model as it stood at the end of Phase 2.
This section records a substantial follow-up fix, made during Phase 4
development, to a limitation Phase 2 had already named but not yet
addressed: "Tyre age and fuel burn-off are confounded... The `tyre_life`
coefficient in this model should be read as pace change per lap of tyre
age and race progress combined, not as an isolated tyre-degradation rate."

### What made it concrete

Phase 4's decision-engine optimiser (`docs/DECISION_ENGINE.md`) searches
for the strategy with the lowest expected race time, which means it will
find and exploit any part of the pace model that is wrong, not just the
parts that happen not to matter. Run against real data, it found one: the
fitted `tyre_life_SOFT` coefficient was slightly **negative** (-0.0154
s/lap) — the model believed soft tyres got faster with age. Chasing that
down to its source confirmed the confound directly rather than leaving it
as a hypothesis: `tyre_life` and lap number are highly correlated within
any single stint (a stint's tyre life is, by definition, laps since that
stint's pit stop), and a car really does get faster over a race as fuel
burns off, so a model with no separate fuel term has no way to avoid
attributing some of that "faster over time" signal to whichever compound
happens to be run.

### The fix, and a second bug it exposed

The fix a Bayesian linear model can actually use is a new covariate that
is structurally different from `tyre_life`: `race_progress`
(`lap_number / session_total_laps`, via `add_race_progress` in
`pace_features.py`). The key property is that `tyre_life` resets to 1 at
every pit stop, but `race_progress` does not — it climbs monotonically
across the whole session regardless of how many stops a driver makes.
Across a pooled dataset where different drivers pit at different laps,
that difference in *when* each variable resets is what lets a linear
model identify a fuel-burn slope separately from a tyre-degradation slope,
rather than folding both into one number.

The first version added `race_progress` as a single column shared across
every compound — physically reasonable, since fuel burn-off is a property
of the car, not the tyre. It measurably worked on two of three hold-outs
(see the table below), but it introduced a second, distinct bug: this
benchmark set's two dry-only races (`bahrain-2024`, `singapore-2023`)
contain zero `INTERMEDIATE` or `WET` laps between them, so a *shared*
race-progress term is estimated entirely from dry-compound evidence and
then applied, with no shrinkage at all, to `INTERMEDIATE` laps in the
`dutch-2023` hold-out evaluation that it was never fit on. The consequence
was concrete and large: the model's single worst residuals on that
hold-out were all `INTERMEDIATE` laps at lap 67 (race progress ≈0.93,
shortly after that race's red-flag restart), where a shared fuel-burn term
learned from bone-dry racing predicted the car should be getting
*faster*, while the real laps were 11-18 seconds slower than predicted.

The fix for this second bug follows the same pattern already used
everywhere else in this feature layout: make `race_progress` per-compound
(`race_progress_SOFT`, `race_progress_MEDIUM`, ...), exactly like
`tyre_life` already is. A compound with no supporting laps in training
now shrinks its fuel-effect coefficient back toward the weakly-informative
prior's zero, the same protection `compound_WET`'s intercept and slope
already had. Both bugs, and the fix for each, are reproduced directly on
synthetic data with a known answer in
`tests/test_pace_features.py::test_race_progress_separates_fuel_effect_from_tyre_wear`
and `::test_race_progress_does_not_leak_across_compounds_with_no_shared_evidence`.

### Result

| Holdout | Baseline MAE / RMSE | Original model | + shared race_progress | + per-compound race_progress |
|---|---:|---:|---:|---:|
| `bahrain-2024` | 1.182 / 1.427 | 1.173 / 1.407 | 0.726 / 0.909 | **0.642 / 0.817** |
| `singapore-2023` | 1.317 / 1.599 | 1.183 / 1.464 | 0.966 / 1.245 | **1.115 / 1.420** |
| `dutch-2023` | 2.688 / 3.872 | 2.652 / 4.370 | 3.049 / 5.190 | **2.691 / 4.379** |

| Holdout | Coverage 50/80/95% (original) | Coverage 50/80/95% (per-compound fix) |
|---|---|---|
| `bahrain-2024` | 40% / 71% / 96% | 66% / 93% / 99% |
| `singapore-2023` | 38% / 71% / 92% | 35% / 58% / 79% |
| `dutch-2023` | 59% / 81% / 99% | 45% / 73% / 89% |

Read honestly, not selectively: the per-compound fix is a clear win on the
project's primary hold-out (`bahrain-2024`, MAE down 45% from the original
model, RMSE down 42%) and still beats baseline clearly on `singapore-2023`.
It repairs the shared-column version's `dutch-2023` regression (MAE was
13% worse than baseline with a shared column; it is now statistically
indistinguishable from baseline) without fully solving that hold-out's
known difficulty — RMSE there is still worse than baseline, continuing the
pattern already named above. It is not a uniform improvement: coverage
calibration on `singapore-2023` is now noticeably worse than before
(further under nominal at every level, the falsely-confident failure mode
this project's honesty commitments care about most), a genuine cost of
this change that is recorded here rather than left out because the
headline accuracy numbers improved. `bahrain-2024`'s coverage moved from
slightly under-covered to somewhat over-covered — a safer direction to err
in, but not the calibration this project would call finished.

The fitted coefficients on the full three-benchmark dataset support the
diagnosis directly: `tyre_life_SOFT` is now +0.0115 s/lap (previously
-0.0154), and `tyre_life_MEDIUM`/`tyre_life_HARD` are +0.036 and +0.049
s/lap respectively — all now positive and physically ordered, consistent
with real tyre-degradation behaviour instead of an artifact. The shared
fuel effect recovered for dry compounds is close to -3 to -3.8 seconds
across a full race distance (a plausible order of magnitude for F1 fuel
burn-off), while `INTERMEDIATE`'s fuel-effect coefficient, now estimated
from its own (limited, single-race) evidence rather than inheriting the
dry-compound value, comes out much smaller in magnitude, as the far
smaller sample size would suggest it should.

### Exit criterion assessment

Phase 2's exit criterion is "confidence intervals are calibrated and
performance is not worse than the best simple baseline," evaluated on this
project's primary, documented hold-out (`bahrain-2024`, training on the two
2023 races). On that configuration the model now beats the baseline by a
substantially larger margin than at the end of Phase 2 (MAE roughly halved
relative to baseline), and its coverage, while imperfect, errs toward
over-caution rather than false confidence. This is treated as continuing
to meet the exit criterion, with three specific, named items carried
forward rather than closed: the `singapore-2023` calibration regression
introduced by this fix, `dutch-2023`'s persistent RMSE weakness, and the
still-unimplemented heavier-tailed-likelihood refinement noted above.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe evaluate --holdout bahrain-2024 --data-dir D:\apexmind-data
```

Requires the three benchmarks to already be ingested (`apexmind ingest`).
Writes `evaluation/pace-model-holdout-<benchmark>.json` under the data
directory; nothing under the data directory belongs in Git.
