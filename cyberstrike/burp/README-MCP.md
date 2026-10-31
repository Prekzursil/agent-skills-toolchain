---
title: README-MCP
type: note
permalink: dqverify-repo-20261013/cyberstrike/burp/readme-mcp
---

# Burp MCP ops runbook (2026-09-19, hardened; LAZY-ACTIVATION REWRITE 2026-10-24)

Service: Burp Suite Pro 2026.3.2 headless + PortSwigger MCP Server BApp v1.3.0
Endpoint: http://127.0.0.1:9876  (SSE at ROOT path — /sse and /mcp are 404)

## Quick health
    curl -N -m 3 http://127.0.0.1:9876/        # expect: event: endpoint / data: ?sessionId=...
    tail -5 D:\opt\burp\logs\launcher.log
    # NOTE 2026-10-24: CyberStrikeMcpWatchdog is DISABLED - watchdog.log is frozen
    # (last write 2026-10-24 01:35). It no longer reports burp health; use the curl probe above.

## Start / stop (lazy activation — NO supervisor, NO auto-revive)

The watchdog era ended 2026-10-24: task `CyberStrikeMcpWatchdog` is DISABLED
(watchdog.log last write 2026-10-24 01:35). Nothing revives Burp automatically.
The service is lazily activated on demand:

    Start-ScheduledTask BurpMcpHeadless        # manual start (logon trigger also fires it at sign-in)
    powershell -File D:\opt\burp\burp-headless.ps1   # direct launch (heapcap-patched 2026-10-24 03:53)
    Stop-ScheduledTask BurpMcpHeadless         # stop: also kill java.exe with 'burpsuite_pro' in cmdline

Verified live state at rewrite time: BurpMcpHeadless task Ready (logon +
on-demand triggers); :9876 confirmed serving SSE during the 2026-10-24 audit.
Optional hardening: flip the task to on-demand-trigger-only so Burp boots only
when first invoked (remove the logon trigger). The old "keep-down requires
disabling watchdog section 5" paragraph is gone — there is no heal to fight.

## Files
- burp-headless.ps1        — dialog-free launcher (pinned project file carries the MCP extension)
- burpsuite_pro_v2026.3.2.jar / BurpLoaderKeygen117.jar — runtime + loader (see licensing note)
- C:\Users\Prekzursil\Documents\2026-06-10.burp — project file WITH the MCP extension loaded
- logs\launcher.log        — launcher events (rotated 2MB x3)
- SSOT: D:\opt\cyberstrike-mcp\mcp-ssot.json (fronts.burp) → apply-client-mcp-ssot.py
- Skill: skills-tree copy `burp-mcp` (post cc-profile skills hide it becomes `burp-mcp.cc-off`; archived repo copy: cyberstrike/burp/SKILL.md, mirrors this)

## Registration status
ZCode (config.json + setting.json), Claude (~/.claude.json, type sse),
Codex (~/.codex/config.toml), CyberStrike (enabled) — all emit from the SSOT.

## Legacy
launch_burp_headless.ps1 (keygen GUI + SendKeys + OCR chain) is DEPRECATED — kept
only as reference. Do not use; use burp-headless.ps1.

## Lazy-activation addendum (2026-10-24)
- CyberStrikeMcpWatchdog: DISABLED 2026-10-24 (corroborated by cyberstrike-mcp-lib.ps1.bak-caTimeout-20261024013534).
- BurpMcpHeadless: Ready — logon + on-demand triggers (next run 05:09 at audit time).
- Service: verified live on 127.0.0.1:9876 during the 2026-10-24 audit (SSE endpoint stream OK).
- Launcher: burp-headless.ps1 heapcap-patched 2026-10-24 03:53 (burp-headless.ps1.bak-heapcap-20261024-035321).