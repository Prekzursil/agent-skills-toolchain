# workflow-authoring — union-merge PROPOSAL (owner decision required)

Lane SKILLS2, item 3. **This is a proposal, not an applied merge.** Nothing in
`workflow-authoring/SKILL.md` was written by this lane. Both sides hold unique, dated,
measured content, so a silent pick in either direction destroys real knowledge — which is
exactly the DIVERGED case that the deploy hop refuses on purpose.

## The pair, measured

| | file | lines |
|---|---|---|
| REPO | `.agents/skills/workflow-authoring/SKILL.md` (identical to `skills/…`) | 587 |
| LIVE | `~/.claude/skills.daily/workflow-authoring/SKILL.md` | 354 |

`difflib` over significant lines, reconstruction control passed both directions
(`common + side-only == file length` for each side):

- common **300**
- LIVE-only **54**
- REPO-only **287**
- two-directional: **yes** → `classify_pair` returns `DIVERGED` → permanently outside
  `safe_to_deploy`. Waiting cannot close this. Evidence:
  `command-center/grounding/S2-WA-UNION.out.txt`, `S2-WA-UNION.json`.

The vault copy (`~/.agents/skills/workflow-authoring/SKILL.md`, 337 lines) is a **third**
variant and is out of scope here; resolve repo↔live first, then re-run the drift report.

## REPO-only content (what LIVE is missing), by section

| lines | section | what it is |
|---:|---|---|
| 46 | `## 1. The runtime API` | **corrected 2026-08-12**: the runtime injects **eight** globals (`agent, parallel, pipeline, phase, log, args, budget, workflow`), not three. Cites `docs/workflow-sota/GROUNDING-NOTES.md` §3 and a verbatim `RUNTIME-API-DUMP.txt`. Notes 0 of 10 saved workflows use `pipeline()` although the runtime doc says "DEFAULT TO pipeline()". Also adds `'max'` to the effort enum. |
| 20 | `## 2. args is delivered VERBATIM` | **corrected 2026-08-12**: reverses the old "one string" rule against the installed runtime's own tool doc; renames the lint check `args-parse-if-string` → `args-unguarded`; keeps the two real footguns (`args` is `undefined` when absent; a caller may pass a JSON-*encoded* string). |
| 39 | `## 5b. Bound every fanned-out agent (H6)` | timeout/heartbeat bounding — SHIPPED design item. |
| 8 | `## 5c. Guard every budget loop on budget.total` | |
| 40 | `## 13. Wire the resume manifest` | the cross-session half of rule 6. |
| 35 | `## Governed single-shot run` | |
| 42 | `## Lint your workflow` | the mechanical `workflow_lint.py` stage-0. |
| 47 | `## Author quick-wins (helper snippets)` | |
| 5 | `## 7.` / 2 `## Companion…` / 2 `## Quick checklist` / 1 frontmatter | see conflicts below |

## LIVE-only content (what a repo→live overwrite DESTROYS), all 8 hunks

1. **`description` (1,062 chars)** — the long form. See "budget interaction" below.
2. blank line (noise).
3. **§1, 3 lines** — the OLD "injects three globals" claim. **Superseded** by the repo's
   corrected §1. Safe to drop.
4. **§1, 1 line** — effort enum without `'max'`. **Superseded.** Safe to drop.
5. **§2 heading + 7 lines** — the OLD "args is one single string" rule. **Superseded** by
   the repo's re-derivation. Safe to drop — *but* the live text carries one idea the repo
   version does not: *"design for the common case where there is no reliable arg channel at
   all — have the agents auto-discover their input from live files (Read/Glob)"*. That advice
   survives the correction and is worth grafting.
6. **§7, 33 lines — THE HARD CONFLICT. See below. Do NOT drop.**
7. **Companion artifacts, 1 line** — trivially superseded by the repo's 2-line version.
8. **Quick checklist, 6 lines** — the checklist items matching hunk 6. Same decision as 6.

## The one hard conflict — `additionalProperties: false` (§7)

The two sides give **opposite instructions on the same schema knob**, and the live side is
the one with the field evidence:

- **REPO §7 (5 lines):** *"Every `agent()` that feeds an aggregation MUST carry a `schema`
  (with `additionalProperties: false` and an explicit `required`)."*
- **LIVE §7 (33 lines):** *"**Do NOT set `additionalProperties: false` on a fan-in
  schema.** It converts a cosmetic extra key into a hard, unrecoverable rejection."* It then
  documents the `{"raw": …}` double-encode failure with a workflow id and a date —
  `wf_950ea2e9-e82`, 2026-07-23 — where a lens with 35 tool calls emitted the whole object
  JSON-encoded into one string field five times and died on
  `StructuredOutput retry cap (5) exceeded`, **because** `additionalProperties: false` plus
  six `required` fields rejected it outright and surfaced no partial credit. Measured cost:
  57 minutes of a 10-lens wave discarded. It gives five ranked mitigations and the
  artifact-first contract (fan-out-contract C1) as the primary fix.

**Deploying the repo copy as-is deletes a dated, id-bearing incident report and reinstalls
the instruction that caused the incident.** That is the whole reason this file must not be
resolved by whichever side is "ahead".

Note the repo is not wrong in general — `additionalProperties: false` is right for a tiny
gate verdict you fully control, which is precisely the carve-out the live text already
states. The two are reconcilable; they are not reconcilable *silently*.

## Budget interaction (couples to item 1)

The live description is **1,062 chars**; the repo's is **389**. Item 1 measured the
skills.daily description fleet at 115,478 chars against a render budget fitted at ~108,144 —
**~7,300 over** — and `workflow-authoring` is one of only two skills that survive the
truncation despite the model predicting it should be dropped. So:

- taking the repo's shorter description **frees ~673 chars** of render budget, and
- the long live description is currently *rendering*, i.e. it is paying its way.

Either choice is defensible. What is **not** defensible is treating the description as
free. UNVERIFIED: whether the 673 chars freed would light up any specific dark skill — the
settling experiment is to shorten this one description alone and re-observe the bare set.

Both descriptions also still say *"injected agent/parallel/phase globals"* — the **three**-
global claim the repo's own §1 now says is wrong. Whichever side wins, the description needs
the same correction.

## Proposed union (for approval — NOT applied)

Base = **REPO** (it is a near-superset: 287 unique lines vs 54, and its unique content is
newer and instrument-derived). Then graft from LIVE:

1. **§7 — replace the repo's 5-line rule with the live 33-line block**, keeping the repo's
   carve-out sentence for tiny fully-controlled gate verdicts. This is the only true merge.
2. **Quick checklist — take the live 6 lines** so the checklist matches the merged §7.
3. **§2 — graft the one surviving live sentence** (agents auto-discover input from live
   files) into the repo's corrected §2. Drop the rest of the live §2 as superseded.
4. **Drop live hunks 3, 4, 7** — superseded by dated repo corrections.
5. **Description — owner's call** (see budget interaction). Whichever is kept, fix
   "agent/parallel/phase" → the eight-global list.

Expected result: ~620 lines, no live-only content lost except text that a dated measurement
supersedes.

## Then, and only then

Apply to `skills/` **and** `.agents/skills/` (dual-write gate) **and**
`~/.claude/skills.daily/` in the same pass. A repo-only edit cannot reach the loaded tree:
`classify_pair` compares unique-line SETS, so any MODIFIED line is `DIVERGED` and
`safe_to_deploy` excludes it forever. Proven executably —
`command-center/grounding/S2-NEGCASE.out.txt` §A: append → `RIGHT-AHEAD`, modify →
`DIVERGED`, with the two verdicts differing so the probe is not inert.
