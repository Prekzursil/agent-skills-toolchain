---
title: PrimariRo gap sweep - flat denominators were the dominant defect class
type: note
permalink: main/projects/primariro-atlas/primari-ro-gap-sweep-flat-denominators-were-the-dominant-defect-class
tags:
- primariro
- atlas
- completeness
- denominators
- provenance
- code4ro
---

# PrimariRo: the dominant defect was flat denominators, not missing data

Session 2026-08-09/10, branch `feat/parliament-2016-from-main`. Six commits, all CI-green.

## The pattern, stated once

`pipeline/verify/completeness.py` measured coverage as `expected` vs `actual`, with `expected`
a **flat constant per office applied to every cycle 1992-2024**. Several of those constants
were provably wrong, and each wrong one manufactured phantom "missing" records for offices
that never existed. **A large fraction of the atlas's apparent gap was arithmetic, not absence.**

The repo knew. `completeness.py:53-55` calls the static values a "fail-closed fallback" and
says they are "NOT a claim that all current UATs existed in each old cycle", and the gate
prints on EVERY run:

> `UNVERIFIED: data/reference/uat-history.json is absent; local-office targets use fail-closed
> current-release counts (3187 mayor seats and 3186 councils) ... Experiment: land
> FOUND-uat-history with cycle-dated unit versions and rerun this gate.`

That file still does not exist. The instrument had been naming its own fix continuously.

## What each flat constant really was

| office | flat value | truth |
|---|---|---|
| parliament | 438 | 2016 = 463, 2020 = 466 (both sourced and now wired). 2024 unresolved — see below |
| mayor | 3187 | 1992 = **2943**, 1996 = 2954, 2000 = 2957, 2008 = 3186, 2012 = 3186 |
| government | 13 | that is the **2025 cabinet's** size (1 PM + 12 ministers) applied back to 1992 |
| county_council | 42 | correct — independently confirmed via Law 69/1991 art. 113 (40 judete + Sectorul Agricol Ilfov + Bucuresti) |

**The mayor denominators needed no research.** Every cycle's own absence row already stated
its contemporaneous denominator in a machine-readable field, and every one closed EXACTLY:
0+2943, 2905+49, 2921+36, 3153+33, 2717+469. Five cycles, five exact closures. Earlier units
did the work correctly and wrote the numbers down; nothing ever read them back.
709 phantom records disappeared with no new data.

## `parliament 2024` is FALSELY GREEN — a circular denominator

It reads expected 438 / actual 438 / missing 0 = COMPLETE. That agreement is an artifact:
`data/public/parliament/seats-2024.json` and the two roster files were created in the SAME
commit (`5704351`), so the denominator is derived from the numerator and **cannot detect a
shortfall**. Corroboration: the 2024 seats file has **zero** `national:ro` minority deputy
seats where 2016 has 17 and 2020 has 18 — Romania always seats ~18.

Generalised lesson: **an exact match to a fallback is a red flag, not a confirmation.** Check
whether the denominator and the numerator share a provenance.

## Two "blocked by design" verdicts that were stale

1. **`local_council 2016`** (3,186 records) was documented as unpublishable because
   `council.schema.json` requires `mandates1`/`mandates2` verbatim and no 2016 source
   publishes the split. True premise, wrong conclusion: the repo ALREADY had a second
   CI-gated total-only shape (`county-council-history.schema.json`,
   `allocation_detail: "source-total-only"`) and `cj_historic` was already using it for the
   2016 COUNTY councils **from the very same pinned CSV**. Published all 3,186 with no
   acquisition. An independent hunt separately confirmed NO 2016 split source exists anywhere
   (the split appears only on the paper PV form, AEP Dec. 12/2016, whose scans were never
   archived — proven with a controlled negative: the same matcher finds 2014's `PV_*.tif` set).

2. **`local_council` 1996-2008** (12,740 records) was documented as blocked because Code for
   Romania "exposes secondary per-locality totals, not ... a historical SIRUTA binding".
   **Refuted by the repo's own output**: it already publishes 12,084 mayor records at
   Confidence "Confirmed" from `api.rezultatevot.ro`, SIRUTA-bound, in those exact four cycles.
   Council ballotIds: 1996=**67**, 2000=**58**, 2004=**49**, 2008=**37**. Measured density on a
   full county across all four cycles: 100% of localities carry candidate seat data, zero empty,
   every seat total inside the legal 9..31 band, and the API states its own `totalSeats` as a
   free internal check. **1992 is genuinely blocked** — the full `/ballots` list contains no
   1992 local_council ballot at all (mechanically different probe than the module's own call).

## The provenance rule, stated exactly

Not "the store rejects binaries". The measured rule is: **non-text bytes may be stored and
bound; they may not be QUOTED.** `decode_snapshot_text()` accepts only UTF-8 or BOM-declared
UTF-16 and runs only for CITED snapshots. Proof: an ISO-8859-2 `siruta.csv` blob is already
stored, bound, and passes `--check` precisely because no cell cites it.

Also: **there is no host allowlist in the contract.** `build.py`'s `ALLOWED_HOSTS` gates only
the builder's own network fetch; 6 of 11 currently-bound hosts are not on it.

## `prefect 2025`: INCOMPLETE with missing=0 is the over-documented signature

expected 42 / actual 41 / documented 43. `absences/prefects-history.json` emitted a county-year
row for all 42 counties in 2025 — including the 41 already published — while
`absences/prefects.json` owned the single genuine gap (`county:VL`). Rows carry no count field,
so each counted as 1: 42 + 1 = 43 against a shortfall of 1. Fixed by making the grid skip any
year that is a published roster cycle, reading the published set from the ingester rather than
hardcoding `{2025}` — because hardcoding is the same freeze-today's-answer mistake one layer up.

## Progress

missing records 20,017 -> 16,115; incomplete cells 31 -> 16. Remaining after the in-flight
Code4Ro harvest lands: mostly `local_council 1992` (genuinely blocked), `mayor 2004` (denominator
UNSOURCED — deliberately left INCOMPLETE rather than invent 3,106), `government` (needs per-cabinet
sourcing), and `parliament 2024` (falsely green).

## Out of scope entirely

**European Parliament is not in the atlas.** `OFFICE_ORDER` has 8 offices and europarl is not
one; confirmed by a structural probe with a passing detector control (48 control matches, 0 EP
hits). ~5 cycles / ~165 records of scope, not gap.

**Person pages are blocked on identity.** `person_id` is derived from the JURISDICTION
(`p:aep2024_siruta1017`), so the same person across cycles has different ids and a career cannot
be assembled. Cross-cycle name matching is derived and must be capped Probable, never Confirmed.

Related: [[primari-ro-local-council-2016-unblocked-source-already-pinned-in-repo]],
[[single-signal-verification]], [[primariro-code4ro-ingest]]
