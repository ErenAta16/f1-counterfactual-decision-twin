# ApexMind Technical Report

**Date:** 13 July 2026
**Scope:** Phases 0-5 of `docs/ROADMAP.md`. This report is a consolidated
summary for a reader who wants the whole picture without reading all
seven phase-level research records; those records remain the
authoritative source for any specific number or claim and are linked
throughout rather than duplicated.

## What this is

ApexMind is an offline research prototype that replays historical
Formula 1 races, fits a probabilistic tyre/pace model, simulates
counterfactual strategies, searches for a legal strategy that beats fixed
baselines, and explains that choice in cited natural language. It is not
a live pit-wall tool, does not claim access to team telemetry, and labels
every number as observed, inferred, or simulated
(`docs/PROJECT_PLAN.md`, Section 3). This report exists so an
independent reviewer can check that claim against what was actually
built, not just what was planned.

## Architecture

```text
FastF1 (public data) + FIA regulation text
              |
     per-lap race-state table                    (Phase 1)
              |
   Bayesian pace/tyre model (compound x tyre-life x race-progress)  (Phase 2)
              |
   Monte Carlo race simulator (green-flag + declared Safety Car)    (Phase 3)
              |
   dynamic-programming strategy search + Article B6.3.6 filter      (Phase 4)
              |
   evidence ledger -> Cohere Command R+ -> cited explanation        (Phase 5)
```

Every arrow above is a real, reproducible code path — the commands in
"Reproducing everything end to end" below run all five stages in order
against real data. `apexmind` is a single Python package
(`src/apexmind/`) with one CLI entry point per stage.

## Results by phase

| Phase | Record | Headline result |
|---|---|---|
| 1 — Data fidelity | `docs/DATA_FOUNDATION.md` | Three benchmark races ingested and independently verified; exact row counts reproduced fresh from a clean clone (1,129 / 1,088 / 1,343 lap-state rows). |
| 2 — Predictive foundation | `docs/PACE_MODEL.md` | Bayesian pace model beats the naive baseline on the primary hold-out; MAE more than halved (1.173s &rarr; 0.606s) after fixing a fuel/tyre-wear confound and, separately, excluding Safety-Car-restart laps that were also being misread as settled pace. The second fix partially repaired a calibration regression the first one introduced on `singapore-2023` — narrowed, not eliminated. A fourth investigation found `dutch-2023`'s "worse than baseline" RMSE is not a bug: it beats baseline on the 79% of that hold-out run on dry compounds, and only loses on the pooled number because of a compound with zero training-set representation. |
| 3 — Counterfactual simulator | `docs/SIMULATOR.md` | Single-car Monte Carlo simulator; bit-for-bit reproducible across independent process runs; real Safety Car episodes extracted and used for context. |
| 4 — Constrained decision engine | `docs/DECISION_ENGINE.md` | Exact dynamic-programming optimiser; Article B6.3.6 encoded from the primary FIA source document (quoted, hashed); winning strategy beats both fixed baselines with a 95% CI excluding zero on all three benchmarks. |
| 5 — Evidence interface | `docs/EVIDENCE_INTERFACE.md` | Complete for v1 scope. Every generated explanation across three real runs cited only real evidence items; a live-API bug (whitespace in document ids) was found and fixed; a minimal replay interface renders real track data alongside the cited explanation; explanation-quality tests cover abstention and safety-critical citation coverage, not yet full claim-level faithfulness. |

## What is honestly unresolved

This project's evidence-contract commitment means naming what still does
not work, not just what does:

- **`singapore-2023` calibration.** The Phase 2 fuel/tyre fix measurably
  worsened this one's interval calibration; a follow-up fix (excluding
  Safety Car restart laps, `docs/PACE_MODEL.md`'s "Third iteration")
  narrowed the gap at every confidence level but did not close it (95%
  coverage: 79% &rarr; 81% against a 95% nominal target). Tracked as an
  open item, not claimed as solved.
