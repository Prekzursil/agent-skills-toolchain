---
title: Burp MCP always-on hardening + MCP health fixes (2026-09-19)
type: decision
permalink: main/decisions/burp-mcp-always-on-hardening-mcp-health-fixes-2026-09-19
---

# Burp Suite MCP hardened (2026-09-19)

- [decision] Burp MCP = official PortSwigger MCP Server BApp v1.3.0 on Burp Pro 2026.3.2, endpoint `http://127.0.0.1:9876` — SSE transport at ROOT path (`/sse` and `/mcp` are 404; `GET /` streams `endpoint` events, POST to `/?sessionId=...`).
- [decision] Always-on architecture: Scheduled Task `BurpMcpHeadless` (logon+ondemand, runhidden.exe) runs `D:\opt\burp\burp-headless.ps1` — dialog-free launch via `--project-file=Documents\2026-06-10.burp` (carries MCP extension) + `--disable-auto-update`. Supersedes the keygen-GUI/SendKeys/OCR chain (`launch_burp_headless.ps1`, deprecated).
- [fact] Self-healing: estate watchdog `CyberStrikeMcpWatchdog` (5-min sweep) section 5 does TCP+SSE-header health; heals via Start-ScheduledTask. sliver-full(31101) added to its deep-probe set. Kill-and-revive verified: 42s reboot, 27 tools back (`send_http1_request`, Repeater/Intruder, proxy/ws history, Collaborator, scanner issues, intercept, config-edit, encoders).
- [fact] SSOT registration: `mcp-ssot.json` fronts.burp + general_http_servers.burp + catalogs specialized/general_cs_kit/general_http; `apply-client-mcp-ssot.py` emits to ZCode/Claude/Codex/CyberStrike (all verified). dbx-ai healed by repointing its dead path to `D:\opt\cyberstrike-mcp\dbx-ai-mcp-server.py`.
- [fact] Gotcha fixed: `TcpClient.Connect()` without timeout hangs forever on half-open ports (was the zombie-launcher root cause) — launcher + watchdog use BeginConnect+WaitOne(1500ms).
- [warning] `D:\opt\burp` runtime is a cracked loader/keygen bundle (+vodkrak) — legal/supply-chain risk; compliant swap = Burp Community (MCP works, no Collaborator tools) or licensed jar at the same path minus `-javaagent`.
- [fact] Browser AI sidebar: Page Assist force-installed via policy in Chrome+Edge (ExtensionInstallForcelist HKCU) and Firefox (Extensions.Install) — self-reinstalling, applies on browser restart. GLM provider `https://api.z.ai/api/coding/paas/v4` (coding-plan key), model glm-5.3. Pay-as-you-go `api/paas/v4` has zero balance (err 1113).
- Skill: [[burp-mcp]]; runbook D:\opt\burp\README-MCP.md; harness block in ~/.zcode/AGENTS.md.

Tags: burp, mcp, cyberstrike, always-on, security-toolchain

- [fact] (18:2x) Final fixes: dbx-ai front health-timeout raised 25s->90s in lib (FastMCP cold-boot chain missed 25s under supervisor -> circuit-opened); sliver-full must be respawned via its OWN launcher (sliver-full-mcp-http.cmd) when dead — deep probe healthy (74 tools) after direct respawn. CyberStrike TUI staleness lesson: dashboard registry is built at process start; toggles can't revive entries that predate config fixes — kill + relaunch (new console via `cmd /c start`). All verified green 18:26-18:31: burp 27 tools, dbx-ai 2 tools, sliver-full 74 tools, watchdog OK lines.