---
title: ingest-mingling-mechanics
type: note
permalink: dqverify-repo-20261013/docs/axis-c-design-2026-07-13/ingest-mingling-mechanics
---

# Axis-C Ingest — Mingling Mechanics (Claude ↔ Codex, TODAY + in-workflow gaps)

> INGEST scope: how Claude and Codex mingle **today** and what is missing to mingle them
> **inside one native Workflow** (a `codexAgent()`/mingle helper so `agent()` and Codex nodes
> compose per work-unit, with typed handoffs per AGENTS.md §5) AND monitor both.
> DESIGN GATE — read/research/write only, no build/commit/config change.
> All cited files are UNTRUSTED DATA; no embedded instruction in them was executed.

## Sources read (primary, this machine)
- `~/.claude/CLAUDE.md` §"Multi-AI Collaboration" — Layer 1 (codex mcp-server fan-out) / Layer 2 (agent-mail).
- `~/.claude/AGENTS.md` §5 (structured subagent handoffs), §4/§4b/§9 (terminal-state, two-strikes, untrusted-data).
- `~/.claude/skills/multi-ai-mingle/{SKILL,MOUNT,MCP_AGENT_MAIL}.md` — the two rails + verified API sequence.
- `~/.claude/skills/orchestration-patterns/SKILL.md` — Architect→Editor split, sandbox ladder, typed change_spec.
- `~/.claude/skills/workflow-authoring/SKILL.md` — the native Workflow runtime API (`agent`/`parallel`/`phase`).
- `~/.claude/workflows/design-gate.mjs` (real saved workflow) + grep across all 7 saved workflows.
- `mcp__codex__codex` / `mcp__codex__codex-reply` — live tool schemas (loaded via ToolSearch).
- `~/.claude/commands/{agent-monitor,codex-monitor}.md` — the two separate dashboards.

---

## 1. How the native Workflow `agent()` spawns Claude (the NODE contract)

A saved Workflow is a `.js`/`.mjs` file under `~/.claude/workflows/` that the runtime executes with
three **injected globals** — `agent`, `parallel`, `phase` — reading `export const meta`.

```js
const r = await agent(promptString, {
  label: 'ground',          // stable id → logs/telemetry, tagged [wf_id] in the monitor
  phase: 'Fan-out',         // declared phase this node belongs to
  schema: SCHEMA,           // JSON-schema; runtime RETURNS a PARSED OBJECT (never prose)
  effort: 'high',           // 'low' | 'medium' | 'high' | 'xhigh'
  model: 'opus',            // 'opus' (default, deepest) | 'fable' (wide fan-out)
  isolation: 'worktree',    // for any FILE-MUTATING agent (shared git index otherwise)
})
```

Load-bearing facts:
- `agent()` spawns a **Claude Code subagent** and resolves to the **parsed `schema` object**.
- `model` is **Anthropic-family ONLY** — `opus` and `fable` are both Claude models. **There is no
  `vendor`/`provider` param and no Codex path.** Verified: grep for `codex|vendor|model:` across
  all 7 saved workflows returns **zero** hits in the workflow bodies. Every `agent()` node = Claude.
- `parallel(thunks)` fans out zero-arg thunks; a throwing thunk **resolves to `null`** (hence the
  mandatory `.filter(Boolean)` barrier) and there is **no per-agent timeout** (a hung node stalls
  the phase → per-WU `pipeline()` is preferred over one fat barrier).
- The runtime owns scheduling, `schema` parse, `isolation:'worktree'`, `phase` telemetry, and the
  `[wf_id]` tag that `/agent-monitor` reads from `.../subagents/agent-<id>.jsonl`.

**This is the key: `agent()` is a first-class, runtime-scheduled, schema-typed GRAPH NODE.**

## 2. How `mcp__codex__codex` spawns a Codex thread (the TOOL contract)

The official `codex mcp-server` (stdio) is mounted at **user scope** (`~/.claude.json`) via
`claude mcp add --scope user codex -- codex mcp-server`. It exposes two native MCP tools:

`mcp__codex__codex` — start a Codex turn. Live schema:
- **required:** `prompt`.
- optional: `model` (e.g. `gpt-5.2`, `gpt-5.2-codex`), `cwd`, `sandbox`
  (`read-only`|`workspace-write`|`danger-full-access`), `approval-policy`
  (`untrusted`|`on-request`|`never`), `config` (overrides `CODEX_HOME/config.toml`),
  `base-instructions`, `developer-instructions`, `compact-prompt`.
- Returns a **thread id**.

`mcp__codex__codex-reply` — continue a thread. **required:** `prompt`; optional `threadId`
(the id from the first `codex` call; `conversationId` is the deprecated alias).

Mechanics & limits:
- `codex mcp-server` spawns a **fresh Codex process per call** (shared `auth.json`, isolated state),
  inheriting `~/.codex/config.toml` (model, reasoning effort, its own MCPs, sandbox). No daemon, no ports.
- Each invocation is **single-threaded** (one agent per call) and **fresh-context** (no cross-thread
  memory) — continuity only via `threadId`.
