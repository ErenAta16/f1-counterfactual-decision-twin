# Constrained Decision Engine — Phase 4 Research Record

**Status:** Implemented for v1 scope; Gate D met numerically on all three
benchmarks, with an important caveat on what the winning plan's shape
actually means

## Purpose

Phase 4 turns the Phase 2 pace model and Phase 3 simulator into something
that chooses a strategy rather than just comparing a fixed pair of examples:
search the legal candidate space, rank it, and check whether the result
beats fixed baselines by a statistically supported margin. This is also the
phase where an FIA sporting regulation is encoded and checked for the first
time — `docs/DATA_FOUNDATION.md` recorded the rule source in Phase 1 and
deferred the encoding until the candidate-strategy decision space existed.

## Encoded regulation

`src/apexmind/regulations.py` encodes Article B6.3.6 of the FIA 2026
Formula 1 Sporting Regulations, Section B, Issue 07 (25 June 2026): unless
intermediate or wet-weather tyres were used, a driver must use at least two
different dry-weather specifications during the race. The quoted article
text, retrieval URL and date, and a SHA-256 hash of the retrieved 99-page
regulation document are recorded in
`docs/regulations/tyre-compound-rule.md`, along with an explicit note on
the one sub-clause (the per-Grand-Prix "mandatory Race specification"
designation) this project's schema cannot check and therefore does not
claim to. This is the only sporting rule encoded in v1: it is the only one
this project's strategy representation — a named sequence of compound/lap
-count stints — has the state to verify.

## Optimiser: exact dynamic programming, not a heuristic

