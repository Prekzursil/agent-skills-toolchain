---
title: SKILLS2-ROUND2
type: note
permalink: dqverify-repo-20261013/command-center/grounding/skills2-round2
---

# LANE SKILLS2 — ROUND 2 (re-entry after a CONFIRMED refutation)

STATUS: **MEASURED.** Every row below names the probe that produced it and the control that
proves the probe can fail. Raw stdout is committed beside this file.

Round 1 shipped commit `1e9cfe81`. An independent audit returned **PARTIAL**; a third-pass
adversarial verifier returned `build_is_sound=TRUE, audit_holds=TRUE, must_fix=EMPTY`. Round 2
fixes what was CONFIRMED and does **not** re-litigate the four DoD items — both reviewers
re-executed all four and passed them.

COVERAGE — what round 2 did NOT measure:
- Why the render budget `B` moves between sessions (only *that* it moves, on three samples).
- The per-description truncation cap value (round-1 residual, still UNVERIFIED).
- `~/.agents/skills` was **read-only** all round; R4 is closed by a scoped sentence + handback.
- The `dead_button_crawl.mjs` union merge is NOT done — only its main-guard was repaired.
- The 7,300–13,000-char budget overrun is still not acted on (owner's call).

---

## Work list — outcome of every item

| # | item | kind | outcome |
|---|---|---|---|
| R1 | `:81` "~7,300 OVER … that is the entire defect" as a fleet constant | OVERCLAIM | **FIXED (sentence)** — refuted on a 3rd sample, re-scoped, old wording kept |
| R2 | `:87` "frees 1,891 = **26%** of the need" | OVERCLAIM | **FIXED (sentence)** — 1,891 reproduces; it is 15–26% *depending on session* |
| R3 | `:81` quoted pre-edit 115,478 while item 4 claims −22 | inconsistency | **FIXED** — fleet is 115,461, measured with the folded-aware parser |
| R4 | "no new drift" — false for the vault (+6) | OVERCLAIM | **FIXED (sentence) + handback**; round 2 added none of its own (403 → 403) |
| R5 | WHEN census 257→256 undisclosed | undisclosed regression | **FIXED (code + sentence)** — real regression was `transcribe`, now net +0 |
| R6 | `dead_button_crawl.mjs` old main-guard | real code defect | **FIXED + proven executably**; two prior characterisations of it REFUTED |
| R7 | a 4th independent boundary sample | new evidence | **DONE** — this session; verdict `H-SESSION` |
| R8 | audit "5 of 7 shorter" vs verifier "4 of 7" | reports disagree | **RESOLVED from raw deltas — verifier is right, 4 of 7** |

---

## R7 — the render budget is NOT a fleet constant (three sessions)

`_s2_r2_boundary.py`. This session's injected skill listing is a sample neither the builder nor
the auditor saw.

| sample | bare | lower bound | upper bound |
|---|---:|---:|---:|
| round-1 build | 30 | 108,144 | 108,144 |
| independent audit | 29 | 102,511 | 105,336 |
| **this session** | **30** | **102,511** | **105,239** |

Best fit here `B = 103,025` at **2 mismatches / 328**. Spread across samples **5,633 chars =
21.4 median descriptions**; the builder's `B` crosses 13 skills later than this session's first
bare entry. Verdict `H-SESSION`. Hypotheses were stated before the control ran and predict
different tables.

Controls, all passing: **C2 parser** reproduces three constants computed by two other,
separately-written parsers (fleet 115,456 pre-edit, folded 12, over-1024 11) — the guard against
the folded-scalar blind spot; **C1 premise** — all 30 observed-bare skills have non-empty text
on disk (0 absent, 0 empty), so this is still a render bug; **C3 order** — the bare set is a
contiguous alphabetical tail ending at the last entry on disk, **0** bare entries before the
zone.

Accuracy corroboration for the two transcriptions: my upper bound and the auditor's differ by
**97** chars — exactly the description length of `writing-skills`, the single skill that renders
in their session and not in mine. Two independent hand transcriptions agreeing to one skill's
worth of chars is a much stronger signal than either alone.

Mechanism unchanged and now confirmed on three samples: order-truncation, contiguous tail,
in-zone survivors. Survivors here span **159–1,154** chars (`ui-ux-pro-max`, `using-superpowers`,
`video-watermark-removal`, `workflow-authoring`), which again refutes any "small entries survive"
reading. `video-watermark-removal` and `workflow-authoring` survive in **all three** sessions —
the strongest hint yet that the exemption term is real, still **UNVERIFIED**.

## R5 — the WHEN census masked the regression it was measuring

`_s2_r2_census.py`. The round-1 regex counts `"Do NOT use when …"` as a positive statement of
when to use a skill. Consequence: the net (−1) was right while the attribution was wrong in
**both** directions — it flagged `research-ops` (which only changed marker wording and still
says when to use itself) and missed `transcribe` (which lost its only positive opener).

| state | old detector | negative-aware detector |
|---|---:|---:|
| PRE (pre-round-1) | 257 | 268 |
| R1 (as committed) | 256 | 267 |
| **R2 (now)** | **257** | **268** |

Round 2: **0** skills lost a WHEN, net **+0** vs pre-round-1.
Control: anchored to the frozen R1 git blob, not to disk. The first version read disk and went
`NOT DISCRIMINATING` the moment the fix landed — a control that dies when its defect is repaired
cannot be cited later. Now: old detector True/True across PRE→R1 (blind), new detector
True/False (sees it), and non-vacuous on real positive-WHEN text.
Disclosed limitation: the new detector accepts `use for`/`use to`, which is why `research-ops`
passes it; a stricter marker set would fail it too, and round 2 restored its `Use when` anyway.

## R6 — the guard fix, and the two sentences it refuted

`_s2_r2_deadbutton.py`, `_s2_r2_guardvals.mjs`, `_s2_r2_guard_exec.ps1`, `_s2_r2_reapply_guard.py`.

1. **"One-line change" / "a copy-back, not new authorship" — both REFUTED.** repo 286 lines vs
   live 367, two-directional, 8 significant repo-only vs **56** significant live-only lines.
   Live replaced the `__uiAuditMut` counter with a signature-based noise-attribution engine.
   A copy-back would import 56 unreviewed lines. This is a second `workflow-authoring`: it needs
   a union merge, **open, handed to the owner**.
2. **The probe's own premise was wrong first.** An 8.3 short path does **not** break the lexical
   guard — Node keeps the short form on both sides — and the first probe therefore reported
   `GUARD IS FIXED` while it was broken. A **junction** (the documented `~/.claude/skills` →
   `skills.daily` shape) does: `LEXICAL false / REALPATH true`. Rebuilt on the measured mechanism.
3. **The repair tool commits the defect class it exists to fix.** `needs_import()` was called on
   the already-patched text, where `OLD` is gone and `NEW` itself contains `realpathSync`, so it
   always answered "already imported" and never inserted the import. The `ReferenceError` was
   swallowed by the guard's own `catch`, falling back to the broken lexical compare. Fixed at the
   call site plus a hard post-condition; `.mjs` files rewound to HEAD bytes and re-patched **by
   the corrected tool** so disk == tool output.
4. **Executable both-states proof**, same inode, same command:

   | state | canonical | via junction |
   |---|---|---|
   | before | exit 1, 157 chars — ran | **exit 0, 0 chars — never ran** |
   | after | exit 1, 157 chars — ran | exit 1, 157 chars — ran |

**Only this probe caught (3).** The diff, `node --check`, the presence of `__isMain`, and the
tool's own exit 0 all said the repair had landed.

## Final verification — `_s2_r2_finalverify.py`, all seven green

| | |
|---|---|
| V1 fleet chars | **115,461** = expected. Folded-blind parser reports 106,618 (**−8,843**) — round 1's trap, reproduced deliberately as a control |
| V2 tri-tree identity | `transcribe` / `screenshot` / `research-ops` byte-identical in all 3 trees |
| V3 lexical-recall gate | all 7 lane-touched skills, **0 undeclared losses**; word survives if in the description **or the skill name** (mechanical, not asserted) |
| V4 cumulative delta | **−17 chars** vs the pre-round-1 baseline (must be ≤ 0) |
| V5 main-guard | old-guard gone / `__isMain` / import present in **all four** trees |
| V6 line endings | `crlf=0` on all four files this lane wrote |
| V7 dual-write gate | exit 0 |

Vault dry-run re-run: `needs_merge` **403**, unchanged — round 2 added no new vault drift
(its edits all touch files that were already `DIVERGED`).

---

## Detector failures round 2 caught in itself

Recorded because each would have shipped a false green:

1. **8.3-short-path premise** — probe reported `GUARD IS FIXED` on a broken guard. Fixed by
   measuring the two compared values instead of assuming which spelling breaks them.
2. **A repair that did not repair** — every cheap signal said it had.
3. **Folded-scalar blind parser** — V1 returned 106,618 against an expected 115,461. Because the
   expectation was written down *first*, the −8,843 was diagnosed as a parser blind spot rather
   than absorbed by editing the constant. `106,618 − 106,613` (round 1's identical misreading)
   `= 5`, exactly this round's net char delta — the two readings are consistent with each other.
4. **Two controls that died on their own fix** — the census and applier controls both read disk
   as the "broken" reference and went dark the moment the repair landed. Both re-anchored to a
   frozen git blob.
5. **A too-strict recall matcher** — prefix-only matching reported 5 false losses on
   `tdd-workflow` alone (`test` not matching `test-driven-development`). Now substring-aware at
   ≥4 chars, plus skill-name recovery.