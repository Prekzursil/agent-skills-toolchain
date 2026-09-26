---
name: ralph-runtime-memory-broken
description: ralph tools memory add fails with a file-locking error on this Windows
  host
metadata:
  node_type: memory
  type: fix
  originSessionId: 905c9ae6-d43a-4c6f-a7e1-e6cafccc5ec3
permalink: main/claude-memory/d-reverse-tools-android-battlecats-toolkit/ralph-runtime-memory-broken
---

`ralph tools memory add ...` fails on this Windows 11 host with: `Error: Failed to store memory / Caused by: File locking not supported on this platform` (it prints the error but still exits 0 — do not trust the exit code). This is why a stray `.ralph/agent/memories.md.lock` exists in the repo.

**Why:** the runtime memory store needs OS file locking the platform doesn't provide.

**How to apply:** don't rely on `ralph tools memory` for durable notes during BC loop runs. Persist cross-session facts in this file-based memory dir instead, and put run-local reasoning in `.ralph/agent/scratchpad.md` + `.ralph/agent/decisions.md`. `ralph tools memory search` is also unreliable as a result. Related: [[ida-mcp-down-objdump-fallback]].