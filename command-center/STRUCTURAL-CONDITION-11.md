# Structural finding: condition 11 is unsatisfiable for every work unit

- **Found:** 2026-08-10, while trying to move TST-0334 / TST-0350 off `BLOCKED`
- **Status:** CONFIRMED by reading both implementations. Needs an OWNER decision, not a code fix.
- **Consequence:** no work unit in the 2,007-unit catalog can reach receipt state `SUCCESS`.

## The contradiction

Two parts of the program's own contract cannot both hold.

**Side A — the completion predicate.** `platform/lib/completion_predicate.py:83` declares condition 11
as *"output was registered in the artifact manifest"* (spec `:10643`), and `_c11_manifest`
(`:1011-1062`) implements it by requiring **every PRIMARY artifact of the receipt** to appear in the
`artifacts` array of the manifest named by `manifest_registration.manifest_path`, with a matching
sha256. An artifact absent from the manifest returns `UNSATISFIED` with the reason *"an artifact on
disk but unregistered is not complete (ARC-0084)"*.

**Side B — the manifest.** `tools/command-center/render.py:34-36` defines `ARTIFACT-MANIFEST.json` as
*"The 13 files Prompt Two names at `_USER-PROMPTS.md:10590-10602`, plus the append-only event log at
`:10603`"* — a hardcoded 14-name tuple, `CONTRACTED_ARTIFACTS`. `render_manifest()` iterates exactly
that tuple. Nothing anywhere adds a unit's produced artifact to it.

Measured now: the manifest holds **14 entries and zero receipts or unit artifacts.**

## Why this caps the whole program

A unit's primary artifact is normally *not* one of those 14 files. TST-0350's is
`tools/measure-guard/suitefloor.py`; TST-0334's is `tools/measure-guard/blobread.py`. Neither is in
`CONTRACTED_ARTIFACTS`, neither can be, and `receipt_core`'s `allOf[0]` makes
`manifest_registration.registered = true` a precondition of `state: SUCCESS`.

So the ceiling is structural, not a property of these two units:

- **TST-0334** and **TST-0350**: `registered: false`, correctly.
- **BLD-0023**, written by a different lane on a different day: also `registered: false`.

Three receipts exist in this repo and all three are capped for the same reason. This is an
independent corroboration of Phase 14's condition-21 verdict, reached from the opposite direction:
Phase 14 concluded the shared predicate returns false for the program; this explains one reason it
*must*, regardless of how well any unit is executed.

## What this is NOT

- **Not a defect in either implementation.** The predicate is right that an unregistered artifact is
  not demonstrably complete. The manifest is right to be the 13 contracted files, because the spec
  says so and `cc-render --check` gates it against drift.
- **Not fixable by me unilaterally.** Adding unit artifacts to `ARTIFACT-MANIFEST.json` would change
  the meaning of a contracted artifact and would alter what `cc-render --check` enforces. That is a
  spec decision.
- **Not an argument for relaxing condition 11.** A receipt claiming SUCCESS for an artifact nothing
  tracks is exactly the failure the condition exists to prevent.

## Options for the owner, least invasive first

1. **Let a receipt name its own manifest.** `manifest_registration.manifest_path` is already a free
   string field, so a unit could point at a per-phase manifest (e.g.
   `command-center/UNIT-ARTIFACT-MANIFEST.json`) that a new renderer maintains. Requires no change to
   the 13 contracted files and no change to the predicate. **Recommended.**
2. **Extend `CONTRACTED_ARTIFACTS`** with a receipts/unit-artifact section. Changes the scope of a
   contracted artifact and therefore what `cc-render --check` gates.
3. **Scope condition 11** to units whose declared output is a command-center deliverable, and record
   `NOT-APPLICABLE` rather than `UNSATISFIED` for source-code artifacts. Weakest option: it edits the
   predicate to accommodate the data, which is the direction this program has repeatedly found to be
   the wrong one.

## Residual

- **UNVERIFIED:** whether `_USER-PROMPTS.md:10643` (condition 11's spec anchor) intends the
  13-file manifest specifically or *a* manifest generally. Reading that line would decide between
  options 1 and 2 immediately, and it is inside the governing spec range this program is scoped to.
  I did not read it, because the surrounding decision is the owner's either way.
- The three-receipt sample is the entire population of receipts, so "all three are capped" is a
  census rather than a sample — but it is a census of 3, and the claim that this generalises to all
  2,007 rests on the mechanism (paths outside `CONTRACTED_ARTIFACTS`), not on the count.
