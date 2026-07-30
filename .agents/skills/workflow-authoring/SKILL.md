---
name: workflow-authoring
description: "Use when writing or debugging a saved Claude Code Workflow (a .js/.mjs script under ~/.claude/workflows using the injected agent/parallel/phase globals to fan out subagents). Covers the runtime API, banned Date.now() non-determinism, worktree isolation, per-fan-in schemas, null-tolerant barriers, and the typed Codex output-schema landmine. Triggers: author a workflow, fan out subagents."
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
- **`required` is the FLOOR, not the wishlist — over-broad `required[]` rejects
  good work.** List in `required` ONLY the fields an agent can ALWAYS produce
  (typically `digest`/`answer` + `evidence`). Anything conditional — a `verdict`
  a null-result unit has no basis for, an `artifact` path a read-only lens never
  writes, an `owner_actions` array that is legitimately empty — must be OPTIONAL.
  A required field the agent cannot fill makes StructuredOutput reject an
  otherwise-correct return and burn all its retries. Ledger-proven 2026-07-19
  (`wf_00a25df9-2cd`): a `DIGEST` requiring `verdict/corrections/evidence/artifact`
  failed 2 agents 5× each — their real analysis (one wrote a 16 KB artifact to
  disk) was thrown away purely on the digest shape. Belt-and-braces: have each
  agent WRITE its full deliverable to disk (rule 11 output contract) so a rejected
  digest never loses the work — the synthesis fan-in reads the artifact, not the
  digest.
- **Editing a shared schema const busts the RESUME cache — plan the schema before
  the first launch.** Resume is prefix-cached: a completed `agent()` replays only
  if its `(prompt, opts)` is byte-identical, and `opts.schema` is part of that.
  A schema referenced by the FIRST phase's agents is therefore the worst thing to
  edit on a resume — it changes every agent's `opts`, so the longest-unchanged
  prefix is empty and ALL agents re-run live (a full "from beginning" run you may
  have been explicitly told to avoid). Corollary: get the schema right up front;
  if you must fix an over-strict schema mid-run, the cache-preserving move is a
  ONE-OFF standalone `Task()` for the single failed lens (writing the same
  artifact path), NOT an edit-and-resume of the shared const.

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

**Windows arg-limit corollary (measured 2026-07-18).** The same active-MCP inventory that voids
`--output-schema` also blows the Windows 32,767-char `CreateProcess` limit: two Codex runs died
with `payload_len=34472` / `os error 206` before executing anything. Pass `--ignore-user-config`
on every non-interactive Codex invocation, and pass the prompt BY FILE (`--prompt-file`, or stdin
via `-`), never inline. See `rules/common/cross-vendor-dispatch.md`.

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

## 11. Fan-out spawn-prompt template

Measured over 50 agents / 6 workflows (2026-07-18): element presence in the prompt predicts
compliance almost perfectly, and **nothing is inherited** from the global contract. Blocks marked
REQUIRED are the ones with measured evidence behind them. Full rationale + the fan-in gates:
`rules/common/fan-out-contract.md`.

