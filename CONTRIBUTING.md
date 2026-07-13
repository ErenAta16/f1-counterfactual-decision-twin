# Contributing to ApexMind

ApexMind is a research project first and a piece of software second: every change should leave the project's claims easier to check, not harder. Before opening a pull request, please read `docs/PROJECT_PLAN.md` for the evidence-class contract (observed / inferred / simulated) that the codebase enforces at the code level, not just in prose.

## Getting set up

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

All three commands must pass before a PR is opened. CI runs the same three checks on Python 3.11 and 3.12.

## What a good PR looks like here

- One focused change per branch. A bug fix does not need to carry a refactor with it.
- If you touch the pace model, simulator, or decision engine, re-run the affected benchmark (`bahrain-2024`, `singapore-2023`, `dutch-2023`) and report the before/after numbers in the PR description — this project's history is full of fixes that looked correct until checked against real data.
- New behaviour needs a test. `tests/` mirrors `src/apexmind/` module-for-module.
- Docs that describe results (`docs/PACE_MODEL.md`, `docs/DECISION_ENGINE.md`, `docs/EVIDENCE_INTERFACE.md`) should be updated in the same PR as the code that changes those results, not after.
- Don't soften an honest limitation to make a PR look more finished. If something is still broken or unproven, say so — see `docs/TECHNICAL_REPORT.md` for the standard this project holds itself to.

## Good first issues

These are scoped, self-contained, and don't require touching more than one or two modules:

- **Student-t likelihood for the pace model.** `singapore-2023`'s calibration gap (documented in `docs/PACE_MODEL.md`) is consistent with heavier-tailed residuals than the current Normal-Inverse-Gamma model assumes. Swapping the likelihood is a contained change to `pace_model.py` with a clear before/after check against the existing calibration report.
- **A fourth historical benchmark.** Add a race outside the current three (`bahrain-2024`, `singapore-2023`, `dutch-2023`) to `benchmarks.py` and run the full pipeline against it. This is the most direct way to find out whether the pace model and decision engine generalise, and it is exactly how the three existing benchmarks caught real bugs.
- **Per-sentence faithfulness testing for `apexmind explain`.** The evidence interface currently validates citation sources and safety-critical-claim coverage, but not that every generated sentence is individually grounded. `docs/EVIDENCE_INTERFACE.md` names this as an open gap.
- **A chart for an existing report.** `docs/PACE_MODEL.md` and `docs/DECISION_ENGINE.md` currently present results as tables. A single well-labelled matplotlib figure (tyre degradation by compound, or a calibration reliability diagram) for one of these documents is a good way to get familiar with the codebase's data shapes.

If you're picking one of these up, open an issue first so two people don't duplicate the work.

## Reporting a problem

If you find a case where the model, simulator, or decision engine produces a result you can show is wrong against the underlying data, that is the most valuable kind of issue this project can receive — please include the benchmark, the exact command, and what you expected instead.
