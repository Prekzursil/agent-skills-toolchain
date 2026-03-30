---
name: multi-agent-quickstart
description: Use when learning how to choose between the Codex multi-agent orchestration tools in the Windows-first setup.
---

# Multi-Agent Quickstart

## Mental Model
- `codex_consult` = one expert answer
- `codex_brainstorm` = two idea-generating peers plus synthesis
- `codex_review` = one critic pass
- `codex_discuss` = two peers debate before synthesis
- `codex_coordinate` = role split plus consolidation
- `codex_curate` = final selector, optionally with PromptBridge talk-only curation

## Beginner Flow
1. Start with `codex_consult` when you need one strong answer.
2. Use `codex_brainstorm` when you want alternatives.
3. Use `codex_review` before a risky implementation.
4. Use `codex_curate` when you already have options and want the best one selected.

## PromptBridge Boundary
- PromptBridge is talk-only.
- It can discuss or curate, but it is not the execution authority.
- If the sidecar is unavailable, continue in Lane A and emit `fallback_to_lane_a = true`.
