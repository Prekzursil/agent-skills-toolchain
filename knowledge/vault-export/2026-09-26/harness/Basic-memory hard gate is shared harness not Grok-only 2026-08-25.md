---
title: Basic-memory hard gate is shared harness not Grok-only 2026-08-25
type: guide
permalink: main/harness/basic-memory-hard-gate-is-shared-harness-not-grok-only-2026-08-25
tags:
- harness
- basic-memory
- hooks
- sessionstart
- cross-ai
---

valid_as_of: 2026-08-25

## Owner request
Hard gate: every AI session must READ and WRITE basic-memory. Must be **shared harness**, not Grok-specific. Skills/hooks/rules live under `.agents` and dispatch to Claude/Codex/Grok.

## Why it "used to work" and then did not
1. `~/.claude/hooks/recall-inject/inject.py` injected on **UserPromptSubmit** from a **local lexical index**, fail-open, high precision (score>=2). Many prompts got **zero** injects.
2. Folded into shared `RecallModule` (`bounded_recall`) which **only ran on UserPromptSubmit** with prompt>=40 chars AND relevance>=16. **SessionStart returned immediately.** Fresh sessions got no vault.
3. SessionStart recovery replay only fires on `resume|compact|clear`, not `startup`.
4. Stop `basic_memory_nudge` is **advisory**, once per session, and **only if a canonical config file was edited**.
5. Grok user-guide: **SessionStart stdout may be ignored**. Portable inject path is **first UserPromptSubmit**.
6. `agents.json` basic-memory `targets` are `codex`+`claude` only. Grok is wired via `~/.grok/config.toml`, not that list.

## What landed 2026-08-25
`RecallModule` now injects a **vault digest** (newest 8 `D:/basic-memory/**/*.md`, skip compaction-checkpoints) on SessionStart **and** the first UserPromptSubmit (once-per-session marker). `reason_code=bm_vault_digest` at GOAL mixer priority. Fail-open if vault missing. Test: `test_recall_session_start_injects_vault_digest_once`.

WRITE is still the Stop nudge, not Exit 2 (AGENTS.md Exit 2 is for irreversible ops). Next if owner wants write as hard as read: Stop inject when any mutation happened and no `write_note` this session (already half-there; expand beyond canonical-tree).

## Schrödinger / this session (do not re-upload)
One `scp` of `2026-2_Schrodinger_Linux.zip` is **already in flight** to 51.159.180.9 (PID 516). Copy-suite FEP died at `mmffld_handle` (known). Do not start a second upload. INSTALL after ZIP_OK.
