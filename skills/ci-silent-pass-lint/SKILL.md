---
name: ci-silent-pass-lint
description: Use before any PR creation or "gates green / ready to merge" claim to detect CI/gate workflows that report GREEN while masking real findings — the recurring "qlty green yet 61 issues + 809 on Codacy" / stale-SHA-gate pattern. Runs a deterministic linter over .github/workflows/*.yml for 11 silent-pass shapes (exits nonzero on HIGH findings) plus an MCP cross-check that compares actual finding-counts at HEAD vs the gate's reported status.
---

# CI Silent-Pass Lint

## When to Trigger

Invoke this skill **before any of the following**:

- Creating a pull request (`gh pr create`, `/pr-shepherd`, `finishing-a-development-branch`)
- Claiming "all gates are green" or "ready to merge"
- Trusting a CI green badge on a new or recently modified workflow
- After adding/modifying any `.github/workflows/*.yml` file
- When `qlty`, Codacy, or DeepSource findings seem inconsistently low ("qlty green but Codacy shows 61 issues")

It also runs implicitly as part of the metaswarm pre-PR gate chain (after `verification-before-completion`, before `pr-shepherd`).

---

## Architecture — Two Parts

### Part A: Deterministic Workflow Linter (`lint_workflows.py`)

Pure-stdlib Python. Run with:

```bash
python skills/ci-silent-pass-lint/lint_workflows.py [repo-path]
# default repo-path: current directory
```

- Scans `.github/workflows/*.{yml,yaml}`
- Reports each shape hit with `file:line`, snippet, severity, and message
- Exits **nonzero** if any `HIGH`-severity finding is detected → directly gate-able
- Optionally uses `pyyaml` for structural shapes (S10, S11) if available; degrades gracefully without it

**Gate rule:** If Part A exits nonzero, the pre-PR gate fails. Fix the workflow issues before creating the PR.

### Part B: MCP Cross-Check (runbook in `gate_findings_at_head.md`)

Executed by the agent using the connected MCP tools. The agent:

1. Resolves `HEAD` SHA via `git rev-parse HEAD`
2. Queries each connected provider for finding-counts **at that exact SHA**
3. Compares against the gate's reported "green"
4. Emits a per-provider verdict table: `CLEAN PASS` vs `SILENT PASS` vs `UNKNOWN`

**Gate rule:** Any `SILENT PASS` row (provider reports green while finding-count > 0 OR SHA is stale) means the "gates are green" claim is refuted. Surface the table before creating the PR.

The full SHA-finding primitive interface — including exact MCP tool names, parameters, and the `claim_guard_check()` contract — is in [`gate_findings_at_head.md`](gate_findings_at_head.md).

---

## The 11 Silent-Pass Shapes

| # | Shape | Severity | Detection |
|---|-------|----------|-----------|
| S01 | `continue-on-error: true` on a gate/analysis step | HIGH | Regex, line-local |
| S02 | `\|\| true` / `\|\| exit 0` swallowing command exit | HIGH | Regex, line-local |
| S03 | Issue/quality policy `mode: audit` (reports, never fails) | HIGH | Regex, line-local |
| S04 | Token-less / empty-token uploads; `fail_ci_if_error: false` | HIGH | Regex, line-local |
| S05 | `set +e` without recheck; `; true`; pipe masks failure | HIGH | Regex, line-local |
| S06 | Gate step with pinned `--ref`/`--sha` SHA arg instead of HEAD | MEDIUM | Regex, line-local† |
| S07 | `if: always()` on a "success/pass/green/summary" step | LOW | Regex, windowed‡ |
| S08 | Soft thresholds: `--exit-zero`, `--no-error`, `--fail-under 0` | HIGH | Regex, line-local |
| S09 | Required-check name that doesn't match any job name | INFO | Structural, job inventory§ |
| S10 | Artifact/result upload without a fail-on-findings gate after it | MEDIUM | Structural (pyyaml) |
| S11 | `fail-fast: false` + matrix + no aggregate gate job | MEDIUM | Structural (pyyaml) |

**Confidence notes:**

- **†S06**: YAML alone cannot prove a SHA is stale (it may be a legitimately pinned historical ref in a backfill job). The linter flags `--ref`/`--sha`/`--commit` with hardcoded SHA args as MEDIUM; Part B's MCP cross-check is the authoritative stale-SHA detector. `uses: action@<sha>` (security pinning) is **not** flagged — that is a recommended practice.
- **‡S07**: `if: always()` is legitimate on artifact-upload and log-collection steps. The linter restricts flagging to steps whose `name:` contains "success", "green", "pass", or "summary" within 5 lines of the `if: always()` — narrow scope to reduce false positives. Severity is LOW/advisory.
- **§S09**: Branch-protection required-context names live in GitHub rulesets, not workflow files. The linter inventories job names as INFO; compare them against `gh api repos/{owner}/{repo}/rulesets` to find mismatches.

**Exit code:**
- `0` — no HIGH findings (MEDIUM/LOW/INFO may be present; review them)
- `1` — one or more HIGH findings → **gate fails**
- `2` — usage error (bad path etc.)

---

## Composition with claim-guard #2

`claim-guard #2` (the "always-verify claims before trusting them" guard) consumes the **same SHA-finding primitive** defined in `gate_findings_at_head.md`:

```
claim_guard_check(repo_path, owner, repo, head_sha, project_keys)
  -> SilentPassVerdict(clean: bool, silent_passes: list, unknowns: list)
```

`ci-silent-pass-lint` is the **proactive, pre-PR** trigger.
`claim-guard #2` is the **reactive, claim-time** trigger (fires when any agent asserts "green").
Both consume the same primitive; neither re-implements it.

---

## Connected MCP Providers

| Provider | MCP Tool (Part B) | SHA-pinned? |
|----------|-------------------|-------------|
| Codacy | `mcp__codacy__codacy_get_repository_with_analysis` | Partially (lags; check `lastAnalyzedCommit`) |
| Codecov | `mcp__codecov__get_commit_coverage` | Yes — pass `commit_sha` directly |
| DeepSource | `mcp__deepsource__run` with `isCommitOid: true` | Yes — pass `head_sha` as `runIdentifier` |
| qlty | `mcp__qlty__qlty_check` (local run) | N/A — always at working-tree HEAD |
| SonarCloud | `curl sonarcloud.io/api/qualitygates/project_status` (no MCP) | Via branch + timestamp |

See `gate_findings_at_head.md` for exact parameters and extraction logic per provider.

---

## Common Failure Modes Detected

- **"qlty green yet 61 issues + 809 on Codacy"** — S03 (audit mode) or S08 (--exit-zero) on the qlty step; Part B confirms actual Codacy count at HEAD.
- **"Gate green on stale SHA"** — S06 in Part A; Part B's `is_stale` field confirms.
- **"Upload step succeeds, findings silently ignored"** — S04 (no token) or S10 (no gate after upload).
- **"One matrix leg fails, overall workflow passes"** — S11 (fail-fast:false, no aggregate).
- **"CI green, branch protection satisfied, but required check was never produced"** — S09 (job name mismatch → INFO, confirmed via rulesets API).
