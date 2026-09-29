---
name: burp-mcp
description: Burp Suite MCP (PortSwigger official BApp) — always-on headless service at http://127.0.0.1:9876 with self-healing via estate watchdog. Use for authorized web-pentest traffic work: send/relay HTTP requests, Repeater/Intruder, proxy + WebSocket history search, Collaborator payloads, scanner issues, intercept control, Burp config editing, encoding utilities.
---

# Burp Suite MCP — Operations

## What exists (verified 2026-09-19)

- **Burp Suite Pro 2026.3.2 headless** + official **PortSwigger MCP Server BApp v1.3.0** (extension id `9952290f04ed4f628e624d0aa9dccebc`).
- **Endpoint: `http://127.0.0.1:9876` — SSE transport at the ROOT path** (`GET /` streams `endpoint` events; `/sse` and `/mcp` do NOT exist — 404).
- **27 tools**: `send_http1_request`, `send_http2_request`, `create_repeater_tab(_http2)`, `send_to_intruder`, `get_scanner_issues`, `generate_collaborator_payload`, `get_collaborator_interactions`, `get_proxy_http_history(_regex)`, `get_proxy_websocket_history(_regex)`, `get_organizer_items(_regex)`, `set_task_execution_engine_state`, `set_proxy_intercept_state`, `output_/set_project_options`, `output_/set_user_options`, url/base64 encode/decode, `generate_random_string`, active-editor get/set. Collaborator tools are Pro-only.
- Boot time ≈ 40–60 s after kill; endpoint handshake proves health.

## Architecture (who starts what)

| Layer | Mechanism |
|---|---|
| Service launcher | `D:\opt\burp\burp-headless.ps1` — dialog-free: `--project-file=C:\Users\Prekzursil\Documents\2026-06-10.burp` (carries the MCP extension), `--disable-auto-update`, hidden window. Logs to `D:\opt\burp\logs\launcher.log` (rotated). First line writes a `[.] launcher invoked` heartbeat. |
| Always-on | Scheduled Task **`BurpMcpHeadless`** (logon trigger + on-demand, `runhidden.exe` wrapper). Idempotent: exits 0 instantly if :9876 already live. |
| Self-healing | `D:\opt\cyberstrike-mcp\watchdog-mcp-estate.ps1` **section 5** (task `CyberStrikeMcpWatchdog`, 5-min sweep): TCP + SSE-header health check → if down, `Start-ScheduledTask BurpMcpHeadless`. Log: `D:\opt\cyberstrike-mcp\logs\watchdog.log`. |
| Client registration | `D:\opt\cyberstrike-mcp\mcp-ssot.json` → `fronts.burp` + `general_http_servers.burp` + catalogs (`specialized`, `general_cs_kit`, `general_http`). Apply changes with `python D:\opt\cyberstrike-mcp\apply-client-mcp-ssot.py`. Emitted to ZCode (`~/.zcode/cli/{config,setting}.json`), Claude (`~/.claude.json`, type `sse`), Codex (`~/.codex/config.toml`), CyberStrike (`~/.config/cyberstrike/cyberstrike.json`, enabled). |

## Using it (any agent)

- HTTP/SSE MCP clients: point at `http://127.0.0.1:9876` (root path!).
- stdio-only clients: `java -jar C:\Users\Prekzursil\AppData\Roaming\BurpSuite\mcp-proxy\mcp-proxy-all.jar --sse-url http://127.0.0.1:9876` (official packaged proxy).
- Raw probe (no MCP client needed):
  1. `curl -N -m 3 http://127.0.0.1:9876/` → must stream `event: endpoint` + `data: ?sessionId=<uuid>`.
  2. POST JSON-RPC `initialize` to `http://127.0.0.1:9876/?sessionId=<uuid>` (body `Content-Type: application/json`); responses arrive on the SSE stream.

## Enable / disable on command

- **Disable (stop the service):** `Stop-ScheduledTask BurpMcpHeadless` + kill Burp JVM (`java.exe` with `burpsuite_pro` in cmdline). NOTE: the 5-min estate watchdog will revive it within ~5 minutes unless you also disable the heal — to keep it down, temporarily comment out section 5 of `watchdog-mcp-estate.ps1` or flip the CyberStrike entry `enabled:false` (client-side only).
- **Enable / start now:** `Start-ScheduledTask BurpMcpHeadless` (or run `D:\opt\burp\burp-headless.ps1` directly).
- **Client-side toggle without touching the service:** flip `"enabled"` in the client config entry (CyberStrike: `~/.config/cyberstrike/cyberstrike.json` → `mcp.burp`).

## Failure classes and how they self-heal

| Symptom | Cause | Healing |
|---|---|---|
| Port 9876 refused | Burp JVM dead/crashed | watchdog sweep → task → relaunch (~1 min) |
| TCP up but no `endpoint` event | JVM wedged mid-boot | same (health check is SSE-aware, not just TCP) |
| Burp boot fails | project file locked by 2nd instance | launcher kills stale Burp JVMs first (single-instance) |
| Client "SSE error" | service mid-restart | retry; back within ~60 s |

## Known cautions

- **Licensing:** the `D:\opt\burp` runtime is an unofficial loader/keygen build (`+vodkrak` bundle). It works, but it is unlicensed software from a crack bundle — supply-chain and legal risk is yours. A compliant swap is Burp Community (free; MCP BApp works, Collaborator tools lost) or a licensed Pro jar: drop the jar at `D:\opt\burp\burpsuite_pro_v2026.3.2.jar` path (or update `$jar` in the launcher, removing the `-javaagent` line) and everything else stays identical.
- Burp has no true headless CLI flag; "headless" = hidden window via launcher. Don't kill java.exe blindly — SonarLint and others run java too; match `burpsuite_pro` in the command line.
- The old fragile chain (`launch_burp_headless.ps1` keygen-GUI + SendKeys + OCR) is superseded — do not use.

## Estate health additions (2026-09-19, same hardening pass)

- **dbx-ai** is now a supervised loopback front: `http://127.0.0.1:31120/mcp` (FastMCP 4.0.5 proxy in pinned venv `D:\opt\cyberstrike-mcp\.venv-dbxaifront` → stdio `dbx-ai-mcp-server.py`). Supervisor Full band (Heavy profile task `CyberStrikeMcpHttpCore`), watchdog deep-probes it. Registered via SSOT (`fronts.dbx-ai` + specialized catalog) — do NOT add stdio entries for it to cyberstrike.json; the SSOT reconciler prunes non-front keys (that's how it died the first time).
- Watchdog deep-probes now include sliver-full (31101) and dbx-ai (31120).
- Known watch item: hexstrike-ai (31113) deep-probe returns dead-child (rc=3) while its port serves; RepairFront has not healed it (pre-existing, dashboard still shows Connected).
- System-wide `fastmcp` (3.4.2) and pipx `mcp-proxy.exe` are BOTH broken against the current `mcp` package (import errors) — never use them for new bridges; use the pinned venv pattern above.
