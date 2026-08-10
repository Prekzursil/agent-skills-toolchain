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

### During the grill — the four domain moves
### Capture decisions back — close the loop
### Why this beats CONTEXT.md / ADR files
