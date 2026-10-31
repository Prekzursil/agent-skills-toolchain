---
name: frida
description: Use when runtime hooking, device instrumentation, API tracing matters
  more than static disassembly. NOT for MCP setup (use frida-mcp).
permalink: dqverify-repo-20261013/skills/frida/skill
---

# Frida

## Overview

Use Frida for live instrumentation: attach, hook, trace, and patch behavior in running targets. Prefer Frida when you need runtime truth from Android, iOS, or desktop software.

## Quick Workflow

1. Verify the transport first with `frida-ps -ai` for local targets or `frida-ps -Uai` for USB devices.
2. Decide whether to attach to an existing process or spawn a fresh one.
3. Start with the smallest hook that proves control over the target function.
4. Record PIDs, device context, timestamps, and script revisions with every finding.
5. Use the companion `frida-mcp` skill only when an MCP client should drive the session.

## Common Mistakes

- Writing a large script before proving the target function is hit.
- Instrumenting the wrong process because transport context was not verified.
- Treating console logs as final truth without correlating them to a specific process and time window.

## Reference Map

Read `references/upstream.md` for install notes and the minimum command-line sanity checks.