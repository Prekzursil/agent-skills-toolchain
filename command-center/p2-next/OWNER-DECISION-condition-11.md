# Owner decision — condition 11 has no satisfiable path, and it is a CONTRACT COLLISION

Raised 2026-08-13 by the orchestrator, independently re-measured after the P2NEXT lane found it.
This is the keystone blocker for Prompt Two delivery. It is NOT the cross-vendor rail, and
`codex login` does not clear it.

## The bar

`platform/lib/receipt_schema_gate.py:515-527`, condition 11:

    reg = receipt.get("manifest_registration")
    if not isinstance(reg, dict):            -> UNSATISFIED "no manifest_registration block"
    elif reg.get("registered") is not True:  -> UNSATISFIED "manifest_registration.registered is not true"
    elif verify_filesystem and not (root / reg["manifest_path"]).is_file():
                                             -> UNSATISFIED "manifest absent on disk"

The schema hard-rejects `state=SUCCESS` while condition 11 is unsatisfied. So a unit can pass an
independent review with a perfect receipt and still not be deliverable.

## Measured, three signals

1. **Nothing in production sets it.** Repo-wide search for a write of
   `manifest_registration.registered = True` finds exactly two sites, both TEST FIXTURES
   (`platform/lib/_p12_refute_predicate.py:161`, `platform/lib/_predicate_real_units.py:182`), plus
   one that deliberately sets it FALSE (`command-center/p2-wave/_build_IMP0433.py:202`).
2. **The receipts overwhelmingly point at the charter manifest.** Of 81 receipts under
   `command-center/` carrying a `manifest_registration` block: **81 declare a `manifest_path`, 80 of
   them `command-center/ARTIFACT-MANIFEST.json`** (the odd one out is
   `command-center/P14-MANIFEST-VERIFY.json`). Only **12** have `registered: True`, and those are
   IMP-0433's own fixtures. The fixture constant agrees:
   `_predicate_real_units.py:28  MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"`.
3. **That manifest is contractually a FIXED charter list and is already complete.** Its own
   self-description:

       contract:          _USER-PROMPTS.md:10590-10603 (13 files + append-only event logs)
       derivation:        tools/command-center/render.py:render_manifest
       expected: 14   present: 14   verified_on_disk: True

   The 14 entries are PROGRAM-CHARTER.md, OWNER-DECISIONS.md, WORK-UNIT-CATALOG.json,
   DEPENDENCY-GRAPH.json, ARTIFACT-MANIFEST.json, CLAIM-REGISTRY.json, TEST-REGISTRY.json,
   RISK-REGISTER.md, UNKNOWNS-REGISTER.md, RELEASE-CHECKLIST.md, ROLLBACK-MANIFEST.md, RUNBOOK.md,
   STATUS.md, events/EVENTS.jsonl. **Zero unit artifacts, by design.**

## Why this is a collision and not a missing function

The first reading -- mine, before signal 3 -- was "the producer was never built, go build it."
That is wrong and would have been an expensive wrong turn. `render_manifest` is not an incomplete
producer; it is a COMPLETE producer for a DIFFERENT contract. Registering unit artifacts into that
file would:

  * falsify its stated contract (`13 files + append-only event logs`),
  * destroy the `expected == present == 14 / verified_on_disk` invariant, which is a working
    integrity check today, and
  * rewrite a contract anchored to the owner's own prompt text.

Whereas pointing units at a different manifest invalidates the `manifest_path` already written into
**80 receipts**. Neither side is free. That is an owner decision, not an implementation detail.

## The options

**A. Extend ARTIFACT-MANIFEST.json with a separate unit-artifacts section.**
  + Matches what 80 receipts already declare; zero receipt rewrites.
  + One place to look.
  - Rewrites the charter contract line and the 14/14 invariant; needs a new invariant that stays
    meaningful at 2,007 units (e.g. charter section stays exactly 14 AND units section is
    self-consistent), or the integrity check silently degrades into a row count.

**B. A dedicated unit-artifact manifest, and condition 11 accepts it.**  <-- RECOMMENDED
  + Leaves the charter manifest and its invariant untouched and still meaningful.
  + Scales to 2,007 without turning one file into a 2,007-row blob.
  - Requires updating `manifest_path` in 80 receipts (mechanical, scriptable, and they are
    currently BLOCKED anyway so nothing regresses), plus a real producer.

**C. Declare condition 11 not applicable to units and drop it from the SUCCESS predicate.**
  - Rejected unless the owner wants it: it removes a durability check rather than satisfying it,
    which is the false-green this program exists to prevent. Recorded only for completeness.

## Recommendation

