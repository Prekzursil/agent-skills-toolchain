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

### Compose with
### PRD template
### Problem Statement
### Solution
### User Stories
### Vertical Slices (tracer bullets)
### Implementation Decisions
### Testing Decisions
### Out of Scope
### Further Notes
