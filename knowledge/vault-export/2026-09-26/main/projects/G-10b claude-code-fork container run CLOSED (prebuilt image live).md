---
title: G-10b claude-code-fork container run CLOSED (prebuilt image live)
type: note
permalink: main/projects/g-10b-claude-code-fork-container-run-closed-prebuilt-image-live
tags:
- claude-code-fork
- g-10b
- docker
- mcp
- delegation-program
---

# G-10b claude-code-fork container closure (wf_c8e4c79c lane B1, 2026-09-22)

Closes the one FAILED-TO-RUN item from PROGRAM-REPORT_2026-09-22 §4.1 (wf2 deferred the
live container run at 0.80-0.84 GB free RAM).

- [fact] Prebuilt image exists locally: `claude-code-fork:1.10.12-fork.1` (ID 68f4ae76f307, 344 MB), built from `D:\tools\claude-code-fork\Dockerfile` (node:22-slim@sha256:48e4b67d…, npm ci genuinely executed in-VM: 228 pkgs in 7.7s). This is the prebuilt path for future lanes; `docker-stdio.sh` in the fork dir is the MCP-client bridge command.
- [fact] Container proof PASS: `docker run --rm -i --network none` + JSON-RPC initialize → exit 0, serverInfo claude_code/1.0.0 handshake identical to host smoke; runs as uid=999(claude) non-root, node v22.23.2, no runtime network needed. Documented honest limit unchanged: claude CLI not in image, tool calls ENOENT until owner-approved bind-mounts.
- [fact] Fork is NOT registered in any MCP registry (agents.json / .claude.json / .codex config.toml all zero matches) — by design, per task constraint.
- [observation] npm audit in-image: 16 vulns (2 critical) inherited from upstream claude-code-mcp @2e401f3 dep tree — not introduced by the fork patch.
- Receipts: `...\workflows\wf_c8e4c79c-1c8\B1-container-run-report.md` + build.log + container-stdout.txt / container-stderr.txt.

Related: [[claude-code-fork G-10b]] build receipts in PROGRAM-REPORT_2026-09-22.