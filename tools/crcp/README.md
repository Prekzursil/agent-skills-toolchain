---
title: README
type: note
permalink: dqverify-repo-20261013/tools/crcp/readme
---

# CRCP — Cross-Rail Control Plane (Phase 1+)

Local tooling for multi-rail auth status, ChatGPT live bridge, bus publish, write path, and health probes.

**Code home:** `agent-skills-toolchain/tools/crcp`  
**Orchestrator:** Claude Code · **Executor:** Grok / Codex · **ChatGPT path:** live REST + export fixtures

## Auth planes (read this first)

| Plane | Source | Role |
|-------|--------|------|
| **Codex OAuth** | `~/.codex/auth.json` access_token | Temporary consumer for backend-api / Codex CLI — **expires** |
| **ChatGPT web account** | Browser / Desktop session | Durable owner plane for chatgpt.com — **endgame** for human account access |

CRCP list/fetch/send via Codex tokens is a **rail**, not the long-term web-account design.
Large research fan-outs for the web endgame: `~/scratch/crcp-web-account-fanout/`.

## Multi-agent implement on Databricks

Do **not** thrash local MCP sandboxes for multi-file CRCP work. Use:

- Skill: `codex-databricks-fanout`
- Guide: `guides/codex-databricks-ops.md`
- Rules: `rules/common/cross-vendor-dispatch.md` §9, `fan-out-contract.md` §C

Proven runs (2026-07-20): P0/P1 implement, merge wiring, smoke (write SUCCESS, health GREEN).
Harness dirs: `~/scratch/crcp-e2e-p0-fanout/`.

## Safety

- Never prints access/refresh tokens or private keys
- ChatGPT bridge is a **token consumer** only — does not call OAuth refresh
- One writable `CODEX_HOME` owns refresh; bridge reloads on file mtime change
- Loopback health must bypass system proxy (Fiddler 502 on 127.0.0.1)
- PoW default deadline is 120s (`CRCP_POW_DEADLINE_SECONDS`)

## Commands

```powershell
cd ~/source/agent-skills-toolchain/tools/crcp
$env:PYTHONPATH = (Get-Location).Path

python -m crcp version
python -m crcp auth status          # multi-rail vault status
python -m crcp health               # table + wfmon snippet
python -m crcp health --json
python -m crcp chatgpt list --limit 10
python -m crcp chatgpt fetch --latest 1
python -m crcp chatgpt fetch --id <conversation-uuid>

# Phase 2
python -m crcp inbox scan           # process drop-folder exports once
python -m crcp inbox scan --watch   # poll inbox/chatgpt
python -m crcp publish              # send new envelopes to agent-mail
python -m crcp publish --force      # re-send
python -m crcp publish --file outbox\envelope_….json

# Phase 3 — always-on live pipe
python -m crcp chatgpt live --poll-interval 60    # HTTP status :8820
python -m crcp chatgpt live --once                # single cycle
python -m crcp auth watch                         # auth.json mtime log
python -m crcp bus register-grok                  # three-way bus proof
```

Shared live service (one process):
- `GET  http://127.0.0.1:8820/health` · `/livez` · `/readyz` · `/metrics` · `/status`
- `POST http://127.0.0.1:8820/poll-now` (requires `CRCP_HTTP_TOKEN` or `CRCP_HTTP_OPEN=1` locally)

```powershell
python -m crcp livez
python -m crcp readyz
python -m crcp chatgpt send --new "ping"   # prepare+PoW; SUCCESS only with SSE terminal
```

Or: `.\bin\crcp.ps1 health`

### Drop-folder

1. Export ChatGPT conversation JSON (full export, not stream-only).
2. Copy into `inbox/chatgpt/*.json`.
3. `python -m crcp inbox scan` → packs land in `outbox/` + `inbox/chatgpt/processed/`.
4. `python -m crcp publish` → posts envelopes to agent-mail as `crcp-bridge`.

### Cockpit

```bat
mon crcp
```

Registered in `~/.agents/skills/monitor-launcher/monitors.toml` as `[crcp]`.
Polls health every 30s (`CRCP_HEALTH_INTERVAL_SEC`) and refreshes `reports/wfmon_crcp_health.json`.

## Outputs

| Path | Purpose |
|------|---------|
| `reports/auth_status_live.json` | Auth vault snapshot |
| `reports/health_live.json` | Full health report |
| `reports/wfmon_crcp_health.json` | Compact cockpit/wfmon feed |
| `outbox/*.json` | Conversation packs + CRCP envelopes |
| `fixtures/chatgpt_desktop/v1/` | Offline stream/export fixtures (Phase 0) |

## Envelope schema

See `crcp/envelope.py` — `crcp.envelope.v1` with `from_rail`, `to_rail`, `intent`, `payload_ref`, `completion`.

## Rails

| Rail | Status source |
|------|----------------|
| Codex auth | `~/.codex/auth.json` JWT + file signals |
| Databricks | `databricks auth describe` DEFAULT / bolt-datascience |
| Agent-mail | `http://127.0.0.1:8812/api/health` |
| ChatGPT live | `GET /backend-api/me` with Codex access_token |
| Claude CLI | `claude --version` (path presence) |