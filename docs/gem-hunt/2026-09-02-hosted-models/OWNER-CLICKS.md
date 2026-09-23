# Hosted-models build wave - OWNER CLICKS (box-only steps a cloud worker must never do)

Every item below needs the owner's hands on the Windows box. Nothing here was executed by the build wave.
Order matters where numbered. Paths follow SSOT-WIRE: edit in `~/source/ast-integrate`, execute from
`~/source/agent-skills-toolchain` after the PR merges and that checkout is pulled. Secrets are named,
never pasted: no command below takes a token value on its command line.

Legend: `[ ]` open, `[x]` done (write the date). Receipts go under
`docs/gem-hunt/2026-09-02-hosted-models/receipts/` (no tokens, no response bodies).

## 0. Before anything else (git safety, D1)

- [ ] **D1-1 Push the box copy of `tools/mcp/glm53-space/` to the archive branch.** The code exists only
  in the executed checkout (CONSOLIDATED-GEM-DECISIONS V1); the PR deleted the registry row, not the
  code, and the branch `archive/glm53-space-2026-09` already carries the last registry state plus an
  `ARCHIVE-README.md` with these exact commands:

  ```powershell
  git -C C:\Users\Prekzursil\source\agent-skills-toolchain fetch origin
  git -C C:\Users\Prekzursil\source\agent-skills-toolchain worktree add D:\wt-archive-glm53 archive/glm53-space-2026-09
  robocopy C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\glm53-space D:\wt-archive-glm53\tools\mcp\glm53-space /E /XD .venv __pycache__
  git -C D:\wt-archive-glm53 add tools/mcp/glm53-space
  git -C D:\wt-archive-glm53 commit -m "archive(glm53-space): box copy of the retired lane (parity oracle for glm53_chat)"
  git -C D:\wt-archive-glm53 push origin archive/glm53-space-2026-09
  git -C C:\Users\Prekzursil\source\agent-skills-toolchain worktree remove D:\wt-archive-glm53
  ```

  Receipt: `git ls-tree origin/archive/glm53-space-2026-09 -- tools/mcp/glm53-space` lists `mcp_server.py`,
  `glm53_core.py`, `openai_proxy.py`, `uv.lock`.
- [ ] **D1-2 Delete the box directory only after D1-1 is pushed**, then run the three merges so the
  stale `glm53-space` block leaves `.claude.json`, `config.toml` and `.cursor/mcp.json`
  (`CURSOR_RETIRED_SERVERS` now drops it; `RETIRED_MCP_SERVERS` in the Codex merge does the same):

  ```powershell
  Remove-Item -Recurse -Force C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\glm53-space
  pwsh -File C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1
  claude mcp list   # inference-hub present, glm53-space absent
  ```

## 1. Tokens and keys (D7, D8) - ADD, never rotate (L6)

- [ ] **D7-1 Mint `HUGGINGFACE_TOKEN_INFERENCE`**: huggingface.co -> Settings -> Access Tokens -> New
  fine-grained token -> tick ONLY "Make calls to Inference Providers" -> name `ast-inference-hub`. Set it as
  a USER environment variable named exactly `HUGGINGFACE_TOKEN_INFERENCE` (System Properties -> Environment
  Variables, or `[Environment]::SetEnvironmentVariable('HUGGINGFACE_TOKEN_INFERENCE', '<paste>', 'User')`
  typed interactively, never in a script file). `HUGGINGFACE_TOKEN` (Hub MCP) is untouched. Restart the
  terminal / Cursor so the shim inherits it. Receipt: `Get-ChildItem Env:HUGGINGFACE_TOKEN_INFERENCE | Select Name`
  (name only) in the receipt file.
- [ ] **D8-1 OpenRouter keys (2-3, labelled, daily `limit_reset`)** at openrouter.ai/settings/keys:
  `or-codex-sidecar` -> env `OPENROUTER_API_KEY_CODEX_SIDECAR`; `or-cli-grunt` -> env
  `OPENROUTER_API_KEY_CLI_GRUNT`; optional `or-ide-opencode` -> env `OPENROUTER_API_KEY_IDE_OPENCODE`.
  Each key: set `limit` (USD) + `limit_reset: daily`. The legacy `OPENROUTER_API_KEY` stays as is.
