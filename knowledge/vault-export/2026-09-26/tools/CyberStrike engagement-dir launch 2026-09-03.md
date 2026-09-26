---
title: CyberStrike engagement-dir launch 2026-09-03
type: note
permalink: main/tools/cyber-strike-engagement-dir-launch-2026-09-03
tags:
- decision
- fact
- cyberstrike
---

# CyberStrike engagement-dir launch 2026-09-03

- [decision] G-8 A: CyberStrike may only launch from `Cowork\\private\\cyberstrike-engagements\\<name>`. Never HOME, never `source\\`.
- [fact] Launcher `D:\\opt\\cs-mcp\\cyberstrike-launch.ps1`, shim `cyberstrike-engage`. Current pointer `D:\\opt\\cs-mcp\\current-engagement.txt` = `cursor-auth-recovery-2026-09-02`.
- [fact] Override via env `CYBERSTRIKE_ENGAGEMENT_DIR` still must resolve under that tree. HOME and source refused in a live probe.

Related: [[CyberStrike Sliver HTTP MCP 2026-09-03]] [[CyberStrike global aggressive agent prompt 2026-09-03]]