---
title: P13-REFERENCE-TRIAGE
type: note
permalink: dqverify-repo-20261013/command-center/p13-reference-triage
---

# P13 — Reference triage: 15 dangling repo-relative references

**Unit:** `reference-triage` · **Status:** COMPLETE — all 15 classified, gate question answered

**COVERAGE — MEASURED:** detector reproduction (pass 2 and pass 3), detector both-states validation
(7 arms), all 15 sites, per-site class with mechanical evidence, existence-elsewhere search, the
candidate-gate scoping ladder, and the motivating-defect retention check. Nothing below is
unclassified.

---

## 1. Detector — reproduced and validated in both directions

Re-implemented from scratch (`triage_scan.py`, in a temp dir so the repo stays clean) rather than
quoted: pass-2 scope rule verbatim, plus pass-3's directory + extension tolerance.

| check | result |
|---|---|
| pass-2 baseline | `source` 178 in-scope / **119 dangling** — matches the brief exactly |
| pass-2 other fields | `file` 163/**0** · `schema_ref` 600/**0** · `validate_against` 103/**0** · `ref` 33/**33** — all match |
| pass-3 (dir + ext tolerance) | `source` 178 in-scope / **15 dangling**; other fields unchanged |
| CONTROL 1: resolver FIRES on 3 planted missing paths | PASS |
| CONTROL 2: resolver SILENT on exact-file / directory / extension forms | PASS |
| CONTROL 3: WALKER catches a bogus `source` injected into a scratch copy of a real blueprint | PASS |
| CONTROL 3b: same scratch file with a REAL `source` → 0 flagged | PASS |

`SUCCESS:detector-control all arms passed`. Both the resolver AND the walker were exercised —
resolver-only controls would not prove the walk reaches the field.

**Gap I found in my own detector and then measured:** my `EXTS` list omitted `.mjs`, and `.mjs` files
are tracked here. Re-running with `.mjs/.mts/.cjs/.txt` added leaves the count at **15**, so the
omission was inert. Measured, not assumed.

## 2. The 15 sites

`platform/workflows/` is abbreviated `pw/` below. Every "resolves as" was produced by re-running the
resolver against the candidate root, not by eyeballing.

| # | site | raw value | class | evidence |
|---|---|---|---|---|
| 1 | `command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.json:105` | `platform/plugin/PACKAGE-MEASUREMENT.json and PHASE5-PLUGIN-REPORT.md` | **B PROSE** | two paths joined by `" and "`; whitespace inside the value |
| 2 | `platform/lib/wfdsl/examples/wf-full-coverage.json:162` | `platform/workflows/source-quality-audit.json` | **F FIXTURE** (see §2a) | host file self-describes as "The conformance workhorse… Every mutation in wfdsl.mutations is applied to THIS document"; **no wfdsl code resolves `subworkflows[].source`** (grep: 0 hits) |
| 3 | `pw/bp-arc-01.architecture-tournament.workflow.json:721` | `workflows/design-gate.mjs` | **E OTHER-ROOT** | `agent-self/config/workflows/design-gate.mjs` (exact-file) |
| 4 | `pw/bp-arc-01.architecture-tournament.workflow.json:727` | `workflows/trainer-gui-mega-plan` | **E OTHER-ROOT** | `agent-self/config/workflows/trainer-gui-mega-plan.js` (extension) |
| 5 | `pw/bp-brn-03-constraint-inversion.json:635` | `workflows/grill.yaml` | **C LIVE-HARNESS** | repo: NONE. Live: `~/.agents/workflows/grill.yaml` (849 B) |
| 6 | `pw/bp-brn-03-constraint-inversion.json:718` | `command-center/WORK-UNIT-CATALOG.json baseline hash` | **B PROSE** | trailing English phrase after a real path |
| 7 | `pw/bp-cnc-01-five-persona-design-council.json:660` | `workflows/design-gate.mjs` | **E OTHER-ROOT** | as #3 |
| 8 | `pw/bp-pln-01.mechanical-plan-lint-then-adversarial-trio.workflow.json:585` | `workflows/plan-gate.mjs` | **E OTHER-ROOT** | `agent-self/config/workflows/plan-gate.mjs` (exact-file) |
| 9 | `pw/bp-pln-03.multi-pr-stacking-order-planner.workflow.json:648` | `workflows/reconcile-all-branches-prs` | **A REAL-MISSING** | see §2b — exists under a TYPO'd name |
| 10 | `pw/bp-pln-04.resume-safe-program-checkpointing.workflow.json:635` | `workflows/codex-auth-research-fanout.mjs` | **E OTHER-ROOT** | `agent-self/config/workflows/codex-auth-research-fanout.mjs` (exact-file) |
| 11 | `pw/bp-req-01-program-scale-extensive-grill.json:888` | `workflows/grill.yaml` | **C LIVE-HARNESS** | as #5 |
| 12 | `pw/bp-req-02-recursive-decision-ledger-walk.json:707` | `workflows/grill.yaml` | **C LIVE-HARNESS** | as #5 |
| 13 | `pw/bp-req-04.assumption-ledger-elicitation.workflow.json:638` | `workflows/plan-gate.mjs` | **E OTHER-ROOT** | as #8 |
| 14 | `pw/bp-req-05.intent-to-prd-with-reviewer.workflow.json:604` | `workflows/plan-gate.mjs` | **E OTHER-ROOT** | as #8 |
| 15 | `pw/two-signal-corroboration-gate.json:427` | `skills/claim-verify-gate/scripts/claim_gate.py` | **E OTHER-ROOT** | `.agents/skills/claim-verify-gate/scripts/claim_gate.py` (exact-file, TRACKED) |

### 2a. Two corrections to the brief's guesses

- **`platform/workflows/source-quality-audit.json` is NOT class A.** The brief flagged it as the
  likely real bug. Evidence against: its only referrer is `wf-full-coverage.json`, whose own
  `description` field reads *"The conformance workhorse: one workflow that exercises every capability
  the spec requires of the DSL… Every mutation in wfdsl.mutations is applied to THIS document"*; it is
  named in `platform/lib/wfdsl/mutations.py:3` and six times in
  `platform/lib/wfdsl/test_schemas_and_examples.py` as the mutation base document; and
  `grep -rn "subworkflows" platform/lib/wfdsl/*.py` filtered for file resolution returns **zero
  hits** — nothing ever opens that path. Its `subworkflows.source` exists to COVER the schema field.
  Creating the file would satisfy no consumer and would add a phantom blueprint to the corpus.
  This needs a **sixth class, F FIXTURE**, because A-E have no slot for "path-shaped value inside a
  schema-conformance document". Forcing it into A manufactures a bug. Confidence **almost certain
  (90-99%)** — three independent signals (self-description, mutation-base role, zero resolver).
- **`skills/claim-verify-gate/scripts/claim_gate.py` is E, not C.** The brief offered it as the
  class-C example. It resolves IN-REPO at `.agents/skills/claim-verify-gate/scripts/claim_gate.py`
  (tracked), so a repo-only gate CAN resolve it with a `.agents/` root. The live harness also has it,
  so C is a defensible alternate reading — but E is the actionable one.

### 2b. The single class-A site, and why "create the file" is the wrong fix

`workflows/reconcile-all-branches-prs` resolves to **nothing** under any root, with or without
extension tolerance. But the intended unit demonstrably exists — twice — under a **typo'd filename**:

- repo: `agent-self/config/workflows/reconcile-all-branches-prs-imporant.js` (tracked)
- live: `~/.claude/workflows/reconcile-all-branches-prs-imporant.js` (9,743 B)

`imporant` is a misspelling of `important`, and the `-imporant` suffix is not part of the workflow's
name anywhere else. So the reference is arguably *more correct than the file*. Remediation is to
**rename the file or re-point the reference — not to create a new file.** I did neither (read-only).
Confidence **almost certain (90-99%)**: both paths listed by `git ls-files` / `ls`.

## 3. Class histogram

| class | count |
|---|---|
| A REAL-MISSING | **1** |
| B PROSE | **2** |
| C LIVE-HARNESS | **3** |
| D REVSPEC | **0** |
| E OTHER-ROOT | **8** |
| F FIXTURE (new — A-E had no slot) | **1** |
| total | **15** |

D is 0 **by construction, not by luck**: pass 2's scope rule already excludes any value containing
`:`, so revspecs never enter scope. They are counted in the out-of-scope tally
(`source:revspec-or-drive`), not hidden.

## 4. Candidate-gate scoping ladder — MEASURED, not projected

Each rung was executed, not estimated:

| gate scoping | dangling `source` |
|---|---|
| pass 3, as the brief left it | **15** |
| + multi-root resolution (`agent-self/config/`, `.agents/`, `platform/`) | **7** |
| + exclude `platform/lib/wfdsl/examples/` (schema fixtures) | **6** |
| + skip whitespace-bearing values (prose) | **4** |

The residual **4** are all live-harness: `workflows/grill.yaml` ×3 (#5, #11, #12 — genuinely absent
from the repo; `git ls-files | grep grill` returns only `grill-me*` SKILL.md files) and
`workflows/reconcile-all-branches-prs` ×1 (#9, the typo).

## 5. Decisive question — with A-class fixed, would a gate over `source` be green?

**No, not from fixing A alone** — fixing the one A-class site takes 15 → 14, because 14 of the 15 are
not missing files. But the stronger claim the brief invited ("`source` cannot be gated") is **not
supported by the evidence, and I am not going to endorse it.** A `source` gate CAN be green, after
four changes, three mechanical and one a policy call:

1. **Multi-root resolution** (~10 lines): try `agent-self/config/` and `.agents/` as alternate roots.
   Clears 8 sites. Measured.
2. **Exclude schema-fixture directories** (`platform/lib/wfdsl/examples/`). Clears 1. Measured.
3. **Fix the 2 prose values** — data edits in `WAVE4-PLUGIN-LIFECYCLE-VERIFY.json:105` and
   `bp-brn-03-constraint-inversion.json:718`. I did not make them (read-only). Skipping the values
   instead of fixing them would let a future genuine typo hide behind a space — prefer the data fix.
4. **Decide the live-harness policy** for `workflows/grill.yaml` (3 sites): vendor it into
   `agent-self/config/workflows/`, or allowlist a documented live-harness prefix set. This is your
   call, not a code fix, and it is the one item that cannot be settled mechanically.

Plus the A-class rename (#9). With 1-4 done, the gate is green at **0**.

**It would still catch the motivating defect.** Verified directly: the `bp-pln-02` target
`platform/workflows/_shared/shared.pairwise-overlap-matrix.subworkflow.json` is tracked now, and it
is rescued by **no** alternate root, is not prose, and is not in a fixture directory — so under the
scoping above its absence would still be RED. That is the property that makes this gate worth
building: it survives every narrowing the false positives demanded. Confidence **almost certain
(90-99%)** — the target was run through the same resolver with all extra roots enabled.

**Caveat, stated inline rather than deferred:** rung 1 includes `platform/` as an alternate root,
which is the loosest of the three — it lets any `workflows/X` resolve as `platform/workflows/X`. In
this corpus no site depended on it (all 8 E-class sites were rescued by `agent-self/config/` or
`.agents/`), so it can be dropped. **UNVERIFIED** whether dropping it changes the count on future
data — I measured today's 15 only.

## 6. Verdict

**SUCCESS.** 15/15 classified with mechanical evidence: A=1 · B=2 · C=3 · D=0 · E=8 · F=1. The bug
class is far smaller than the raw count suggested — **one** genuine reference defect, and its fix is a
rename, not a file creation. Two of the brief's own guesses are corrected with evidence. A `source`
gate is achievable and would retain the defect that motivated it, but it needs multi-root resolution,
a fixture-directory exclusion, two data fixes, and one live-harness policy decision first.

Nothing was created, edited, committed or pushed; no pytest was run. The scan and classifier live in
`C:/Users/Prekzursil/AppData/Local/Temp/p13-triage/` and are re-runnable
(`python triage_scan.py --control`, then without the flag).

---

## 7. Orchestrator addendum — the class-B recommendation is REFUTED, and it settles the gate design

Written after §1-§6, by the orchestrator, having gone to make the two class-B data edits §5 item 3
recommends. I did not make them. The original text above is left intact for lineage.

**`source` is a POLYMORPHIC field with at least four distinct semantics**, and the two class-B sites
are correct as written in theirs.

| JSON location | meaning | resolvable path? |
|---|---|---|
| `subworkflows[].source` | RUNTIME dependency | **yes — must resolve** |
| `lineage.derived_from[].source` | provenance / attribution | should resolve |
| `constraints[].source` | citation with a locator | **no — free text by design** |
| `lane_comparison_*.source` | the document SET an audit read | no — may name several |

The decisive evidence is the document's own embedded schema, in the same file as site #6:

```json
"source": {"type": "string",
           "description": "The document or measurement it came from; empty means UNSOURCED"}
```

"document **or measurement**", and empty is a legal value meaning UNSOURCED. Three of the four real
instances in that file are not paths at all: `spawn brief`, `AGENTS.md 9` (twice — document plus
section, exactly the shape of site #6), and the catalog-hash one. So
`command-center/WORK-UNIT-CATALOG.json baseline hash` is a conforming value, not sloppy prose, and
editing it would corrupt a field that is behaving to its own contract.

Site #1 is the same story: it sits under `lane_comparison_read_only_after_measuring`, where the
audit compared TWO documents. `"A and B"` truthfully records what it read; collapsing it to one path
would make the record less accurate, not more.

### Consequence for the gate — key on the PATH, never on the field NAME

- A gate over the field name `source` is **invalid**. It cannot be made green without either
  corrupting conforming data or special-casing until it measures nothing.
- A gate over `subworkflows[].source` is **valid and worth building**. That is the field that had
  three committed blueprints pointing at the uncommitted
  `platform/workflows/_shared/*.subworkflow.json` files, and it is the one context where the value
  is unambiguously a repo path with a consumer.

So §5's four prerequisites reduce to one that matters — scope by JSON path — and the two data edits
and the whitespace-skipping heuristic are both dropped. The live-harness policy call (`grill.yaml`
×3, §5 item 4) also disappears from the blocking set: those sites are `lineage`/`constraints`, not
`subworkflows`.

**Verdict on §5:** the ladder was measured correctly and the conclusion drawn from it was wrong,
because every rung treated `source` as one field. Not a counting error — a schema error. My own
earlier "a `source` gate is theatre" was also wrong, for the opposite reason: the gate is buildable,
just not over the name.