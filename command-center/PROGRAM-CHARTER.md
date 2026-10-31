---
title: PROGRAM-CHARTER
type: note
permalink: dqverify-repo-20261013/command-center/program-charter
---

# PROGRAM-CHARTER

The command center for the four interleaved programs: **A-toolchain** (Prompt Two),
**HARNESS** (the unified two-program contract's own machinery), **MONITOR** (the unified
cockpit) and **B-workflow_design**.

Contract source: `_USER-PROMPTS.md:10586-10603` — *"Create a durable command-center directory
with: PROGRAM-CHARTER.md; OWNER-DECISIONS.md; WORK-UNIT-CATALOG.json; DEPENDENCY-GRAPH.json;
ARTIFACT-MANIFEST.json; CLAIM-REGISTRY.json; TEST-REGISTRY.json; RISK-REGISTER.md;
UNKNOWNS-REGISTER.md; RELEASE-CHECKLIST.md; ROLLBACK-MANIFEST.md; RUNBOOK.md; STATUS.md; and
append-only event logs."*

## 1. Why this exists, stated as the failure it prevents

Work on these programs was deferred, drafted, and then forgotten. Three mechanisms did it, all
measured:

1. **The designated survive-context-loss pointer went stale with nothing enforcing it.**
   `RESUME.json` was last written 2026-07-23 23:54 and still says `"A3_land_m02": "landing"`.
   M02 merged as PR #160 on 2026-07-24. It is not merely 15 days old, it is **wrong** — and a
   wrong pointer that reads as authoritative is worse than an absent one.
2. **The backlog was prose, so completeness was not computable.** It carried 4 of the 33
   mandated per-item fields, and neither `10-DEPENDENCY-GRAPH.json` nor
   `11-CAPABILITY-PRESERVATION-GRAPH.json` was ever written — so the contract's own rule,
   *every item reachable from a final disposition*, could not be evaluated even in principle.
3. **Receipt trees were never created**, so "unfinished" left no artifact and every program
   lacked a terminal state.

The previous command center was also **not version-controlled**. That is the point of this one.
Everything here is in git, is derived by an algorithm where an algorithm can derive it, and is
guarded by a test that fails on drift.

## 2. What is authoritative

| question | authority |
|---|---|
| what work exists, and its state | `WORK-UNIT-CATALOG.json` (the SSOT) |
| what blocks what | `DEPENDENCY-GRAPH.json` (fully derived; never hand-edited) |
| is the set complete | `python tools/command-center/validate.py` |
| what the owner still has to answer | `OWNER-DECISIONS.md` (derived) |
| where the numbers came from | `sources/REGISTER.md` (committed provenance snapshot, sha256 pinned) |

`sources/REGISTER.md` is a **snapshot**, not a live authority. It is committed so the seed is
reproducible and auditable; the catalog is what the tooling reads. The validator (REACH-6)
fails if a row in the snapshot has been dropped from the catalog, and fails if the snapshot's
sha256 no longer matches the one the catalog was seeded from.

## 3. Status vocabulary, and what a disposition means

`DONE-VERIFIED` · `DONE-CLAIMED` (= NOT-CHECKED, stays open) · `IN-FLIGHT` · `OPEN` ·
`SUPERSEDED` · `DROPPED-BY-OWNER` · `UNKNOWN`.

Exactly three are **final dispositions**: `DONE-VERIFIED`, `DROPPED-BY-OWNER`, `SUPERSEDED`.
Everything else is open. **A close requires cited evidence and is refused without it** — a
"done" with no `file:line` or reproducible command is DONE-CLAIMED, which this register treats
as NOT-CHECKED and keeps in the open set.

Deferral is not closure. A deferred item stays open, stops being surfaced until its
`defer_until`, and returns on its own.

## 4. Operating rules

- **Nothing may be dropped without an explicit recorded owner decision naming it.** That is
  what `DROPPED-BY-OWNER` plus `disposition_evidence` encodes, and REACH-5 enforces it.
- **Closing must stay as cheap as opening**, or the register rots: both are one command
  (`tools/command-center/close.py`), both append to the event log, both regenerate the graph.
- **Owner questions go out as ONE batch.** The owner asked explicitly not to be interrupted
  piecemeal.
- **Rotation of any credential is the owner's action, never an agent's** (AGENTS.md §9).
  `R-B08` is recorded as a decision-and-quarantine item for exactly this reason.
- **Two mechanically independent signals** before any load-bearing claim, and a detector must
  be shown able to go red before its silence counts as evidence.

## 5. Scope boundary

The `Reframe` project is out of scope for this command center and is not read, analysed or
tracked here. The register's `B4 = Reframe` row (backlog numbering) is explicitly not actioned.