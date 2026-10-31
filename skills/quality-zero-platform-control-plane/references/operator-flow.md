---
title: operator-flow
type: note
permalink: dqverify-repo-20261013/skills/quality-zero-platform-control-plane/references/operator-flow
---

# Operator Flow

Use this reference when the task is operational rather than architectural.

## Required order

1. Resolve controller truth.
2. Audit live GitHub wrapper workflows.
3. Audit live ruleset presence and required-status-check parity.
4. Audit latest relevant workflow conclusions.
5. Classify the repo.
6. Only then propose or apply the smallest next step.

## Classification

- `success`
  - repo is enrolled
  - expected wrappers exist
  - ruleset exists and matches expected contexts
  - latest relevant platform and gate runs are green
- `partial`
  - repo is enrolled but drifted
  - wrappers are missing or stale
  - ruleset is missing or mismatched
  - latest platform runs still fail
- `blocked`
  - GitHub auth is unavailable
  - trusted-runner auth is unavailable
  - provider secret or variable inputs are missing
  - provider admin truth must be confirmed manually before tightening rulesets

## Next-step priority

1. Fix controller and rollout drift before product code.
2. Fix missing repo-local verify and AGENTS contract before tightening rulesets.
3. Fix stale wrapper refs before interpreting recent failing runs as code debt.
4. Treat provider bootstrap or missing secret problems as blockers, not silent skips.

## Do not do this

- Do not call a repo “configured” because wrapper files exist.
- Do not compare only dashboards or only workflow files.
- Do not create or tighten rulesets until the repo actually emits the required contexts.
- Do not let remediation or backlog automation write directly to the default branch.