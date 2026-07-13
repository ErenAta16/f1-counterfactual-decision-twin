# Progress Record 07 — Diagnosing `dutch-2023`'s RMSE Gap

**Date:** 13 July 2026
**Status:** Diagnosed precisely; not a bug, and not fixable without new data — documented as such rather than left as an unexplained negative number

## Why this record exists

`docs/progress/06-safety-car-restart-lap-fix.md`'s "Next action" named
`dutch-2023`'s persistent RMSE weakness as the next open item, with a
specific hypothesis to check: whether it was still driven by a small
number of large residuals, the same shape of problem the original Phase
2 outlier fix addressed. That hypothesis turned out to be half right —
the RMSE gap is driven by a small subset of laps, but not because they
are statistical outliers.

## Work completed

1. Applied the same worst-residual inspection method used for both prior
   fixes to `dutch-2023`'s hold-out residuals. The top 5 laps by squared
   error (0.5% of the test set) contributed 5.8% of total squared error;
   the top 50 (5.4%) contributed 39.2% — a genuinely concentrated error
   distribution, worth investigating further rather than accepting as
   generic noise.
2. Found the concentrated laps were almost entirely `INTERMEDIATE`
   -compound, in two clusters: laps 3-4 (still-wet opening laps) and lap
   67 (after the race's red-flag restart) — not a single mechanism like
   the two fixes before this one.
3. Checked whether these were true statistical outliers within their own
   compound group (the same question the original `remove_pace_outliers`
   filter answers) by inspecting every `INTERMEDIATE` lap's pace delta by
   stint, not just the worst few: every stint already averages 7-10
   seconds off the dry-compound baseline, with a moderate 1.6-2.7s
   within-stint standard deviation. Conclusion: these are not outliers
   to filter. The entire `INTERMEDIATE` category behaves this way.
4. Traced the mechanism: `bahrain-2024` and `singapore-2023` — the only
   two benchmarks in `dutch-2023`'s training set — contain zero
   `INTERMEDIATE` or `WET` laps between them, so those coefficients sit
   at the weakly-informative prior's default whenever `dutch-2023` is
   held out. This is the same "no evidence, no extrapolation" behaviour
   already relied on for `WET` throughout this project, showing up as a
   cost rather than a safety feature in this specific evaluation.
5. Added `metrics_by_compound_class` to `src/apexmind/evaluation.py` and
   wired it into `apexmind evaluate`'s report and console output, so this
   distinction is a permanent, reusable diagnostic rather than a one-off
   script's finding. Confirmed on real data that `bahrain-2024` and
   `singapore-2023` correctly show only a "dry" row (they have no
   `INTERMEDIATE`/`WET` laps at all), and `dutch-2023` shows both.
6. Added 2 new tests for the new function. 86 tests total, all passing;
   `ruff check` clean.

## Result

| Compound class | Share of `dutch-2023` laps | Baseline MAE / RMSE | Model MAE / RMSE |
|---|---:|---:|---:|
| Dry | 79% (735 laps) | 1.408 / 1.657 | 1.033 / 1.244 |
| `INTERMEDIATE`/`WET` | 21% (192 laps) | 7.704 / 7.949 | 9.197 / 9.403 |

On dry compounds — 79% of this hold-out, and everything Phase 4's
strategy decisions are actually made of — the model beats baseline by
roughly the same margin it does on every other benchmark. The pooled
"worse than baseline" headline comes entirely from the 21% of laps on a
compound this training split has no way to have learned. Full detail in
`docs/PACE_MODEL.md`'s "Fourth iteration" section.

## What this is not

This is not a fix, and is not presented as one. No code change makes the
model perform better on `INTERMEDIATE` in this holdout configuration
without either inventing training data that does not exist or breaking
the hold-out by leaking `dutch-2023`'s own wet-weather laps into its own
training set. The value here is diagnostic: `dutch-2023`'s RMSE gap is
now a precisely understood, correctly attributed, and honestly
unfixable-without-new-data limitation, rather than an unexplained
negative number sitting next to two real, fixed bugs.

## Next action

The one item from `docs/TECHNICAL_REPORT.md`'s unresolved list with a
plausible, scoped path forward is `singapore-2023`'s residual
calibration gap (still under nominal coverage at every level after the
Safety Car restart-lap fix). A Student-t or other heavier-tailed
likelihood remains the most-named, not-yet-attempted lever for it. This
project's core roadmap (Phases 0-5) remains complete for v1 scope
regardless of whether that item is picked up next.
