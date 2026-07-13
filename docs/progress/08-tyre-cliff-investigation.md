# Progress Record 08 — Investigating a Non-Linear ("Cliff") Degradation Term

**Date:** 13 July 2026
**Status:** Investigated with a proper held-out test; not adopted — the evidence does not support it at this project's data volume, and that conclusion is itself the useful result

## Why this record exists

A July 2026 paper on a production F1 strategy system (*Pitwall*, described
in this project's `README.md` "Related work" section) reports mining
37 circuit-compound-specific non-linear degradation "cliffs" from 8,278
real stints (191k laps) rather than assuming a smooth functional form.
This project's pace model (`src/apexmind/pace_model.py`) is linear in
tyre life by design (documented as a deliberate simplicity choice in
that module's docstring). Given a finding like Pitwall's from a much
larger corpus, it was worth checking directly, on this project's own
three benchmarks, whether the same kind of non-linearity is present and
detectable — rather than assuming either that it must be there or that
it can't be, on priors alone.

## Method

1. Fit the existing linear model on all three benchmarks pooled (the
   same design `apexmind decide`/`apexmind simulate` use) and binned the
   in-sample residuals by 5-lap tyre-life buckets, per compound.
2. Computed the correlation between tyre life and residual separately
   **per benchmark, per compound** (not pooled) — pooling across
   benchmarks with different track characteristics and stint-length
   distributions would average out exactly the kind of localised,
   circuit-specific effect Pitwall reports.
3. For the one clear signal that surfaced (below), fit an explicit
   quadratic tyre-life term and re-ran this project's own established
   evaluation protocol — `temporal_holdout_split`, train on two
   benchmarks, test on the third — for **all three** hold-out
   configurations, comparing MAE/RMSE against the current linear model.
   This step is the one that matters: an in-sample residual pattern is
   not evidence a model change will generalise, and this project's own
   history (`docs/PACE_MODEL.md`'s "Fourth iteration") already has one
   example of a plausible-looking pattern that turned out to have a
   different cause entirely.

## What the data showed

Step 1-2 surfaced one real signal: `bahrain-2024`'s `SOFT` and `HARD`
compounds both show a smooth, monotonically increasing in-sample
residual as tyre life grows (`SOFT`: -0.27s at 0-5 laps &rarr; +1.32s at
20+ laps; `HARD`: -0.46s &rarr; +0.48s), with correlations of +0.62 and
+0.48 respectively between tyre life and residual. Bahrain is a
well-known abrasive circuit, so a real, accelerating degradation curve
there is physically plausible. `singapore-2023` and `dutch-2023` did not
show a comparable pattern (correlations near zero, or, for
`dutch-2023 HARD`, a large negative correlation from only 37 laps —
too little data to mean anything on its own).

Step 3 is where this got resolved. Adding a quadratic tyre-life term
and testing it the way this project tests everything else:

| Hold-out | Linear MAE / RMSE | Quadratic MAE / RMSE |
|---|---:|---:|
| `bahrain-2024` | 0.606 / 0.774 | 0.644 / 0.821 (worse) |
| `singapore-2023` | 1.046 / 1.321 | 1.065 / 1.344 (worse) |
| `dutch-2023` | 2.724 / 4.420 | 2.534 / 4.364 (better) |

The quadratic term only helps on the one hold-out (`dutch-2023`) that
already has a separately diagnosed, unrelated cause for its RMSE gap
(`docs/progress/07-dutch-2023-rmse-diagnosis.md` — zero `INTERMEDIATE`
training data in that split), so that improvement is not trustworthy
evidence for a general tyre-cliff effect either. On the two hold-outs
without a confound, the quadratic term makes held-out accuracy worse.
The `bahrain-2024` in-sample pattern from step 2 did not survive being
tested out-of-sample: a term fit from `singapore-2023` and `dutch-2023`
does not predict `bahrain-2024`'s degradation shape any better than the
existing linear one.

## Conclusion

Not adopted. This project's three benchmarks (roughly 2,700 laps total
after filtering) are around two orders of magnitude smaller than the
corpus Pitwall mined its cliffs from; the held-out test above is
consistent with that gap being the reason, not with non-linear
degradation being physically absent. The honest conclusion is a
data-volume limit, not a settled fact about tyre physics — recorded
here specifically so a future contributor with more benchmark data
does not have to re-run this same check from zero, and does not
mistake the `bahrain-2024` in-sample correlation for evidence on its
own without re-checking it out-of-sample first.

## Next action

`CONTRIBUTING.md`'s "a fourth historical benchmark" good-first-issue is
the direct prerequisite for revisiting this: with a fourth or fifth
race, particularly another abrasive circuit, the `bahrain-2024`-only
signal found here would either replicate (worth adding) or stay
isolated (confirms it was noise). Re-running this exact held-out
comparison is the right first step once that data exists, rather than
re-deriving the method from scratch.
