---
title: P2NEXT-ADVVERIFY
type: note
permalink: dqverify-repo-20261013/command-center/ssot/salvaged-from-scratch/p2-next-advverify
---

# P2NEXT adversarial verification (round 3 verifier) — MEASURED

Repo: C:/Users/Prekzursil/source/ast-integrate  HEAD 673cd180 (measurement rev)
All numbers below re-derived by MY OWN scripts in C:/Users/Prekzursil/source/_advver_M14/scratch/,
reading committed blobs (`git show HEAD:<path>`). Nothing in the repo was written by me.

## BUILD — every DoD item re-derived and it holds

| claim | my independent method | result |
|---|---|---|
| population 52 BLOCKED/FAILED | (a) catalog `output_path` route, (b) git tree-walk over 582 committed JSONs, catalog never consulted | 52 both ways, identical id set, 0 outside catalog |
| split 42 / 10 | STRICT regex EXCLUDING bare vendor names (`cross-vendor|different vendors|differently-vendored|second vendor|other vendor|non-anthropic`) | 42 / 10, same members |
| no use-vs-mention padding | control: strict regex silent on `openai/gpt-5-codex reviewer`, fires on `two reviewers from DIFFERENT vendors` | passes both directions |
| dangerous direction | every catalog field + every receipt string on the 10 satisfiable | 0 cross-vendor demands; all vendor hits are file paths / CI-workflow inventory |
| scripts CHECK-only | 4 scripts run under my own sha256 guard (control: hasher sees a 1-byte change) | artifacts_changed=[] every run |
| both-states controls | re-ran `_r2_control_stability.py` and `_r2_control_b20.py` myself | 6 move on broken / 0 on fixed; rc=1 on mutated expectation / rc=0 unmutated |
| commit scope | 3 commits, `--name-only` filtered | 19/14/2 files, 0 outside `command-center/p2-next/` |
| four " M" REVIEW files | worktree bytes vs HEAD blob (control: ADV-0041 116314 vs 78567 → False) | all 4 identical → stale stat-cache |
| committed lint | `ruff format --check` on the 42 tracked lane .py | 42/42 formatted; `ruff check` clean |
| review SUBSTANCE (new signal) | EXECUTED two review-note claims neither builder nor auditor executed | crcp `sentinel`↔`write_path` cycle exists; exactly 1 `.coverage-thresholds.json` — both hold |

## AUDIT — verdict survives, three evidentiary sentences do not

1. "156 quoted strings … BYTE-FOR-BYTE … 0 mismatches" → **23 of 156 differ.** 13 `blocked_on`
   quotes in VENDOR-SATISFIABILITY.json are silent 300-char prefixes; 10 `reviewer_requirement`
   quotes in REVIEW-GATE-SPLIT.json are silent 240-char prefixes. All strict prefixes, no
   fabrication. Comparator control: 133/156 exact, so it discriminates.
   Impact on DoD1: NONE — I checked that no truncation drops the cross-vendor clause for any of
   the 42 (`rail rows where truncation LOST the clause: []`).
2. FINDING 1 "FIVE lines across TWO files still say 43" → **7 assertive lines** (+1 citation):
   CROSS-VENDOR-RAIL-STATUS.md:1,4,**20**,69 and E2E-WAVE-STATUS.md:124,369,**384** (+:660 cites
   the anchor). The auditor missed :20 and :384 — the same incomplete-blast-radius defect it
   was reporting.
3. "my 9 probes untracked and ruff-formatted so they cannot red-block" / "TREE LEFT AS FOUND" →
   8 untracked `_a3_*.py`, and **2 of them fail `ruff format --check`**, so
   `uvx ruff@0.15.17 format --check command-center/p2-next` (the exact command the BUILD cites)
   now exits 1: `_a3_idem_and_137.py`, `_a3_preedit.py`. CI unaffected (tracked-only is 42/42).

## Disclosure gap neither side stated plainly (non-blocking)
All 10 "independent fresh-context" reviews carry
`reviewer_id = "p2next-build-lane-fresh-context-claude-opus-5-reviewer"` and only TWO distinct
timestamps (7 @ 19:40:53Z, 3 @ 21:30:12Z). The reviewer is the BUILD LANE, batch-writing. The
operative clause ("has not seen this unit's transcript") is met, the id self-discloses, and the
notes survive my executable spot-checks — but the lane brief said "run independent review", and
what ran is an honestly-labelled self-review by the lane.

VERDICT: build_is_sound = TRUE. audit_holds = FALSE (conclusions right, three verification
sentences executably false). must_fix = EMPTY — no blocking build defect proven.