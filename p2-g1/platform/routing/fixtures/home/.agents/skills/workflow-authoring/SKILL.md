---
name: workflow-authoring
description: Use when writing or debugging a saved Codex Workflow (a .js/.mjs orchestration script under ~/.Codex/workflows that uses the injected agent/parallel/phase globals to fan out subagents). Covers the exact runtime API, the args-as-string gotcha, the banned Date.now() non-determinism, worktree isolation for file-mutating agents, one-level nesting, a schema on every fan-in, null-tolerant barriers via filter(Boolean), per-work-unit pipelines so one slow agent cannot deadlock the cohort, cache-cliff-aware fan-out, the typed Codex output-schema landmine when MCP tools are active, and the SDK context-editing / task-budgets / canUseTool notes. Also the map to the saved schema-typed gate Workflows plan-gate and design-gate and the mechanical plan-lint stage-0. Triggers include author a workflow, write a saved workflow, fan out subagents, my parallel workflow deadlocks, workflow returns empty, schema-typed reviewers, or codify a gate as a workflow. NOT for single ad-hoc Task subagents (spawn a Task directly) or for the metaswarm phase pipeline itself.
---

# workflow-authoring

How to write a **saved Codex Workflow** — an orchestration script under
`~/.Codex/workflows/*.js` (or `*.mjs`) that the runtime executes to fan out
subagents, collect their typed results, and return a structured answer. This is
the durable, re-invokable form of a multi-agent job (invoked as `/name`), as
opposed to a one-off `Task()` subagent.

The rules below are distilled from the workspace's own recorded footguns
(`feedback_workflow_orchestration`, `feedback_parallel_agent_worktree`, the
"Workflow args-as-string gotcha") and the G.6 gem-hunt finds. Follow them and
your workflow will not deadlock, will reproduce, and will not contaminate the
shared git index.

---

## 1. The runtime API (the whole surface)

A workflow file is NOT a plain ES module. The runner injects three globals —
`agent`, `parallel`, `phase` — reads your `export const meta`, wraps the body so
top-level `await` and a trailing top-level `return` are legal, and executes it.

```js
export const meta = {
  name: 'my-workflow',                       // the /slash name; keep it stable
  description: 'one line — shown in the picker',
  phases: [{ title: 'Ground' }, { title: 'Fan-out' }, { title: 'Synthesize' }],
}

phase('Ground')                              // declare/enter a phase (telemetry)
const SCHEMA = { type: 'object', additionalProperties: false,
  required: ['answer'], properties: { answer: { type: 'string' } } }

const ground = await agent('prompt string', {
  label: 'ground',        // stable id for this agent (used in logs/telemetry)

### 2. args-as-string (the recorded gotcha)
### 3. Never call `Date.now()` (or `Math.random()`, `new Date()`) in workflow JS
### 4. `isolation: "worktree"` for any agent that MUTATES files
### 5. Null-tolerant barriers: `.filter(Boolean)` after every `parallel`
### 6. Per-work-unit pipelines, not one fat barrier
### 7. One-level nesting + a schema on EVERY fan-in
### 8. Cache-cliff-aware fan-out
### 9. Typed Codex `--output-schema` landmine (#15451)
### 10. SDK notes (context-editing, task-budgets, canUseTool)
### 11. Fan-out spawn-prompt template
### 12. agentType caveat — a fan-out is only as synchronous as its slowest lie
### Companion artifacts in this workspace