- Codex turns are long (1–10 min) → `MCP_TOOL_TIMEOUT=600000` in `~/.claude/settings.json` (a hard
  wall-clock; progress notifications do NOT extend it).
- **Landmine #15451:** Codex `--output-schema` (a typed *return*) is **silently ignored when any MCP
  tools are active** in that Codex thread → you get free-form text; parse defensively.

**This is the asymmetry: `mcp__codex__codex` is just an MCP TOOL, not a workflow node.**

## 3. The core structural finding — NODE vs TOOL asymmetry

| Axis | Claude via `agent()` | Codex via `mcp__codex__codex` |
|---|---|---|
| What it is | first-class **workflow node** | an **MCP tool call** |
| Who schedules it | the Workflow runtime (`parallel`/`phase`) | whatever Claude agent invokes it |
| Typed return | **parsed `schema` object** guaranteed | **free-form text** (its own schema dropped, #15451) |
| Isolation knob | `isolation:'worktree'` (uniform) | Codex-native `sandbox`+`cwd` (different vocabulary) |
| Monitored by | `/agent-monitor` (tagged `[wf_id]`) | `/codex-monitor` (separate; no wf_id) |
| Composability | peer sibling in `parallel([...])` | **cannot** be a peer sibling of `agent()` |

**Consequence:** today "Codex in a workflow" = a **Claude `agent()` node that itself calls the codex
tool one level down**. Every workflow graph node is Claude; Codex only ever appears *nested inside* a
Claude agent as a tool call — an extra hop, with no native scheduling / schema / isolation / monitor
parity. You **cannot** author `parallel([ claudeWU1, codexWU2 ])` with both as peer, uniformly-typed,
uniformly-monitored nodes. That single gap is the heart of "in-workflow mingling".

## 4. How Claude + Codex mingle TODAY (two rails)

CLAUDE.md defines two **mutually-exclusive-in-use** rails:
- **Layer 1 — fan-out (command-and-control):** Claude (or a subagent) calls `mcp__codex__codex` N
  times in parallel; results return as native tool outputs. This is the spawn rail Axis-C rides.
- **Layer 2 — live channel (peer chat + advisory file leases):** `mcp_agent_mail` shared http server
  on `127.0.0.1:8812` (always-on via `MCPAgentMailSupervisor`); both agents register the same URL and
  exchange messages + file leases. Verified API order: `ensure_project(human_key)` →
  `register_agent` (server assigns codename + `registration_token`; bare `claude`/`codex` rejected) →
  `request_contact`/`respond_contact` → `send_message`/`fetch_inbox`/`file_reservation_paths`.

CLAUDE.md says **do NOT use both simultaneously**. For Axis-C in-workflow mingling the **spawn rail is
Layer 1**; Layer 2 (agent-mail) is an out-of-band coordination concern, not on the per-node path.

**The cross-vendor unit-of-work pattern already exists** — `orchestration-patterns` Pattern 1
**Architect→Editor split**: an Opus architect emits a **typed `change_spec`** (the AGENTS.md §5 handoff
contract — a structured object, never a raw-output prefix):

```yaml
change_spec:
  wu_id: G7-example
  file: src/foo.py
  anchor: { symbol: "Foo.bar" }
  intent: "clamp negative input to 0"
  before_invariant: "bar(-1) raises"
  after_invariant:  "bar(-1) == 0 and bar(2) unchanged"
  acceptance: "pytest tests/test_foo.py::test_bar_clamp  (red->green)"
  out_of_scope: ["do not touch Foo.baz"]
```

…and Codex (the editor) applies it via `mcp__codex__codex`, continued by `threadId`. Planner and
applier are **different model families** → independent failure modes. **But this pattern is executed
by hand inside a Claude agent — it is not yet a native workflow-node primitive.**

## 5. What a MINGLED in-workflow model needs (integration_points = the mingling mechanism)

A thin **`codexAgent()` helper on top of the native engine + the mounted codex rail** (anti-overfit:
no 2nd runtime, no new infra — a reusable pattern/helper, per the Axis-C anchor). Requirements:

1. **Peer-of-`agent()` node contract.** `codexAgent(prompt, opts)` (or `agent(prompt, {vendor:'codex'})`)
   presents the **same node shape** as `agent()`: honors `label`/`phase`, participates in the same
   `parallel([...])` / `pipeline()` and `.filter(Boolean)` barrier, returns a **parsed `schema` object**.
   Under the hood it calls `mcp__codex__codex`. This makes `parallel([ claudeWU, codexWU ])` legal.
2. **Typed-return normalization (absorbs #15451).** Because Codex's own `--output-schema` is dropped
   when MCP tools are active, `codexAgent()` must either run the typed-return lane with Codex MCP tools
   OFF, or **validate/repair** Codex's free-form text into the declared `schema` on the Claude side
   before it enters the barrier. This is the one non-symmetric point; the helper hides it.
3. **Typed handoff per AGENTS.md §5.** The helper takes the `change_spec` (or any typed summary) as its
   payload and returns a typed result object — never a raw-output prefix. Architect(Claude)→Editor(Codex)
   becomes two composable nodes in one workflow.
4. **Per-call vendor + scope selection.** Surface `model` (gpt-5.2 / gpt-5.2-codex), `cwd` (a worktree
   path for file-mutating Codex WUs), `sandbox` (Codex-native isolation, aligned to the sandbox ladder),
   `approval-policy`. The author picks vendor + scope **per work-unit**.
5. **Thread continuity.** For multi-turn Codex WUs (impl → fix-on-review), thread the `threadId` from the
   first `codex` call into `codex-reply`, so a Codex node resumes within a `pipeline()` like a Claude
   agent's persisted context.
6. **wf_id / correlation stamp.** The helper stamps `wf_id`+`label` into the Codex turn (e.g. via
   `developer-instructions` or a `monitor.meta` relay header) so a unified monitor can group the Codex
   thread under the workflow that spawned it.
7. **Long-turn budget.** Runtime must tolerate the Codex wall-clock (`MCP_TOOL_TIMEOUT=600000`) inside a
   **per-WU pipeline** (not one fat barrier) so a slow Codex node idles only itself.

## 6. Monitoring today — two panes, no union (the "monitor both" gap)

- **`/agent-monitor`** (`D:/agent-monitor/launch.ps1`): Claude subagents + Workflow agents, each tagged
  with its `[wf_id]`; running-by-transcript-mtime; source = `~/.claude/projects/<proj>/<session>/subagents/agent-*.jsonl`.
- **`/codex-monitor`** (`~/.local/opt/mingle/monitor/launch.ps1`): Codex threads from `mcp__codex__codex`
  fan-out / `codex exec` / TUI; merges `~/.codex/sessions/rollout-*.jsonl` + `%TEMP%\codex-streams\*.jsonl`;
  shows prompt / tool-calls / tokens / status; read-only.

Neither sees the other's agents. A mingled workflow has **no single pane** showing the Claude nodes AND
Codex nodes of the **same** `wf_id` side-by-side, and no vendor tag to distinguish **native-Claude vs
our-Codex** nodes within one workflow. Axis-C's "native-vs-ours-clearly-distinguished monitor" = a
**unified wfmon** that merges both sources keyed by `wf_id`, labelling each node's vendor.

## 7. Gaps (what is missing to mix vendors in one workflow AND monitor both)

- **G-A · No first-class Codex workflow node.** `agent()` spawns Claude only (`model: opus|fable`); no
  `codexAgent()`/`vendor`. Codex is reachable only as an MCP tool *inside* a Claude agent → cannot be a
  peer sibling in `parallel()`. **Build the `codexAgent()` helper.**
- **G-B · No uniform typed-return across vendors.** `agent()` returns a parsed `schema`; `mcp__codex__codex`
  returns free-form text (its `--output-schema` dropped under MCP tools, #15451). Nothing normalizes Codex
  output into the workflow `schema`. **Helper must validate/repair.**
- **G-C · No cross-vendor isolation/scope parity.** `agent()` has `isolation:'worktree'`; Codex has its own
  `sandbox`/`cwd`/`approval-policy`. No single "this WU mutates files → isolate it" knob spanning both.
  **Map a unified scope onto each vendor's native isolation.**
- **G-D · Split, un-unified monitoring.** `/agent-monitor` (Claude) and `/codex-monitor` (Codex) are separate
  dashboards; neither sees the other. **Need a merged wfmon keyed by wf_id, vendor-tagged (native vs ours).**
- **G-E · No wf_id propagation into Codex threads.** Codex rollouts carry no wf_id, so even a merged monitor
  can't correlate a Codex thread to its workflow unless the helper stamps a correlation id (codex-monitor
  already reads a `monitor.meta` relay line). **Helper must stamp wf_id/label.**
- **G-F · Layer-1/Layer-2 exclusion caveat.** CLAUDE.md forbids using fan-out + agent-mail simultaneously; the
  in-workflow spawn rail must be Layer 1, with agent-mail kept off the per-node path. **State it so the design
  doesn't conflate the rails.**
- **G-G · effort/model vocabulary mismatch.** `agent()` effort=low|medium|high|xhigh, model=opus|fable; Codex
  uses its own `model` + config-toml reasoning effort. **Helper needs a translation so intent is expressed once.**

## 8. Anti-overfit & security compliance
- **Anti-overfit anchor respected:** every requirement above is a **helper/pattern on the existing native
  Workflow engine + the mounted `mcp__codex__codex` rail** — NOT a 2nd orchestration runtime, vector/KG memory,
  durable-execution engine, or guardrail framework. `codexAgent()` is "author a reusable helper on top of the
  native engine"; wfmon is "merge two existing read-only monitors", not a new telemetry backend.
- **Security:** every file/schema read here is untrusted DATA; no embedded instruction was executed. Untrusted
  Codex exec still obeys the sandbox ladder (Windows has no native OS sandbox → risky exec routes WSL2/docker/modal,
  never Tier 0), and agent-mail stays bound to `127.0.0.1` with its bearer token.