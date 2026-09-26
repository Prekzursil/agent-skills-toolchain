---
title: 'GitHub CodeQL fleet gotchas (2026-07): required-context rename + default-setup
  conflict + FP classes'
type: note
permalink: main/reference/github/git-hub-code-ql-fleet-gotchas-2026-07-required-context-rename-default-setup-conflict-fp-classes
tags:
- github
- codeql
- ci
- ruleset
- fleet
- gotcha
- dependabot
- security-scanning
---

# GitHub CodeQL fleet gotchas (discovered 2026-07-17/18, QZP + fleet sweep)

Three distinct, non-obvious CodeQL/code-scanning traps that each silently broke a fleet of repos. All fixed this session.

## 1. The `codeql / CodeQL` -> `CodeQL` required-context RENAME (fleet-wide PR blocker) — HIGH
GitHub renamed CodeQL's reported check from the status-context **`codeql / CodeQL`** to a check_run named **`CodeQL`** (+ per-language `Analyze (python|actions|javascript-typescript)`). Any repo whose branch **ruleset** (or protection) lists the OLD context `codeql / CodeQL` as a required status check is **permanently BLOCKED**: the old context never reports, so `mergeStateStatus=BLOCKED` even with every real check green.
- **Symptom:** a PR pileup that started around the rename; PRs show `[BLOCKED]` with Control-Plane/quality/CodeQL all green; `gh pr view --json statusCheckRollup` shows a check named `CodeQL` (SUCCESS) but NO `codeql / CodeQL`; the ruleset's required list still says `codeql / CodeQL`.
- **Fix (surgical, per repo):** GET the active ruleset, change ONLY that one context string `codeql / CodeQL` -> `CodeQL`, PUT it back preserving every other rule; assert `CodeQL` survives + rule types unchanged. `gh api -X PUT repos/<slug>/rulesets/<id> --input <patched.json>`. **12 of 14 QZT-governed repos had this.** A looped script fixed all 12 (per-repo verify, never empty a ruleset).

## 2. Code-scanning DEFAULT-setup + advanced `codeql.yml` CONFLICT — HIGH
Having BOTH the code-scanning **default setup** (`state: configured`) AND an advanced `.github/workflows/codeql.yml` -> GitHub **disables the advanced workflow** ("Cannot trigger workflow_dispatch on a disabled workflow"), surfaces a **"CodeQL Actions workflow not enabled"** warning, and **stale alerts never close** (the advanced scan can't upload).
- **Fix:** `gh api -X PATCH repos/<slug>/code-scanning/default-setup -f state=not-configured` -> then `gh workflow enable codeql.yml` -> `gh workflow run codeql.yml --ref main`. The fresh advanced scan then closes stale alerts (e.g. an already-code-fixed command-injection). Verify: `gh api repos/<slug>/code-scanning/default-setup` = not-configured.

## 3. CodeQL false-positive classes -> DISMISS-with-reason, not "fix" — MEDIUM-HIGH
- **`py/command-line-injection` on an argv LIST:** `subprocess.run(argv_list, ...)` with NO `shell=True` is the SAFE pattern, but CodeQL still flags it CRITICAL if any user-derived value is in the argv (taint reaches subprocess). The argv-list IS the mitigation -> dismiss-with-reason (don't shell-escape a non-shell call). (Reframe #1752: `wsl --exec bash <file> <args>` argv + isinstance guard — still flagged.)
- **`py/unused-import` on a STRING cast:** an import used only as `cast("ModuleSpec", spec)` under `if TYPE_CHECKING:` is flagged unused (CodeQL can't trace the string). Fix = move to a RUNTIME import + unquote (`cast(ModuleSpec, spec)`) so the usage is visible — NOT delete it (deleting breaks the type-checker).
- **`py/import-and-import-from`:** same module imported both `import a.b.c as x` and `from a.b.c import y`. Fix = make consistent: change the plain import to `from a.b import c as x` (same object, from-style).

## Related QZT main-red root cause
A new `scripts/*.py` that (a) isn't in `sonar.coverage.exclusions` (sonar-project.properties) AND (b) violates the Codacy-compat contract (must have `from __future__ import absolute_import`, must NOT have `from __future__ import annotations`, use `typing.List/Dict` not `list[]/dict[]`) -> 3 failures in `test_sonar_coverage_exclusions_contract` + `test_quality_codacy_compatibility` -> Control Plane Verify RED -> the WHOLE fleet's PRs inherit the red. See [[fleet-0-dependabot-alerts-always-grill-decision-log-2026-07-17]].