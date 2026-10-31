---
title: _VERIFY-docs-r3
type: note
permalink: dqverify-repo-20261013/command-center/ssot/salvaged-from-scratch/verify-docs-r3
---

# VERIFY lane DOCS r3 — independent audit — COMPLETE

Every row below was EXECUTED by me at HEAD `bfec0543` in `C:/Users/Prekzursil/source/ast-integrate`.

COVERAGE: all 3 DoD items executed. Full CI-equivalent suite executed (the builder had it as
NOT-CHECKED). NOT measured: an actual Linux runner; the 175 archive-dir dead refs; URL rot.

| # | Builder claim | My independent probe | Verdict |
|---|---|---|---|
| 1 | commit 84bf3a33, 2 files, +192/-3 | `git show --numstat` → 179/0 + 13/3 = +192/-3, 2 paths | CONFIRMED |
| 2 | AGENTS/CLAUDE/README byte-identical | `git rev-parse <c>^:f` vs `<c>:f` → 7bce9460 / 72a91ba9 / f5e7fc02 both sides; worktree also clean | CONFIRMED |
| 3 | 337 / 346 / 334 / 3 / 12 | my own FS-scan + `git ls-tree` at 3 revs, injection control on both arms | CONFIRMED (names identical) |
| 4 | 15 passed | `pytest ci/tests/test_docs_executable_claims.py -q` → 15 passed, exit 0 | CONFIRMED |
| 5 | both-states r1=1 pre_r1=1 fixed=0 | re-ran; blobs verified as the real historical states via `--find-object` | CONFIRMED |
| 6 | mutation survivors=[] | re-ran; 4 kills + 1 labelled expected survivor; sha256 restore MATCH | CONFIRMED |
| 7 | skills 07-18/18/19, guard 07-21, strict-parity 07-24 | `--diff-filter=A` + `-S --reverse` (stronger than builder's `-1`) | CONFIRMED |
| 8 | sync-skills.ps1:45 | read line 45 verbatim | CONFIRMED |
| 9 | guard is a DIFF guard (cited :19-24) | sentence is verbatim present at lines **17-22** | CONFIRMED content, 2-line citation drift |
| 10 | all claimed files exist; clone removed | Test-Path ×15 all True; `C:/Users/Prekzursil/ast-r3-clone` absent | CONFIRMED |
| 11 | roadmap.md carries the measured fix + REFUTED record | read lines 3-21 | CONFIRMED |
| 12 | skill-dual-write.yml PR-only, no push | `on:` block = `pull_request:` only; quality.yml never names the suite | CONFIRMED |
| 13 | tools/lib 72 tests / 6 files | `node --test tests/*.test.mjs` → tests 72 pass 72 fail 0; 6 files | CONFIRMED |
| 14 | 1 pre-existing sibling failure | full CI cmd → **4 failed**, 674 passed, 1 skipped; all 4 Windows-only, 0 refs to this lane | REFINED (see F1) |
| 15 | ruff 0.15.17 check+format exit 0 | `uvx ruff@0.15.17` both exit 0; file CR=0 | CONFIRMED |
| 16 | AGENTS.md 5 spawn hits all comments | 5 hits, lines 8/100/147/149/152, all `//` or `*` | CONFIRMED |
| 17 | workspaces / cov / claude-only 35 | package.json ×3 exact; quality.yml:295; 35 dirs | CONFIRMED |

DoD 1 PASS · DoD 2 PASS · DoD 3 PASS. Verdict CLEAN.