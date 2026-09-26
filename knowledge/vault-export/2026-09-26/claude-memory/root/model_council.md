---
name: model-council
description: LangGraph multi-model council (Claude+Codex+Antigravity) over CLI/subscription
  auth — location, strategies, one-time auth
metadata:
  node_type: memory
  type: reference
  originSessionId: 36cba66d-b7f5-47e0-86a9-0861130bb158
permalink: main/claude-memory/root/model-council
---

LangGraph "model council" built 2026-05-24 at **`D:\model-council`** (venv 3.12). Multi-model deliberation: 3 seats answer/debate/vote and produce a collective answer, all **CLI/subscription-backed (no API keys)** — chosen over provider keys to reuse Claude Max / ChatGPT / Google One.

**Seats** (`council.toml` [seats.*]) — TESTED working config:
- `claude` = `langchain-claude-code-cli` ChatClaudeCode (opus, effort high). **Requires** `council/_patches.py` monkeypatch: claude-code-sdk 0.0.25 (latest) raises MessageParseError on the CLI's `rate_limit_event` → patch turns unknown msg types into SystemMessage. Auto-applied when building the seat.
- `codex` = custom `council/codex_cli_wrapper.py` ChatCodexCLI driving `codex exec -c sandbox_mode=read-only -c approval_policy=never -o <tmpfile>`. **Do NOT use `langchain-codex-oauth`** — it completes but returns EMPTY content for gpt-5.5 on a ChatGPT account (wrong endpoint / reasoning-parse; tried model/effort/verbosity/streaming, all empty).
- `gemini` = `council/cli_chat.py` ChatPrintCLI — WORKS, needed 3 fixes (all required): (1) `--allowed-mcp-server-names __none__` so gemini-cli doesn't hang connecting the 33 MCP servers in ~/.gemini/settings.json on startup; (2) `-y` auto-approves folder-trust prompt; (3) run the node bundle `...\@google\gemini-cli\bundle\gemini.js` via node (bypass gemini.cmd shim — cmd.exe breaks on multi-line prompts) + `close_stdin=true` (gemini-cli readStdin hang #6715). Works until 2026-06-18 deprecation.
- `agy` (Antigravity) = **DEAD END headless in v1.0.2**: `agy -p`/`--print` emits nothing to a non-TTY pipe, no `--output-format` flag. Defined in config but not in default_members; swap in when Google fixes headless output.
- Windows gotcha: `codex`/`gemini` are npm `.cmd` shims → wrappers resolve via shutil.which + route `.cmd` through `cmd /c`. `ask_all` has a per-seat timeout (240s) so flaky seats don't hang the council.

**FREE seats added (`openai_compat` type, ChatOpenAI + base_url + token from env, no cost):** `deepseek` = GitHub Models `deepseek/DeepSeek-V3-0324` via `$GH_TOKEN` (base_url https://models.github.ai/inference); `llama` = HF router `meta-llama/Llama-3.3-70B-Instruct` via `$HF_TOKEN` (base_url https://router.huggingface.co/v1). Token read from env via `api_key_env` config key — never stored in council.toml. **Default council = 5 seats** (claude, codex, gemini, deepseek, llama); verified live (all 5 contributed). No Ollama/LM Studio locally. Add more free endpoints (Groq/Cerebras/OpenRouter-:free/Ollama) the same `openai_compat` way.

**7 strategies** (registry `council/strategies/__init__.py`, select via `--strategy`): parallel (default), debate (`--rounds`), vote (judge), orchestrator (lead decomposes→delegates), round_robin, devils_advocate, moderator_panel. Add one = new module + registry entry.

**Run:** `.venv\Scripts\python.exe -m council "question" [--strategy X --members claude,codex,agy --rounds N --judge codex]`. Transcripts → `runs/<ts>-<strategy>.{json,md}`. Seats are fault-isolated (one CLI failing → council uses the rest).

**One-time auth before live use:** codex → `.venv\Scripts\langchain-codex-oauth auth login`; agy → run `agy` once (Google sign-in); claude already logged in (but **concurrent with another Claude Code session can 401** — [[claude-code-401-auth-notes]]).

**LangSmith tracing (set up 2026-05-24):** key `lsv2_pt_...` in `.env` (+ User & Machine env vars) `LANGSMITH_API_KEY`/`LANGSMITH_TRACING=true`/`LANGSMITH_PROJECT=model-council`. **CRUCIAL GOTCHA: the key is EU-region** → default US endpoint 403s it (both `/runs/multipart` tracing AND `/metadata/submit`). Fix = `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` (set in .env + User + Machine). Also blanked `LANGSMITH_CONTROL_PLANE_API_KEY=` in .env (it defaults to LANGSMITH_API_KEY → langgraph dev ran a platform-telemetry loop that 403'd). CLI traces too (added `load_dotenv` in run.py). Verified: runs land in EU project `model-council`. View at **https://eu.smith.langchain.com** (EU, not the US smith.langchain.com). `.gitignore` protects `.env`. Key is in this session transcript — rotate if logs shared.

**GUI:** LangGraph Studio — `D:\model-council\studio.cmd` (= `.venv\Scripts\langgraph dev`) → opens Studio at smith.langchain.com/studio?baseUrl=http://127.0.0.1:2024; all 7 strategies registered as graphs (`langgraph.json` → `council/studio_graph.py`, ABSOLUTE imports required since Studio loads it by path). Verified boots + registers.

**Verified 2026-05-24:** 7/7 strategy graphs (stubs) + LIVE 3-seat `parallel` run where ALL THREE (claude+codex+gemini) answered and synthesized cleanly. Council fully working. Robust guide: `D:\model-council\docs\ROBUST_GUIDE.md`.