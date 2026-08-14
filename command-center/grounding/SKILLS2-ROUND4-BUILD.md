# SKILLS2 — BUILD round 4

Two commits, both in the lane's file scope, both with the gate that could have refused them
actually refusing something. Plus one refuted grounding claim and one detector failure of my own.

## DoD status

| item | verdict | where |
|---|---|---|
| 1 render bug DIAGNOSED with a probe separating budget-truncation from parse-failure | **PASS** | both-states on the real render path, below |
| 2 vault dry-run plan read and reported | **PASS** | `H-REFUSES`, below |
| 3 workflow-authoring union-merge proposal written | **PASS (pre-existing)** | `command-center/S2-WORKFLOW-AUTHORING-UNION-MERGE.md` |
| 4 negative-case clauses added where safe | **PASS** | 12 more, net +0 chars, commit `0e2370be` |

## 1 · The render bug, settled on the instrument that was broken

`bc-drive-plus` carried ` #` inside a plain YAML scalar. Space-hash opens a YAML comment, so
440 of its 793 description characters never reached the listing.

- **BEFORE** — this session's injected skill listing at spawn rendered the entry as
  `...(closes bc-drive's` and stopped. 353 of 793 characters.
- **AFTER** — once the write landed in `skills.daily`, the client re-injected the entry
  carrying the full 417 characters, ending `...builds on bc-drive and bcsfe-save-roundtrip.`

That separates the two hypotheses **for this entry**: the cause was PER-FILE PARSE FAILURE,
not the listing budget. The entry never left the listing; only its tail was missing, and
deleting one `#` restored it. It also confirms `~/.claude/skills.daily` is the tree the client
reads, because that is where the write landed.

**Scope this claim carefully.** The re-injection channel is NOT budget-filtered: when the
later batch landed, it echoed back 10 skills that were *bare* in the spawn listing
(`voice-*`, `x64dbg`, `skill-scout`, `using-git-worktrees`, `video-join-concat`). So the
observation proves the PARSE is fixed and the full string is now what the client receives from
the file. It does **not** prove bc-drive-plus survives the budget in a fresh session — that is
a separate measurement I did not take.

**Budget discipline on the fix.** Quoting the scalar restores all 793 chars for **+440** on a
surface already over budget. That is an owner trade, not a bug fix, and round 3 was right to
decline it. Rewriting instead cost **+64** (353 -> 417), which removes the objection rather
than spending it.

### The mechanism is documented, and was documented before this lane started
Fetched independently this round (not inherited): <https://code.claude.com/docs/en/skills>

> ...Claude Code shortens descriptions to fit the listing's character budget... The budget
> scales at 1% of the model's context window. When the listing overflows, Claude Code drops
> descriptions **starting with the skills you invoke least**.

Per-entry cap **1,536** chars on `description` + `when_to_use` combined
(`skillListingMaxDescChars`). Levers: `skillListingBudgetFraction`,
`SLASH_COMMAND_TOOL_CHAR_BUDGET`, `skillOverrides: "name-only"`. Instruments nobody here had
read: `/doctor`, the `/context` Skills row, `--debug`.

Measured by key presence only (no credential read or printed):
`skillListingBudgetFraction = 0.04` in BOTH settings files — 4x default, **the primary lever
is already spent**. The other three are unset.

This is now pinned in `writing-skills/SKILL.md` (both roots) so the next lane hits it before
probing. Commit `ff14d2a6`.

### Sample 6 — my own spawn listing (an external signal I do not produce)
31 bare / 6 in-zone survivors, first bare `triage-dispatch`. Survivors: ui-audit,
ui-ux-pro-max, use-image-clipboard, video-watermark-removal, workflow-authoring,
**writing-skills**. Prior samples: 26 / 29 / 30 / 30 / 32 bare, with 5 survivors at sample 5.
The delta is writing-skills. **One observation, no cause established** — the boundary is
session-dependent, which is exactly why the ratchet gate is advisory.

## 2 · Vault dry-run — the tool is not the remedy

`python scripts/deploy-skills-daily.py --target C:/Users/Prekzursil/.agents/skills`

    IDENTICAL 219 · LEFT-AHEAD 1 · RIGHT-AHEAD 5 · DIVERGED 103
    safe to deploy 133 · needs a human merge 405 · repo-only NOT resurrected 18

Reading the plan per-file (positive control passed: `ui-audit/_fix_main_guard.py` -> COPYABLE):

| broken-guard file | bucket |
|---|---|
| ui-audit/axe_scan.mjs | NEEDS-MERGE |
| ui-audit/capture.mjs | NEEDS-MERGE |
| ui-audit/critique.mjs | NEEDS-MERGE |
| ui-audit/layout_lint.mjs | NEEDS-MERGE |
| design-studio/loop.mjs | NEEDS-MERGE |
| design-studio-session/session.mjs | NEEDS-MERGE |

**verdict H-REFUSES.** `--apply` at the vault copies 133 files and fixes **zero** of the 6
silent no-ops — they are exactly the files the hop refuses by design. Pointing the existing
tool at the vault answers the DoD question NEGATIVELY, and that is the useful answer: the
vault no-op needs a union merge, not a deploy.

