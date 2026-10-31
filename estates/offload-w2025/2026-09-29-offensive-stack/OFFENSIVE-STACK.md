---
title: OFFENSIVE-STACK
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/offensive-stack
---

# OFFENSIVE-STACK — Estate AI Security Tooling (installed 2026-09-29)

State-of-the-art layered stack per the 2026 landscape analysis: one gateway, one
process per concern, everything MCP-centered, dual-mode where reality allows.

```
                    ┌────────────────────────────────────────────┐
                    │   CyberStrike TUI / Web (127.0.0.1:4096)   │  CLI agent, BYOK
                    └──────────────────┬─────────────────────────┘
                                       │ single MCP registration
                    ┌──────────────────▼─────────────────────────┐
                    │  cyberstrike-gateway  127.0.0.1:31100/mcp  │  ONE process
                    │  harness_capabilities / _invoke / _status  │  no watchdog
                    └─┬────────┬────────┬───────────┬────────────┘
        ┌─────────────┘        │        │           └────────────┐
  ┌─────▼─────┐   ┌────────────▼──┐  ┌──▼───────────┐   ┌────────▼─────────┐
  │ search    │   │ decepticon    │  │ hexstrike    │   │ binaries (reaped)│
  │ exa/tavily│   │ recon :3001   │  │ :8888        │   │ nuclei :PATH     │
  │ firecrawl │   │ initacc :3002 │  │ 150+ tools   │   │ nmap (1-click)   │
  │ (dual-mode│   │ term :3003    │  │ adaptive AI  │   │ frida/mitmproxy  │
  │  local/api│   │ dual-mode     │  └──────────────┘   └──────────────────┘
  │  +DDG kl.)│   └───────────────┘
  └───────────┘
  ┌─────────────────────────────────────────────────────────────────────┐
  │ PentAGI full profile (docker)  ·  Decepticon upstream 7svc (docker) │  docker-pending
  └─────────────────────────────────────────────────────────────────────┘
```

