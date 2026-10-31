---
title: phase4_status_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/phase4-status-2026-07-20
---

# Phase 4 status — 2026-07-20

## Decisions
- **No Databricks** for CRCP ChatGPT relay (owner: same as verdict-app = local + GitHub).
- Fiddler system proxy ON breaks naive localhost probes — use `UseProxy=false` / `NO_PROXY`.

## Deliverables

### p4-1 Write-path RE
- Guest web + **Desktop auth** captures complete
- Auth 200: `POST /backend-api/f/conversation` with `openai-sentinel-chat-requirements-prepare-token` + proof + turnstile
- Reports under `reports/write_path_*`
- `write_path.py` updated; bare token still 403 without PoW/Turnstile

### p4-2 Grok agent-mail
- Config already correct: `[mcp_servers.agent-mail] url=http://127.0.0.1:8812/mcp type=http enabled=true`
- Agent-mail supervisor continuous + proxy-safe health probe
- Bus three-way proof: **SUCCESS** IvoryBarn (Grok) ↔ VioletTower (Claude) ↔ OrangeCreek (Codex)

### p4-3 CRCPChatGPTBridge
- Task registered: `CRCPChatGPTBridge` (logon + restart)
- Wrapper: `scripts/run_crcp_live_bridge.ps1`
- Installer: `scripts/install_crcp_chatgpt_bridge_task.ps1`
- Live `--once` proven: fetch + publish to bus

### p4-4 Relay (non-DBX)
- `databricks/README.md` documents local/GitHub path
- Relay script local dry-run OK (list conversations)
- DBFS accidental upload left as optional artifact only — **not** scheduled

### p4-5 SSH nonce
- No Claude SSH host in `~/.ssh/config` (only `ssh.lightning.ai` → publickey denied)
- Local nonce recorded: `SSH-CROSSVENDOR-E2E-20260720-A7F3` in `reports/ssh_nonce_echo_2026-07-20.md`

## Remaining (optional next)
1. Sentinel PoW/Turnstile solver or capture-replay for auth write 200 from CRCP
2. Confirm `:8820` health after long-run task stable
3. Add Claude SSH host if cross-vendor SSH rail still desired