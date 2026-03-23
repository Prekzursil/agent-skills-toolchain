---
name: agent-lanes-chatgpt-web-curate
description: Use when the user explicitly wants final comparison or curation through the direct ChatGPT web lane. Triggers include requests to have ChatGPT web pick the best option, `chatgpt5_web_curate`, or `chatgpt_web_curate`.
---

# Agent Lanes ChatGPT Web Curate

## Overview

Run the direct ChatGPT web curation lane for browser-mediated comparison and final recommendation.

## Required Behavior

- Prefer `chatgpt5_web_curate` or `chatgpt_web_curate`.
- Use for direct ChatGPT-web-side comparison and recommendation.
- Surface readiness or session-state errors clearly.
- Do not silently substitute Codex orchestration unless the user changes the lane.
