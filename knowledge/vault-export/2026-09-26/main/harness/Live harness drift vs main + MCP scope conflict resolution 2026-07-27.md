---
title: Live harness drift vs main + MCP scope conflict resolution 2026-07-27
type: reference
permalink: main/harness/live-harness-drift-vs-main-mcp-scope-conflict-resolution-2026-07-27
tags:
- harness
- drift
- hooks
- mcp
- scopes
- deployment
- windows
---

# Live harness drift vs main + MCP scope conflict resolution (2026-07-27)

Owner asked: *"is our local version of the harness not up to the main one from the toolchain repo?
If not bring it to live while carefully not breaking anything."* Measured it properly.

## Drift, measured by CODE lines (not bytes)

Of **193** hook `.py` files on `origin/main`:

| class | count | meaning |
|---|---|---|
| IDENTICAL | 158 | fine |
| LIVE-STALE | 8 | repo strict superset → safe to deploy |
| **LIVE-AHEAD** | **0** | the old "7 LIVE-AHEAD, never overwrite" note is now STALE — they were reconciled |
| DIVERGED | 11 | both sides unique code → per-file judgement |
| MISSING | 16 | on main, absent live |

**Compare CODE lines, never bytes.** `sessionstart-replay.py` looked "not deployed" at 4230 vs
4326 bytes; by code lines it was IDENTICAL — the difference was comments alone. I called it
undeployed on that basis and was wrong.

## What was safely synced

- **16 MISSING added** (purely additive; a file nothing references cannot change behaviour) —
  incl. `_shared/hookrun.py`, `_shared/failure_taxonomy.py`, `cmd-rewrite/msys_pathconv.py`
  (notable: MSYS path conversion bit me twice the same day and the hook for it wasn't deployed),
  `harness-bench/gate.py`.
- **7 LIVE-STALE updated** (repo superset), incl. `_shared/use_vs_mention.py` **+56 code lines** —
  which was a skew I had *created* by deploying `sentinel.py` and `stubscan.py` from main without
  their shared dependency.

## The trap I walked into: TEST-AHEAD-OF-IMPLEMENTATION

Deploying newer TESTS whose IMPLEMENTATIONS are DIVERGED (and therefore skipped) produced 4 new
failures. **When syncing selectively, a test and its implementation must move together** — or the
suite reports a regression that does not exist. Undone by restoring those two test files.

Also learned: **36 of the failures were PRE-EXISTING**, not mine. Live `per-edit-check/test_secrets.py`
has always tested a `_scan_secrets` gate that live `check.py` does not implement.

## STILL OPEN: a security control merged but not live

`hooks/per-edit-check/check.py` — the write-path secret gate (**PR #211**) is merged but **NOT
deployed**. Live 9,546 bytes / **zero** `_scan_secrets`; repo 15,378 with the full gate. Repo is
effectively a superset (its only 3 live-only lines are docstring prose), so it is deployable — but
it **blocks edits with exit 2** and 13 fixture files would need `PER_EDIT_SECRETS=off`. Deploying it
also fixes all 36 failing live tests. **Owner decision.**

`semantic-router/eval.py` is genuinely LIVE-AHEAD (10 unique code lines incl. `def score`,
`["binary-ninja"]`) — needs a real merge, never a blind overwrite.

## MCP scope conflicts — canonical is right, USER scope is stale

Claude Code reported `playwright` / `angr` / `frida-mcp` defined in two scopes.

| server | `~/.mcp.json` (canonical) | `~/.claude.json` (user) |
|---|---|---|
| angr | local `.venv\Scripts\angr-mcp.exe` (exists) | `sse → 127.0.0.1:8760` — **port CLOSED, dead** |
| frida-mcp | local `.venv\Scripts\frida-mcp.exe` (exists) | `npx -y frida-mcp` |
| playwright | `@playwright/mcp@0.0.78` (pinned) | `npx` unpinned |

Cause: the promote script pushed an OLDER snapshot into user scope; `~/.mcp.json` moved on.
Fix = `claude mcp remove <name> -s user` for the three, so canonical wins. NOT done unasked —
[[feedback-mcp-enabled-state]] requires explicit per-occurrence approval, and user-scope promotion
is Claude-CLOSED-only.

**Refuted here:** I assumed `npx -y frida-mcp` was one of the known E404 stubs. `npm view frida-mcp`
returns **1.0.0** — it is real. And npm's current `@playwright/mcp` **is** 0.0.78, so the unpinned
user entry resolves to the same thing; that conflict is cosmetic.

Related: [[claude-desktop-repair-the-code-tab-config-truth-2026-07-27]] ·
[[always-write-durable-memory-to-basic-memory-not-the-ledger-or-auto-memory]]
