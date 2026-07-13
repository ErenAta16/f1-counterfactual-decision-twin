# Constrained Decision Engine — Phase 4 Research Record

**Status:** Implemented for v1 scope; Gate D met on all three benchmarks
with credible, non-degenerate winning plans, after a root-cause fix to the
pace model described below

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

## A real failure found during development, and its root-cause fix

An early, unbounded version of this search was run against the real
ingested `bahrain-2024` data and returned a technically legal but not
credible plan: 56 laps on `SOFT` and a 1-lap `HARD` stint purely to satisfy
the compound rule. Inspecting the fitted posterior directly explained why:
`tyre_life_SOFT`'s coefficient was slightly **negative** (-0.0154 s/lap) in
the model fit on all three benchmarks. This was not evidence that soft
tyres get faster with age — it was the tyre-age/fuel-burn confound
`docs/PACE_MODEL.md` had already named as an open limitation ("the
`tyre_life` coefficient... should be read as pace change per lap of tyre
age and race progress combined, not as an isolated tyre-degradation
rate") showing up as a concrete, unwanted consequence for the first time.

The first response, shipped in an earlier version of this record, was a
`max_stint_laps` bound: refuse to plan a stint longer than the longest one
actually observed in training. That was a reasonable safety net, but it
only contained the symptom — every benchmark's optimal `SOFT` stint still
pinned to exactly that bound, meaning the search was still trying to run
soft tyres as long as the cap would legally allow. The actual fix required
going back into `docs/PACE_MODEL.md`'s pace model itself: adding a
per-compound `race_progress` covariate (`add_race_progress`,
`build_pace_feature_matrix`) that lets the model separate a car getting
faster from fuel burn-off (which does not reset at a pit stop) from a
tyre getting slower with age (which does). Full detail, including a second
bug this fix exposed and fixed, is in `docs/PACE_MODEL.md`'s "Second
iteration" section.

With that fix in place, `tyre_life_SOFT`'s coefficient recovers to +0.0115
s/lap — positive and physically ordered against `tyre_life_MEDIUM`
(+0.036) and `tyre_life_HARD` (+0.049) — and the `max_stint_laps` bound,
still kept in place as defence in depth (the same "do not extrapolate past
the evidence" discipline Phase 3 applies to Safety Car laps), is no longer
what the optimiser's chosen plans are pinned against on two of the three
benchmarks. `optimise_strategies`'s `max_stint_laps` parameter still
exists and is still computed from the longest tyre life actually observed
in training, but it is now a safety margin rather than the thing shaping
the answer.

## Result after the fix, all three benchmarks (declared Safety Car scenario on, seed 42, 3000 draws)

| Reference benchmark | Optimiser's plan | vs 1-stop (medium/hard) | vs 2-stop (soft/soft/hard) |
|---|---|---:|---:|
| `bahrain-2024` (57 laps) | MEDIUM×20 / SOFT×37 | +13.74s [+13.31, +14.17], significant | +37.76s [+37.35, +38.17], significant |
| `singapore-2023` (62 laps) | MEDIUM×21 / SOFT×41 | +16.64s [+16.16, +17.13], significant | +54.22s [+53.78, +54.67], significant |
| `dutch-2023` (72 laps) | MEDIUM×24 / SOFT×48 | +23.49s [+23.01, +23.97], significant | +50.52s [+50.08, +50.96], significant |

Figures are the mean paired advantage in total race time (positive = the
optimiser's plan is faster), with a 95% confidence interval computed from
the same paired Monte Carlo draws `run_monte_carlo` already produces
(common random numbers), via `paired_mean_difference_ci` in
`src/apexmind/evaluation.py`. In every case the interval excludes zero, so
Gate D's "statistically supported advantage" is met, and every ranked
candidate is legal by construction.

## What this result honestly means, and does not mean

`bahrain-2024` and `singapore-2023`'s optimal plans (37 and 41 laps on
`SOFT` out of 57 and 62 total) no longer touch the `max_stint_laps` bound
at all — a genuinely different, more credible result than before, not
just a smaller version of the same artifact. `dutch-2023`'s plan (48 laps
on `SOFT`) sits one lap under its 49-lap bound, which is worth naming
rather than glossing over: it is closer to the boundary than the other
two, consistent with `docs/PACE_MODEL.md`'s finding that `dutch-2023`
remains this project's hardest hold-out even after the fix.

A 37-to-48-lap single stint on soft tyres is still longer than real F1
strategy typically runs a soft tyre, and that gap has an honest
explanation rather than a hidden one: `tyre_life_SOFT`'s fitted
degradation slope (+0.0115 s/lap) is small in absolute terms, a
characteristic `docs/PACE_MODEL.md` already flagged before Phase 4 began
("the current pace model's still-modest degradation slopes"). Fixing the
fuel/tyre confound corrected the *sign* and the *attribution* of that
coefficient — the search no longer profits from a spurious negative slope
— but it did not, and could not without more or better data, change the
underlying fact that a linear, single-regime model fit to this benchmark
set finds only a modest degradation signal. That is a separate, smaller,
already-named limitation carried forward, not a new one this fix
introduced.

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
excluding zero, and — unlike the version of this record shipped before the
fuel/tyre confound fix — the winning plans are no longer a known model
artifact stretched to a safety boundary on every benchmark. This is
treated as meeting the exit criterion for v1 scope. The still-modest
`SOFT` degradation slope and `dutch-2023`'s persistent difficulty are
carried forward as named, tracked limitations rather than closed
questions — consistent with how Phase 2's own calibration gap was carried
forward into Phase 3.
