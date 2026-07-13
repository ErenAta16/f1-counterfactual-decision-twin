# Encoded Regulation: Mandatory Dry-Weather Tyre Compound Rule

This is the versioned regulation excerpt referenced by
`src/apexmind/regulations.py`, kept here so a reviewer can check the code's
rule text against the primary source without re-downloading a 99-page PDF,
per the retention policy in `docs/PROJECT_PLAN.md` (Section 5.5).

## Source

- **Document:** FIA 2026 Formula 1 Sporting Regulations, Section B: Sporting
- **Issue:** 07
- **Issue date:** 25 June 2026
- **Article:** B6.3.6
- **Retrieved from:** https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_07_-_2026-06-25.pdf
- **Retrieved on:** 13 July 2026
- **SHA-256 of the retrieved PDF:** `77ecb97eaf08598c40073ebc9c52c8ec943dccef77af0c3a406edde7534b5110`

This matches the rule source already recorded in `docs/DATA_FOUNDATION.md`
("Rule provenance"), which named this exact issue and date before any rule
was encoded.

## Quoted text (Article B6.3.6)

> Unless they have used intermediate or wet-weather tyres during the Race,
> each driver must use at least two (2) different specifications of
> dry-weather tyres during the Race, at least one (1) of which must be a
> mandatory dry-weather Race tyre specification (Article B6.1.2).
>
> Unless the Race is suspended and cannot be re-started, failure to comply
> with these requirements will result in the disqualification of the
> relevant driver from the Race results. If the Race is suspended and
> cannot be re-started, thirty (30) seconds will be added to the elapsed
> time of any driver who did not, when required to do so, use at least two
> (2) specifications of dry-weather tyre during the Race.

## What is encoded, and what is not

`src/apexmind/regulations.py` encodes only the first sentence: a strategy is
legal if it uses at least two different dry-weather compounds (`SOFT`,
`MEDIUM`, `HARD`), unless it includes an intermediate or wet-weather stint.

Two parts of this article are deliberately **not** encoded, and the code
says so rather than silently approximating them:

1. **"...at least one (1) of which must be a mandatory dry-weather Race
   tyre specification (Article B6.1.2)."** The mandatory Race specification
   is a per-Grand-Prix designation the FIA announces roughly two weeks
   before each event (Article B6.1.2b.ii); it is not a fixed property of
   `SOFT`/`MEDIUM`/`HARD` and this project's ingested schema
   (`docs/DATA_FOUNDATION.md`) has no field recording which compound was
   designated mandatory for a given race. Checking this sub-clause would
   require a new, currently absent per-event data source.
2. **The penalty mechanics** (disqualification, or a 30-second time penalty
   if the race cannot be restarted) are not modelled. The decision engine
   treats a violation as "not a legal candidate strategy" and excludes it
   from the search space; it does not simulate what actually happens to a
   driver who breaks this rule in a real session.

The retrieved regulation document also contains other sporting rules
(pit-lane procedure, parc fermé, tyre-allocation counts, penalty
mechanics elsewhere in the document) that this project's strategy
representation has no state to check against and which are therefore out
of scope for v1, consistent with the non-goals in `docs/PROJECT_PLAN.md`.