## 3 · A grounding claim REFUTED, with a controlled census

Grounding: *"design-studio/loop.mjs and design-studio-session/session.mjs carry the old
lexical guard in ALL FOUR trees."*

Detector control: known-FIX -> `H-FIX`; known-BROKEN -> `H-OLD`; distinguishes = true.

| tree | H-FIX | H-OLD |
|---|---|---|
| repo `.agents/skills` | 7 | 0 |
| repo `skills/` | 7 | 0 |
| live `skills.daily` | 7 | 0 |
| live vault `.agents` | 1 | **6** |

Both files carry the realpath guard in three of four trees. Correctly scoped: **the vault is
the only tree with the old guard, and it is 6 files.** Nothing to repair in the repo roots.

### My own detector failure, same probe
My first classifier required `resolve(argv[1]) === __filename`; the shape on disk is
`resolve(argv[1]) === resolve(__filename)`. It reported `H-NONE` for 6 genuinely broken files
— and its control **passed**, because I had mutated a known-good file into the shape my own
regex was written to catch. That is self-consistency, not discrimination. Fixed by using a
REAL known-broken file (the vault's own `capture.mjs`) as the control.

## 4 · 12 negative-case clauses, net +0 characters

The brief says a clause "costs nothing". On this fleet that is false: the surface is over
budget, so every added character pushes roughly its own length of tail into darkness. The
clause is free only if paid for out of the same description.

Gates, each of which refuses rather than negotiates: P1 exists in all three trees · P2
description IDENTICAL in all three (a diverged file is left alone) · P3 `len(new) <= len(old)`
· P4 no `"`, no ` #`, no `: `.

- Two controls run first and were both refused (a 4,000-char candidate on P3; a ` #` candidate on P4).
- `video-resize-aspect` was refused **twice** by P3 (301 > 294, then 297 > 294) before it fit.
- Net across 12: **+0 characters**, which P3 makes structurally unreachable to exceed.
- Written to all THREE trees at once: `classify_pair` compares unique-line SETS, so a
  description MODIFY is DIVERGED forever and an edit authored only in the repo can never reach
  the tree the client reads.
- Token-delta printed per edit and reviewed; two losses bought back (`reverse-engineering` in
  ghidra-bridge, the `Reel/Short` trigger in video-resize-aspect).

Post-write re-read: 12 skills x 3 trees, parsed == intended, trees identical. Diff: 24 files,
24 lines, **zero** non-description lines.

### A separate defect this surfaced
`video-resize-aspect`, `video-join-concat` and `subtitle-translate` end mid-sentence
(`...the SAR/DAR +.` / `...needs identical.`). These are **not** a parse bug — they are quoted
scalars that a prior ~300-char capping pass cut on a character boundary. Two are repaired
here; `subtitle-translate` is not (P2/P3 not checked for it).

## Residual — NOT fixed, and why

1. **Defect A, the ratchet guards the wrong tree.** `ci/check_skill_description_ratchet.py`
   measures repo `.agents/skills` (105,261 chars / 346 skills) while the client reads
   `skills.daily` (~115K / 328). **`ci/` is outside this lane's declared file scope**, so this
   is reported, not fixed. Its wrong *premise* — the 1,024 limit — is corrected at the source
   in `writing-skills`.
2. **Defect B, exemptions calibrated to 1,024.** `ci/skill-description-exemptions.txt` pins
   five descriptions as over a "1,024 spec max"; the render cap is 1,536, so only
   workflow-foundry (1,750) is actually shortened. Same scope reason.
3. **The vault's 6 silent no-ops remain live.** The deploy hop refuses all six (item 2). They
   need a union merge; writing `~/.agents/skills` was not in scope and the DoD asked only for
   the dry-run.
4. **Item 3 does not scale as one document.** workflow-authoring is 1 of ~74 repo/live
   description pairs the hop refuses permanently. This needs ONE owner policy
   (live-wins / repo-wins / union) plus a multi-tree atomic writer — not a bespoke merge doc
   per file. The existing union-merge doc is the worked example.
5. **Whether the 12 edited skills render in a fresh session is UNMEASURED.** The delta channel
   that echoed them back is not budget-filtered (see item 1). Settling experiment: start a
   fresh session and read the Skills row of `/context`.

## Confidence

- **Almost certain (90-99%):** the bc-drive-plus cause was a YAML comment, and it is fixed
  (both states on the real render path + post-write re-parse in 3 trees). The vault plan
  refuses all 6 broken-guard files (per-file bucket read, positive control passed). The 12
  clauses are net +0 (P3 makes an increase unreachable; it fired twice). The guard census
  refutes the all-four-trees claim (controlled classifier, real known-broken control).
- **Likely (55-80%):** the ~74 permanently-refused description pairs are the real blocker
  upstream of items 2-4. Rests on one dry-run per tree, not on a full pairwise audit.
- **Uncertain (20-55%):** why writing-skills survived in my sample and not in sample 5. One
  observation, no cause established.
