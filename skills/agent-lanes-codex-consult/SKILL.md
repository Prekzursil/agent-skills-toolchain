---
name: agent-lanes-codex-consult
description: Use when the user explicitly wants a Codex-side consultation lane for structured analysis, tradeoff review, or decision support. Triggers include requests to use Codex orchestration, `codex_local_consult`, `codex_orchestrator_consult`, or a "Codex consult" pass instead of direct ChatGPT web automation.
---

# Agent Lanes Codex Consult

## Overview

Run the Codex-side consult lane for structured analysis first. This is the default explicit lane when the user wants Codex orchestration rather than direct browser-mediated ChatGPT interaction.

## Required Behavior

- Prefer the Codex-local consult tools such as `codex_local_consult` or `codex_orchestrator_consult`.
- Keep the task scoped to analysis, decision support, or architecture comparison.
- Surface whether ChatGPT web curation was used secondarily and whether fallback stayed on Codex synthesis.
- If the user explicitly wants direct ChatGPT web behavior, do not use this skill.
