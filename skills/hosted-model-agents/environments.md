---
title: environments
type: note
permalink: dqverify-repo-20261013/skills/hosted-model-agents/environments
---

# Environments (where the weights run)

Pick the environment for **cost, privacy, GPU type, and API shape**. Then attach the harness tool loop ([tool-loop.md](tool-loop.md)).

## Hugging Face

| Surface | Use for | How agents talk to it |
|---|---|---|
| **Hub MCP** (`huggingface`) | Models, datasets, Spaces, papers, Hub file ops | Official plugin/MCP. Already in `.agents/agents.json`, Claude target, `HUGGINGFACE_TOKEN`. |
| **Space — Gradio UI** | Humans, quick demos | Browser / Gradio client. Optional `mcp_server=True` on Gradio 6+ exposes *that app’s* tools as MCP (app tools, not Hub). |
| **Space — OpenAI `/v1`** | Any OpenAI-compat client, tool_calls | Mount FastAPI routes on Gradio `App.create_app`. ZeroGPU: keep generate under `@spaces.GPU`; protocol code GPU-free. Private Spaces need Bearer token. |
| **Inference Endpoints / TGI / vLLM** | Dedicated GPU, OpenAI `/v1` | Standard chat completions. Same tool-loop as a Space `/v1`. |
| **Jobs / dedicated hardware** | Long train/eval | Hub MCP + Jobs docs; not a chat agent unless you add an API. |

Do **not** treat Hub MCP as the chat runtime. Do **not** skip Hub MCP and only document one private Space.

Auth: reuse `HF_TOKEN` / `HUGGINGFACE_TOKEN` / `HUGGING_FACE_HUB_TOKEN`. Never rotate. Never print.

## Other GPU clouds

Skill `cloud-infra-toolchain` (cloud-hub multiplexer): **Modal**, **RunPod**, **Lightning**, Kaggle, Azure/GCP ops. Those platforms **rent GPUs**; this skill **turns a GPU into an agent runtime** (OpenAI `/v1` or native SDK) and attaches tools locally.

## Azure AI Foundry

Skill `microsoft-foundry` / `deploy-model`. Hosted catalog models with Azure auth. Tool loop still local unless Foundry’s own tool runtime is explicitly in scope.

## Local

llama-server, LM Studio, Ollama — OpenAI-compat on localhost. Same tool loop. No Hub MCP involved.

## Cursor Max / Claude Max (not a deploy)

Native Cursor models and Claude Max are **subscription runtimes**, not HF. Cursor quota from a TUI uses **auth2api `:8317`** via process-local wrappers (`ai-mode`, `grok-cursor`, …) — that is **G-32**. Do not conflate with HF.

## App hosts (not model runtimes)

`vercel-deploy`, `netlify-deploy`, `cloudflare-deploy`, `render-deploy` ship **apps**. They are not “put Qwen on Vercel.” **fly-deploy** is an audit *checkbox* for a Fly.io skill that was never written; do not invent it to green the harness audit unless the owner wants Fly.io.

## Checklist before you “just MCP it”

1. Is this Hub search? → existing `huggingface` MCP / plugin.
2. Is this one app’s Gradio tools? → that Space’s Gradio MCP, optional, scoped.
3. Is this chat completions? → HTTP `/v1`, process-local client.
4. Would adding it to `agents.json` duplicate Hub MCP or dump 50 tools into every turn? → don’t. `mcp-fleet-curation`.