---
name: agent-lanes-chatgpt-web-discuss
description: Use when the user explicitly invokes the agent-lanes ChatGPT web discuss lane (chatgpt_web_discuss, debate or discuss with ChatGPT web) for ideation or sparring in an agent-lanes workflow ; do NOT use for the newer chatgpt5-web-discuss route ; returns ChatGPT web discussion result.
---

# Agent Lanes ChatGPT Web Discuss

## Overview

Run the direct ChatGPT web discuss lane for back-and-forth ideation through the browser-mediated session.

## Required Behavior

- Prefer `chatgpt5_web_discuss` or `chatgpt_web_discuss`.
- Use for ideation, framing, and sparring-partner style discussion through ChatGPT web.
- Surface readiness or browser-session issues clearly.
- Do not switch to Codex orchestration unless the user asks for a Codex lane.
