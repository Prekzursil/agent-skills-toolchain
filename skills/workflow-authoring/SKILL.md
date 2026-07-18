---
name: workflow-authoring
description: Use when writing or debugging a saved Claude Code Workflow (a .js/.mjs orchestration script under ~/.claude/workflows that uses the injected agent/parallel/phase globals to fan out subagents). Covers the exact runtime API, the args-as-string gotcha, the banned Date.now() non-determinism, worktree isolation for file-mutating agents, one-level nesting, a schema on every fan-in, null-tolerant barriers via filter(Boolean), per-work-unit pipelines so one slow agent cannot deadlock the cohort, cache-cliff-aware fan-out, the typed Codex output-schema landmine when MCP tools are active, and the SDK context-editing / task-budgets / canUseTool notes. Also the map to the saved schema-typed gate Workflows plan-gate and design-gate and the mechanical plan-lint stage-0. Triggers include author a workflow, write a saved workflow, fan out subagents, my parallel workflow deadlocks, workflow returns empty, schema-typed reviewers, or codify a gate as a workflow. NOT for single ad-hoc Task subagents (spawn a Task directly) or for the metaswarm phase pipeline itself.
---

# workflow-authoring

How to write a **saved Claude Code Workflow** — an orchestration script under
`~/.claude/workflows/*.js` (or `*.mjs`) that the runtime executes to fan out
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
  phase: 'Ground',        // which declared phase this belongs to
  schema: SCHEMA,         // JSON-schema; the runtime RETURNS a parsed object
  effort: 'high',         // reasoning effort: 'low' | 'medium' | 'high' | 'xhigh'
  model: 'opus',          // 'opus' (default, deepest) or 'fable' for wide fan-out
})

phase('Fan-out')
const results = (await parallel(
  items.map((it) => () => agent(promptFor(it), { label: `lens:${it.key}`, phase: 'Fan-out', schema: SCHEMA }))
)).filter(Boolean)          // <-- the null-tolerant barrier; see rule 5

