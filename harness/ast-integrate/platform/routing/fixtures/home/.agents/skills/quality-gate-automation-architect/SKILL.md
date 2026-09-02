---
name: quality-gate-automation-architect
description: Use when designing, comparing, or reviewing autonomous repo-quality automation for pull-request repair, coverage ratchets, analyzer debt burn-down, or merge-governance decisions. Triggers include requests to keep PRs green, auto-fix failing checks, plan Sonar or Codacy workflows, compare GitHub-native versus Codex versus local automation, or decide between zero-touch and human-approved merges.
---

# Quality Gate Automation Architect

## Overview

Design safe, bounded automation systems for repo quality work. Prefer short, auditable loops with explicit stop rules over long-lived "super-agent" flows that mix repair, debt cleanup, and merge policy into one opaque process.

## Reference Map

- Read [references/github-control-plane.md](references/github-control-plane.md) when GitHub is or should be the control plane.
- Read [references/openai-codex-workers.md](references/openai-codex-workers.md) when Codex is a candidate worker or the user mentions Codex app, Codex Cloud, `codex exec`, or `openai/codex-action`.
- Read [references/analyzers-and-gates.md](references/analyzers-and-gates.md) when coverage, SonarQube Cloud, Codacy, Codecov, or branch-protection quality gates are involved.
- Read [references/local-consult-lane.md](references/local-consult-lane.md) when PromptBridge, local schedulers, VS Code sidecars, or Codex app automations are part of the design.
- Read [references/evidence-refresh.md](references/evidence-refresh.md) when the user wants the skill or references to absorb recurring lessons from prior sessions or repos.

## Workflow Decision

```dot
digraph automation_decision {
    rankdir=TB;
    ask [label="Need unattended repo work while away?", shape=diamond];
    github [label="Prefer GitHub as control plane", shape=box];
    local [label="Local lane can stay secondary", shape=box];
    codex [label="Need custom prompts and worker behavior?", shape=diamond];

### Required Discovery
### Required Comparison
### 1. GitHub-native agent
### 2. OpenAI-first Codex
### 3. Local-first hybrid
### Required Lane Separation
### Required Guardrails
### Output Contract
### Prompt Patterns
### PR repair
