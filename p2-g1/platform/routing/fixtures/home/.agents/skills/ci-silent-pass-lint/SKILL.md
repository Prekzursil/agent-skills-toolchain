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

### The 11 Silent-Pass Shapes
### Composition with claim-guard #2
### Connected MCP Providers
### Common Failure Modes Detected
