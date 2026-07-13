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
| Sandbox ladder | WSL2 · `mcp__docker__*` · `mcp__cloud-hub__modal_sandbox_*` | none |
| Serena PageRank repo-map | `mcp__plugin_serena_serena__*` (LSP edges) + `mcp__repomix__pack_codebase` | none |
| Goose lead/worker escalation | Claude orchestrator (lead) + Task()/Codex workers | none (pattern only) |
| Per-edit lint ladder | `smallest-check-ladder` L0 (changed-file lint) | none |

---

## Pattern 1 — Architect→Editor split (cross-vendor per work-unit)

**Shape.** The **architect** (this Opus session) reasons and emits a **typed change-spec** — a
structured object, not prose. The **editor** (Codex, via the mounted `mcp__codex__codex` thread)
applies it. Planner and applier are **different model families**, so their failure modes are
independent (the same cross-vendor-diversity principle `execution-grounded-bon` exploits for
consensus, applied one level up at authoring time).

**The typed change-spec is the handoff contract** (AGENTS.md §5 — hand off a *structured summary*,
never a raw-output prefix). One spec per work-unit:

```yaml
change_spec:
  wu_id: G7-example
  file: src/foo.py
  anchor: { symbol: "Foo.bar" }          # symbol/line anchor, not a fuzzy "the function that..."
  intent: "clamp negative input to 0"
  before_invariant: "bar(-1) raises"
  after_invariant:  "bar(-1) == 0 and bar(2) unchanged"
  acceptance: "pytest tests/test_foo.py::test_bar_clamp  (must go red->green)"
  out_of_scope: ["do not touch Foo.baz"]  # scope fence (subagent discipline)
```

Then start a Codex editor thread with that spec as the task via `mcp__codex__codex`; continue by
`threadId` (see `multi-ai-mingle` for the exact fan-out wiring). Fan out one Codex thread per WU
for parallel WUs.

**Landmine (verified, MASTER G.7 / #15451).** Codex `--output-schema` (asking Codex to return a
*typed result*) is **silently ignored when MCP tools are active** in that Codex thread. So do not
rely on a schema-typed Codex *return* when the editor thread also has MCP tools mounted — parse
its result defensively, or run the typed-return exec lane with MCP tools off.

**Why this over "Opus does everything".** Cross-vendor authoring catches the class of bug where a
single model both writes and rationalizes the same wrong mental model. Keep the architect at
`effort:xhigh` (planning/architecture); the editor WU is mechanical application, eligible for
`effort:medium` (council C2 Lever 1 — still Opus if you keep it in-family, or Codex for the
diversity).

---

## Pattern 2 — Sandbox ladder (the Windows constraint that kills the naive build)

**The constraint.** Windows 11 has **no native OS-level process sandbox** (no Linux
namespaces/seccomp/cgroups). The naive plan — "build a local sandbox to run risky exec" — is
**not buildable natively on Windows**. So do not build one. **Route** risky/untrusted exec up a
ladder of *already-built* isolation, choosing the **cheapest tier that contains the blast
radius**:

