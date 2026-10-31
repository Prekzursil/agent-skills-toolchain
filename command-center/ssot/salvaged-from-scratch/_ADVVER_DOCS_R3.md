---
title: _ADVVER_DOCS_R3
type: note
permalink: dqverify-repo-20261013/command-center/ssot/salvaged-from-scratch/advver-docs-r3
---

# ADVERSARIAL VERIFY — DOCS lane round 3 (build 84bf3a33, audit verdict CLEAN)

VERDICT: audit HOLDS · build SOUND · must_fix EMPTY. All rows below executed at HEAD 673cd180.

## Claims attacked

| # | claim | my independent probe | verdict |
|---|---|---|---|
| A1 | 2 files, +192/-3 | `git show --numstat 84bf3a33` -> 179/0 + 13/3 | CONFIRMED |
| A2 | AGENTS/CLAUDE/README blob-identical | parent==child==HEAD blob SHAs; porcelain empty; index==HEAD | CONFIRMED |
| A3 | divergence (3,12) | 4 methods: ls-files(index), ls-tree HEAD, ls-tree 84bf3a33, filesystem — all agree; injection control both arms | CONFIRMED |
| A4 | gate is real, not a claim-reader | reads `roadmap_violations()`: parses 2 ints, compares to freshly measured `git ls-files` set diff | CONFIRMED |
| A5 | in-suite control not vacuous | built H2 (merely-notices-digits) + H3 (always-silent); BOTH FAIL the shipped control, only H1 passes | CONFIRMED |
| A6 | both-states fires on real blobs | my own impl vs blobs 75b1e418/d3c5b035/24022f1c -> 1/1/0; worktree CRLF(69) -> 0 | CONFIRMED |
| A8 | 3 skills predate the guard | ALL adds enumerated (not `-1`): 07-18/07-18/07-19, one add each; guard 07-21; strict-parity 07-24 | CONFIRMED |
| A9 | 15 tests pass | `pytest ci/tests/test_docs_executable_claims.py -q` -> 15 passed, exit 0 | CONFIRMED |
| A10 | 4 CI-equiv failures independent | ran ONLY the 4 node IDs (lane file never collected) -> same 4 fail | CONFIRMED (stronger than audit's grep) |
| A11 | audit F2: docstring :17-22 not :19-24 | read lines 1-30 | CONFIRMED — audit right, builder off by 2, report-only |
| A13 | gate never runs on push | skill-dual-write.yml:34-36 `pull_request:` only; no named step in quality.yml | CONFIRMED |
| A14 | shipped doc text accurate | every clause: sync-skills.ps1:45 exact; counts 4-way; DIFF-guard from docstring; dating exhaustive | CONFIRMED |
| — | AGENTS.md path claims | own sweep + both-states control: 32 tokens, 8 unresolved, ALL 8 mention/absence/scoped-present | CONFIRMED accurate |
| — | gate fails CLOSED | collapsed measurement -> 2 violations (RED), not silent green | CONFIRMED |
| — | lane artifact 14 rows | 3 FIX DOC / 11 no-change / 0 FIX CODE — matches both reports | CONFIRMED |

## My own detector failures (2, each caught by a second probe)
1. `git ls-files 'skills/*/SKILL.md'` — git pathspec `*` crosses `/`, gave 338/352 vs true 337/346.
   Would have manufactured a false numeric defect against both reports.
2. `grep -oiE 'FIX DOC|FIX CODE|ACCURATE'` over the whole lane artifact -> 4/1/8, contradicting both
   reports. Reading the actual table rows showed both correct. Counting the DOCUMENT not the FIELD —
   inside a lane whose subject is use-vs-mention.

## Audit weaknesses (conclusions all correct; none blocking)
- W1 "every AGENTS.md one I opened is use-vs-mention" — partial check stated as full. I completed it.
- W2 independence of the 4 failures rested on grep + inference; I proved it by execution.
- W3 called its dating "stronger"; for the 3 skills it used the same `-1`. I enumerated ALL adds.

## Top residual (CONFIRMED, disclosed by BOTH, not blocking)
The gate never executes on this program's direct-to-main pushes.