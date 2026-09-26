---
title: Basic-memory SOTA session contract (hook-injected not recognition-invoked)
type: guide
permalink: main/harness/basic-memory-sota-session-contract-hook-injected-not-recognition-invoked
tags:
- harness
- basic-memory
- sota
- hooks
- sessionstart
- capture
---

valid_as_of: 2026-08-25

## The finding (same class as skill-router)
Skills/MCPs/memory fail the same way: they are **recognition-invoked**. The model is shown a catalogue and must notice a match. It will not, unless the user names it. Fix recorded in [[Skill/MCP router hook — fixes only uses skills/MCPs when explicitly invoked]]: **inject via UserPromptSubmit**, do not wait for a tool call.

Architecture (2026-06-11): L4 recall = hook inject; L5 capture = Stop writer. **Writer was the named gap.** mem0 is NO-GO. Vault is D:/basic-memory. MCP at 127.0.0.1:8765 is optional; **CLI/filesystem is the durable path** (PR#24 `basic-memory tool write-note` bypasses flappy MCP; spool to disk first).

## Perfect contract (cross-AI, shared dispatcher)
**READ (the model must see notes without asking):**
1. SessionStart: inject newest vault titles (cwd-relevant first). Fail-open if vault down.
2. First UserPromptSubmit: same digest (Grok may ignore SessionStart stdout).
3. Later prompts: high-precision lexical overlap only (score gate), deduped per session. Silent on trivia.
4. resume/compact/clear: also replay **event-ledger** open failures (not a second memory store).

**WRITE (the model must not be the only writer):**
1. PreCompact: auto-checkpoint.
2. Stop: if this session mutated files or logged a milestone AND no vault write → **hook writes** a session note via CLI to the vault (spool then flush). Model `write_note` is extra.
3. SessionStart: if spool unflushed, re-flush.

**Do not:** Exit 2 every PreToolUse (bricks sessions when BM is down). Do not add mem0. Do not keep BM Claude-only in agents.json.

## Why sessions still skip it (measured)
RecallModule ignored SessionStart; UserPromptSubmit required prompt>=40 and relevance>=16 so most turns injected **nothing**. Stop nudge only if a *canonical config* file was edited. Grok SessionStart stdout may be ignored. That is why it feels like "only when told".
