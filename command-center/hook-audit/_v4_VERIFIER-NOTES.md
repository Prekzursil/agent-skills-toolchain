---
title: _v4_VERIFIER-NOTES
type: note
permalink: dqverify-repo-20261013/command-center/hook-audit/v4-verifier-notes
---

# HOOKRESEARCH — round-4 ADVERSARIAL VERIFIER notes (attacking BUILD **and** AUDIT)

STATUS: COMPLETE. Every row below was EXECUTED, not read. Probes are re-runnable and left
untracked next to the auditor's own untracked `_verify_r4_*.py`.

COVERAGE — NOT measured (stated so no verdict here is cited beyond its evidence): the 7 launcher
settings entries; the LIVE copies of `git-hygiene`/`wire-check` on the guarded path (the live
15-minute throttle clock was deliberately left alone); whether a live Stop event has ever hit the
35 s ceiling; `probe_hook_fleet.py --inertness` was NOT re-run (it rewrites a tracked file and the
auditor already reproduced it).

| # | claim under attack | verdict | instrument |
|---|---|---|---|
| V1 | 861fd533 = 15 files, no foreign paths | CONFIRMED | `git show --name-only` |
| V2 | four gates + five R4 probes reproduce | CONFIRMED except `_r4_githygiene_range.py` | executed all |
| V3 | AUDIT D1b: fail path destroys committed evidence | **CONFIRMED, deterministically** | `_v4_d1_repro.py` |
| V4 | AUDIT D2: 3 regression files collect 0 pytest tests | CONFIRMED (pre-dates r4) | `pytest --collect-only` |
| V5 | DoD-1 aggregate the gate cannot check | HOLDS | `_v4_indep_h4.py` (planted-outlier control) |
| V6 | index→label mapping of the 17 cited rows | ALL 4 named rows map | `_v4_indep_h4.py` |
| V7 | CLONE-GREEN (neither lane ran this) | **GREEN, detector live in the clone** | `_v4_cloneproof.py` |
| V8 | uncited budget cells are WRONG numbers | REFUTED — all match both manifests | `_v4_budget_crosscheck.py` |
| V9 | within-table citation coverage | 45 uncovered cells in 9 passing tables | `_v4_budget_crosscheck.py` |
| V10 | tree integrity, hooks untouched | CONFIRMED clean before and after | `git status --porcelain` |

## Ledger

* **V3.** `GIT_HYGIENE=off` (`hooks/git-hygiene/check.py:1183`) forces BOTH arms early-return, so
  `arms_discriminate` is False by construction — a deterministic repro in ~1 s instead of the
  auditor's lucky 97.1x. Result: `R4-GITHYGIENE-RANGE.json` rewritten, **6 top-level keys lost**
  (`samples_ms`, `range_ms`, `range_pct_*`, `h4_recorded_run_ms`, `understatement_factor_vs_h4`),
  gate `0 unbacked -> 15 unbacked`. The auditor's split "8 drift + 7 unresolved" is WRONG; measured
  **5 EVIDENCE-DRIFT + 10 path-does-not-resolve**. Total 15 is right.
* **MY OWN DETECTOR FAILURE, recorded not deleted.** `_v4_d1_repro.py` reported
  `restored_byte_exact=false`. That was CRLF: worktree 40 CRLF vs blob 0, identical after LF
  normalisation (`_v4_indep_h4.py:crlf_artifact`). The restore WAS exact — post-restore sha equals
  pre-probe sha and the gate returned to green. A self-contradicting field is a detector failure,
  not a finding.
* **V8/V9.** The H4 rule demands ONE marker per measurement table, so 45 measurement cells inside
  the 11 tables the gate PASSES carry no marker. ~26 sit in deliberately waived "refuted round-1
  wording" tables. The live ones I could resolve are all CORRECT: event budgets 20/35/15/15 match
  both manifests; `0 B` / `1,364 B` match `stdout_bytes`; `271 ms` matches `subsequent_max_ms`
  271.4. So this is a COVERAGE residual, not a wrong number — but the docs disclose only the
  *prose* gap, not this one.
* **Manifest mirror vs live settings.** `Stop` mirror 35 == live 35 (auditor checked this one).
  `PostToolUse` mirror 15 vs live **25**; `PreToolUse` mirror 15 vs live **20**. The error direction
  is conservative (a too-small denominator over-reports ceiling violations), so F4's count of 1 live
  violation cannot be an under-report.
* **CI.** `check_citations|test_citation_gate|hook-audit` appear in ZERO workflow files at HEAD
  (27da3215). The `_r4_` hits in `mcp-audit.yml` are a SIBLING lane's `_r4_redproof`/`_r4_selfcheck`
  — a mention, not this lane's gate.
* **Push state.** 861fd533 IS on `origin/main` (contained in 27da3215). A round 5 is a follow-up
  commit, never an amend.

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.
— superseded: this file was rewritten after every milestone and the table above is measured.