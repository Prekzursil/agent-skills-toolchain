---
title: README
type: note
permalink: dqverify-repo-20261013/tools/web/readme
---

# Web Tools

`tools/web/` is the bounded home for browser- or session-mediated tooling.

## Current bounded projects

None. This surface is currently empty and is kept as the reserved home for future
browser- or session-mediated tool projects.

## Retired 2026-08-09 — the ChatGPT-web lane

`agentify-desktop`, `promptbridge-talk-lane` and `agent-lanes-chatgpt-web` were deleted
together with their Codex-side drivers (`tools/mcp/codex-orchestrator`,
`tools/mcp/agent-lanes-codex`). The lane drove the ChatGPT web UI through a local Electron
desktop app; the app, its runtime directory (`CODEX_HOME/promptbridge-runtime`) and its state
directory (`~/.promptbridge-desktop`) no longer exist on any target, and no live config
registered the server.

Reusable, transport-independent survivors were extracted into
[`tools/lib/`](../lib/README.md) before the delete (path containment, workspace detection,
git-diff review packets, a handled-ledger with atomic JSON writes, a loopback-only remote-address
allowlist, and Windows Codex-binary resolution). Nothing else was preserved.

Replacement for the capability itself: call Codex directly through the official
`codex mcp-server` rail (`mcp__codex__codex` / `mcp__codex__codex-reply`).