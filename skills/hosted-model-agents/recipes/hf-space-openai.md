---
title: hf-space-openai
type: note
permalink: dqverify-repo-20261013/skills/hosted-model-agents/recipes/hf-space-openai
---

# Recipe: Hugging Face Space with OpenAI `/v1` (tool proposer)

**Example only.** Checkpoint today: private Space `Prekzursil/qwen38-27b-heretic-chat` (Qwen3.8-27B Heretic-ARA, ZeroGPU). The same recipe applies to any chat model you mount the same way.

- Code: `C:\Users\Prekzursil\Cowork\tools\hf-space-qwen38-27b-heretic`
- Wire contract: `../../qwen-space-tool-api/reference.md` (kept under the deprecated skill name so old links resolve)
- Wrapper: `qwen-space` → that repo’s `qwen-space.ps1` (HTTP only, no tool execution)
- Hub control plane for this Space (create, files, status): **`huggingface` MCP / plugin**, not this `/v1`

## What this recipe is

Gradio app + GPU-free FastAPI `/v1/models`, `/v1/chat/completions`, `/healthz`. Model returns OpenAI `tool_calls`. Local harness executes.

## What this recipe is not

- Not the Hugging Face Hub MCP.
- Not “the Qwen agent skill.”
- Not an `agents.json` MCP server.

## Checkpoint-specific traps (this Space)

- `reasoning_effort: high` → alias to `xhigh` (stock Qwen3.8 template).
- Replay `tool_calls.arguments` as **dicts** for Jinja `|items`.
- ZeroGPU: only `generate` under `@spaces.GPU`.
- Auth: Bearer `HF_TOKEN`; Space is private.

Tests (GPU-free): `python -m unittest discover -s tests -t . -v` in that repo. Coverage: **NOT-CHECKED** (no `.coverage-thresholds.json`).