`src/apexmind/decision_engine.py`'s `optimise_strategies` searches the
dry-compound strategy space (`SOFT`, `MEDIUM`, `HARD` — see "Scope
decisions" below) by exact dynamic programming over
`(lap, current compound, current tyre life, dry compounds used so far)`.
The state space here is small enough (three compounds, at most one tyre
life per lap of the race, eight possible used-compound subsets) that exact
search is cheap and there is no reason to accept a heuristic's risk of
discarding a state that looks expensive now but is optimal later. Every
transition is either "stay on the current tyre one more lap" or "pit now,
switch to any dry compound"; a candidate only survives to the final ranking
if it used at least two different dry-weather compounds, which is the
Article B6.3.6 filter applied directly inside the search rather than as a
separate post-hoc pass. This also serves the roadmap's separate "candidate
-strategy generator" item: generating the legal candidate set and ranking
it are the same computation here, not duplicated work.

The DP scores every lap by the Phase 2 posterior **mean** pace delta only
— a deterministic planning simplification, not a claim of certainty. The
`apexmind decide` command re-evaluates the winning plan and the fixed
Phase 3 baseline plans through the full stochastic Monte Carlo simulator
afterwards (which does sample from the posterior, and can include the
declared Safety Car scenario), for the uncertainty-aware half of the
comparison this planning stage does not attempt.

## A real failure found during development, and its fix

An early, unbounded version of this search was run against the real
ingested `bahrain-2024` data and returned a technically legal but not
credible plan: 56 laps on `SOFT` and a 1-lap `HARD` stint purely to satisfy
the compound rule. Inspecting the fitted posterior directly explained why:
`tyre_life_SOFT`'s coefficient is slightly **negative** (-0.0154 s/lap) in
the model fit on all three benchmarks. This is not a claim that soft tyres
get faster with age — it is the tyre-age/fuel-burn confound
`docs/PACE_MODEL.md` already named as an open limitation ("the
`tyre_life` coefficient... should be read as pace change per lap of tyre
age and race progress combined, not as an isolated tyre-degradation
rate") showing up as a concrete, unwanted consequence for the first time.
An unbounded DP takes the posterior mean literally and extrapolates that
coefficient across a stint length far beyond anything the model was fit on
— the longest stint actually observed in the training data tops out at 49
laps of tyre life, not 56.

The fix, `optimise_strategies`'s `max_stint_laps` parameter, is the same
discipline Phase 3 already applies to the Safety Car case: do not use a
model outside the range of evidence it was fit on. `apexmind decide`
computes this bound from the actual training data (the longest tyre life
observed across every benchmark the posterior was fit on: 49 laps in this
dataset) rather than an arbitrary constant, and passes it to the search.

## Result after the fix, all three benchmarks (declared Safety Car scenario on, seed 42, 3000 draws)

| Reference benchmark | Optimiser's plan | vs 1-stop (medium/hard) | vs 2-stop (soft/soft/hard) |
|---|---|---:|---:|
| `bahrain-2024` (57 laps) | HARD×8 / SOFT×49 | +14.86s [+14.34, +15.39], significant | +45.53s [+44.99, +46.07], significant |
| `singapore-2023` (62 laps) | HARD×13 / SOFT×49 | +14.87s [+14.30, +15.44], significant | +60.48s [+59.88, +61.08], significant |
| `dutch-2023` (72 laps) | SOFT×49 / HARD×23 | +14.13s [+13.56, +14.71], significant | +55.50s [+54.94, +56.07], significant |

Figures are the mean paired advantage in total race time (positive = the
optimiser's plan is faster), with a 95% confidence interval computed from
the same paired Monte Carlo draws `run_monte_carlo` already produces
(common random numbers), via the new `paired_mean_difference_ci` in
`src/apexmind/evaluation.py`. In every case the interval excludes zero, so
Gate D's "statistically supported advantage" is met, and every ranked
candidate is legal by construction.

## What this result honestly means, and does not mean

The `SOFT` stint pins to the 49-lap bound in **all three** benchmarks, not
just one — this is a systematic property of the fitted model, not
benchmark-specific noise. Reading this as "run the softs almost the whole
race" would be a mistake: it is the search correctly exploiting a pace
model whose tyre-life coefficient for `SOFT` is confounded with fuel
burn-off and race progress, bounded only by the longest stint the model
has any evidence about at all. No car has actually run a 49-lap stint on
soft tyres in this benchmark set; the bound prevents extrapolation past 49
laps, but it does not — and could not, without inventing data — prove that
49 laps behaves the way the model predicts either.

What the result **does** show, credibly: given this project's own pace
model, an exhaustive legal search reliably beats both fixed example
strategies by tens of seconds, the margin is consistent across a dry race,
a Safety Car race, and a changing-conditions race, and every plan involved
is legal and reproducible. What it does **not** show: that a 49-lap soft
stint is good race strategy in reality. That gap traces directly back to
Phase 2's pace model, not to a bug in the search — the DP is doing exactly
what it was asked to do with the evidence available. Fixing the underlying
cause (separating tyre degradation from fuel burn-off, which
`docs/PACE_MODEL.md` already flagged as deferred pending a fuel-load
signal this project's data source does not currently provide) is carried
forward as a named risk, not closed here.

## Scope decisions and their limits

- **Dry compounds only.** `WET` has no supporting laps in this benchmark
  set (`docs/PACE_MODEL.md`), so the fitted model predicts no offset and
  no degradation for it — not because wet tyres are fast, but because
  there is nothing to estimate from. Searching wet-tyre strategies with
  that model would produce a confidently wrong answer, so `INTERMEDIATE`
  and `WET` are excluded from the search space (though `regulations.py`
  still recognises them as satisfying Article B6.3.6's wet-tyre exemption
  if a caller constructs such a strategy directly).
- **Single-car, matching Phase 3's scope.** The optimiser inherits Phase
  3's single-car simulator; it ranks strategies by total race time, not by
  finishing position, gaps, or overtaking risk.
- **No Safety Car in the planning stage.** The DP's expected-pace table
  comes from the green-flag-only Phase 2 posterior; Safety Car timing is
  not something a deterministic lap-by-lap plan can anticipate, and is
  only reintroduced in the Monte Carlo comparison stage afterward.
- **One rule encoded, not the full regulation document.** See
  `docs/regulations/tyre-compound-rule.md` for exactly what Article
  B6.3.6 says and which parts of it are and are not checked.

## Reproducing this result

```powershell
.\.venv\Scripts\apexmind.exe decide --reference-benchmark bahrain-2024 --n-simulations 3000 --seed 42 --data-dir D:\apexmind-data
```

Requires the three benchmarks to already be ingested (`apexmind ingest`).
Writes `decision/decision-<benchmark>.json` under the data directory;
nothing under the data directory belongs in Git. Reproducibility was
checked directly: two separate process invocations with the same seed
produced byte-identical console output.

## Exit criterion assessment

Phase 4's exit criterion is "no illegal strategies and a statistically
supported advantage in the defined simulation benchmark." No illegal
strategy can leave `optimise_strategies` by construction (Article B6.3.6
is a hard filter inside the search, verified again by
`is_legal_strategy` before a candidate is returned), and every baseline is
also checked and confirmed legal before comparison. The statistical
advantage is met on all three benchmarks with 95% confidence intervals
excluding zero. This is treated as meeting the exit criterion for v1
scope, with the pace-model confound described above carried forward as a
named, tracked risk rather than a closed question — consistent with how
Phase 2's own calibration gap was carried forward into Phase 3.
