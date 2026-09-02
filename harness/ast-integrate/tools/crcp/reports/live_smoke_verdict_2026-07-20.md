# CRCP live smoke verdict — 2026-07-20

## Proven working

| Check | Result | Evidence |
|-------|--------|----------|
| Codex auth | LOGGED_IN | `crcp health` rails |
| ChatGPT list | OK | 3+ conversations returned |
| Live poll `--once` | OK | listed=9, published envelopes to agent-mail (BoldCat → OrangeCreek/VioletTower), errors=[] |
| Spool lifecycle | OK | event_key in cycle summary; second cycle no new_or_updated |
| HTTP `:8820` livez/readyz/metrics | OK after merge restart | `{"live":true}`, `{"ready":true}`, spool_backlog_count=0 |
| Agent-mail bus | OK when process up | `/api/health` → `{"status":"ok"}`; publish succeeded |
| Unified health overall | **GREEN** | all rails LOGGED_IN when mail+bridge up |
| Write path send | **SUCCESS** | `status=SUCCESS`, `http_ok=true`, `ok=true`, prepare+proof present, model gpt-5-5, new conversation |

Send report: `reports/chatgpt_send_last.json`  
Summary JSON: `reports/live_smoke_verdict_2026-07-20.json`

## Fixes applied during smoke

1. **live_bridge** still used removed `bridge._auth_mtime` → use `CredentialSnapshot` / `is_stale_mtime`
2. **write_path** still used `bridge._access` → `credentials.apply_to_headers`
3. **agent_mail_status** used system proxy → `ProxyHandler({})` for loopback (Fiddler 502)
4. **PoW default deadline** 25s → **120s** (25s failed on this desktop; 180s env send succeeded ~155s)

## Ops notes (not code bugs)

- **Agent-mail flaps** if supervisor/task not always-on: restart  
  `…\mcp_agent_mail\.venv\Scripts\python.exe -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8812`  
  Prefer logon task `MCPAgentMailSupervisor` (was Ready but not running earlier).
- **Fiddler/system proxy** breaks `127.0.0.1` unless NO_PROXY / ProxyHandler empty.
- **Live bridge** must run merged code (`PYTHONPATH` = tools/crcp). Old process lacked `/livez`.
- **Singleton lock** blocks second long-running bridge; `--once` is fine for ad-hoc cycles.
- CLI `readyz` may still show lease `unknown` while HTTP `:8820/readyz` is ready (process vs state file semantics). **overall GREEN** is the multi-rail gate.

## Steady-state commands

```powershell
$env:PYTHONPATH = "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\crcp"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:CRCP_HTTP_OPEN = "1"   # local poll-now without token

# mail
& "$env:USERPROFILE\.local\opt\mcp_agent_mail\.venv\Scripts\python.exe" -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8812

# bridge
python -m crcp chatgpt live --poll-interval 60 --http-port 8820

# probes
python -m crcp health --json
curl.exe --noproxy "*" http://127.0.0.1:8820/livez
curl.exe --noproxy "*" http://127.0.0.1:8812/api/health

# write (uses 120s PoW default)
python -m crcp chatgpt send --new "ping"
```

## Verdict

**Working for the intended owner-ops path:** auth → list → poll/spool/publish → health GREEN → paid write with PoW + SSE terminal SUCCESS.  
Residual: keep agent-mail supervised always-on; optional polish CLI lease check vs HTTP ready.
