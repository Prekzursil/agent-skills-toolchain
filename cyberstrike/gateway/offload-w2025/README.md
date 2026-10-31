---
title: README
type: note
permalink: dqverify-repo-20261013/cyberstrike/gateway/offload-w2025/readme
---

# CyberStrike MCP engagement kit (rebuilt 2026-09-29, single-process design)

## Architecture (no supervisor, no watchdog, no front fleet)
ONE long-lived process: `gateway-server.py` on 127.0.0.1:31100/mcp.

- `kind=module` backends are imported IN-PROCESS — zero extra processes.
- `kind=binary` backends spawn PER INVOCATION via `subprocess.run(timeout=)`
  — the OS reaps the child on return; nothing can orphan or pile up.
- `kind=rpc` backends (msfrpcd, Burp :9876, C2 peers, RE bridges) — the
  gateway is a CLIENT; it never owns, restarts, or babysits those servers.
- Availability is computed lazily (importable / on PATH / RPC reachable), so
  the manifest can never drift from reality. Unavailable backends stay
  discoverable and `harness_invoke` returns their install note — no raw
  fallback, no silent degradation.
- Lifecycle = one logon scheduled task (`CyberStrikeGateway`, single
  instance). That is the whole mechanism; there is nothing to watch because
  there is nothing that can leak.

This replaces the previous supervisor/watchdog fleet that produced 19
dead-parented orphans (measured 2026-09-03) — the multi-port HTTP front model
was the root cause, and it is gone, not patched.

## Chain
mcp-ssot.json (single source of truth) -> apply-client-mcp-ssot.py ->
~/.config/cyberstrike/cyberstrike.json (exactly ONE MCP registration:
cyberstrike-gateway).

## Ops
- Register autostart (once, elevated):
    powershell -File gateway-autostart-install.ps1
- Start now:    Start-ScheduledTask -TaskName CyberStrikeGateway
- Stop:         powershell -File gateway-stop.ps1
- Deep probe:   python deep_front_probe.py 31100
- TUI session:  cyberstrike-launch.ps1 / start-session-tui.ps1

## Adding a backend
Drop an importable package under `fronts/` exposing `run(tool, args)`, add a
`kind=module` row to mcp-ssot.json — it self-registers; no config reload, no
port, no process. Binaries: add a `kind=binary` row with the exe name.