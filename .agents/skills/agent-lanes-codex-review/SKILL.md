---
name: agent-lanes-codex-review
description: Use when the user explicitly wants a Codex-side review or critic lane. Triggers include requests to review, critique, audit, or pressure-test a plan or patch using Codex orchestration, `codex_local_review`, or `codex_orchestrator_review`.
---

# Agent Lanes Codex Review

## Overview

Run the Codex-side review lane to critique correctness, risks, weak assumptions, regressions, or missing verification.

## Required Behavior

- Prefer `codex_local_review` or `codex_orchestrator_review`.
- Focus on concrete issues, missing tests, and reviewer-grade risk statements.
- State whether secondary ChatGPT web curation ran and whether Codex fallback was used.
- If the user explicitly asks for direct ChatGPT web review, do not use this skill.
