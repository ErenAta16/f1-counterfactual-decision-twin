# Progress Record 06 — Safety Car Restart-Lap Fix

**Date:** 13 July 2026
**Status:** Fixed and verified against real data; a real, checkable second cause of `singapore-2023`'s calibration regression, found and partially resolved

## Why this record exists

`docs/TECHNICAL_REPORT.md` named `singapore-2023`'s calibration
regression (introduced by the Phase 2 fuel/tyre confound fix,
`docs/progress/05-fuel-tyre-confound-fix.md`) as an open, unresolved
item. Rather than leaving it as a known limitation, it was investigated
directly — the same discipline this project has applied to every
previous named gap.

## Work completed

1. Fit the current (per-compound race-progress) pace model on the
   `singapore-2023` hold-out and inspected the worst individual
   residuals directly, rather than only looking at aggregate error.
   Five of the ten largest residuals were the same lap: lap 23,
   immediately after the real race-control message `SAFETY CAR IN THIS
   LAP` on lap 22.
2. Checked this against the *full* green-flag lap set, not just the
   worst residuals, to rule out coincidence: lap 23's mean pace delta
   was 4.5 seconds across 17 of the field's roughly 20 drivers, against
   a benchmark-wide green-flag average of 1.7 seconds. Checked the same
   pattern in `dutch-2023` (its Safety Car restart lap, lap 22, averaged
   3.2 seconds against 1.6-1.9 seconds for the settled laps immediately
   after it) and checked that a Virtual Safety Car ending does *not*
   show the same effect (`singapore-2023`'s VSC restart lap averaged
   -0.4 seconds) — a physically sensible distinction, since a VSC
   involves no physical bunching behind a pace car and no rolling
   restart, while a Safety Car does.
3. Added `exclude_safety_car_restart_laps` to `src/apexmind/pace_features.py`:
   drops the lap immediately following a Safety Car (not VSC) episode's
   end, identified from the same real race-control evidence
   `extract_safety_car_episodes` already parses for Phase 3. Wired into
   the same per-benchmark pipeline `_evaluate` and `_reference_race_stats`
   (shared by `simulate`/`decide`) already use for
   `remove_pace_outliers` and `add_race_progress`.
4. Added 3 new tests, including one that reproduces the real distinction
   found in step 2 directly: an SC restart lap gets dropped, a VSC
   restart lap does not. 84 tests total, all passing; `ruff check`
   clean.
5. Re-ran `apexmind evaluate` and `apexmind decide` against real
   ingested data for all three benchmarks before writing up any result,
   matching this project's standing practice of confirming a fix against
   real data rather than trusting the reasoning alone.

## Result

| Holdout | MAE (before &rarr; after) | RMSE (before &rarr; after) | Coverage 95% (before &rarr; after) |
|---|---|---|---|
| `bahrain-2024` | 0.642 &rarr; 0.606 | 0.817 &rarr; 0.774 | 99% &rarr; 99% |
| `singapore-2023` | 1.115 &rarr; 1.046 | 1.420 &rarr; 1.321 | 79% &rarr; 81% |
| `dutch-2023` | 2.691 &rarr; 2.724 | 4.379 &rarr; 4.420 | 89% &rarr; 87% |

`bahrain-2024` improved further; `singapore-2023`'s point accuracy and
calibration both improved, though calibration is still meaningfully
under nominal (81% observed against a 95% target) — this fix narrowed
the second-iteration regression, it did not eliminate it. `dutch-2023`
moved by about 1% in mixed directions, within noise. Full numbers,
including the coverage table at every confidence level, are in
`docs/PACE_MODEL.md`'s "Third iteration" section.

The decision engine's chosen strategies shifted by a lap or two on all
three benchmarks (refit on updated training data) but remained legal and
statistically significant against both baselines on all three —
`docs/DECISION_ENGINE.md` has the updated table. One notable change:
`dutch-2023`'s optimal `SOFT` stint now lands exactly on the
`max_stint_laps` safety bound (49 laps) rather than one lap under it,
making `dutch-2023` the one benchmark where that bound is still doing
real work.

## What this does not claim

This is not presented as "singapore-2023's calibration is fixed." It
is not. The gap narrowed at every confidence level and did not close.
The most-named remaining lever — a heavier-tailed (Student-t) likelihood
in place of the current Normal assumption — is still unimplemented and
remains the most likely next step for whoever picks this up.

## Next action

Two items remain open and well-defined, per `docs/TECHNICAL_REPORT.md`:
`singapore-2023`'s residual calibration gap (candidate: Student-t
likelihood) and `dutch-2023`'s RMSE gap (candidate: check whether it is
still driven by a small number of large residuals, as the original
Phase 2 outlier fix addressed for a different benchmark). Neither blocks
any already-completed phase.
