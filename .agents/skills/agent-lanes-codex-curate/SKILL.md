---
name: agent-lanes-codex-curate
description: Use when the user explicitly wants Codex orchestration to compare options and choose the best one. Triggers include requests to curate, synthesize, or select among alternatives through `codex_local_curate` or `codex_orchestrator_curate`.
---

# Agent Lanes Codex Curate

## Overview

Run the Codex-side curation lane to compare alternatives and select the best option.

## Required Behavior

- Prefer `codex_local_curate` or `codex_orchestrator_curate`.
- Use this lane for final selection among candidate plans, implementations, or recommendations.
- If browser-mediated ChatGPT web curation fails, keep the Codex fallback result and say so.
- If the user explicitly asks for direct ChatGPT web curation, do not use this skill.