return { ...ground, results }   // top-level return is the workflow's result
```

- `agent(prompt, opts)` → a Promise of the **parsed schema object** (not raw
  text). Always pass a `schema` so you get typed fields, never prose to re-parse.
- `parallel(thunks)` → a Promise of an array, one entry per thunk, in order.
  **Pass an array of zero-arg thunks** (`() => agent(...)`), not an array of
  already-started promises — the thunks let the runtime schedule/limit them.
- `phase(title)` is telemetry/structure; call it once per phase before its work.

---

## 2. args-as-string (the recorded gotcha)

A Workflow receives its invocation arguments as **one single string**, not a
parsed array or object. If you expect structured input, **parse it yourself**
inside the workflow, and design for the common case where there is no reliable
arg channel at all: **have the agents auto-discover their input from live files**
(Read/Glob) rather than relying on args being threaded in. The saved gate
Workflows do exactly this — they tell each reviewer where to find the plan/design
doc and let it locate + Read it. Do not assume `argv[1]` semantics.

## 3. Never call `Date.now()` (or `Math.random()`, `new Date()`) in workflow JS

Non-determinism in the orchestration layer breaks two things: **prompt-cache
stability** (a changing timestamp in a shared prefix busts the cache for every
downstream agent — see rule 8) and **reproducibility** (two runs of the same
workflow diverge for no reason). If you genuinely need a timestamp or a random
id (e.g. to name a shadow-log line), **generate it inside an agent's tool call**
(`Get-Date -Format o` in PowerShell, `date -Is` in a POSIX shell) — never in the
workflow's own JavaScript. The gate Workflows produce their shadow-sink timestamp
this way for precisely this reason.

## 4. `isolation: "worktree"` for any agent that MUTATES files

Parallel subagents share ONE git index and working tree by default. A broad
`git add -A` in one agent then sweeps a sibling's in-flight files into the wrong
commit (`feedback_parallel_agent_worktree`). Any agent that WRITES to the repo
must run isolated:

```js
agent(prompt, { label: 'impl:WU3', schema: S, isolation: 'worktree' })
```

Read-only agents (reviewers, researchers, the gate reviewers) need no worktree —
declare them read-only in the prompt and skip the overhead. Pair worktree
isolation with **disjoint file scopes** (rule 7) so two mutating agents can never
target the same file.

## 5. Null-tolerant barriers: `.filter(Boolean)` after every `parallel`

`parallel()` has **no per-agent timeout** and a throwing thunk **resolves to
`null`** rather than rejecting the whole batch. Two consequences:

- **Always** `.filter(Boolean)` the result so one dead agent does not poison the
  aggregation with a `null` you then dereference.
- One HUNG (not thrown — actually stuck) agent will still **stall the whole
  phase** until it dies, because the barrier waits for all thunks. That is the
  recorded barrier-deadlock (`feedback_workflow_orchestration`). The structural
  fix is rule 6.

```js
const reviews = (await parallel(reviewers.map((r) => () =>
  agent(r.prompt, { label: `review:${r.role}`, schema: REVIEW_SCHEMA })
))).filter(Boolean)   // a throwing reviewer becomes null -> dropped, phase completes
```

## 6. Per-work-unit pipelines, not one fat barrier

Prefer `pipeline()`-style per-WU flows (impl → validate → review → commit for
each WU independently) over a single wide barrier that waits for the slowest WU
before ANY progress. A per-WU pipeline means a slow or stuck WU idles only
itself, not the whole cohort — and it composes with the cross-session resume
manifest (rule 10) so a died WU is re-driven while its siblings keep their
completed state. When you must use a wide `parallel`, keep the batch small and
homogeneous (similar expected runtimes) so the barrier's tail is short.

## 7. One-level nesting + a schema on EVERY fan-in

- **One level of nesting.** `parallel([... agent ...])` at the top is fine.
  Nesting `parallel` inside an `agent` inside another `parallel` makes runtimes,
  failures, and telemetry impossible to reason about — flatten into sequential
  phases instead.
- **Schema on every fan-in.** Every `agent()` that feeds an aggregation MUST
  carry a `schema` (with `additionalProperties: false` and an explicit
  `required`). You then aggregate typed objects, never re-parse prose. The
  aggregator agent also takes a schema. This is what makes the gates
  "schema-typed": `{ verdict, blocking, ... }` on each reviewer.

## 8. Cache-cliff-aware fan-out

For a wide fan-out (many lenses/WUs), keep the **shared prompt prefix
byte-stable** across all agents so the prompt cache is hit N-1 times instead of
paid N times. Concretely: build one immutable `CONTEXT` / `PROBLEM` string and
prepend it identically to every agent prompt (only the per-agent tail varies);
do not interpolate anything volatile (timestamps, random ids, re-serialised JSON
with unstable key order) into that prefix — that is the cache cliff, and it is
the other reason rule 3 bans `Date.now()`. Pack a repo once (repomix) and let N
agents grep the pack rather than each re-reading the tree.

## 9. Typed Codex `--output-schema` landmine (#15451)

When a workflow fans out to Codex (via the mounted `codex mcp-server` /
`codex exec`), a typed `--output-schema` is **silently ignored if any MCP tools
are active** in that Codex invocation (OpenAI codex issue #15451). You will get
free-form text back and your `schema` parse will fail or mis-fill. Mitigations:
run the schema-typed Codex lane with MCP tools disabled for that call, or
validate/repair Codex's output on the Claude side before aggregating. Do not
assume the schema was honored just because you passed it.

## 10. SDK notes (context-editing, task-budgets, canUseTool)

When a workflow is driven through the Agent SDK rather than the in-app runtime:

- **context-editing (`clear_tool_uses`)** trims tool-call history to fit long
  fan-outs — enable it for long-running orchestrations so agents do not blow the
  window on accumulated tool noise.
- **task budgets** cap per-agent spend; set them on mechanical/harvest agents so
  a runaway agent cannot drain the wave.
- **`canUseTool`** is the SDK's per-agent tool gate — the file-scope / capability
  enforcement point for fan-out subagents (the parity for in-app subagent
  scoping). Use it to hold a mutating agent to its declared file scope (rule 4/7).

---

## Companion artifacts in this workspace

- **`/plan-gate`** (`~/.claude/workflows/plan-gate.mjs`) — saved, schema-typed
  Plan Review Gate: a mechanical stage-0 lint, then 3 fresh adversarial reviewers
  (Feasibility, Completeness, Scope & Alignment), each returning
  `{ verdict, blocking }`. SHADOW/advisory — records a verdict, never blocks.
- **`/design-gate`** (`~/.claude/workflows/design-gate.mjs`) — saved Design
  Review Gate: 5 fresh reviewers (PM, Architect, Designer, Security, CTO) in
  parallel, each `{ verdict, blocking }`. SHADOW/advisory.
- **`plan_lint_stage0.py`** (`~/.claude/harness-meta/`) — the mechanical stage-0
  the gate runs FIRST: `lint(plan)` checks WU ≤ 5 files, no overlapping scopes,
  and a valid DAG, returning `PLAN_LINT:clean|dirty|na` (SHADOW, exits 0). It
  also ships the **cross-session resume manifest** (`done.jsonl` + write-ahead
  `partial` records): mark a WU `partial` before it runs and `done` after it
  commits, then on a resumed session `resume(all_wu_ids)` classifies WUs into
  done / partial (crashed → re-drive) / pending — so a teammate that dies on a
  session cut is not silently redone.

Both gates ship in **SHADOW mode** (council C5): they surface a verdict + append
one line to a bounded, auto-rotating shadow sink; promotion to an ENFORCE gate
that blocks on a blocking FAIL is a separate, deferred step.

## Quick checklist before saving a workflow

- [ ] `export const meta` with a stable `name` + `phases`
- [ ] a `schema` (with `additionalProperties: false`) on every `agent()` fan-in
- [ ] `.filter(Boolean)` after every `parallel()`
- [ ] `isolation: 'worktree'` on every file-MUTATING agent; disjoint scopes
- [ ] no `Date.now()` / `Math.random()` / `new Date()` in the workflow JS
- [ ] byte-stable shared prompt prefix; volatile data only in per-agent tails
- [ ] one level of nesting; wide barriers kept small + homogeneous
- [ ] agents auto-discover their input (args arrive as one string)