```
[REQUIRED] VERIFIED GROUND TRUTH — established by direct inspection immediately before this
workflow. Treat as high-confidence. Each claim is tagged [probe: <how it was measured>].
To confirm OR refute you MUST use a mechanically DIFFERENT probe — a different shell, a
different data field, a different measurement. Re-running the tagged probe does NOT count as
verification and must not be reported as CONFIRMED. Report every reconciliation in a
dedicated section, whatever the outcome.
  1. <claim>  [probe: Get-Command mon, PowerShell 7]
  2. <claim>  [probe: directory listing at 00:25 — may be stale]
  ...
[REQUIRED] ACCESS METHODS — for every path above that is NOT readable by Read at that literal
path, state how to read it:
  - tools/monitorcore/** exists ONLY on origin/main: read via `git show origin/main:<path>`.
    The working tree is on branch <X> and does not contain it.

[REQUIRED] ANTI-OVERFIT ANCHOR — a proposal counts only if it (a) rides the EXISTING bus
(<name the buses>), and (b) does not reintroduce a rejected component (<name them>).
Prefer "enable a native feature" and "fold into the existing adapter" over "new daemon".
[If a deliverable deliberately waives this, say so explicitly and say why.]

ENVIRONMENT: <OS, shells, language constraints, RAM ceiling>.

=== YOUR TASK (<lens-slug>) ===
<2-5 sentences. Name the concrete artefacts to read. State the deliverable as numbered
outputs. End with "Be concrete about <the specific axis>, not generic <domain> advice.">

[REQUIRED] PER-FINDING RUBRIC — apply to every RECOMMENDATION (skip for pure audit findings):
  name / what it is / why THIS user specifically / how to build-or-adopt (file, function,
  command) / source: file:line or URL / value (H|M|L) x effort (H|M|L) /
  disposition: NATIVE (already exists, just enable) | ADOPT (external, vendor it) |
    BUILD (write it) | PRUNE (delete something) /
  confidence: almost-certain 90-99% | likely 55-80% | roughly-even 45-55% | unlikely 20-45%,
    followed by the evidence that justifies that band.

[REQUIRED] HONESTY CONTRACT — the global contract does NOT carry into this fan-out; these
apply here or not at all:
  - Attach UNVERIFIED INLINE to the sentence it qualifies. A limitations section at the end
    does NOT satisfy this. If a recommendation's premise is UNVERIFIED, its heading inherits
    the tag.
  - Every UNVERIFIED names the experiment that would settle it.
  - "Absent / not found / broken" is a claim, not an observation. Verify your detector can
    find a known-present item before reporting absence.
  - Do not report CONFIRMED on a probe that is the same mechanism as the one being checked.
  - If a tool is denied, you are in a subagent — no user will answer. Do not stop. Record the
    gap, use an alternative, report it in your digest.

[REQUIRED] OUTPUT CONTRACT
  1. Write the full deliverable to <abs path>. Write it with the **Write** tool. If a single
     call is too large, chunk with `Add-Content` — never build a multi-KB literal inside a
     shell command string (Windows 32,767-char limit -> os error 206).
  2. Then return a <= 400 word structured digest as your final text (NOT the whole doc).
     LEAD the digest with any ground-truth correction, then the top findings.
  3. Append an EVIDENCE: block of 3-5 file:line / URL anchors. It is EXEMPT from the word
     cap — 87% of file:line refs and 100% of URLs otherwise die at the digest boundary.
  4. Your final line must be: DELIVERED: <abs path> (<n> bytes)
```

For a cross-vendor (Codex) unit, do NOT paste a here-string output contract and do NOT route
through a `*-rescue` forwarder — see §12 and `rules/common/cross-vendor-dispatch.md`.

## 12. agentType caveat — a fan-out is only as synchronous as its slowest lie

`agent({ agentType: 'codex:codex-rescue' })` is NOT an interchangeable work-unit executor. Its
definition instructs it to **prefer background execution** for tasks that are "complicated,
open-ended, multi-step" — i.e. every work unit — and it ships `model: sonnet` with `tools: Bash`
only, so it cannot write a report or verify its own artifacts. Measured: 3 such agents, 34 turns,
**0 production files**; one returned only a job id, and that job then completed on disk with a
real finding the harness could not collect. Use `agentType: 'codex'` (the synchronous adapter).
Any barrier that accepts a result containing `started in the background` or `Check /codex:status`
is accepting a receipt, not an answer — reject it at fan-in.

## 13. Wire the resume manifest — the cross-session half of rule 6

`plan_lint_stage0.py` has shipped a complete, `fsync`'d `ResumeManifest` since 2026-07-12 and, as
measured 2026-07-29, had **zero callers**: the only reference anywhere was the `LINTER` const at
`plan-gate.mjs:35`, which runs `lint()` and never touches the manifest. Consequence — every saved
Workflow that dies mid-wave redoes the whole wave.

**Wire it with an `agent()` step, never a JS shim.** The runner *wraps the body* (rule 1), so a
static top-level `import` is a SyntaxError; measured across all 11 saved workflows there is not one
`import`, `require(`, `child_process` or `fs.` call — every disk read is delegated to an agent's
shell. Copy `templates/resume-wired-fanout.md` (its `js` block is kept lint-clean and is gated by
`scripts/test_workflow_lint.py`). Three touch-points, nothing else:

| when | command | effect |
|---|---|---|
| GROUND, once | `--manifest M --ids <all> --next` | stdout = exactly the ids still to run, one per line |
| BEFORE each unit | `--manifest M --mark-partial <id>` | write-ahead; an `fsync`'d `partial` record |
| AFTER each unit | `--manifest M --mark-done <id>` / `--mark-failed <id>` | terminal state |

