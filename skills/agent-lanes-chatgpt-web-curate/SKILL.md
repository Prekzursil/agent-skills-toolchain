---
name: agent-lanes-chatgpt-web-curate
description: Use when the user explicitly invokes the agent-lanes ChatGPT web curation lane (chatgpt_web_curate, have ChatGPT web pick the best option) for final comparison in an agent-lanes workflow ; do NOT use for Codex-side orchestration or the newer chatgpt5-web-curate route ; returns ChatGPT web curation result.
---

# Agent Lanes ChatGPT Web Curate

## Overview

Run the direct ChatGPT web curation lane for browser-mediated comparison and final recommendation.

## Required Behavior

- Prefer `chatgpt5_web_curate` or `chatgpt_web_curate`.
- Use for direct ChatGPT-web-side comparison and recommendation.
- Surface readiness or session-state errors clearly.
- Do not silently substitute Codex orchestration unless the user changes the lane.
