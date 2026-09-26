---
name: QZP silent-pass gate patterns to watch for
description: Three patterns where QZP gates report green while real findings sit on
  main. Surfaces during fleet audits.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-qzp-silent-pass-patterns
---

QZP's gate scripts have two known shapes that report PASS while real findings exist. Always check these when auditing:

1. **`name != "smells"` exemption in `run_qlty_zero.py`**: the `_run_checks` propagation step used to short-circuit smell failures. Closed by PR #175 — the test `test_smells_output_marks_run_as_failed_even_when_cli_exit_code_is_zero` now asserts the fail-on-findings semantics. If you see a regression, look for similar exemptions on the propagation `if final_return_code == 0 and entry["status"] != "pass": ...` pattern in any `run_*_zero.py`.

2. **`issue_policy.mode: audit` on the QZP self-profile**: `profiles/repos/quality-zero-platform.yml` historically carried `mode: audit`, which makes `check_codacy_zero.py:290` and `check_deepsource_zero.py:312` hardcode-return `pass`. PR #164 was opened to flip this and was superseded by PR #175 + later cleanup. The flip-to-zero should be the LAST step after main is at 0 findings on every gate, otherwise it blocks every PR.

3. **Codecov per-flag upload pinning**: airline (and any repo) pinned to a pre-Phase-2 SHA of `reusable-codecov-analytics.yml` (before commit `062e5c3`) does a single Codecov upload with empty `flags: []`, leaving cpp/node/scripts at 0% in Codecov even when Coverage 100 Gate is green locally. Bumping the pin to QZP main with the per-flag iteration fixes it. **Why:** Codecov's UI shows 0% on a flag → operator thinks the test suite doesn't exist; reality is just an upload-loop bug. **How to apply:** check the `uses: ...@sha` pin on every consumer's `codecov-analytics.yml` after merging a Phase 2+ change.