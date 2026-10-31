---
title: VERIFY-MCPRESEARCH-r3
type: note
permalink: dqverify-repo-20261013/command-center/ssot/salvaged-from-scratch/verify-mcpresearch-r3
---

# VERIFY LANE MCPRESEARCH round 3 — independent re-measurement — COMPLETE

VERDICT: **PARTIAL** — all four DoD items PASS when I execute them; one REAL DEFECT in a
shipped factual claim (the CRLF residual), which does not touch any DoD verdict.

COVERAGE: measured = commits/scope, file existence, all 4 DoD items, 9-gate sweep, blob
gate, secrets gate ×3, leak check, hunt, corroborate, ruff census, tool-count cross-check,
a real codex call, CRLF (two independent detectors + both-states controls), doc scoping
disclosure, refuted-wording preservation.
NOT measured: full CI (~23 steps), the one-time ruff-reformat `diff -q` equivalence.

## 0. Commits — all three exist, in scope, 0 foreign paths
bfec0543 13 files +1068/-48 · 0d3c9e93 2 files · 673cd180 1 file. Every path under
docs/mcp-audit or command-center/mcp-audit. `git status --porcelain` on both lane dirs is
EMPTY. No shared file (quality.yml, ruff.toml, .gitattributes, tools/) touched.

## 1-5. DoD — 4/4 PASS, re-executed by me
`_r2_dod_check.py 673cd180` → 4/4 PASS, 5/5 negative controls fire, rc=0.
`_r2_dod_check.py 630bb8af` → rc=1 `FAILED:dod-check ['DoD3']`. Both-states holds.

INDEPENDENT CORROBORATIONS I RAN (not the lane's instruments):
* the 23 row names are SET-IDENTICAL to the 23 mcp__* namespaces the harness exposed to
  THIS auditor session. 0 only-in-session, 0 only-in-rows.
* lane tool_count vs my session's tool inventory, 11 servers: 11/11 AGREE, 0 disagree.
  Control (deliberately wrong context7 count) → flagged.
* a REAL `mcp__codex__codex` call → `{"threadId":"019ff980-...","content":"PONG"}`.
  The codex rail WORKS; the orchestrator's briefed "a real call FAILS at OpenAI
  agent-identity registration" is REFUTED by a mechanically different probe. Lane correct.

DoD3 residual is honestly scoped by the builder inline (16/23 measured, 7 carry
`not-measured: transport='http'...`). Per C2 that is a CONFIRMED claim with a disclosed
residual, not a refutation — it must not block.

## 6-7. Gates — every quoted command reproduced
9/9 sweep markers byte-identical incl. `want 1`. Blob gate on bfec0543 (6 blobs, 0 CRLF,
ruff rc=0/rc=0, MANGLED control fires) rc=0; fail-closed on the docs-only commit as
disclosed. Secrets gate ×3 with the committed-synthetic control firing each time. Leak
check control PASSED, 40 artifacts clean, 0 matches. `_r3_hunt` refutes the stale-figures
hypothesis (r1==r2 on every cost field). `_r2_corroborate` 16/16 with its control.
ruff census in_scope=0, repo-wide 39.

## 8. REAL DEFECT — the shipped CRLF claim is false

`docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md:228-230` states as fact:
  "the `.md`/`.json` blobs carry CRLF (`ROUND3-DEFECT-CLOSURE.md` 278,
   `disposition.json` 840)"
Repeated as residual #5 of the builder report.

MEASURED — both numbers are exact LINE counts and both files are ZERO CRLF:
| rev | file | claimed | CRLF | LF |
|---|---|---|---|---|
| 0d3c9e93 | ROUND3-DEFECT-CLOSURE.md | 278 | **0** | **278** |
| 673cd180 | disposition.json | 840 | **0** | **840** |

TWO INDEPENDENT SIGNALS, both controlled:
1. byte count over `git show <rev>:<path>` — control: known-CRLF buffer → 3 (want 3),
   known-LF → 0. (My FIRST attempt used `b'\\r\\n'` = four literal chars and reported 0
   everywhere; the control caught it. Recorded, not hidden.)
2. `git ls-files --eol` → `i/lf` for README.md, AGENTS.md, disposition.json, all three
   mcp-audit .md files. Control: `*.ps1` shows `attr/text eol=crlf`, so the detector does
   distinguish.

At the ROUND-2 commit 630bb8af too: H1 "the numbers are CRLF counts" matches **0/5**;
H2 "they are line counts with 0 CRLF" matches 3/5 exactly (the 2 misses are files still
being edited within round 2, both still 0 CRLF).

CONSEQUENT — the builder's own "detector failure #2" narrative (doc :218-226) is itself a
control-that-cannot-distinguish. "AGENTS.md reads 112, exactly round 2's number, so the
detector fires and agrees": AGENTS.md's blob is 0 CRLF and 112 LF LINES, so a line count
agreed with a line count and said nothing about a CRLF detector. His FIRST reading —
"round 2's CRLF table is wrong" — was CORRECT, and the inert second control talked him out
of it. The `7aa86f16` attribution is also wrong: that commit is `docs: repair a decapitated
README section` (+7/-3 on README.md), not an EOL rewrite, and README.md is `i/lf` on both
sides of it.

SCOPED REPLACEMENT SENTENCE: "README.md and AGENTS.md are CRLF in the WORKING TREE
(`w/crlf`) but LF in the committed blob (`i/lf`); every blob this lane committed — .py,
.md and .json alike — is 0 CRLF, which is what CI reads. `.gitattributes` pins only
`*.sh`/`*.ps1`, so the worktree is unnormalised, but no committed byte is affected."
UNVERIFIED (20-55%): whether round 2's numbers came from counting the worktree or from
counting lines. Settling experiment: re-run round 2's own CRLF probe against both
`git show <rev>:<path>` and the worktree file and compare.

## 8b. OVERCLAIMS vs REAL DEFECTS
* REAL DEFECT ×1: the CRLF sentence above (false statement of fact, shipped).
* OVERCLAIM ×1: "the detector fires and agrees" (§8 consequent). Code fine, sentence wider
  than evidence; scoped version given.
* NOT overclaims — verified correctly scoped: DoD3's 16/23 disclosure; the 51.8x
  BYTES-not-tokens caveat (inline at :263); the `--` = not-measured legend
  (DISPOSITION-TABLE.md:29); "CI is not claimed green"; the provenance caveat about the
  missing round-2 verifier report; the 122 non-mounted rows disclosed at :16/:353/:393.
* Refuted round-1 and round-2 wordings ARE preserved in blockquotes, not deleted
  (ROUND2-DEFECT-CLOSURE.md:126-131) — as claimed.

## 8c. LATENT GATE GAP (not an active defect)
`dod1()` checks per-row fields but never set membership, and `main()` only fails closed
below 20 rows — so dropping up to 3 mounted servers would still print DoD1 PASS. The row
set is correct TODAY (independently confirmed 23/23), so this is latent. Settling: assert
the row-name set equals the mounted-namespace set.

## 9. Verdict
PARTIAL. 4/4 DoD items PASS on execution; every gate and quoted command reproduces; commits
clean and in scope. One real defect: a false CRLF claim in a shipped doc plus the inert
control that produced it. Nothing found that invalidates the audit's inventory, liveness,
cost or disposition results.