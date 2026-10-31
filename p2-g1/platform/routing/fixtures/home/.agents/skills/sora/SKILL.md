---
name: "sora"
description: "Use when the user asks to generate, remix, poll, list, download, or delete Sora videos via OpenAI\u2019s video API using the bundled CLI (`scripts/sora.py`), including requests like \u201cgenerate AI video,\u201d \u201cSora,\u201d \u201cvideo remix,\u201d \u201cdownload video/thumbnail/spritesheet,\u201d and batch video generation; requires `OPENAI_API_KEY` and Sora API access."
---


# Sora Video Generation Skill

Creates or manages short video clips for the current project (product demos, marketing spots, cinematic shots, UI mocks). Defaults to `sora-2` and a structured prompt augmentation workflow, and prefers the bundled CLI for deterministic runs. Note: `$sora` is a skill tag in prompts, not a shell command.

## When to use
- Generate a new video clip from a prompt
- Remix an existing video by ID
- Poll status, list jobs, or download assets (video/thumbnail/spritesheet)
- Batch runs (many prompts or variants)

## Decision tree (create vs remix vs status/download vs batch)
- If the user has a **video id** and wants a change → **remix**
- If the user has a **video id** and wants status or assets → **status/poll/download**
- If the user needs many prompts/assets → **create-batch**
- If the user asks for two versions with a small change (same shot, different subject/detail) → **create** the base, then **remix** for the variation
- Otherwise → **create** (or **create-and-poll** if they need a ready asset in one step)

## Workflow
1. Decide intent: create vs remix vs status/download vs batch.
2. Collect inputs: prompt, model, size, seconds, and any input reference image.
3. If batch: write a temporary JSONL under tmp/ (one job per line), run once, then delete the JSONL.
4. Prefer CLI augmentation flags (`--use-case`, `--scene`, `--camera`, etc.) instead of pre-writing a structured prompt. If you already produced a structured prompt file, pass `--no-augment` to avoid double-wrapping.

### Authentication
### Defaults & rules
### API limitations
### Guardrails (must enforce)
### Prompt augmentation
### Examples
### Generation example (single shot)
### Remix example (invariants)
### Prompting best practices (short list)
### Guidance by asset type
