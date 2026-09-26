---
title: PrimariRo local_council backfill is blocked by design, not by sources
type: report
permalink: main/projects/primariro/primari-ro-local-council-backfill-is-blocked-by-design-not-by-sources
tags:
- primariro
- completeness
- provenance
- wayback
- bec
- refutation
---

# PrimariRo: the local_council backfill is blocked BY DESIGN — my Wayback plan was wrong

Verified 2026-08-09. **This note REFUTES the acquisition table in
[[PrimariRo atlas — completeness is 96% accounting artefact, and Wayback unblocks the real gaps]]**
(§3 of that note). Read this one first; that table over-promised.

## The refutation

`schema/council.schema.json` **hard-requires `mandates1` and `mandates2`** on every `composition`
entry, and says why in its own description:

> "each competitor's seat total is mandates1 + mandates2 **as published**, so it is a Confirmed
> sourced fact, **never a self-derived allocation**"

That is a deliberate anti-fabrication rule: the atlas refuses to publish a council composition
unless the SOURCE publishes the first-/second-allocation split. Both shipped artifacts
(`councils/2020.json`, `councils/2024.json`) carry those fields on every party entry.

The 2016 absence row already recorded this and I failed to read it before planning:
`data/public/absences/councils-2016.json` has `access_status: "reachable_source_insufficient"`,
reason *"the assessed official 2016 AEP/BEC machine-readable resources publish each competitor's
final NumarMandate total but no first-/second-allocation mandate counts; the required 2024 council
shape cannot be populated without inventing mandates1/mandates2."*

**Consequence: the six empty `local_council` cells (19,110 records, 95.5% of the reported gap) are
blocked by SHAPE, not access.** No archive find changes that. `local_council 2004` (`clt1jj.pdf`)
inherits the same blocker. The existing absence rows are correct and must stay.

## The two errors that produced the wrong plan

1. **"Loc" means *localităţi*, not *local councils*.** `SIAL2016_Mandate_VVE_Loc-2.xlsx` and
   `SIAL2016_Mandate_Part_Loc-1.xlsx` are titled **PRIMARI**. Real columns, read from row 5 (rows
   0-1 blank, merged title at row 2): `Voturi[Numar, % in circ, % in jud] | Mandate[Numar, %, %] |
   Primar ales`. Row 10: `PARTIDUL NAȚIONAL LIBERAL … 1 … HAVA MIRCEA-GHEORGHE` — the elected mayor
   of Alba Iulia. `mayor 2016` is already COMPLETE, so these files fill nothing.
2. **I planned from a filename gloss instead of a header.** I had even tagged the glosses
   UNVERIFIED and then built the table on them anyway.

## Revised realistic surface: ~553 records, not 7,000+

| cell | records | candidate | risk |
|---|---:|---|---|
| `parliament 2016` | 438 | `parlamentare2016.bec.ro` `Mandate-nominale-pe-competitori-pe-circumscriptii*.xlsx` | header unread |
| `mayor 2004` | 81 | `roaep.ro/bec_loc_2004/.../pales.pdf` | mayor shape = one holder per locality, no round split |
| `mayor 2008` | ~34 | `beclocale2008.roaep.ro/.../palesjudloc.pdf` | same |

## Reusable lessons

- **A filename is not a schema.** Read the actual header before planning an ingest. Two of my
  glosses were wrong in one table; both would have been caught by one fetch each.
- **Read the existing absence row first.** The repo often already contains the assessed reason a
  cell is empty, with an `access_status` that distinguishes *unreachable* from
  *reachable_source_insufficient*. Those are completely different problems and only one is fixable
  by finding a new source.
- **Detector failure to avoid:** a substring hint list containing `"local"` matches
  `locale2016.bec.ro` in every URL on that host, so the filter matched 410 of 410 and told me
  nothing. Anchor hints to path segments, and sanity-check that a filter EXCLUDES something.
- **An anti-fabrication schema requirement can make a gap permanent.** "Missing" is not the same as
  "fillable". Before scoping a backfill, check whether the target schema demands a field the
  historical sources never published.

Relations:
- refutes [[PrimariRo atlas — completeness is 96% accounting artefact, and Wayback unblocks the real gaps]]
- relates_to [[Single-signal verification]]