- [ ] **D8-2 One Guardrail** (openrouter.ai/settings/guardrails) assigned to all three keys: provider
  allowlist `fireworks, together, deepinfra, novita`; model allowlist `z-ai/glm-5.2:free, z-ai/glm-5.3`;
  `data_collection: deny`; Secrets preset ON; `limit_usd` = your daily cap (`0` is the instant
  no-rotation kill switch). Receipt: `GET https://openrouter.ai/api/v1/key` per key -> `limit`,
  `limit_remaining` (numbers only) in the receipt.

## 2. M0 probe receipt (D9, T0-12) - read-only, from the box, never while a `cursor-agent` runs (G-36)

- [ ] **D9-1** For each of auth2api `http://127.0.0.1:8317/v1`, Ollama `http://127.0.0.1:11434/v1`,
  LM Studio `http://127.0.0.1:1234/v1`, HF router `https://router.huggingface.co/v1`: `GET /models`;
  `POST /chat/completions` `{"model": <first id>, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}`;
  `POST /responses` `{"model": ..., "input": "ping", "max_output_tokens": 1}`;
  `POST /messages` `{"model": ..., "max_tokens": 1, "messages": [...]}`. Record ONLY
  `{endpoint, path, http_status, has_expected_shape, latency_ms, server_version_if_any}` to
  `receipts/m0-probe-<date>.json`. A 404/400 is a valid answer. The probe tool does exactly this and
  writes the lattice: `python C:\Users\Prekzursil\source\agent-skills-toolchain\.agents\scripts\models_probe.py --endpoint cursor-auth2api --write`
  (dry-run without `--write` first; it refuses to print tokens or bodies).
- [ ] **D9-2 Consequence table.** `/v1/responses` on `:8317` is 200 -> the Codex renderer may render the
  `cursor-auth2api` block; 404 -> it stays excluded (routing report `wire:responses=absent`,
  alternative `inference-hub`). `/v1/messages` 200 -> `claude-cursor` wrapper `ok`; 404 -> `broken`.
- [ ] **D9-3 Host budget** (lens 04 step 0): `Get-Counter '\Memory\Available MBytes'`,
  `(Get-CimInstance Win32_Processor).NumberOfCores`, `(Get-CimInstance Win32_PhysicalMemory).Speed`,
  `(Get-CimInstance Win32_VideoController).Name`, `Get-NetTCPConnection -State Listen | ? LocalPort -in 8765,8812,8317,8770,8901,11434,1234,8080`
  -> same receipt folder. Also `nvidia-smi --query-gpu=memory.total,memory.free --format=csv`.

## 3. Local inference posture (D10, T0-8, T0-13)

- [ ] **D10-1 Ollama user env**: `OLLAMA_KEEP_ALIVE=2m`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`,
  `OLLAMA_CONTEXT_LENGTH=8192`, `OLLAMA_KV_CACHE_TYPE=q8_0` (user scope), then quit and restart the Ollama
  tray app. Check `ollama --version` >= 0.17.1 and that `Get-NetTCPConnection -LocalPort 11434` shows
  `127.0.0.1`, not `0.0.0.0`.
- [ ] **D10-2 Pull the Tier S / M picks** (eval-gated rows in `.agents/models.json`):
  `ollama pull qwen3:4b-instruct-2507-q4_K_M`; `ollama pull qwen3:8b`. `qwen2.5:7b` is already on disk.
- [ ] **D10-3 LM Studio as the `llmster` daemon**: `lms daemon up`; `lms server start --port 1234`;
  in the GUI disable "run the server on login"; Developer settings: JIT model loading ON, Auto-Evict ON,
  idle TTL 600 s (default is 60 min). Never `lms load` without `--ttl`. Receipt: `lms ps --json`.

## 4. Enable and smoke the hub (after the PR merges and the checkout is pulled)

- [ ] **HUB-1** `pwsh -File C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1` (renders the
  `inference-hub` stdio shim into Claude, Codex and the Cursor safe-default set).
- [ ] **HUB-2** First call from Claude Code: `inference-hub.models_list` then
  `inference-hub.chat model="glm-5.3" messages=[{"role":"user","content":"Reply with exactly: E2E_OK"}]`.
  Expect `E2E_OK`, a ledger line under `%USERPROFILE%\.agents\state\inference-ledger\<date>.jsonl`
  (no prompt text in it), and `http://127.0.0.1:8901/healthz` answering. Ten minutes idle -> the
  process is gone (`Get-Process python | ? CommandLine -match inference-hub` empty).
