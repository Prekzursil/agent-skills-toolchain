---
name: to-prd
description: Use when the user wants a PRD synthesized from the current conversation and codebase context (not an interview) and fed into the build pipeline as tracked, agent-ready work. Triggers include "turn this into a PRD", "write the PRD", "make issues from this", "spec this out for the team".
---

# To PRD

## Overview

Synthesize a PRD from the **current conversation + codebase understanding** — do NOT interview the user, use what you already know — then feed it into the metaswarm build pipeline as tracked, agent-ready GitHub work decomposed into tracer-bullet vertical slices.

## The native pipeline (the rewire)

mattpocock's original published to a generic tracker with a `ready-for-agent` label via a `/setup-matt-pocock-skills` config step. Here the PRD is the **input to the workspace's gates**, and there is no label-map:

1. **Synthesize the PRD** (template below). First pull the domain vocabulary and prior decisions from **basic-memory** + the **event-ledger** so wording matches what was already decided; respect prior decisions in the area you are touching. Compose with `grill-with-docs` if the plan is contested — its captured decisions become this PRD's Implementation Decisions.

2. **Sketch the seams.** Identify where the feature will be tested. Prefer existing seams to new ones; use the highest seam possible; if new seams are needed, propose them at the highest point. Confirm the seams match the user's expectations.

3. **STOP at the Design Review Gate.** Per the project workflow, a fresh design doc must pass `/review-design` (the design-review-gate: PM, Architect, Designer, Security, CTO — all must approve) before planning. Do NOT skip straight to issues. For a smaller change, run at least the plan-review-gate before presenting.

4. **Decompose into tracer-bullet vertical slices.** Each slice = one thin end-to-end path (UI -> logic -> data) that ships and is testable on its own. These become metaswarm work-units. List them in build order, each naming the seam it exercises.

5. **Publish to GitHub.** Use `gh issue create` (or the metaswarm `/create-issue` command) — one parent PRD issue plus one issue per vertical slice (or sub-issues under the parent). Triage is the metaswarm gates, not a label.

## Compose with

- **prototype** — a prototype snippet that nails a decision (reducer, state machine, schema, type shape) can be inlined in Implementation Decisions; see the template exception below.
- **grill-with-docs** — run a docs-aware grill first if the plan is contested; feed its captured decisions in.
- **design-review-gate / plan-review-gate / create-issue** — the gates and issue creation this PRD feeds.

## PRD template

```md
## Problem Statement
The problem the user is facing, from the user's perspective.

## Solution
The solution to the problem, from the user's perspective.

## User Stories
A LONG, numbered list. Each story: "As an <actor>, I want a <feature>, so that <benefit>."
Cover all aspects of the feature; be extensive.

## Vertical Slices (tracer bullets)
Numbered, in build order. Each slice is one thin end-to-end path that ships and is
testable on its own (a metaswarm work-unit). For each: the path it cuts and the seam
it exercises.
1. Slice — <thin end-to-end path> — seam: <where it is tested>

## Implementation Decisions
Modules built/modified, interfaces touched, technical clarifications, architectural
decisions, schema changes, API contracts, specific interactions.
Do NOT include specific file paths or code snippets — they go stale fast.
Exception: if a prototype produced a snippet that encodes a decision more precisely
than prose (state machine, reducer, schema, type shape), inline the decision-rich
bits and note it came from a prototype — not a working demo, just the important parts.

## Testing Decisions
What makes a good test here (test external behavior, not implementation details),
which modules will be tested, and prior art (similar tests already in the codebase).

## Out of Scope
What is explicitly not part of this PRD.

## Further Notes
Anything else.
```

---
_Idea adapted from the `to-prd` skill in https://github.com/mattpocock/skills — MIT License, Copyright (c) 2026 Matt Pocock. This is a workspace-native rebuild: the publish path is rewired from a generic tracker + label-map to the metaswarm gates (design-review-gate / plan-review-gate) and GitHub issues via gh / create-issue, with tracer-bullet vertical-slice decomposition and basic-memory/event-ledger vocabulary grounding added. Original under MIT; full notice in LICENSE (this folder). Built 2026-06-30._