| Tier | Rail | Isolation | Use for |
|---|---|---|---|
| 0 · local | PowerShell / Bash | none (owner's live machine) | known-safe, reversible ops only |
| 1 · WSL2 | WSL2 shell / native `/sandbox` | Linux namespaces, local FS | risky-but-local; the only place `/sandbox` is real on this box |
| 2 · docker | `mcp__docker__create-container` → exec → `get-logs` → remove | container FS + net isolation, local | untrusted deps, network-shaping, throwaway builds |
| 3 · modal | `mcp__cloud-hub__modal_sandbox_create` → `modal_sandbox_exec` → `modal_sandbox_terminate` | **remote ephemeral, zero local blast radius** | untrusted/hostile code, anything that must never touch the live machine; also the "external by construction" eval lane (C4/F8) |

**Rules.**
- Never run untrusted or exploit-class code at Tier 0. On Windows the honest floor for "risky" is
  **Tier 1** — hop into WSL2, because that is where a real sandbox exists.
- Escalate a tier when the payload can reach the network hostilely, mutate outside its worktree,
  or you cannot prove it reversible. Tier 3 (modal) is the containment ceiling — nothing it does
  survives `modal_sandbox_terminate`.
- Always tear the sandbox down (`remove` / `modal_sandbox_terminate`) — leaked containers/sandboxes
  are cost + drift.

**Anti-overfit:** this is *routing to existing rails*, not a build. Do not stand up a bespoke
sandbox service (SKIP-list: no new runtime).

---

## Pattern 3 — Serena-seeded PageRank repo-map (no tree-sitter, no vector)

**Goal.** Seed a fixed context-token budget with the **most central code** for the current
work-unit (the Aider repo-map idea) so agents point at the right symbols instead of blind-grepping
a whole tree.

**Build it off the LSP, not off a parser or embeddings.**
1. **Nodes** = symbols/files. Enumerate with `mcp__plugin_serena_serena__get_symbols_overview` /
   `find_symbol`.
2. **Edges** = real reference relations from `mcp__plugin_serena_serena__find_referencing_symbols`
   (and `find_implementations` / `find_declaration`). These are the **language server's actual
   reference graph** — semantically accurate, no tree-sitter heuristic re-parse, no chunker.
3. **Rank** = **personalized PageRank** over that directed graph, personalized toward the files the
   current WU touches (bias centrality to the change surface). Top-K symbols → the context bundle.
4. **Pack once, share** = `mcp__repomix__pack_codebase` on the top-K, then N agents grep the one
   pack (C1/cost doctrine: pack-once, byte-stable shared prefix for cache hits).

**Why not the alternatives.** The SKIP-list rejects vector-DB/embedding recall (mem0/OpenMemory/
codanna/ChunkHound/grepai) and tree-sitter chunkers. This rides the **already-mounted Serena** →
net-zero new infra, and the LSP edges are *more* precise than a tree-sitter approximation.

**Honest precondition.** Serena is currently **"disabled-yet-mounted"** on this workspace (the H.1
Serena split-brain, pending an in/out decision). Before relying on this pattern:
`mcp__plugin_serena_serena__activate_project` on the target repo and confirm the LSP responds
(`get_current_config`). **Fallback if Serena is out:** rank by import/reference degree from a
`repomix` pack (coarser, no LSP) or skip the map — never fabricate a ranking.

---

## Pattern 4 — Goose-style lead/worker failure-threshold escalation

**Shape (concrete trigger for the planned MaAS / A5 layer).** Borrow Block's Goose lead/worker
loop — the **pattern, not the runtime** (SKIP-list: copy the loop shape, do not install a 2nd
orchestrator). On this box the **lead = the Claude orchestrator**; **workers = Task() subagents +
Codex threads**.

- Track **per-WU consecutive failures** (a worker's `FAILED:<id>` terminal markers, §4).
- On the **Nth failure (threshold, default N=3)**, the worker **does NOT relaunch identically**.
  It **escalates to the lead**, which **re-decomposes** (split the WU smaller), **re-routes**
  (hand the stuck WU cross-vendor — e.g. Codex if Claude is stuck, or vice-versa), or asks the
  owner. This is the mechanism form of the two-strikes-pivot / anti-tunnel-vision rule
  (AGENTS.md §2/§4b).
- The escalation carries a **structured summary** (§5), not the failed worker's raw transcript.

**Why a threshold.** Identical retries past the threshold are the sunk-cost grind
(`fresh-context-verify` exists for exactly this). Escalation converts "grind harder" into
"re-plan / diversify" — the failure becomes a routing signal, not a loop.

---

## Pattern 5 — Per-edit lint ladder + reflection cap (max_reflections=3)

**Shape.** After **each edit**, run the **smallest check on changed files only** —
`smallest-check-ladder` **L0** (lint the edited file), never the whole suite on every keystroke.
Proportionate, cheap, fast feedback.

- If L0 fails: **reflect + fix**, but **cap at `max_reflections=3`**.
- On the **3rd** failed reflection: **escalate** (Pattern 4 — to the lead / cross-vendor / owner).
  **Do not grind.** Three self-corrections on the same edit that still fails means the mental
  model is wrong, not the syntax.
- Ladder *up* the check (L1 impacted tests → L2 full suite → L3 e2e) only at WU boundaries, not
  per edit — full-suite-per-edit is the latency anti-pattern.

**Advisory only.** This is guidance for the agent's own edit loop; it is **not** an auto-blocking
hook. Log the reflection count; never hard-block a commit and never nag on it.

---

## Shadow-mode / advisory posture (council C5)

This skill is **advisory documentation** — Claude reads it and applies the patterns. There is **no
auto-firing dispatcher hook here, so there is nothing to "shadow"** in the gate sense. Where a
pattern touches a would-be gate (the lint-ladder reflection cap, the failure-threshold), follow it
in **observe/advise mode**: record the signal to a bounded sink, never hard-block, never nag. If
any of these are ever promoted into an actual dispatcher branch, they enter the standard
**OFF → SHADOW → ADVISE → ENFORCE** ladder like every other gate (C5), under the C1 net-zero
always-on cap. Safety-class routing (e.g. "untrusted code must not run at Tier 0") is the one
part that is a fail-closed invariant, not a shadowed heuristic (C5 tier-1 / AGENTS.md §9).

## Anti-overfit boundary (what this deliberately does NOT build)
- **No 2nd orchestration runtime** — Goose is a copied loop shape, not an installed engine.
- **No vector/KG/embedding repo-map and no tree-sitter chunker** — the map rides Serena LSP edges.
- **No local sandbox build** — the ladder routes to WSL2 / docker / modal, all already mounted.
- **No trained router / learned critic** — routing is deterministic (risk-class → tier, failure
  count → escalate).
All five ride the existing bus; each adds a *pattern*, not a standing service.

## Testing / real proof (how this file was validated)
- YAML frontmatter parses and carries `name` + `description`; description contains **no angle
  brackets** (`quick_validate.py` constraint).
- Every load-bearing tool name cited resolves in this environment: `mcp__codex__codex`,
  `mcp__docker__create-container`, `mcp__cloud-hub__modal_sandbox_create` /
  `modal_sandbox_exec` / `modal_sandbox_terminate`,
  `mcp__plugin_serena_serena__find_referencing_symbols` / `get_symbols_overview` /
  `activate_project`, `mcp__repomix__pack_codebase`.
- Cross-referenced sibling skills exist: `multi-ai-mingle`, `execution-grounded-bon`,
  `smallest-check-ladder`, `fresh-context-verify`.

## Evidence
MASTER-DECISION-QUEUE.md **§G.7** (Orchestration mechanics, teardown-agents [REC]):
Architect→Editor split · Goose lead/worker failure-threshold escalation · Serena-seeded PageRank
repo-map (build-path pivot for 6.4) · sandbox ladder (Windows constraint kills the naive 6.2
build) · typed Codex `--output-schema` landmine (#15451) · per-edit lint ladder + `max_reflections=3`.
COUNCIL-VERDICT.md **C1** (net-zero cap / pack-once) · **C2** (effort:medium for mechanical editor
WUs) · **C5** (shadow/advisory posture). Anti-overfit SKIP-list: MASTER §2 (no 2nd runtime, no
vector/KG memory, no tree-sitter, no trained router).
