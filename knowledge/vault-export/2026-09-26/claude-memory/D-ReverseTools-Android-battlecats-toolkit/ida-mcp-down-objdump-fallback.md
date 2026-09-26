---
name: ida-mcp-down-objdump-fallback
description: IDA MCP is unavailable in hat sessions; use objdump on the on-disk .so
  instead
metadata:
  node_type: memory
  type: reference
  originSessionId: 905c9ae6-d43a-4c6f-a7e1-e6cafccc5ec3
permalink: main/claude-memory/d-reverse-tools-android-battlecats-toolkit/ida-mcp-down-objdump-fallback
---

For BC RE work: the IDA Pro MCP (`mcp__mcp-funnel__ida-pro-mcp__*`) is **not connected** in hat/agent sessions even though the IDA database IS open on disk (`libnative-lib.so.id0` etc. present and recently modified). `ToolSearch` for "ida"/"mcp-funnel" returns nothing.

Working fallback for static RE: **objdump** (GNU binutils 2.44 at `/c/Program Files/CodeBlocks/MinGW/bin/objdump`; `r2` also present at `/c/ProgramData/chocolatey/bin/r2`). The ELF `.text` VMA equals the file address (imagebase 0x0), so addresses in the architecture docs map 1:1.

```
cd .../split_config.x86_64.extracted/lib/x86_64
objdump -d --start-address=0xADDR --stop-address=0xADDR libnative-lib.so
```

This fully substitutes for static decompile/disasm queries when the architecture doc (`docs/research/2026-05-24-bc-event-architecture-complete.md`) already has the decompiled logic and you only need exact addresses. See [[ralph-runtime-memory-broken]].