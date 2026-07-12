# Progress Record 01 — Data Foundation

**Date:** 12 July 2026
**Status:** Complete with documented provider exceptions

## Work completed

1. Researched FastF1, OpenF1, and FIA data/regulation documentation and selected a single-source ingest policy for v1.
2. Defined three benchmark candidates: 2024 Bahrain for a dry control, 2023 Singapore for Safety Car behaviour, and 2023 Dutch for changing weather and interruption behaviour.
3. Added a typed benchmark registry, project-local cache conventions, FastF1 race ingest adapter, normalised per-lap, race-control, and weather tables, provenance manifest writer, quality reporter, and command-line ingest entry point.
4. Added unit tests for benchmark selection, local storage creation, race-state transformation, and source-schema failures.
5. Recorded provider caveats, source links, schema boundaries, and acceptance checks in `docs/DATA_FOUNDATION.md`.

## Deliberate exclusions

- Raw car telemetry is not loaded in this phase.
- OpenF1 is not merged into the primary state table.
- No values are imputed and no predictive model is introduced.
- No sporting rule is encoded until the strategy action space exists.

## First ingest result

All three benchmark sessions were downloaded and transformed with FastF1 3.8.3. The run produced 1,129 Bahrain lap-state rows, 1,088 Singapore rows, and 1,343 Dutch rows. The detailed counts and provider warnings are recorded in `docs/DATA_FOUNDATION.md`; generated artefacts remain local under `work/data/`.

## Replay review

The initial replay review found the expected strategic interruption signals: no Safety Car/VSC/red-flag event in the Bahrain control candidate; Singapore Safety Car deployment on lap 20 and in-lap on 22 alongside pit transitions; and Dutch Safety Car, VSC, red-flag, restart, and intermediate-tyre transitions. The generated tables preserve those event sequences without joining weather or race-control evidence into a misleading single lap value.

## Next action

Begin Phase 2 with naive pace and pit baselines. OpenF1 remains a later independent validation source; it is not a prerequisite for the single-provider v1 data contract.