## Home-reconcile audit (2026-09-29, round 2)
- `~/source/agent-skills-toolchain` here is a payload COPY without `.git` - the
  branch/PR state lives in its `RECONCILE-STATE_2026-09-01.md` (110 refs, 6 open
  PRs with per-PR verdicts: #282/#281 carried, #288 no-merge, #290 split, #283
  rebase, #286 owner-call). Verdicts ADOPTED as standing decisions for this box.
- Home `tools/mcp/canonical-mcp-servers.json` is the MCP SSOT (agents.json
  mirrors it, incl. idle-RAM supervision + quarantine + duplicate policy).
- Home `~/.local/opt` installs: cheatengine REBUILT on D: (payload venv pointed
  at home's Python312 path), deepsource present but needs DEEPSOURCE_API_KEY,
  ida-pro payload lacks dist (repointed to npx), frida/ghidra/mitmproxy kept as
  own-kind rows. Broken ones mirrored here rather than wired bad.
- Home `scripts/zai_key_failover.py` (dual Z.AI key rotation) adopted AND
  improved: gateway front `fronts/zai_keys.py` rotates at CALL TIME (lazy probe
  cache, rotate-on-exhaust, mid-call retry) - no hooks, no scheduled probes,
  same state file for interop. Keys seeded to User env (sha8 2cbe00c7 active /
  2b98b9a3 standby). Verified with a live GLM completion through the gateway.

## Anti-orphan guarantees (hard, not best-effort)
mcp-stdio backends run in a managed worker pool: ONE child per backend
(single-flight lock - duplicates structurally impossible), lazy spawn, idle-TTL
reap ON TOUCH (no timer threads; zero work while idle), every child in a
Windows Job Object with KILL_ON_JOB_CLOSE (hard-killed gateway takes children
down), timed-out workers reaped immediately, atexit shutdown. Verified: two
sequential hacktricks calls reuse one worker (2nd call 0.0s).

## ZCode / agents integration
- `cyberstrike-gateway` registered in `~/.agents/agents.json` (claude/codex/
  gemini/cursor targets, http transport) - every agent on the box can
  harness_invoke the 43-backend estate.
- CyberStrike provider `zai-coding-plan` (api.z.ai/api/anthropic, glm-4.6 +
  glm-4.5-air) using the rotation-managed active key.

## Live now (no Docker needed)

### CyberStrike (CLI agent layer)
- CLI: `cyberstrike` v1.1.16 (npm global, SRI-pinned). TUI: `cyberstrike`.
- Web: `cyberstrike web --hostname 127.0.0.1 --port 4096` (password in
  `~/.config/cyberstrike/SSOT-secrets.md`, also set as user env var). VERIFIED HTTP 200.
- Config: `~/.config/cyberstrike/` (AGENTS.md standing scopes, config.md, SSOT-secrets.md).
- Providers: OpenAI (estate key, sha8 933002a6) + Ollama local (`ollama-local/qwen3:4b`).
- Kit: `D:\opt\cyberstrike-mcp` — README there. Gateway = ONE process, logon
  autostart via scheduled task `CyberStrikeGateway`. `verify_stack.py` = end-to-end probe.

### Gateway backends — AVAILABLE (11, verified live)
exa (cloud API 200) · tavily (keyless DDG fallback) · firecrawl (cloud API 200) ·
nuclei v3.11.1 (D:\opt\bin) · hexstrike :8888 (150+ tools) · decepticon-recon :3001 ·
decepticon-initial-access :3002 · decepticon-terminal :3003 · frida · mitmproxy · caldera(rpc)
- 27 more rows stay discoverable & unavailable with install notes (honest manifest).

### Search provider dual-mode (estate mandate)
| provider | local/self-host | cloud API | keyless |
|---|---|---|---|
| firecrawl | `FIRECRAWL_API_URL` → your instance | `FIRECRAWL_API_KEY` (fc-…, User scope, FIXED) | — |
| tavily | `TAVILY_API_URL` (proxy) | key NOT on box (old env vars were broken `${…}` templates - cleared) | DDG fallback ✓ |
| exa | none exists (no self-hosted upstream) | `EXA_API_KEY`/`_2` (both valid) | DDG fallback for search |

### Decepticon — two editions
- **Local variant** `D:\opt\decepticon` (LangGraph swarm + Streamlit, runs WITHOUT Docker):
  dual-mode patched (`src/tools/mcp/_exec.py`): kali container when Docker is up,
  local Git Bash otherwise. Start: `powershell D:\opt\decepticon\start-decepticon.ps1`
  (fronts :3001-3003 + UI 127.0.0.1:8501). CLI: `.venv\Scripts\python.exe frontend\cli\cli.py`.
- **Upstream (PurpleAILAB)** `D:\opt\decepticon-upstream`: real 7-service stack
  (PostgreSQL, LiteLLM, Neo4j KG, Kali sandbox, LangGraph runtime, web, terminal).
  `.env` READY: profile=max, `DECEPTICON_TELEMETRY=off`, `DO_NOT_TRACK=1`,
  OpenAI estate key, ChatGPT-OAuth auth on, Ollama wired, secrets randomized.
  Bring-up: `docker compose up -d` (docker-pending). v1.1.44 ≥ 1.1.17 → CVE-2026-61732 fixed.

### Other agents installed
- **offsec-ai** (`C:\Python314\Scripts\offsec-ai.exe`) — OWASP LLM Top10 / MCP-server auditor.
- **strix** — installed via strix.ai script; sandbox is Docker-based (docker-pending).
- **HexStrike AI** `D:\opt\hexstrike-ai` (pinned ref 8333779): server
  `cd repo && ..\.venv\Scripts\python.exe hexstrike_server.py --port 8888`;
  MCP front `hexstrike_mcp_launcher.py`. First server start installs tool venvs lazily.

### Local models
- Ollama 0.34.4 at `D:\opt\ollama` — serve: `set OLLAMA_MODELS=D:\opt\ollama\models && D:\opt\ollama\ollama.exe serve`
  (currently RUNNING on 127.0.0.1:11434). Models: qwen3:4b (262k ctx), nomic-embed-text.

## Docker-pending — DECIDED 2026-09-29: remote Linux engine (nested-virt RETIRED)
GCP docs (2026-09-28): Hyper-V inside a GCP VM is NOT supported (KVM only) —
the nested-virt path on this Windows L1 is the boot-loop corruption class.
The earlier-enabled VirtualMachinePlatform/WSL features were ROLLED BACK
(verified Disabled, hypervisorlaunchtype Off) — reboot is safe.
SAFE PATH: `D:\opt\scripts\provision-docker-remote-host.ps1` (Debian VM +
docker in project 750220148127, drive via `DOCKER_HOST=ssh://…`, no exposed
API). Old nested-virt script retired in place with DO-NOT-RUN notice.
Everything docker-shaped is staged:
- **PentAGI** `D:\opt\pentagi`: .env FULL profile (OpenAI + Tavily/Firecrawl/Exa keys,
  Ollama, Graphiti KG on, loopback-only binding, hardened pg/scraper creds) +
  compose base/langfuse/graphiti/observability + `bring-up.ps1`.
- Post-reboot: launch Docker Desktop → `powershell D:\opt\pentagi\bring-up.ps1`.
- Enable nested virt (kills this kind of session - run from Cloud Shell):
  `D:\opt\scripts\enable-nested-virt-and-docker.ps1` (gcloud stop → update
  --enable-nested-virtualization → start; project 750220148127, zone europe-central2-a).
- Alternative without any reboot: remote engine — `$env:DOCKER_HOST="tcp://<tailnet-ip>:2375"`
  then the same bring-up script.

## Pending one-click items
1. **nmap**: silent installs hang on the embedded Npcap EULA. Double-click
   `D:\tmp\installs\nmap-setup.exe` once (Next→agree→Finish). Gateway lights it up
   automatically (manifest row `nmap`, kind=binary).
2. If you create a Tavily key: `setx TAVILY_API_KEY tvly-…` → tavily front flips
   from DDG-fallback to cloud automatically.

## Credentials
All sha8+plaintext in `C:\Users\prekzursil\.config\cyberstrike\SSOT-secrets.md`.
PentAGI/upstream-Decepticon generated secrets: inside their `.env` files (chmod-free
private estate; files are local-only). NEVER-ROTATE estate rule applies.