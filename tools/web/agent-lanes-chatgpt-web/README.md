# Agent Lanes ChatGPT Web

`tools/web/agent-lanes-chatgpt-web/` is the bounded web-tool home for the browser-mediated ChatGPT lane.

## Purpose

Provide an explicit web-session lane for ChatGPT browser automation without pretending it is the same class of system as MCP-native Codex orchestration.

## Explicit aliases

Preferred explicit aliases on this side include:
- `chatgpt5_web_query`
- `chatgpt5_web_discuss`
- `chatgpt5_web_curate`
- `chatgpt_web_query`
- `chatgpt_web_discuss`
- `chatgpt_web_curate`

## Boundary

This lane owns:
- browser-mediated ChatGPT interaction
- tab and session targeting
- readiness checks
- session inspection and configuration
- direct query, discuss, and curate operations

It does not own Codex orchestration or repo-local execution planning.

## Safety notes

This lane is expected to be more fragile than MCP-native tooling because it depends on:
- browser state
- login state
- CAPTCHA or handoff requirements
- session drift
- DOM or product changes

Consumers should surface readiness and session-state failures clearly instead of masking them.

## Promotion rule

Keep this folder as the live bounded home for the web-lane contract, docs, and packaging plan. Runtime code may live elsewhere until the project is promoted into a fully in-repo runnable package.
