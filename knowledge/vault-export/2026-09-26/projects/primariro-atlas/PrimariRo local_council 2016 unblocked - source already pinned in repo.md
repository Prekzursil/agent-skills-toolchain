---
title: PrimariRo local_council 2016 unblocked - source already pinned in repo
type: note
permalink: main/projects/primariro-atlas/primari-ro-local-council-2016-unblocked-source-already-pinned-in-repo
tags:
- primariro
- atlas
- completeness
- local-council
- provenance
---

# PrimariRo: `local_council 2016` was never blocked by a missing source

Measured 2026-08-09 in `C:/Users/Prekzursil/Documents/GitHub/PrimariRo-atlas-build`.

## The wrong prior (mine, from an earlier session)

I had recorded that `local_council` backfill (19,110 records, 95.5% of the 20,017-record gap) was
**"blocked by design"** because `council.schema.json` requires `mandates1`/`mandates2` "as published,
never a self-derived allocation" and no source published the split.

That is **half right and operationally wrong**. It is true no 2016 source publishes the split. It is
false that this blocks publication — because the repo *already contains a second, CI-gated schema for
exactly this case*, and already uses it.

## What is actually true

`schema/county-council-history.schema.json` defines an `allocation_detail` discriminator:

- `"source-total-only"` -> composition items are `{competitor_name, seats, cell}`, `method: csv-open-data`
- `"source-two-round-split"` -> items are `{competitor_name, mandates1, mandates1_cell, mandates2, mandates2_cell}`, `method: official-json`

`pipeline/ingest/cj_historic.py` already ships 41 county councils for 2016 through the
`source-total-only` branch. **No party_id, no invented split.** So the honest pattern for a
total-only source already exists, is shipped, and is gated.

## The source is already acquired and pinned

`sha256:456f188bcf291f01b6f1ce89879307f0a4a7cbee85a6bbabb36dc2b941cd2705`
= `data.gov.ro/.../exportmandate.csv` (bound in `pipeline/snapshots/acquisitions.json`,
blob present at `data/snapshots/456f188b...`, 178,241 B gzipped / 1,486,703 B decoded).

It is byte-identical in content to `Export_mandate-2.csv` archived on `locale2016.bec.ro`
(Wayback `20211105023321`) — I found it via Wayback first and only then discovered the repo
already had it from data.gov.ro. **Search the repo before hunting the web.**

Columns: `Alegeri,NrJudet,NumeJudet,NrCircumscriptie,Siruta,Localitate,CodUnic,TipCompetitor,Competitor,CandidaturaPersoana,PozitieBuletin,NumarCandidati,NumarMandate`

Streams: `CONSILIERI LOCALI` 11,415 rows / **3,186 SIRUTA** · `CONSILIERI JUDETENI` 164 rows / **42
counties** · `PRIMARI` 3,186 · `PRIMAR GENERAL` 1.

## Four independent reconciliations (why I trust it)

1. `sum(NumarMandate)` per stream **matches the control totals published in a DIFFERENT file**
   (`SIAL2016_Situatia_mandatelor_partide-2.xlsx`): PRIMARI 3186, CONSILIERI LOCALI 40220,
   CONSILIERI JUDETENI 1436. All three exact.
2. Every one of the 3,186 localities has a seat total inside the legal Romanian band 9-31. Zero outliers.
3. The CL SIRUTA set **exactly equals** the shipped, COMPLETE `local_council 2024` set:
   `csv \ 2024 = 0` and `2024 \ csv = 0`.
4. 3,186 PRIMARI + 1 PRIMAR GENERAL = 3,187 = the already-shipped, COMPLETE `mayor 2016` count.

## Second finding: the "Bucharest has no county council" claim is refuted by the source

`pipeline/ingest/cj_historic.py`'s docstring states *"Bucharest's CGMB/general-mayor rows are checked
and excluded because Bucharest has no county council or CJ president"*, and every `county_council`
absence row therefore says `expected_records: 41`.

But the completeness denominator is **42**, and `data/public/councils/2024.json` ships
`county:B` / `county_councillor` / `total_seats: 55` sourced from AEP's own
`prezenta.roaep.ro/.../pv_b_final.json`. AEP publishes Bucharest **inside the county-level PV stream**.

The pinned 2016 CSV confirms it independently: `CONSILIERI JUDETENI` has 42 distinct `NumeJudet`
including `MUNICIPIUL BUCUREŞTI` (`NrJudet=42`), 5 competitors, **4+8+24+15+4 = 55 seats — the same 55
the 2024 record ships.** So CGMB is in-universe, and excluding it is the bug.

Consequence: this off-by-one is why `python -m pipeline.verify.completeness` FAILS strict mode with
`documented absence for ('county_council', 2008) must equal the exact uncovered count 42, got 41`.
It is the single hard gate failure in the repo.

## Buildable with zero new acquisition

| cell | records | pinned source |
|---|---|---|
| `local_council 2016` | 3,186 (closes a 3,185 gap outright) | `456f188b...` |
| `county_council 2016` | +1 Bucharest CGMB (41 -> 42) | `456f188b...` |
| `county_council 2020` | +1 Bucharest CGMB (41 -> 42) | `cc80fb4c...` `pv_b_final.json`, already bound |
| `county_council` absence rows 2008/2012/pre-2008 | denominator 41 -> 42 | correction, fixes the failing gate |

`measure_actual` in `pipeline/verify/completeness.py` walks every JSON under `data/public/` and counts
any record carrying `council_id` + a council `office_type`, so a new artifact is counted with **no
change to the gate**.

## Transferable lessons

- **Search the repo before hunting the web.** I spent real effort on Wayback CDX for a file the repo
  had already acquired, bound, and shipped from a different host.
- **A "blocked by design" verdict decays.** It was recorded against `council.schema.json` alone; a
  second schema for the same problem already existed. Re-check the constraint, not the memory of it.
- **A docstring assertion is not evidence.** "Bucharest has no county council" was stated in prose,
  propagated into 9 absence rows, and is contradicted by both the shipped 2024 data and the source bytes.

Related: [[primariro-code4ro-ingest]], [[single-signal-verification]]
