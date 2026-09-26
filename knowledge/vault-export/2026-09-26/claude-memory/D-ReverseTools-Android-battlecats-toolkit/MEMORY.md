---
title: MEMORY
type: note
permalink: main/claude-memory/d-reverse-tools-android-battlecats-toolkit/memory
---

# Memory Index

- [IDA MCP down → objdump fallback](ida-mcp-down-objdump-fallback.md) — RE the BC .so with objdump when the IDA MCP isn't connected
- [Ralph runtime memory broken](ralph-runtime-memory-broken.md) — `ralph tools memory add` fails (file locking); use file memory instead
- [Frida hold dies at hat boundary](frida-hold-dies-at-hat-boundary.md) — background frida harness can't hold its hook into the next hat's iteration; verifier always sees a dead hook
- [Batch content ships in EN APK](bc-batch-content-ships-in-en-apk.md) — iter-18 recon: celebration/behemoth "needs-content" batch already has real MapStageData in the APK; blocker is the server schedule, not content
- [BC unlock loop auto-restart livelock](bc-unlock-loop-autorestart-livelock.md) — at real ceiling; PID kill (DEC-043) didn't fully stop respawns (fresh run_id reappeared ~16th cycle). Fix: as Planner emit BC_UNLOCK_COMPLETE directly, never route a wave