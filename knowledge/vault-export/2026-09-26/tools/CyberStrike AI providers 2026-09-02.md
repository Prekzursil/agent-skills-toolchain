---
title: CyberStrike AI providers 2026-09-02
type: note
permalink: main/tools/cyber-strike-ai-providers-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- cyberstrike
- providers
- heretic
- huggingface
---

- [decision] CyberStrike 1.1.15 global config is `~/.config/cyberstrike/cyberstrike.json`. Keys stay `{env:...}` interpolation only; never argv, never literals in the file.
- [decision] Default model is `google/gemini-3.1-pro-preview` with small model `google/gemini-3.6-flash` because those completed live (200). Native Anthropic env key 401s; OpenRouter paid Claude 402s; OpenAI env key 401s (ChatGPT oauth still stored in auth.json).
- [decision] Do not persist auth2api `:8317` as a CyberStrike provider (G-32). Ollama is disabled: daemon listens, zero models.
- [fact] Stored CyberStrike credentials: Hugging Face api, OpenAI oauth, OpenRouter api. Env-detected: NVIDIA, Google/Gemini, HF_TOKEN, OpenRouter, Anthropic, Databricks, AWS_REGION, OpenAI, GitLab, GitHub, Vultr.
- [fact] Owner Space `Prekzursil/qwen38-27b-heretic-chat` is live (`/healthz` 200, model `qwen38-heretic`). Wired as `qwen38-heretic-space/qwen38-heretic`.
- [fact] Owner Space `Prekzursil/GLM-5.3` is 503 (space in error) — not wired.
- [fact] Live heretic/abliterated inference with tool_calls (HF router + Featherless, 2026-09-02): `heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai`, `huihui-ai/Huihui-Qwen3.8-27B-abliterated:featherless-ai`, `huihui-ai/Huihui-CyberStrike-OffSec-35B-abliterated:featherless-ai`. Bare heretic-ara without `:featherless-ai` 400s. DreamFast 8B heretic returned length/no tools.
- [fact] Stock GLM-5.3 Flash on Novita also tool-called (`zai-org/GLM-5.3-Flash:novita`). Not heretic; kept as a live capable fallback.
- [fact] OpenRouter Hermes-3/4 and Dolphin Venice advertise no tool-use endpoints (404 on tools). Do not use them for CyberStrike agent loops.
- [fact] `ABLIT_KEY` / abliteration.ai is unset. That host (`https://api.abliteration.ai/v1`, models `abliterated-model-large-v2` GLM-5.3, tools documented) is the next hosted-abliterated option if the owner adds a key later. Never rotate existing keys.
- relates_to [[CyberStrike]]
- relates_to [[hosted-model-agents]]
See also [[openrouter-routing]].

- [fact] Upgrade 04.09.2026: `@cyberstrike-io/cyberstrike` 1.1.15 → 1.1.16 via `npm install -g …@latest`; `cyberstrike --version` verified **1.1.16**. npm allow-scripts guard blocked the package postinstall (owner npm config, not bypassed) — if the shim misbehaves: `npm install -g --allow-scripts=@cyberstrike-io/cyberstrike`. Global config `~/.config/cyberstrike/cyberstrike.json` untouched by the upgrade.
