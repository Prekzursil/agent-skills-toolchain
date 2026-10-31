---
title: github-control-plane
type: note
permalink: dqverify-repo-20261013/skills/quality-gate-automation-architect/references/github-control-plane
---

# GitHub Control Plane

Use this reference when GitHub should own orchestration, status truth, or merge governance.

## What GitHub-native automation is good at

- GitHub Copilot coding agent works autonomously in a GitHub Actions-powered environment and creates pull requests with the results.
- The PR workflow remains explicit: Copilot requests review when it finishes and can iterate through PR comments.
- Draft PRs from Copilot require approval by a user with write permissions before Actions workflows run, and Copilot cannot approve or merge its own PRs.
- Copilot only opens one pull request per assigned task and is scoped to the repository where the task started.

## Design implications

- GitHub is strongest when the goal is "repair the PR until the required checks for the latest head SHA are green."
- Treat branch protection, rulesets, and required checks as the control contract.
- Prefer human-approved merge by default because GitHub's agent model is intentionally review-centric.
- Keep the worker stateless across attempts. Each run should evaluate the latest SHA and produce one bounded update.

## Workflow patterns

### `workflow_run` follow-up workflow

Use `workflow_run` when one workflow should react to the conclusion of another:

```yaml
on:
  workflow_run:
    workflows: ["Build"]
    types: [completed]
```

GitHub exposes the triggering workflow payload to the follow-up run, which makes this pattern useful for repair jobs that need artifacts, logs, or PR metadata from the failed workflow.

### Concurrency groups

Use per-branch or per-PR concurrency to prevent multiple repair runs from fighting each other:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Use a PR-specific fallback when `github.head_ref` is not always defined:

```yaml
concurrency:
  group: ${{ github.head_ref || github.run_id }}
  cancel-in-progress: true
```

## Safe defaults

- Resolve required checks from GitHub rules first, then map them to actual producers.
- Keep one repair workflow per lane when possible: PR rescue, coverage ratchet, debt burn-down.
- Prefer merge queue or queue-like protection for final integration.
- Keep audit output in GitHub-native surfaces: PR comments, job summaries, artifacts, or check run output.

## When not to use GitHub as the primary lane

- The repo cannot expose the necessary secrets or runners.
- The user wants rich local-only context, private desktop tools, or sidecar-only data in the main loop.
- The task is mostly consultation and explanation, not unattended mutation.

## Official signals to remember

- GitHub Copilot coding agent runs in a GitHub Actions-powered environment and creates pull requests for review.
- Mentioning `@copilot` on an existing PR can ask it to make changes.
- Copilot-created PRs do not auto-run workflows until a write-enabled user approves them.

Keep those constraints visible when comparing GitHub-native automation against Codex-first designs.