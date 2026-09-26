---
title: PrimariRo PR 6 merged and deployed
type: note
permalink: main/projects/primariro/primari-ro-pr-6-merged-and-deployed
tags:
- primariro
- merged
- deploy
- corrected-claim
- completeness
---

# PrimariRo PR #6 merged — state as of 2026-08-08 ~14:00 local

`valid_as_of: 2026-08-08`.

## Landed

PR #6 **squash-merged** to `main` as `a570ff2`. First push to `main` since 2026-07-20.
Owner authorized the merge explicitly (AskUserQuestion, "Merge it (squash)").

Four commits went in on `atlas/scope1-integration`, each both-states verified:
- `737aef1` combobox keyboard-active scroll-into-view
- `9580679` repaired two private-leak gate tests, one of which was **passing vacuously**
- `4760c5e` **CI unblock** — derive the cycle set from `RELEASE_ARTIFACTS`
- `ca07be1` the audited UI/a11y wave, 27 files, +3435/-446

Gates on the merged head: svelte-check 0 errors · vitest 139 · playwright 31 · ruff clean ·
pytest 974 passed @ 67.80% coverage vs a 55.98% floor.

## CORRECTION — the "2,190 parliament records are a key mismatch" claim was WRONG

I stated that 2,190 of the 23,079 missing records were "already committed and fully provenanced,
invisible to the gate purely from a key mismatch." **That is refuted.** Do not act on it.

What is true: `data/public/parliament/historic.json` holds 3,213 individually provenanced roster
members (2,637 for cycles 1992-2008), each with `record_id`, `source_url`, `snapshot_hash`,
`verbatim_quote`. And `_walk_records` (`pipeline/verify/completeness.py:588`) only yields a mapping
that has `term_id` or `council_id`, so those rows are indeed never counted.

What makes the "fix" wrong: `RELEASE_ARTIFACTS` maps that file to `historical-series.schema.json`,
NOT `mandate.schema.json`. A published parliament mandate (`deputies-2024.json`) carries
`elected_party` with full provenance + confidence; a historic roster member carries only
`roster_entry` with a `parliamentary_group_label`, and the file's own `coverage_definition` says
*"Displayed parliamentary-group labels are not treated as elected-party claims."* The parliament
completeness cell measures elected-party-attributed mandates. Counting roster rows would mark five
cells COMPLETE for a claim the data explicitly disclaims = fabricated coverage.

**The repo had already decided this.** `data/public/absences/parliament-2012.json` states: *"The
CDEP legislature roster contains both original members and successors, so it cannot substitute for
the election result."* So the lane's H1 contradicted a documented prior decision. Lesson: when a
finding says "the gate is just missing already-published data", check whether an absence ledger
already explains why that data does not satisfy the claim.

## The genuinely honest work that IS available there

Parliament 1992-2008 measure `exp 438 / act 0 / doc 0 / missing 438` each (= the 2,190). `doc = 0`
is the real defect: 2,637 hash-pinned roster rows are neither counted as published NOR documented
as a partial. The gate is already complaining about the adjacent cells:
`NOTE: documented absence for ('parliament', 2012) must equal the exact uncovered count 438, got 2`
and the same for 2016. Ledgers exist only for 2012/2016/2020 — none for 1992-2008.

So the fix is absence-ledger work: declare "roster published (N rows, cdep.ro, hash-pinned) but no
per-mandate elected-party attribution, because the displayed group label is a CURRENT group and
changes after a defection". That moves `missing -> documented` without inventing coverage. The
ledger schema is `schema/absence.schema.json` with `additionalProperties: false` — it FORBIDS the
positive-claim fields, which is what made the old gate unsatisfiable by construction.

UNVERIFIED: how the gate derives `doc` per cell (entry count vs a declared count field) — the
mayor ledgers reach `doc 2943` so a count field must exist. Settle by reading
`_absence_missing_count` in `completeness.py` before authoring the ledgers.

## Other verified facts worth keeping

- **759 of the 791 "missing" mayor records are a denominator artifact**, not missing offices. The
  gate uses a static 3,187 fallback (today's UAT count) for historical cycles; `completeness.py:553-558`
  already discloses this in its own UNVERIFIED note.
- **BLOCKED-GATED = 0 records.** No cell's only remaining route is CAPTCHA-gated, so that
  constraint never binds on this backlog.
- Live site serves HTTP 200 at https://prekzursil.github.io/PrimariRo/ .

## Remaining work the owner asked for (all four, plus "everything else")

1. Parliament absence ledgers (the honest version above), NOT the `record_id` gate change.
2. Wave 2 — 8 gaps the 138-unit audit never assigned: licensing/attribution (nothing credits
   rezultatevot.ro / prezenta.roaep.ro / data.gov.ro; `Export.ts` ships no reuse terms), the
   `mayor_phone`/`mayor_email` vs footer-promise contradiction, SEO/social (zero og/twitter/
   canonical/hreflang), print styles, dark mode, `404.html` head, PWA, and an audit of `Export.ts`
   (601 lines, zero findings ever). Script drafted: `scratchpad/wf-finish-wave2.mjs`.
3. `data.ts:605` module-level `await fetchClientSnapshot()` gates ALL hydration — the last
   confirmed BLOCKER. Needs a serialized pass; touches every route + 139 tests.
4. A regression test pinning `MAX_RESTORED_PAGES` / the `?page=100` restore clamp — currently
   nothing pins it, so that fix can be reverted with a fully green suite.

## Relations

- relates_to [[PrimariRo CI block was code, not billing]]
- relates_to [[PrimariRo finish workflow wf_549c7956-0a3]]
