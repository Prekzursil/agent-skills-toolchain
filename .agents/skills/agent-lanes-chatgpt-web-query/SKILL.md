---
name: agent-lanes-chatgpt-web-query
description: Use when the user explicitly wants a direct ChatGPT web / Agentify lane rather than Codex orchestration. Triggers include requests to ask ChatGPT directly, use `chatgpt5_web_query`, use `chatgpt_web_query`, or send work through the browser-mediated ChatGPT lane.
---

# Agent Lanes ChatGPT Web Query

## Overview

Run the direct ChatGPT web lane for browser-mediated querying.

## Required Behavior

- Prefer direct ChatGPT web tools such as `chatgpt5_web_query` or `chatgpt_web_query`.
- Use when the user explicitly wants the ChatGPT web side rather than the Codex-local lane.
- Surface readiness or session-state problems clearly instead of hiding them.
- Do not route back to Codex orchestration unless the user asks for it.