**B**, with the producer written as a real gate: it must enumerate the unit's declared artifacts,
FAIL CLOSED on an empty walk or a missing file, and emit a terminal marker. Before it is trusted,
feed it a unit whose artifact is deleted and require it to go red -- a registration producer that
has never refused anything is indistinguishable from a no-op, and this program already has one
gate that certified a file asserting 999999 passing tests.

Whichever is chosen, `state=SUCCESS` must NOT be hand-flipped on the 7 reviewed units. The P2NEXT
lane was explicitly right to leave them BLOCKED.

## Blast radius if unresolved

2,007 units. 1 delivered. Every future unit hits this same bar regardless of review quality or
vendor. It also sharpens FM-7 in `platform/architecture/marketplace-first.md` from "never exercised
at scale" to "not currently satisfiable".

## Third instance of one defect class, same night

A consumer with no producer:
  * `/rollback` promises a pre-edit checkpoint and reads an index no deployed hook writes
    (`edit-checkpoints` is in git, not deployed).
  * `mcpctl/matrix.py` exposes `tool_count`/`pid`/`rss_bytes`/`last_error` -- null in 145/145 rows,
    the producing primitive exists unwired.
  * condition 11 requires a registration nothing produces.
Worth a standing check: for every gate condition, name the code that can satisfy it.

---

## POSTSCRIPT 2026-09-19 — Option B implemented (PR #325 lane C11); the numbers above are stale

The 2026-08-13 counts moved before this lane ran, and the fix already half-existed:

* **"80 receipts point at the charter manifest" is now 20.** The 2026-08-16 p2-wave
  `_pack_receipt.py` builders repointed most receipts at per-probe
  `p2-wave/probes/<unit>/UNIT-ARTIFACT-MANIFEST.json` files (361 by fresh census). Fresh
  measurement: `command-center/p2-next/C11-CENSUS.json` (425 receipt-shaped files carry a
  `manifest_registration` block; 20 old-path, 44 top-level-new-path, 361 probe-local).
* **A producer already existed but could never run.** `tools/command-center/unit_manifest.py`
  (v1) failed closed on the FIRST of ~90 receipts naming probe outputs that were never
  committed (`C11-MISSING-ARTIFACTS.json`), so the top-level
  `command-center/UNIT-ARTIFACT-MANIFEST.json` could not be written at all while 44 receipts
  already pointed at it. AUD-0095/AUD-0090 recorded this as "global unit_manifest.py --check
  remains a sibling BLD-0001 issue" and lanes fell back to per-probe manifests.

What this lane shipped (all on branch pr-325, disk-verified):

* **Producer v2 — closed registration contract.** The derivation set is every receipt-shaped
  JSON under `command-center/` whose `manifest_registration.manifest_path` names THIS manifest
  (probe-local manifests are separate contracts, ignored). FATAL on: empty walk, unreadable
  claimer, a `registered: true` claim naming an absent artifact (an un-honor-able claimed
  registration is the false-green this program exists to prevent), zero-registrable corpus.
  Non-claiming receipts naming absent artifacts are disclosed in an `unregistrable` block —
  green by disclosure, never by silence. Both-states self-test covers every fatal rule.
* **The manifest exists**: `command-center/UNIT-ARTIFACT-MANIFEST.json` — 50 claimers, 48
  units, 58 artifact rows hashed (CRLF→LF), 5 unregistrable claimers disclosed by name and
  missing path (AUD-0006, CC-0011, REL-0001, TST-0129, RES-0164 — all `registered=false`).
* **Migration**: `_c11_migrate_manifest_path.py` repointed the 6 REAL old-path receipts
  (ADV-0026, ADV-0032, casualty ADV-0021/ADV-0022, TST-0334, TST-0350). The other 14 old-path
  files are frozen both-states fixtures under `p2-wave/fixtures/` consumed by
  `ready_units.py`/`unitgate.py` (AUD-0095 freeze inventory) and are deliberately untouched;
  their charter-manifest path remains valid (the file exists).
* **Red proof on the live tree**: `C11-REDPROOF.json` — deleting a registered unit's artifact
  turns `--check` red; restoring turns it green with hash-identical bytes; the receipt gate
  (`receipt_schema_gate.evaluate_gate_a`) scores condition 11 SATISFIED via the new
  `manifest_path` with filesystem verification on, and UNSATISFIED ("manifest absent on
  disk") when the manifest is missing.
* **CI wiring**: `.github/workflows/unit-artifact-manifest.yml` (self-test, then `--check`).
  Separate file per the p2next-rail-count.yml precedent — quality.yml is a closed charter
  set.

No `state` field and no `registered` flag was flipped anywhere; the 7 reviewed units stay
BLOCKED, as this decision required.

