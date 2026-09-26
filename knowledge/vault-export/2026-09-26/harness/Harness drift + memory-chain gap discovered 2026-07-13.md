---
title: Harness drift + memory-chain gap discovered 2026-07-13
type: note
permalink: main/harness/harness-drift-memory-chain-gap-discovered-2026-07-13
tags:
- harness
- drift
- centralization
- basic-memory
- enforcement
---

# Harness drift + memory-chain gap discovered 2026-07-13

## Finding — the canonical harness is unversioned and drifted
`~/.agents/harness` is the LIVE canonical harness every Claude + Codex session loads. It is **NOT a git repo**. Its versioned source is `~/source/agent-skills-toolchain/ci/harness` (last commit `b062627`, 2026-07-11, clean in git). **All 8 `.py` files are DRIFTED** live-vs-source (adapters, dispatcher, ledger, models, modules, redaction, storage, __init__) — verified against a pre-edit backup, so the drift is pre-existing, not from today's edit.

Implication: sessions edit the live copy in-place; changes never flow back to the repo → no history, no changelog, unreviewed changes, possible contradictions. A re-deploy of `ci/harness` would silently overwrite live changes. This is the root of the "we don't know what changed / if it's broken or intended" problem.

## Memory chain — where durable facts actually go
`D:/basic-memory` (canonical vault) → `recall_index.build_index(--vault D:/basic-memory)` → `recall-index.json` → harness `RecallModule` injects relevant notes on UserPromptSubmit. The file-based `~/.claude/projects/<proj>/memory/MEMORY.md` is a SEPARATE auto-loaded index NOT connected to basic-memory. **Durable cross-session facts MUST be written to basic-memory (`write_note`)**, not just MEMORY.md — a note only in MEMORY.md is invisible to the harness recall in other sessions. (A session on 2026-07-13 drifted to MEMORY.md-only — the gap that surfaced this.)

## Loop fix landed 2026-07-13 (must be propagated)
Fixed the Stop-hook completion-gate endless loop ("Shared harness: Stop 3/4", ~53k tokens): `adapters.normalize_event` now maps the host's `stop_hook_active` flag → `event.trigger` (Claude Code puts re-entrancy in `stop_hook_active`, NOT `trigger`, so the guard never fired); `ClaimWarningModule.run` returns silent on a re-entrant Stop. 349 harness tests pass + 2 new regression tests pinning the production path. **Landed in LIVE `~/.agents` only** — must be propagated to `ci/harness` + committed or it is lost.

## Action (top priority)
Centralize + enforce: a single versioned source of truth for the harness + configs (skills, `.mcp.json`, hooks/settings), a guard against direct `~/.agents` edits, and a basic-memory-write discipline. Relates to [[Codex parity config 2026-07-11]] and [[Harness session-scoping fix 2026-07-11]].