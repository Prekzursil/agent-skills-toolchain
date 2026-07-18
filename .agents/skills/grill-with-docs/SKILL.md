---
name: grill-with-docs
description: Use when stress-testing a plan against the workspace's accumulated domain knowledge and prior decisions — challenge terminology, sharpen fuzzy language, check the plan against what was already decided, and write resolved decisions back. Use when the user says "grill against our docs/decisions", "does this match our domain model", or wants a glossary-aware, decision-store-aware design grill.
---

# Grill With Docs

## Overview

Grill a plan, but **grounded in the workspace's actual accumulated knowledge** instead of a per-repo glossary file. Pull the domain glossary and prior decisions from **basic-memory** (the semantic D: vault) and the **event-ledger**, challenge the plan against them, and write every resolved decision **back** into those same stores.

This beats grilling against a repo-local `CONTEXT.md` / `docs/adr/` set: the stores are cross-project, semantic, always current, and the SessionStart hook replays the ledger after compaction — so the grounding and the decisions both survive context loss.

## This is a layer, not a new grill

Do **not** re-implement the questioning loop. Run the existing grill for the cadence, then add the store-awareness on top:

- Single plan -> `grill-me` (interview relentlessly, one question at a time, recommend each answer, explore the codebase instead of asking when a question is answerable).
- Wide / under-specified program -> `grill-me-extensive` (the 7-step method: scout, diverge, structure, foundation-first, one-at-a-time, capture, converge — plus its grill modes).

`grill-with-docs` = those, plus the four domain moves and the load/capture wiring below.

## Before the grill — load the grounding

Recall is the part everyone skips. Do it first so your challenges are grounded, not generic:

- `mcp__basic-memory__search_notes` / `mcp__basic-memory__build_context` for the domain glossary and prior decisions in this area; `mcp__basic-memory__recent_activity` for what changed lately.
- Read recent **event-ledger** decisions (`~/.claude/event-ledger/`, or `note.py` history) so you grill against what was already decided, not from a blank slate.

If a relevant term or decision already exists, that is your grounding. If the plan contradicts it, that is your **first** challenge.

## During the grill — the four domain moves

One question at a time, each with your recommended answer (the grill-me discipline). Layer these in:

1. **Challenge against the glossary.** A term that conflicts with the stored definition: call it out immediately. "Memory defines 'cancellation' as X, but you seem to mean Y — which is it?"
2. **Sharpen fuzzy language.** Vague or overloaded term: propose a precise canonical term. "You said 'account' — do you mean the Customer or the User? Those are different things."
3. **Discuss concrete scenarios.** Stress-test domain relationships with specific edge-case scenarios that force precision about the boundaries between concepts.
4. **Cross-reference the code.** When the user states how something works, check whether the code agrees. On a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

## Capture decisions back — close the loop

As each decision crystallises, write it where the workspace looks for it — **inline, not batched** (long grills outlive a context window):

- Decision / rationale -> `python ~/.claude/hooks/event-ledger/note.py --kind decision "<resolved decision + why>"`.
- A dead-end ruled out -> `--kind failure` with falsifiable preconditions; a milestone that overturns a prior dead-end uses `--supersedes` so it is retired, not re-walked.
- A durable glossary term or cross-project decision -> `mcp__basic-memory__write_note` so recall surfaces it on the next project.
- **Temporal validity:** when a decision corrects an earlier one, mark the old note `superseded_by:` and the new one `valid_as_of:` (mirrors `note.py --supersedes`). Recall then surfaces current truth and retired dead-ends are not silently re-walked.

## Why this beats CONTEXT.md / ADR files

- One semantic store across every project, not a per-repo glossary you forget to read or keep in sync.
- Decisions land in the same ledger the SessionStart hook replays after compaction — they are recoverable, not stranded in a file.
- No new file taxonomy to maintain; the stores already exist and auto-load on recall.

If a repo genuinely also wants a committed, human-readable glossary or ADR, you can still write one — but the stores are the source of truth, and the committed file is a derived artifact.

---
_Idea adapted from the `grill-with-docs` skill in https://github.com/mattpocock/skills — MIT License, Copyright (c) 2026 Matt Pocock. This is a workspace-native rebuild: grounding and decision capture are rewired from CONTEXT.md/docs/adr files to basic-memory + the event-ledger, and the grilling loop composes with grill-me / grill-me-extensive rather than duplicating it. Original under MIT; full notice in LICENSE (this folder). Built 2026-06-30._
