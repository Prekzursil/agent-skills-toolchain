---
title: gate_findings_at_head
type: note
permalink: dqverify-repo-20261013/skills/ci-silent-pass-lint/gate-findings-at-head
---

# SHA-Finding Primitive — Cross-Check Findings at HEAD

This runbook documents the **shared SHA-finding primitive** used by:

- **Part B** of `ci-silent-pass-lint` (MCP cross-check: actual finding-counts at HEAD vs gate's "green")
- **claim-guard #2** (consuming the same interface to assert truthfulness of any "gates green / ready to merge" claim)

---

## Interface Contract

```
Input:
  repo_path    : str   — local path to the repository checkout
  owner        : str   — GitHub org/user (e.g. "Prekzursil")
  repo         : str   — repository name (e.g. "my-project")
  head_sha     : str   — 40-hex commit SHA at HEAD (see §1)
  project_keys : dict  — per-provider project identifiers (see §2)

Output per provider (assemble into a list):
  {
    "provider"       : str,   # "codacy" | "codecov" | "deepsource" | "qlty"
    "finding_count"  : int,   # issues/violations at head_sha; -1 = unavailable
    "gate_status"    : str,   # "pass" | "fail" | "unknown"
    "sha_checked"    : str,   # SHA the provider actually analyzed
    "is_stale"       : bool,  # sha_checked != head_sha (or provider returned no SHA)
    "raw_response"   : dict,  # trimmed provider payload for audit trail
  }

Silent-pass verdict:
  SILENT PASS if gate_status == "pass" AND (finding_count > 0 OR is_stale == True)
  CLEAN PASS  if gate_status == "pass" AND finding_count == 0 AND is_stale == False
  REAL FAIL   if gate_status == "fail"
  UNKNOWN     if finding_count == -1
```

---

## Step 1 — Resolve HEAD SHA

```bash
git -C <repo_path> rev-parse HEAD
```

Store the result as `head_sha` (40 hex chars). This is the ground-truth SHA every
cloud provider must be queried against. If the provider returns a different SHA,
`is_stale = True`.

---

## Step 2 — Query Each Provider at HEAD SHA

### 2A. Codacy — `mcp__codacy__codacy_get_repository_with_analysis`

MCP tool: `mcp__codacy__codacy_get_repository_with_analysis`

Parameters:
```json
{
  "provider": "gh",
  "organization": "<owner>",
  "repository": "<repo>",
  "branchName": "<current-branch-or-omit-for-default>"
}
```

Extraction logic:
- `finding_count` ← `response.repository.issueCount` (or `.issues.total` depending on response shape)
- `gate_status` ← `"pass"` if `finding_count == 0`, else `"fail"` (Codacy doesn't expose a binary gate field in this endpoint — use the issue count directly)
- `sha_checked` ← `response.repository.lastAnalyzedCommit` or `response.commit.sha`; compare to `head_sha`
- If the response contains no SHA field, set `is_stale = True` (cannot confirm provenance)

For PR-level analysis use `mcp__codacy__codacy_get_repository_pull_request` with the open PR number.

Note — Codacy does NOT expose a per-commit gate-status endpoint in the connected MCP.
The `codacy_get_repository_with_analysis` endpoint reflects the most recently analyzed
state, which may lag HEAD. If `sha_checked != head_sha`, the result is stale → `is_stale = True`.

### 2B. Codecov — `mcp__codecov__get_commit_coverage`

MCP tool: `mcp__codecov__get_commit_coverage`

Parameters:
```json
{
  "owner": "<owner>",
  "repo": "<repo>",
  "commit_sha": "<head_sha>"
}
```

This tool is **SHA-pinned by design** — it queries exactly the commit you pass.

Extraction logic:
- `finding_count` ← not applicable directly (Codecov tracks coverage %, not issue count)
  Use `response.totals.coverage` < threshold → treat as finding for coverage gate purposes.
- `gate_status` ← `"pass"` if coverage meets repo threshold, else `"fail"`
- `sha_checked` ← `response.commitid` (should equal `head_sha`)
- `is_stale` ← `response.commitid != head_sha`

Also available: `mcp__codecov__get_repo_coverage` (branch-level, less precise).

### 2C. DeepSource — `mcp__deepsource__run` (by commitOid)

MCP tool: `mcp__deepsource__run`

Parameters:
```json
{
  "projectKey": "<deepsource-project-key>",
  "runIdentifier": "<head_sha>",
  "isCommitOid": true
}
```

This resolves the analysis run for the exact commit SHA.

Extraction logic:
- `finding_count` ← `response.run.issuesRaisedCount` (or `.summary.occurrences`)
- `gate_status` ← `"pass"` if `finding_count == 0`, else `"fail"`
- `sha_checked` ← `response.run.commitOid`
- `is_stale` ← `sha_checked != head_sha`
- If no run found for this commitOid → `finding_count = -1`, `gate_status = "unknown"`, `is_stale = True`

List recent runs with `mcp__deepsource__runs` (params: `projectKey`) to find the latest run's
commit SHA — if it doesn't match `head_sha`, the last analysis is stale.

### 2D. qlty — `mcp__qlty__qlty_check` (local execution at HEAD)

MCP tool: `mcp__qlty__qlty_check`

Parameters:
```json
{
  "repo_dir": "<repo_path>",
  "all": true,
  "summary": true
}
```

qlty runs locally against the working tree, so it is **always at HEAD** — no SHA staleness.

Extraction logic:
- `finding_count` ← parse `response` for total issue count
- `gate_status` ← `"pass"` if `finding_count == 0`, else `"fail"`
- `sha_checked` ← `head_sha` (by construction — local run)
- `is_stale` ← `false` always

Check qlty config presence first: `mcp__qlty__qlty_status` (params: `repo_dir`).

### 2E. SonarQube / SonarCloud — no connected MCP server

SonarQube/SonarCloud does not have a connected MCP server. Use the REST API directly:

```bash
# Quality gate status at a specific SHA (analysis key resolved from commit)
curl -s -u "$SONAR_TOKEN:" \
  "https://sonarcloud.io/api/qualitygates/project_status?projectKey=<sonar-project-key>&branch=<branch>"
```

Extraction logic:
- `gate_status` ← `response.projectStatus.status == "OK"` → `"pass"` else `"fail"`
- `sha_checked` ← `response.projectStatus.periods[].date` (no direct SHA field — use timestamp comparison)
- `is_stale` → compare last analysis timestamp against last `git log --format=%ci HEAD` timestamp

For SHA-pinned lookup: `api/project_analyses/search?project=<key>` then match `revision` field to `head_sha`.

---

## Step 3 — Assertion Logic

```python
def assert_gate_is_clean_at_head(results: list[dict]) -> bool:
    """
    Returns True only if ALL providers report:
      - gate_status == "pass"
      - finding_count == 0 (or N/A for coverage-only providers)
      - is_stale == False
    Emits a structured verdict for each provider.
    """
    silent_passes = []
    for r in results:
        if r["gate_status"] == "pass" and (r["finding_count"] > 0 or r["is_stale"]):
            silent_passes.append(r)
    return len(silent_passes) == 0
```

Output format per provider (for claim-guard #2 consumption):

```
PROVIDER   | FINDING_COUNT | GATE_STATUS | SHA_CHECKED        | IS_STALE | VERDICT
-----------|---------------|-------------|---------------------|----------|--------
codacy     | 61            | pass        | abc123...           | True     | SILENT PASS
codecov    | 0             | pass        | <head_sha>          | False    | CLEAN PASS
deepsource | 809           | pass        | <head_sha>          | False    | SILENT PASS
qlty       | 0             | pass        | <head_sha> (local)  | False    | CLEAN PASS
```

The canonical "qlty green yet 61 issues + 809 on codacy" scenario shows up as two
SILENT PASS rows — the gate claiming green while real findings exist at HEAD.

---

## Step 4 — Threshold Handling

If the project has declared an explicit threshold (e.g. coverage >= 80%, issues <= N),
substitute the threshold comparison for the `finding_count == 0` check:

```python
is_within_threshold = finding_count <= declared_threshold
gate_status_honest = "pass" if is_within_threshold else "fail"
is_silent_pass = (reported_gate_status == "pass") and not is_within_threshold
```

Thresholds live in:
- Codecov: `codecov.yml` → `coverage.status.project.target`
- DeepSource: project settings (API-only)
- Codacy: `Settings > Quality Settings > Issue threshold`
- qlty: `.qlty/qlty.toml` → `[smells]` thresholds

---

## Notes for claim-guard #2

This primitive is designed to be called at the moment any agent claims
"gates are green / ready to merge." The wire interface is:

```
claim_guard_check(
  repo_path  = cwd,
  owner      = git_remote_owner(),
  repo       = git_remote_repo(),
  head_sha   = git_rev_parse_head(),
  project_keys = load_from_project_config(),   # .deepsource.toml, sonar-project.properties, etc.
) -> SilentPassVerdict(clean: bool, silent_passes: list[dict], unknowns: list[str])
```

A verdict with `clean=False` and non-empty `silent_passes` means at least one provider
is reporting green while real findings exist at HEAD — the "claim" is refuted.