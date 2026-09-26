---
title: Reframe Intelligence WU-C2 gate dispute RESOLVED (coverage>=7.6 default exclusions)
type: note
permalink: main/projects/reframe-intelligence-wu-c2-gate-dispute-resolved-coverage-7.6-default-exclusions
tags:
- reframe
- intelligence
- coverage
- wu-c2
- false-blocker
- decision
---

# Reframe Intelligence WU-C2 gate dispute RESOLVED

## Context
Task: apply blocking fixes to WU-C2 (commit 7795ab2, branch feat/intelligence-design, repo Prekzursil/Reframe). An adversarial reviewer returned NO-GO claiming the WU-C2 full-suite gate (`cd sidecar && pytest --cov=media_studio --cov-branch --cov-fail-under=100`) FAILS at 99.79% on a clean checkout (12 missed stmts, +30 stmt delta = 11659 vs builder's 11629), asserting the builder's green depended on an uncommitted coverage-exclusion config.

## Finding (FALSE BLOCKER)
- [decision] Reviewer NO-GO is INCORRECT. Gate is genuinely GREEN on the committed tree.
- [observation] Two independent fresh clones of 7795ab2, run with the task-specified venv `/tmp/msv` (coverage 7.14.1, pytest-cov 7.1.0): TOTAL 11629 stmts / 2918 branch / 0 miss / 100.00%, 3086 passed. Matches builder exactly.
- [observation] Root cause of the discrepancy REPRODUCED: with coverage 7.5.4 (pre-7.6) the SAME tree gives TOTAL 11659 / 12 miss / 99.62% FAIL — exactly the reviewer's 11659 / 12-miss numbers.
- [decision] coverage.py >= 7.6.0 (Aug 2024) excludes `if TYPE_CHECKING:` blocks and `...` ellipsis bodies BY DEFAULT. The reviewer's +30 stmts and 12 misses are entirely those pre-existing phase-8 lines, counted only by old coverage. No missing config exists.
- [observation] CI (`.github/workflows/quality.yml:45`) installs `pytest pytest-cov` UNPINNED with `pip install --upgrade pip` and no lockfile → resolves latest coverage (>=7.6) → CI passes at 100%. There is NO `requirements.lock.txt` in sidecar.
- [observation] `best_frame.py` is 100% even under old coverage; all 12 misses are in other phase-8 files. WU-C2 introduced zero coverage gaps.

## Outcome
No blocking fix applies. Tree clean, HEAD==origin, WU-C2 commit scoped to the 2 declared files (best_frame.py + test_best_frame.py). Nothing committed/pushed. Returned FIXED (no change needed; blocker refuted).

## Reusable lesson
[failure] Coverage NO-GO based on raw % without checking coverage.py version: pre-7.6 vs >=7.6 differ on `if TYPE_CHECKING:` + `...` default exclusion → ~30-stmt swing on this repo. Always pin the verifier's coverage to what CI installs before declaring a coverage blocker.
