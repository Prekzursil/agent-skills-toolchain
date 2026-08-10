---
name: orchestration-patterns
description: Use when orchestrating a multi-agent or multi-step coding workflow and you need the proven cross-vendor patterns for THIS Windows workspace - the Architect-to-Editor split (an Opus architect emits a typed change-spec, Codex applies it via the mounted codex mcp-server rail, cross-vendor diversity per work-unit), the sandbox ladder (route risky or untrusted exec to WSL2 native, the docker MCP, or a modal_sandbox, because Windows has no native OS-level process sandbox, the constraint that kills a naive local-sandbox build), a Serena-seeded PageRank repo-map (rank the most central symbols by running PageRank over the mounted Serena LSP reference edges, no tree-sitter pipeline and no vector store), Goose-style lead/worker failure-threshold escalation (on N worker failures escalate to the lead for re-decomposition instead of grinding), and a per-edit lint ladder capped at max_reflections=3 (changed-file-only lint, escalate not grind). Triggers include split architect and editor across models, route risky exec to a sandbox, build a repo map without embeddings, cap agent retries, escalate a stuck work-unit, or design the orchestration loop. NOT for wiring the Codex fan-out channel itself (use multi-ai-mingle) or picking among finished candidate patches (use execution-grounded-bon).
---

# orchestration-patterns

Five orchestration patterns that ride the **already-mounted bus** on this Windows 11 machine
(codex mcp-server, Serena LSP, the docker + cloud-hub/modal MCPs, WSL2, the smallest-check
ladder). They are **advisory patterns Claude applies while orchestrating** — not a new runtime,
not a new gate, not a hook. Every one deliberately re-uses existing infrastructure rather than
building a parallel stack (the anti-overfit gate: no 2nd orchestration runtime, no vector/KG
memory engine, no tree-sitter chunker, no local sandbox build, no trained router).

## When to use
- You are decomposing work into agents / work-units and want the cross-vendor, Windows-correct
  shape for the loop (who plans, who edits, where risky code runs, how the loop stops grinding).
- You need a repo map / context bundle **without** embeddings or a tree-sitter pipeline.
- A work-unit is stuck and you must decide "retry vs escalate vs re-decompose".

## When NOT to use
- Wiring the Codex fan-out channel or the agent-mail back-channel itself → **`multi-ai-mingle`**.
- Choosing among several *finished* candidate patches → **`execution-grounded-bon`** (execution
  consensus), not this skill.
- Running the smallest test for a diff in isolation → **`smallest-check-ladder`** (this skill
  only wires its L0 into the per-edit loop).

## The bus these ride (no new runtime)
| Pattern | Existing rail it rides | New infra? |
|---|---|---|
| Architect→Editor split | `mcp__codex__codex` (mounted codex mcp-server) | none |

### Pattern 1 — Architect→Editor split (cross-vendor per work-unit)
### Pattern 2 — Sandbox ladder (the Windows constraint that kills the naive build)
### Pattern 3 — Serena-seeded PageRank repo-map (no tree-sitter, no vector)
### Pattern 4 — Goose-style lead/worker failure-threshold escalation
### Pattern 5 — Per-edit lint ladder + reflection cap (max_reflections=3)
### Shadow-mode / advisory posture (council C5)
### Anti-overfit boundary (what this deliberately does NOT build)
### Testing / real proof (how this file was validated)
### Evidence