- [ ] **HUB-3** `/v1` face smoke: `curl http://127.0.0.1:8901/v1/models`.
- [ ] **HUB-4 (optional, always-on instead of lazy)** only if you want zero cold-start: the
  `tools/mcp/mcp-http-host/run_host.ps1` `-InstallTask` pattern applies; the default is lazy start.

## 5. Renderers (D4) - `--write` per runtime, in this order, dry-run + routing report first, never while a `cursor-agent` runs

Each renderer: `python <script> --live <path>` prints the dry run + routing report; add `--write` to apply
(a `.bak-<timestamp>` copy is taken); the post-write smoke must exit 0 or the renderer restores the copy.

- [ ] **R-1 Goose** `merge_generated_goose_models.py` -> `%APPDATA%\Block\goose\config\custom_providers\`; smoke `goose info`.
- [ ] **R-2 Grok** `merge_generated_grok_models.py` -> `~/.grok/settings.toml` (or the path `grok inspect` reports); the `[endpoints]` block for auth2api renders only if D9-1 proved `/v1/models` with >= 36 ids; smoke `grok inspect`.
- [ ] **R-3 OpenCode** `merge_generated_opencode_models.py` -> `~/.config/opencode/opencode.json`; smoke `opencode models`.
- [ ] **R-4 Aider (+ wrappers)** `merge_generated_aider_models.py` -> `~/.aider.model.metadata.json`, `~/.aider.model.settings.yml`, `~/.aider.conf.yml`; `merge_generated_wrappers_models.py` -> `~/.local/bin/<cli>-on-<upstream>` shims + `ai-mode`; smoke `aider --list-models openai/` and one `E2E_OK` one-liner per shim.
- [ ] **R-5 Fabric** `merge_generated_fabric_models.py` -> fenced region in `~/.config/fabric/.env`; smoke `fabric -L`.
- [ ] **R-6 Codex LAST** `merge_generated_codex_models.py` -> FIRST against a copy: `$env:CODEX_HOME='D:\codex-home-copy'` (copy of `~/.codex`), `--write`, `codex --version`, `codex login status`; only then the real `~/.codex/config.toml`. It never renders `wire_api = "chat"` and never touches top-level `model` / `model_provider`. Rollback = the `.bak` copy.

## 6. Meta loop (D12)

- [ ] **M-1** `pwsh -File C:\Users\Prekzursil\source\agent-skills-toolchain\scripts\register-catalog-task.ps1 -DryRun` then without `-DryRun` (task `AgentsCatalogSync-Daily`, 03:30, `IgnoreNew`, mutex).
- [ ] **M-2** First live sync: `python C:\Users\Prekzursil\source\agent-skills-toolchain\command-center\ssot\catalog_sync.py --root C:\Users\Prekzursil\.agents\state\catalog`; read `last-diff.json`.
- [ ] **M-3** Probe ladder: `python C:\Users\Prekzursil\source\agent-skills-toolchain\hooks\mcp-liveness\liveness.py --mode all` (L4 one-token probes need `--allow-inference`).
- [ ] **M-4** Weekly `uvx mcp-scan@latest scan --local-only --json` over the client configs; file the report.

## 7. Skill validation (pwsh only)

- [ ] `pwsh -File .\scripts\validate-all-skills.ps1` in `~/source/ast-integrate` (validates the updated
  `hosted-model-agents`, `multi-ai-mingle`, `openrouter-routing`, `qwen-space-tool-api` skills), then
  `sync_shared_state.ps1`.

## 8. Things the wave deliberately did NOT do (and you should not either, without a new decision)

- Rotate or revoke any token (L6). Register OpenRouter in Cursor or as `ANTHROPIC_BASE_URL` (L1).
- Install LiteLLM, LangGraph or any second orchestration runtime (L2). Open any new port but 8901 (L4).
- Run any `--write` from the cloud, or any live probe of `:8317` / `:11434` / `:1234` from CI.