`--ids` and `--next` exist because a Workflow's unit list is a **JS array**: `resume()` derives
`pending` from a declared work-list, and the CLI's only other source was `--plan`, which reads a
plan *document*. So an author had to synthesise a throwaway `plan.wu.json` just to name their own
units — that friction is the mechanical reason the manifest shipped uncalled.

Durability, measured (not assumed): with `--mark-partial WU3` written, a `taskkill /F` on the unit
process, and `--resume` in a fresh interpreter, WU3 lands in `partial` — process-crash recovery is
**executable-proven** (13/13 assertions, and 3/3 mutants of the fold/append/torn-line logic go RED,
so the probe is not vacuous). **UNVERIFIED, inline: machine-crash / power-loss durability is NOT
proven** — a process kill cannot distinguish `fsync`'d bytes from page-cache bytes, so the
experiment cannot see the `fsync` at all (only an instrumented counter shows the call is reached,
`FSYNC_CALLS=1` per append). Settling experiment: run the same protocol in a VM and hard-cut power
between the append and the read.

Two honest limits to design around: `--mark-done` is **asserted by the unit agent**, not verified by
the orchestrator, so pair it with an independent postcondition probe (artifact exists AND ends with
your completion marker) exactly as the accumulator workflow's AND-gate does — a unit that lies is
skipped forever, which is worse than being re-driven. And `done.jsonl` is append-only and never
pruned; `records()` re-reads the whole file, which is fine at wave scale and is not a database.

---

## Governed single-shot run

Everything above is how to write the workflow JS. When you instead want to GOVERN a whole run
end-to-end from a single invocation — ground → design/plan gates → fan-out → integrate → reconcile
→ one focused merge-when-green PR → memory sync — this skill vendors a reusable orchestrator
meta-prompt: [`templates/governed-run-orchestrator.md`](templates/governed-run-orchestrator.md).

It is a fill-in **template, not a second engine** — it rides the native Claude Code Workflow tool
and this skill's bus. Use it in four steps:

1. **Fill** — copy the template and replace ONLY its two authoritative slots. `<GOAL>` is the
   durable outcome + named scope + resume-state + exclusions; `<DoD>` is the numbered completion
   AND-gate. Add as many `DOD-NN` rows as the goal needs, each an externally observable state with
   TWO mechanically independent evidence sources. Remove every `[...]` instructional sentinel; keep
   the `<GOAL>`/`<DoD>` tag names and the `DOD-NN` id format.
2. **Freeze** — freeze the filled `<GOAL>`/`<DoD>`, the artifact root, the schemas, and the prompt
   hashes before the first unit launches, and never rewrite them mid-run (fan-out contract §A10).
3. **Launch** — invoke `/workflow` and paste the whole filled prompt as its single raw string
   argument. `/workflow` takes ONE string; do not invent `--goal`/`--dod` flags (see §2,
   args-as-string).
4. **Terminal marker** — the run ends with exactly one mechanically derived
   `SUCCESS:<workflow-id>` (only when every `DOD-NN` passes with both evidence records) OR
   `FAILED:<workflow-id> <reason>` (with every unmet id, preserved artifacts/branches, the exact
   blocker, and one resumable next action). A progress report, a job id, "started in the
   background", or "check status" is NEVER terminal success.

This **complements, and does not duplicate**, the neighbouring orchestration skills: the
cross-vendor architect/editor split, the sandbox ladder, and retry-escalation live in
[`../orchestration-patterns/SKILL.md`](../orchestration-patterns/SKILL.md); the large
parallel-agent-on-Databricks fan-out lives in
[`../codex-databricks-fanout/SKILL.md`](../codex-databricks-fanout/SKILL.md). Author the workflow
JS with §1–§12 above; reach for the template only to govern an entire run.

---

## Lint your workflow

Before saving, run the bundled static linter over your workflow file(s):

```bash
python skills/workflow-authoring/scripts/workflow_lint.py ~/.claude/workflows/my-wf.mjs
python skills/workflow-authoring/scripts/workflow_lint.py ~/.claude/workflows   # or a whole dir
```

It **HARD-FAILS** (non-zero exit) on the determinism-breakers that silently corrupt resume + the
prompt cache, and **WARNS** on the recorded footguns — every check maps to a rule above:

