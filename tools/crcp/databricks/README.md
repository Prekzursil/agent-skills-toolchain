---
title: README
type: note
permalink: dqverify-repo-20261013/tools/crcp/databricks/readme
---

# CRCP ChatGPT relay — **local / GitHub**, not Databricks

Databricks job deploy for this relay is **retired**. Same pattern as
`Prekzursil/verdict-app`: code lives in GitHub; runtime is **local**
(Scheduled Task / CLI), CI is lean quality gates — not a DBX cluster.

## Runtime (canonical)

| Piece | How |
|-------|-----|
| Live poller | Windows task **`CRCPChatGPTBridge`** → `scripts/run_crcp_live_bridge.ps1` → `python -m crcp chatgpt live` on `127.0.0.1:8820` |
| One-shot list/fetch | `python -m crcp chatgpt list` / `chatgpt fetch` / `chatgpt live --once` |
| Relay dry-run | `python databricks/crcp_chatgpt_relay.py` (name historical; uses `~/.codex/auth.json` locally) |
| Agent bus | `http://127.0.0.1:8812` (`MCPAgentMailSupervisor`) |

Install bridge task:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/crcp/scripts/install_crcp_chatgpt_bridge_task.ps1
```

## GitHub (verdict-app style)

- Source of truth: `agent-skills-toolchain` (this tree)
- Quality: existing repo workflows (`quality.yml` family) — no separate cloud job required
- Optional: `tools/crcp` unit checks under pytest when present

## Explicit non-goals

- No Databricks job schedule for ChatGPT fan-out by default
- No secrets pushed to DBX secret scopes for CRCP relay
- Token refresh stays local Codex/`auth.json` consumer (read + optional local refresh)

`crcp_chatgpt_relay.py` remains as a **portable script** (list/fetch) for ad-hoc use on any Python host that can read auth — including a future notebook only if explicitly requested.