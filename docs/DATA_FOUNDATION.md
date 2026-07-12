# Data Foundation — Phase 1 Research Record

**Status:** Complete with documented provider exceptions

## Purpose

Phase 1 establishes a reliable, inspectable per-lap race state before any tyre model or optimiser is introduced. The project must be able to say which source produced a value, which provider caveat applies, and whether the value is observed or derived.

## Source decision

| Source | v1 role | Why it is used | Boundaries |
|---|---|---|---|
| [FastF1](https://docs.fastf1.dev/data_reference/index.html) | Primary offline ingest | Provides race laps, tyre/stint fields, track status, weather, race-control messages, and later telemetry through a Python interface | Timing/telemetry data is generally available from 2018 onward; absolute timestamp alignment has documented jitter; a used tyre's `TyreLife` can include prior-session laps |
| [OpenF1](https://openf1.org/docs/) | Independent, later-stage cross-check | Offers API-level laps, pit, stint, weather, telemetry, and race-control endpoints from 2023 onward | It is not mixed into v1 rows; provider semantics must be reconciled before a dual-source truth table exists |
| [FIA regulations](https://www.fia.com/regulation/category/110) | Rule-version authority | Official source for sporting, technical, operational, and financial regulation versions | Store an explicit issue number and retrieval date before encoding a rule |

FastF1 is the only row-producing source in v1. Using one provider first avoids silent inconsistencies in lap timing, pit semantics, and position snapshots. OpenF1 will become a validation source only after row-level comparison rules are specified.

## Provider-aware caveats

- `LapTime`, sector times, pit timestamps, and position are retained as provider evidence. Missing values are not filled during ingestion.
- FastF1 documents that absolute timing can show synchronisation jitter; state construction therefore does not use absolute timestamps for precision alignment.
- `TyreLife` is recorded as reported. It is not silently relabelled as race-only tyre age because used sets can carry laps from earlier sessions.
- The v1 ingest disables raw telemetry. It loads the data needed for the phase gate: laps, weather, track status, and race-control messages.
- The cache is explicitly project-local (`work/data/cache/fastf1`) so one machine's global cache cannot alter another machine's results. Generated data and caches are excluded from Git.

## Benchmark set

| ID | Race | Condition class | Research purpose |
|---|---|---|---|
| `bahrain-2024` | 2024 Bahrain Grand Prix | Dry control | Establish normal lap, stint, and pit-flow behaviour before modelling interruptions |
| `singapore-2023` | 2023 Singapore Grand Prix | Safety Car | Test a neutralisation that changes pit windows; the official race report records a Safety Car restart at the end of Lap 22 |
| `dutch-2023` | 2023 Dutch Grand Prix | Changing conditions | Test rain, tyre transitions, VSC, and a red flag in one deliberately difficult replay |

The Bahrain race is a **control candidate**, not a hard-coded assertion that its state history is clean. It passes the benchmark only when the downloaded track-status and data-quality reports meet the Phase 1 acceptance criteria.

Sources: [Bahrain 2024 event page](https://www.formula1.com/en/racing/2024/bahrain), [Singapore 2023 report](https://www.formula1.com/en/latest/article/sainz-holds-off-norris-and-fast-charging-mercedes-pair-to-take-sensational.16sNsRUz2MAFyXxSE3RdwX), [Dutch 2023 report](https://www.formula1.com/en/latest/article/verstappen-overcomes-wet-weather-chaos-to-make-it-a-hat-trick-of-dutch-gp.4VJ0ULOqjodSSN1zC6kWui).

## Reproducible ingest

Create an isolated environment, install the project with its development tools, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\apexmind.exe ingest --benchmark singapore-2023 --data-dir D:\apexmind-data
```

Every run writes:

- a `processed/<benchmark>-lap-state.parquet` table;
- a `processed/<benchmark>-race-control.parquet` event table;
- a `processed/<benchmark>-weather.parquet` observation table;
- a `manifests/<benchmark>-lap-state.json` provenance record;
- a `quality/<benchmark>-lap-state.json` data-quality report;
- a FastF1 cache below the selected data root.

None of those artefacts belong in Git. The manifest records the source adapter version and output record count, but does not contain credentials.

## Initial lap-state schema

| Field group | Fields |
|---|---|
| Identity | `benchmark_id`, `condition_class`, `event_year`, `event_name`, `session_name`, `driver`, `driver_number`, `team` |
| Observed timing and stint | `lap_number`, `stint`, `position`, `compound`, `tyre_life`, `fresh_tyre`, `lap_time_seconds`, sector times |
| Pit and race context | `is_pit_in_lap`, `is_pit_out_lap`, `track_status` |
| Data quality | `is_deleted`, `is_accurate` |

The schema intentionally contains no inferred tyre degradation, battery state, active-aero state, or recommendation. Those are later-stage outputs and must not enter the observed-data table. Race-control messages and weather observations are separate tables: neither is falsely joined to a lap during ingestion.

## Phase 1 acceptance checks

1. All three benchmark downloads complete with a manifest and non-empty lap-state file.
2. Every row has a driver and positive lap number; each driver/lap pair is unique.
3. Provider-reported deleted and inaccurate laps are retained rather than discarded.
4. A manual replay review verifies selected pit, stint, position, and track-status transitions against session data.
5. A data-quality report identifies missing timing, tyre, and position fields before modelling begins.

## First ingest results

The initial run on 12 July 2026 used FastF1 3.8.3 and completed structurally for all three benchmarks.

| Benchmark | Lap-state rows | Drivers | Missing lap times | Missing positions | Provider notes |
|---|---:|---:|---:|---:|---|
| `bahrain-2024` | 1,129 | 20 | 2 | 0 | 20 deleted and 105 inaccurate laps retained |
| `singapore-2023` | 1,088 | 19 | 26 | 4 | 10 deleted and 130 inaccurate laps retained; FastF1 marked driver 18's laps inaccurate during its accuracy check |
| `dutch-2023` | 1,343 | 20 | 33 | 2 | 1 deleted and 329 inaccurate laps retained; FastF1 reported a 2.059-second session-end discrepancy for driver 1 |

These results **pass structural ingestion**, not scientific acceptance. Missing, deleted, and inaccurate values remain part of the evidence. The next review must manually compare selected pit, position, and race-control transitions against the source session before any predictive model uses these rows.

## Replay review

Selected event-to-lap transitions were reviewed from the generated tables and checked against the official race reports linked above.

| Benchmark | Generated evidence checked | Review finding |
|---|---|---|
| `bahrain-2024` | Early pit-in/pit-out rows for Albon and Alonso; neutralisation messages | The state table records lap-15 pit-ins and lap-16 out-laps on a normal track status. The race-control table contains no Safety Car, VSC, or red-flag event; only the chequered-flag entry matches the control-race purpose. |
| `singapore-2023` | Race-control and pit rows around laps 20–22 | The event table records `SAFETY CAR DEPLOYED` on lap 20 and `SAFETY CAR IN THIS LAP` on lap 22. Albon and Alonso each have a lap-20 pit-in and lap-21 out-lap, matching the expected strategy-window change. |
| `dutch-2023` | Weather-condition tyre changes and interruption events | The event table records the Safety Car on lap 16, VSC and a red flag on lap 64, then the restart procedure. The lap-state table shows an intermediate-tyre transition for Albon during the late changing conditions. |

This review establishes that the separate tables preserve the expected temporal story. It does not remove the provider warnings above or turn any observed data into ground truth for a counterfactual claim.

## Rule provenance

The current rule source is **FIA 2026 F1 Sporting Regulations, Section B, Issue 07, 25 June 2026**. This phase records the source only; it does not yet encode sporting rules. Rule encoding begins in Phase 4 after the candidate-strategy decision space is defined.