| level | check | rule |
|---|---|---|
| ERROR | `no-date-now` · `no-math-random` · `no-argless-new-date` | 3 — banned non-determinism (`Date.now()` / `Math.random()` / argless `new Date()`) |
| ERROR | `meta-missing` · `meta-not-object` · `meta-not-literal` | 1 + 8 — a pure-literal `export const meta` |
| WARN  | `args-parse-if-string` | 2 — `args.<field>` with no parse-if-string guard |
| WARN  | `agent-schema` | 7 — an `agent()` fan-in with no `schema:` option |
| WARN  | `parallel-filter-boolean` | 5 — a `parallel()` result not passed through `.filter(Boolean)` |

`--strict` also fails on warnings; `--json` emits machine-readable findings with `file:line`.
The linter is a **stdlib-only lexical pass** — it MASKS comment + string/template bodies before
matching, so a banned call quoted in a string never false-fires — plus a recursive-descent
literal parser for `meta`. It is **not** a full JS parser; the honest limits are in the module
docstring (e.g. options passed to `agent()` via a variable read as a false WARN; `Date.now()`
hidden in a nested template interpolation may be missed). Treat ERRORs as blocking, WARNs as
advisory. Tests live beside it (`scripts/test_workflow_lint.py`) and run in CI at 100% branch
coverage.

## Author quick-wins (helper snippets)

Copy-paste patterns that make the checks above pass. These are DOC snippets — the runtime API
(section 1) is unchanged.

**Parse-if-string args (rule 2).** `args` arrives as ONE string. Normalise it once, then read
fields off the parsed value — never off raw `args`:

```js
const input = (() => {
  if (typeof args !== 'string') return args ?? {}      // already an object
  const s = args.trim()
  if (!s) return {}
  try { return JSON.parse(s) } catch { return { raw: s } }  // fall back to the raw string
})()
const topic = input.topic ?? '(none)'   // read off `input`, not `args`
```

**Schema-builder helper (rule 7).** A tiny builder keeps every fan-in schema consistent, with
`additionalProperties: false` and a tight `required[]` (the FLOOR only — an over-broad `required`
makes StructuredOutput reject good work):

```js
const obj = (properties, required = []) => ({
  type: 'object', additionalProperties: false, required, properties,
})
const DIGEST = obj(
  { digest: { type: 'string' }, evidence: { type: 'array', items: { type: 'string' } } },
  ['digest', 'evidence'],   // fields an agent can ALWAYS fill; keep verdict/artifact optional
)
const r = await agent(prompt, { label: 'lens', schema: DIGEST })
```

**`{ envelope: true }` result shape.** For a fan-in that must not lose a partial cohort, return a
typed envelope, not a bare array — it carries the survivors AND what failed, so a null-tolerant
barrier degrades visibly:

```js
const results = (await parallel(thunks)).filter(Boolean)   // rule 5: drop the nulls
return {
  envelope: true,
  ok: results.length,
  total: thunks.length,
  dropped: thunks.length - results.length,   // how many agents died — surfaced, not hidden
  results,
}
```

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
  session cut is not silently redone. **Wiring it is rule 13**; the copy-paste
  template is `templates/resume-wired-fanout.md`.

Both gates ship in **SHADOW mode** (council C5): they surface a verdict + append
one line to a bounded, auto-rotating shadow sink; promotion to an ENFORCE gate
that blocks on a blocking FAIL is a separate, deferred step.

## Quick checklist before saving a workflow

- [ ] lint clean: `python skills/workflow-authoring/scripts/workflow_lint.py <file>` (no ERROR findings)
- [ ] `export const meta` with a stable `name` + `phases`
- [ ] a `schema` (with `additionalProperties: false`) on every `agent()` fan-in
- [ ] `.filter(Boolean)` after every `parallel()`
- [ ] `isolation: 'worktree'` on every file-MUTATING agent; disjoint scopes
- [ ] no `Date.now()` / `Math.random()` / `new Date()` in the workflow JS
- [ ] byte-stable shared prompt prefix; volatile data only in per-agent tails
- [ ] one level of nesting; wide barriers kept small + homogeneous
- [ ] agents auto-discover their input (args arrive as one string)
- [ ] no spawn prompt asserts a tool is blocked without a live probe backing it
- [ ] every contracted output path is `Test-Path`-checked at fan-in before its digest is read
- [ ] cross-vendor units use `agentType: 'codex'`, never a `*-rescue` forwarder
- [ ] briefed facts carry `[probe: …]` + a timestamp + a different-mechanism re-verify rule
- [ ] adversarial reviewers receive siblings' FULL text and their own on-disk artifact contract
- [ ] agents flush a partial artifact on a cadence (a cohort interrupt must degrade, not zero)
