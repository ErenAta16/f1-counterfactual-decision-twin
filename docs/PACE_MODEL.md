# Pace and Tyre Model — Phase 2 Research Record

**Status:** Implemented; exit criterion not yet met (see Calibration result)

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

## Result (2026-07-13, holdout: `bahrain-2024`)

| Metric | Naive baseline | Bayesian pace model |
|---|---:|---:|
| MAE (s) | 1.404 | 1.323 |
| RMSE (s) | 2.137 | 1.725 |
| CRPS (s) | — | 1.214 |

The model beats the naive baseline on both MAE and RMSE, on 988 held-out
laps trained from 1,822 laps across the other two races.

### Calibration

| Nominal interval | Observed coverage |
|---:|---:|
| 50% | 90.6% |
| 80% | 99.4% |
| 95% | 100.0% |

The intervals are **not calibrated** — they are systematically too wide.
The most likely cause: the model pools residual noise across all training
benchmarks into a single variance term, but `dutch-2023` (changing weather,
red flag, tyre-compound transitions) has far higher lap-time variance than
the calmer `bahrain-2024` dry control race (compound-level lap-time
standard deviation up to 6.81s in the Dutch data versus around 1–1.6s in
Bahrain). The shared noise term is dragged wide by the noisiest race in
training, producing falsely cautious intervals on a calmer test race.

### Exit criterion assessment

Phase 2's exit criterion is "confidence intervals are calibrated and
performance is not worse than the best simple baseline." Point-accuracy is
met; calibration is not. Per the risk mitigation already recorded in
`docs/PROJECT_PLAN.md` (pre-2026 patterns may not transfer cleanly, and
with only three benchmark races a held-out condition class has no matching
training example), this is treated as a real, open finding rather than
rounded up to "done." Candidate next steps, not yet implemented:

1. Estimate noise variance per condition class or per benchmark instead of
   pooling it, so a calm race is not penalised by a chaotic one.
2. Add more benchmark races per condition class so a held-out race always
   has at least one same-class training example.
3. Re-run the same evaluation with each benchmark held out in turn, not only
   Bahrain, to see whether the miscalibration direction is consistent.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe evaluate --holdout bahrain-2024 --data-dir D:\apexmind-data
```

Requires the three benchmarks to already be ingested (`apexmind ingest`).
Writes `evaluation/pace-model-holdout-<benchmark>.json` under the data
directory; nothing under the data directory belongs in Git.