- **`dutch-2023` RMSE.** Worse than baseline when pooled across every
  compound — but now precisely attributed, not just observed
  (`docs/PACE_MODEL.md`, "Fourth iteration"): on the 79% of this
  hold-out's laps run on dry compounds, the model beats baseline by
  roughly the same margin it does everywhere else (MAE 27% better, RMSE
  25% better). The pooled number is worse than baseline only because of
  the 21% run on `INTERMEDIATE`, a compound with zero representation in
  either of the two training benchmarks whenever `dutch-2023` is held
  out. This is not an outlier-filtering problem like the two fixes
  above; there is no training signal for that compound to recover, and
  fixing it for real would need a benchmark race with more wet-weather
  data than this project currently has. Named as understood and
  currently unfixable, not left as an unexplained negative number.
- **The `SOFT` degradation slope is still small.** Fixing the fuel/tyre
  confound corrected its *sign*, not its *magnitude* — a genuine, separate
  limitation of a linear, single-regime model on this data volume.
- **Explanation faithfulness beyond citation validity.** Phase 5 checks
  that citations point at real evidence and that two safety-critical
  claims are never silently dropped; it does not yet check that every
  sentence in a generated explanation is individually faithful to its
  cited source.
- **The Safety Car scenario, and the "mandatory Race tyre specification"
  half of Article B6.3.6**, remain declared assumptions and a named scope
  gap respectively (`docs/SIMULATOR.md`, `docs/regulations/tyre-compound-rule.md`)
  — not fitted from enough data to claim otherwise.

## Reproducing everything end to end

```powershell
# 1. Environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. Tests and lint (no network required)
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .

# 3. Ingest real race data (network required; writes to a local, untracked data directory)
.\.venv\Scripts\apexmind.exe ingest --benchmark all --data-dir D:\apexmind-data

# 4. Phase 2: fit and evaluate the pace model
.\.venv\Scripts\apexmind.exe evaluate --holdout bahrain-2024 --data-dir D:\apexmind-data

# 5. Phase 3: simulate example strategies
.\.venv\Scripts\apexmind.exe simulate --reference-benchmark bahrain-2024 --n-simulations 3000 --seed 42 --data-dir D:\apexmind-data

# 6. Phase 4: search for and rank legal strategies
.\.venv\Scripts\apexmind.exe decide --reference-benchmark bahrain-2024 --n-simulations 3000 --seed 42 --data-dir D:\apexmind-data

# 7. Phase 5: generate a cited explanation (requires COHERE_API_KEY; see .env.example)
.\.venv\Scripts\apexmind.exe explain --reference-benchmark bahrain-2024 --data-dir D:\apexmind-data

# 8. Phase 5: render the replay page (open the resulting .html file in a browser)
.\.venv\Scripts\apexmind.exe replay --reference-benchmark bahrain-2024 --data-dir D:\apexmind-data
```

Steps 4-8 can be repeated with `--reference-benchmark singapore-2023` or
`--reference-benchmark dutch-2023` to reproduce the other two benchmarks'
results referenced throughout the phase records. Nothing under
`D:\apexmind-data` (or whichever `--data-dir` is chosen) belongs in
version control — every artefact there is regenerated from the commands
above, and `.gitignore` excludes it by default (`work/`, `data/`).

## What to check, as an independent reviewer

1. Run steps 1-2 above on a fresh clone and confirm 86 tests pass and
   `ruff check` is clean.
2. Run step 3 and confirm the row counts printed match the table in
   `docs/DATA_FOUNDATION.md`.
3. Run step 4 and confirm the MAE/RMSE/coverage numbers match
   `docs/PACE_MODEL.md`'s "Third iteration" table for `bahrain-2024`.
4. Run step 6 twice with the same `--seed` and confirm identical output
   (`docs/DECISION_ENGINE.md` and `docs/SIMULATOR.md` both report this
   check; it is not a one-time claim).
5. Run step 7 and open the written `explanation-<benchmark>.json`; check
   every `evidence_ids` value in `citations` against the `evidence` list
   in the same file — every id should resolve.
6. Run step 8 and open the resulting HTML file directly in a browser (no
   server needed) to see the real track-status timeline, the chosen
   strategy overlaid on it, and the cited explanation together.
