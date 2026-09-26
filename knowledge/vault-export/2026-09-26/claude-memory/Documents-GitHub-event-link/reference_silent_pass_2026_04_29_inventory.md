---
name: 2026-04-29 silent-pass mechanism inventory
description: Catalogue of silent-pass mechanisms in the QZP scanner-matrix that masked
  findings on cloud dashboards while CI reported green
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-silent-pass-2026-04-29-inventory
---

Each entry is a concrete pattern that produced "green CI but red dashboard" symptoms. Reference this list before declaring a gate strict-zero compliant.

## Closed (PRs landed or open)

### 1. Semgrep `ci` exits 0 on non-blocking findings
- **Symptom:** event-link 2 findings, DevExtreme 7, but lane reports green
- **Why:** `semgrep ci` only exits 1 when findings have "blocking" severity on the cloud policy; non-blocking findings are dashboard-only
- **Fix:** PR #221 — capture `--sarif-output`, run `check_semgrep_zero.py` SARIF gate which counts ALL findings regardless of severity
- **Gotcha:** `--error` / `--strict` are `semgrep scan` flags, NOT `semgrep ci` — using them on `ci` causes "unknown option" failure on every run

### 2. Semgrep auth not configured → no SARIF
- **Symptom:** After fix #1 lands on QZP, `semgrep ci` rejects with "run `semgrep login` before using `semgrep ci`" because SEMGREP_APP_TOKEN isn't set; SARIF is empty; gate has nothing to count
- **Fix:** PR #221 fallback — `semgrep scan --config auto --sarif --output` produces SARIF without auth, gate counts findings same way

### 3. Inline `# nosemgrep` / `# nosem` ignored by `--config auto`
- **Symptom:** Suppression directives that work under cloud-config don't honor inline forms
- **Fix:** PR #221 — use `.semgrepignore` (file-level) which works for both modes
- **Lesson:** When a gate has authenticated + unauthenticated modes, prefer file-level config over inline directives — inline rule-ID resolution can silently differ between modes

### 4. Codacy gate only checked issue count
- **Symptom:** Complexity 15% > goal 10%, duplication 19% > goal 10%, coverage missing — gate green
- **Fix:** PR #222 — `codacy_quality_thresholds.py` queries repository-analysis endpoint, fails when `complexFilesPercentage > goal`, `duplicationPercentage > goal`, coverage uploaded=False, OR coverage < 100% (override of Codacy's default 60% min)

### 5. Codacy publish step `continue-on-error: true` + wrong token
- **Symptom:** All fleet repos show empty coverage on Codacy dashboard despite Coverage 100 Gate passing locally
- **Why:** Reporter used `secrets.CODACY_API_TOKEN` (account-scoped) against a project-scoped reporter endpoint — exits 1 with "Request URL not found" but `continue-on-error: true` masks it
- **Fix:** PR #223 — switch to `secrets.CODACY_PROJECT_TOKEN`, remove `continue-on-error`, add preflight error message when secret missing

### 6. DeepSource publish `|| true` on each report
- **Symptom:** Missing `DEEPSOURCE_DSN` or any per-file API error swallowed; coverage never reaches dashboard
- **Fix:** PR #223 — drop `|| true`, add preflight check for `DEEPSOURCE_DSN`

### 7. Workflow contract test locked-in silent-pass form
- **Symptom:** `tests/test_workflow_contracts.py::test_semgrep_lane_uses_supported_cli_invocation` REJECTED `--error` and required the bare `semgrep ci` form
- **Fix:** PR #221 — invert test to require the new SARIF + zero-gate pattern, reject the silent-pass forms
- **Lesson:** Contract tests can ossify the bug they were meant to prevent. When updating a gate's enforcement shape, also check what its contract test asserts.

## Documented but not closed (need operator action)

### 8. QZP `issue_policy.mode: audit`
- **Symptom:** DeepSource gate correctly counts 875 issues from QZP HTML, but `_codacy_status` returns "pass" because the policy mode treats findings as informational
- **Why:** Deliberate carve-out documented in `profiles/repos/quality-zero-platform.yml`: *"110 Sonar / 838 Codacy / 1116 DeepSource issues accumulated before governance landed — fixing them all is out of scope"*
- **Resolution:** Flip to `mode: zero` once operator is ready to absorb the merge freeze on QZP main

### 9. DeepScan github_check_context skips when no status exists
- **Symptom:** Airline has 0 DeepScan GitHub status checks on commits; gate's `_evaluate_github_check_context` returns 0 issues + no findings on push events
- **Why:** DeepScan GitHub App not installed on the repo; gate trusts presence-of-status as signal
- **Resolution:** Install the DeepScan GitHub App, OR add an explicit status-required validation to the gate

## Repo-level config gaps closed

### 10. DevExtreme had no `.deepsource.toml`
- **Symptom:** 140 DeepSource findings, ~120 of them on `ent/**` (entgo-generated CRUD layer)
- **Fix:** DevExtreme PR #29 — add config that excludes `ent/**`, `schema_definitions/**`, etc.

### 11. env-inspector had no `.deepsource.toml`
- **Symptom:** Repo doesn't appear on DeepSource dashboard at all (no analyses)
- **Fix:** env-inspector PR #113 — add baseline config so analyses can start once `DEEPSOURCE_DSN` secret is set

## Pattern recognition

When the user reports "X cloud platform shows N issues but PR/main is green":
1. Check the gate script's exit-code semantics — does it propagate findings or just check for status presence?
2. Check `continue-on-error: true` and `|| true` in the workflow lane
3. Check the gate's policy_mode handling — `audit` mode silently maps fail → pass
4. Check whether the upload step uses the right per-platform token (Codacy needs project-scoped, others need DSN/PAT)
5. Check whether contract tests are locking in the silent-pass form