---
title: Always write durable memory to basic-memory, not the ledger or auto-memory
type: feedback
permalink: main/claude-memory/root/always-write-durable-memory-to-basic-memory-not-the-ledger-or-auto-memory
tags:
- feedback
- memory
- basic-memory
- recurring
- process
---

# Always write durable memory to basic-memory, not the ledger or auto-memory

**Owner instruction, 2026-07-27:** *"always use basic-memory to maintain memory"* — given after a
long session in which I recorded everything to the **event ledger** (`note.py`) and the file-based
**auto-memory** directory, and wrote **nothing** to basic-memory until told.

## Why this is wrong, not just a style preference

The three stores have **different roles** and are not substitutes:

| store | role | survives compaction | searchable later |
|---|---|---|---|
| **basic-memory** (D: vault) | **canonical SEMANTIC layer** | yes | yes — this is the point |
| event ledger (`~/.claude/event-ledger/`) | objective turn history | replayed at SessionStart | poorly, and project-keyed |
| auto-memory (`~/.claude/projects/*/memory/`) | per-project index loaded each session | yes | only what fits in MEMORY.md |

Writing a finding to the ledger and calling it "recorded" leaves the canonical semantic layer
**empty**. The ledger is objective turn data; it is not a knowledge base and does not answer
"what did we learn about X."

## This is a RECURRENCE, not a first offence

Already observed and written down once:
[[variant-4-prompt-two-program-is-one-program-in-two-sessions-gate-half-execution-half]] records —
*"basic-memory was UP all along but I wrote ZERO semantic notes for ~2 days of work — only the
PreCompact hook's auto-checkpoints existed. The canonical semantic layer was empty."*

So the failure mode is: the ledger is **right there** in the hook output and feels like recording,
the PreCompact hook auto-checkpoints so nothing looks lost, and basic-memory requires an explicit
MCP call I keep skipping. **Convenience wins unless I make it a rule.**

## How to apply

- Write a basic-memory note **at the end of any substantive work unit** — a landed PR series, a
  resolved defect, a research verdict, a refuted hypothesis — not only at compaction time.
- Keep using the ledger for turn-level decisions/failures (AGENTS.md §3). It is **additional**, not
  a replacement.
- Prefer ONE well-structured note per program over many fragments; link with `[[permalink]]`.
- On a superseded fact, add `superseded_by:` to the old note and `valid_as_of:` to the new one so
  recall surfaces current truth.
- **Recall proactively too** — after a compaction/resume, or when the owner references prior work,
  call `search_notes` / `build_context` BEFORE asking them to re-explain.

Related: [[reference_claude-memory-extension]] ·
[[harness-drift-memory-chain-gap-discovered-2026-07-13]]
