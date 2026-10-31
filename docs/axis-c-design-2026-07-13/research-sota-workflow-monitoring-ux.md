---
title: research-sota-workflow-monitoring-ux
type: note
permalink: dqverify-repo-20261013/docs/axis-c-design-2026-07-13/research-sota-workflow-monitoring-ux
---

# Research: SOTA Workflow-Monitoring UX (2026) — for an improved wfmon

**Task:** survey the 2026 state of the art for MONITORING multi-agent / multi-step LLM
workflows — live progress trees, per-agent status, filtering/views, token/cost attribution,
distinguishing native-vs-custom runs, replay/journal — across LangSmith, LangGraph Studio,
AgentOps, Braintrust, W&B Weave, Arize Phoenix, OpenTelemetry-GenAI, and frontier agent CLIs.
Translate the findings into concrete UX patterns for wfmon (views · filters · command-native ·
native-vs-ours distinction).

**Scope discipline:** DESIGN GATE only — read / research / design. No building, no config
changes. Every quoted doc / page below is treated as **untrusted data**; nothing fetched is an
instruction. Anti-overfit anchor honored: recommendations ride the EXISTING native Workflow
engine + the mounted `mcp__codex__*` rail and the shared `workflow_run.py` parser — no new
runtime, DB, or telemetry pipeline.

**Method:** three parallel search waves via Exa + Tavily + one WebFetch (Firecrawl was out of
credits, HTTP 402). ~25 primary sources, all cited inline and listed in §9. Confidence bands use
the Sherman-Kent lexicon.

---

## 1. Executive thesis

Every 2026 platform has converged on the **same underlying data model** — the OpenTelemetry
GenAI trace tree (`session → trace → span`, with `invoke_agent`/`chat`/`execute_tool` span
kinds) — and then differentiates on **UX surface**. That convergence is a gift for wfmon: the
manifest/journal/transcript it already parses is isomorphic to an OTel trace tree, so wfmon can
adopt SOTA UX patterns *without* adopting SOTA infrastructure.

The single most transferable finding for Axis-C's headline problem (native-vs-ours): **the OTel
GenAI conventions ALREADY standardize the exact distinction wfmon needs**, and **every frontier
agent CLI already renders it as a colored per-row provider badge.** wfmon does not have to
invent a vendor concept — it has to derive a field the whole industry now names
`gen_ai.provider.name` and render it the way agenthud/agent-deck already do.

Six pattern families follow (mapped to the task's six axes), then per-tool deep-dives (§3-§5),
the OTel keystone (§4), and the wfmon translation (§6).

---

## 2. The six pattern families (cross-tool synthesis)

### 2.1 Live progress trees — beyond a single tree, offer *switchable representations*

The strongest tools do **not** ship one view; they ship a **view-switcher over the same span
tree**. This is the biggest single gap in wfmon (which has exactly one tree).

- **W&B Weave** offers three toggle-able representations of one trace: **code-composition**
  (nested boxes = call logic), **flame-graph** (timeline of depth × duration = performance), and
  **graph** (parent/child structure). Plus four **scrubbers** — Timeline, Peers (same op type,
  jump to next `predict`), Siblings (same parent), Stack (up/down the call stack) — for
  keyboard-fast traversal of large trees. [wandb-tracetree]
- **AgentOps** ships **Timeline + Tree + Details + Analytics** as four lenses on one session, with
  the **Session Waterfall** (time viz left, event details right) as its hero. [agentops-spans,
  agentops-intro]
- **Braintrust** toggles **row-type = Traces vs Spans** (roll-up vs raw ops) and **Timeline vs
  Thread** view; the trace viewer opens as a right-hand panel, expandable to fullscreen.
  [braintrust-viewlogs, braintrust-examine]
- **Weave's waterfall** encodes two facts wfmon's tree cannot: **the longest bar = latency
  dominator**, and **overlapping bars = genuine parallelism** (concurrent vs sequential agents).
  [wandb-agents]
- **Phoenix/Arize** render the tree with **latency, token counts, and estimated cost inline on
  every span**, root at top, children by `parent_id`. [phoenix-openinference]

**Takeaway for wfmon:** keep the `run → phase → agent` tree as the default, but add (a) a
**waterfall/timeline** view (wfmon already has `startedAt`/`durationMs`/`lastProgressAt` — enough
to draw bars and show parallelism/stalls visually) and (b) **sibling/peer jump** keybinds for
fast traversal at fleet scale. Confidence this is high-value: **HIGH** (5/6 tools do it).

### 2.2 Per-agent status — a richer state machine + attention-first sort (wfmon already leads here)

wfmon's glyph set (`◔`running `✓`done `✗`error `·`idle) and triage sort (error → stall → retry →
running → idle → done) are **already SOTA-aligned** — the frontier CLIs do exactly this:

- **agent-deck**: `●`running(green) `◐`waiting(yellow) `○`idle(gray) `✕`error(red) — near-identical
  to wfmon. [agentdeck]
- **agent-view** sorts "most attention-needing states first (Crashed, Waiting, Draft, Paused)" so
  "anything [needing] your eyes floats to the top" — wfmon's triage exactly. It also has a
  **richer state vocabulary** worth stealing: `Draft` (typed but unsent), `Paused` (blocked on
  approval), **`Compacting`** (freeing token budget), `Monitoring`, `Crashed` vs `Error`,
  `Stopped`. [agentview]
- **Claude Code's native `claude agents`** groups by state — **`Ready for review` / `Needs input`
  above `Working` / `Completed`** — and folds overflow completed rows into a `… N more` sentinel
  (wfmon's "+N more (triaged)" is the same idea). [cc-agentview]
- **agenthud** distinguishes **live** states (`[working]` = pending tool call at the tail;
  `[waiting]` = turn yielded to you) from **recency** states (`[hot]/[warm]/[cool]/[cold]`) and
  lets live override recency. wfmon has stall detection but no "waiting-on-you" state. [agenthud]

**Takeaway:** wfmon's status model is competitive; the cheap wins are (a) a **"blocked/needs-input"
state** distinct from idle, and (b) surfacing a per-agent **one-line self-report** instead of a raw
last-tool name (Claude Code moved to this in v2.1.205: "row summaries show the session's own
one-line report … instead of a raw tool invocation"). [cc-agentview] Confidence: **MEDIUM-HIGH**.

### 2.3 Filtering / views — the biggest UX gap; SOTA is *facets + saved views + a query language*

wfmon has two filter axes (fuzzy text + 4 status chips). Every observability platform has an
order of magnitude more, built on three reusable primitives:

- **A filter bar + a "filter shortcuts" panel** auto-populated from the most frequent attributes
  in the data (LangSmith), so common facets are one click. [langsmith-filter]
- **Saved / named views** that persist filter + columns + sort + time-range, shared per project,
  with built-ins you can fork: Arize ships **"Arize Default"** and **"Recent Errors (15m)"**
  (pre-filtered `status_code = ERROR`); Braintrust ships **Default / Non-errors / Errors /
  Unreviewed / Assigned-to-me**. [arize-explore, braintrust-viewlogs]
- **A copyable query language** for power users and programmatic reuse — LangSmith's
  `and(eq(is_root,true), eq(feedback_score,1))`; Braintrust's **BTQL** (`Name LIKE 'POST%'`);
  Arize's `"attributes.openinference.span.kind" = 'LLM' AND "status_code" = 'ERROR'`.
  [langsmith-filter, braintrust-otel, arize-explore]
- **Structural (tree/root/multi-span) filters** — the standout advanced capability. LangSmith:
  filter runs *whose root run* has an attribute, or *whose subtree contains* a span named `Foo`.
  Arize goes further: up to **5 span queries combined with `AND/OR/NOT`, `->` (temporal), `=>`
  (parent-child)** — e.g. "traces where an LLM call follows a retrieval," "errors but no tool
  calls." [langsmith-filter, arize-explore]
- **Column customization** grouped by category (span cols / evals / annotations), toggled per
  view. [arize-explore]
- **Natural-language filter authoring** — Arize's Alyx (`Cmd/Ctrl+L`, "Find tool spans from user X
  in the last hour") generates the filter for you. [arize-explore]
- **Frontier-CLI keystroke facets** — agent-deck: `!`running `@`waiting `#`idle `$`error;
  agenthud/`agent-view` scope-to-cwd; the pattern is *single-key status toggles* (wfmon has chips;
  a keybind per chip is trivially additive). [agentdeck, agenthud]

**Takeaway:** this is where wfmon should invest most. The additive, anti-overfit ladder: (1) more
chips/facets computed from data it already has — **vendor, model (`opus` vs `fable`), phase,
session/project, has-error, stalled, retrying, token-threshold**; (2) **saved views** (persist the
chip+text+sort config to a dotfile) with built-ins ("Recent errors", "Cross-vendor only",
"Stalled"); (3) a tiny **filter DSL** the export CLI can also accept (`vendor:codex AND
state:stalled`), mirroring LangSmith's copyable-filter idea. Confidence high-value: **HIGH**.

### 2.4 Token / cost attribution — rollup up the tree + a model-pricing table + cache/reasoning splits

The universal pattern is **per-span cost that aggregates up every parent to the trace/thread
level**, plus a **project dashboard** for trends:

- **LangSmith** shows cost three ways — **in the trace tree** (total for the trace, aggregated per
  parent, broken down per child), **in project stats**, and **in dashboards** (prebuilt: total
  cost + input/output token breakdown; custom: group-by tag/metadata/run-type). Cost is derived
  from **token counts × a model-pricing table** (OpenAI/Anthropic/Gemini priced by default,
  editable), or sent directly as `usage_metadata.total_cost` for non-LLM runs. Critically: **child
  runs must carry `thread_id` or their tokens/cost are excluded from thread rollups.**
  [langsmith-cost, langsmith-threads, langsmith-dash]
- **W&B Weave** auto-tracks cost for supported providers, shows it in the trace tree and calls
  table, and exposes it under `call.summary["weave"]["costs"]`; custom pricing via
  `add_cost(llm_id, prompt_token_cost, completion_token_cost, effective_date)`. Its **Agents view**
  summary cards report Spans / Conversations / **Tokens / Cost / Error-rate / Agents** for the
  window, with time-series and a **"top tools / agents / models / providers by usage"** breakdown.
  [wandb-costs, wandb-agents]
- **Cache + reasoning token splits are now first-class** (2026): Weave surfaces **Cache read /
  Cache written / Cache hit-rate / Reasoning tokens / Reasoning ratio**; Braintrust captures
  **prompt / cached / completion / reasoning tokens** and a **"Cached tokens view"** that filters
  to LLM spans and scales bars by cached-read tokens. [wandb-agents, braintrust-best,
  braintrust-examine]
- **Frontier CLIs** put cost in the TUI directly: agent-deck's **`$` cost dashboard**
  (today/week/month, top sessions, model breakdown, 14 models priced with daily refresh, budget
  limits with 80% warn / 100% hard-stop); agent-dashboard's **per-agent token/cost + live
  rate-limit bars**; agent-view's **account-level rate-limit bars** (green<50% / yellow / red≥80%).
  [agentdeck, agentdashboard, agentview]

**Takeaway:** wfmon already sums `totalTokens`. The additive wins: (a) a **cost estimate** via a
small static model→price map (the manifest carries `model` + `tokens`); (b) a **per-run and
per-vendor token/cost rollup** in the rollup bar (already computed, just split by the new vendor
field); (c) a **"top models / vendors by tokens"** mini-breakdown, cheap since it's a group-by on
parsed data. Confidence: **MEDIUM-HIGH** (cost precision is limited without per-token cache/reason
splits in the manifest — flag as best-effort).

### 2.5 Native-vs-custom distinction — THE keystone, and it is already a solved problem upstream

This is Axis-C's headline deliverable, and the research is unambiguous: **the distinction wfmon
needs is now an industry standard.**

- **OTel GenAI (v1.41, 2026)** encodes it four ways simultaneously [greptime-otel, otel-blog,
  webfetch]:
  1. **`gen_ai.provider.name`** — the vendor field: `openai`, `anthropic`, `aws.bedrock`,
     `azure.ai.inference`. "Determines which provider-specific attributes apply." This is the
     canonical name for wfmon's `vendor(agent)`.
  2. **`invoke_agent` span-kind split: `CLIENT` vs `INTERNAL`** — v1.41 *explicitly* splits
     "`CLIENT` for remote calls" from "`INTERNAL` for local framework execution (e.g. LangGraph
     running agent logic in-process)." **This is precisely native-vs-ours:** a Claude subagent
     running in-process = INTERNAL/native; a Codex thread invoked over the `mcp__codex__*` rail =
     a remote/CLIENT call.
  3. **`invoke_workflow`** (new in v1.41) vs **`invoke_agent`** — "workflows follow predetermined
     paths; agents reason autonomously." Maps to distinguishing a **deterministic gate workflow**
     (plan-gate/design-gate) from an **autonomous fan-out**.
  4. **MCP semantic conventions (v1.39)** — a cross-vendor call over MCP emits a `CLIENT` span with
     `gen_ai.operation.name = execute_tool`, `mcp.method.name = tools/call`, `mcp.session.id`,
     `gen_ai.tool.name`, `mcp.protocol.version`. **wfmon's `mcp__codex__*` detection is literally
     the MCP-span signal the standard prescribes.**
- **The frontier CLIs already render provider as a first-class badge** — this is the proof the UX
  works: agenthud tags **each row with a "colored provider label (`claude`/`codex`/`kiro`/
  `opencode`)"** plus model + context gauge, and **merges multiple agents' sessions into one
  tree** (sub-agents nest under their parent "regardless of which agent spawned them").
  agent-dashboard, agent-deck, agent-view, seshions are all explicitly **multi-backend** (Claude
  Code + Codex + Gemini + OpenCode) with per-row provider identity. [agenthud, agentdashboard,
  agentdeck, agentview, seshions]
- **Observability platforms filter by provider/model/framework as a routine facet** — Weave's
  "top … providers by usage" breakdown and per-span `Provider` field; Telerik/Progress lists
  "filter … by app, environment, release, customer, **model, workflow**, status, tags, or
  metadata"; OTel's `gen_ai.system`/`gen_ai.provider.name` is "LLM vendor." [wandb-agents,
  telerik, kong-otel]

**Takeaway (design, not build):** wfmon should compute a pure **`vendor(agent) ∈ {claude, codex,
mixed}`** in the shared `workflow_run.py`, deriving it (cheap→authoritative) from **(a) label
convention → (b) `mcp__codex__*` in `lastToolName`/timeline → (c) `model` tiebreak**, then roll up
per run to **`native` / `cross-vendor` / `codex-only`** — exactly mirroring OTel's
provider.name + CLIENT/INTERNAL semantics and the CLIs' colored badge. Render it as a **vendor
glyph/badge on every agent & run line**, a **vendor filter chip row**, and a **vendor column in
the board + rollup + export DAG legend**. This is the direct answer to "CLEARLY distinguish native
ultracode from our cross-vendor runs." Additionally, distinguish **workflow-kind** (gate vs
fan-out vs execution) the way OTel distinguishes `invoke_workflow` vs `invoke_agent`. Confidence
the signals exist and the UX is proven: **HIGH**.

### 2.6 Replay / journal — time-travel over checkpoints, session-replay, and a machine-readable follow-feed

Three distinct "replay" idioms, all relevant to wfmon's read-only journal:

- **State time-travel (LangGraph Studio)** — the richest. Every node execution writes a
  **checkpoint**; the timeline (step #, node, timestamp, state-indicator) sits **alongside the
  animated graph**; controls are **Step Forward / Backward / Jump-to-step / Reset-to-latest**;
  each step shows the **full state object + a color-coded delta (green added / red removed / yellow
  modified)**; and you can **Fork from any checkpoint** (optionally editing state) to replay a
  branch, or set `interrupt_before` as a **human-in-the-loop breakpoint**. [langgraph-timetravel,
  langgraph-viz, markaicode]
- **Session replay + run-history (frontier CLIs)** — agent-view records **run history with
  archived logs**, re-attaches to past runs (`r`) or promotes them to full sessions (`P`);
  agenthud's **`follow`** emits a "chronologically-merged stream of every event … as human lines
  or `--json` NDJSON — the read-only substrate a higher-level supervisor can consume";
  `claude agents --json` exports per-session `state ∈ {working, blocked, done, failed, stopped}`
  (+ `waitingFor`). [agentview, agenthud, cc-agentview]
- **Trace comparison / diff (Weave)** — select N traces → **side-by-side or unified diff** of
  code/prompts/tokens/cost/latency, with a **baseline** ("known-good run") and numeric diff as
  int/%/multiplier. This is "replay" as *cross-run comparison*, invaluable for regression triage.
  [wandb-compare]

**Takeaway:** wfmon's `journal.jsonl` + transcripts already ARE a replay substrate; it just doesn't
expose replay UX. Additive wins: (a) a **journal scrubber** — step through an agent's
`TimelineEvent`s (thinking/text/tool_use/tool_result) as discrete steps (wfmon already parses
these); (b) a **`wfmon follow [--json]`** NDJSON event stream (agenthud's substrate pattern — a
supervisor or the codex-monitor can consume it); (c) **export-time run comparison** (diff two runs'
DAGs/token/vendor rollups) as a natural extension of the existing export model. Confidence:
**MEDIUM** (time-travel-with-state-edit is out of scope for a read-only monitor; the journal
scrubber + follow-feed are the realistic, high-value subset).

---

## 3. Per-tool deep-dives (the standout contribution of each)

**LangSmith** — *filtering + threads + cost-rollup reference implementation.* Data model:
`project → trace → run(span)`, linked into `thread`s by `session_id`/`thread_id`; `tags` +
`metadata` are the filter/group primitives. Threads side-panel has **three views with keyboard
shortcuts — Messages (`M`, conversation layer), Turns (`T`, per-turn cards), Details (`D`,
debug layer)** — and preserves collapsed/expanded state across the M/D switch. Filtering is the
gold standard: filter bar + auto-populated shortcuts panel + full-text (indexes ≤250 chars) +
key-value (≤100 keys/run) + **advanced root/tree filters** + **saved views** + a **copyable query
language**. Dashboards: prebuilt (traces/LLM-calls/cost&tokens/**run-types** = high-level execution
path) + custom (group-by tag/metadata/run-name/run-type, top-5 by frequency). [langsmith-*]

**LangGraph Studio** — *time-travel + live graph animation reference.* Local agent IDE: renders
the graph as a node-edge diagram, **nodes light up with execution-status indicators as they run**,
click a node → State Inspector with **color-coded state diff**; **fork from any checkpoint**;
`interrupt_before` = breakpoint; hot-reload re-runs a node after a prompt edit. Explicitly a *local
dev tool* (localhost); pairs with LangSmith for hosted/fleet-scale filtering. [langgraph-*,
markaicode]

**AgentOps** — *waterfall + OTel span-kind taxonomy.* Built on OpenTelemetry. Span kinds:
**SESSION → AGENT → WORKFLOW → OPERATION/TASK → LLM / TOOL** (a clean hierarchy wfmon's
run→phase→agent already approximates). Hero = **Session Waterfall** (time viz + detail panel);
plus Timeline / Tree / Message / Analytics views and a **Session Overview** meta-analysis across
all sessions. LLM spans carry **Model / Provider / Prompt-tokens / Completion-tokens / Cost /
Messages**; `tags` for dashboard filtering. [agentops-*]

**W&B Weave** — *multi-representation trace tree + agents view + comparison.* Trace tree with
**code-composition / flame-graph / graph** toggle and Timeline/Peers/Siblings/Stack/Path scrubbers.
**Agents view** models `agent → conversation → turn → LLM-call → tool-call` (OTel
`invoke_agent`/`chat`/`execute_tool`, sub-agent = nested `invoke_agent`); **Spans tab** exposes raw
ops with **Kind / Operation / Finish-reason / Error-type** columns and **trace-grouping** (click a
row → highlight all same-`trace_id` spans; "a single conversation may contain multiple traces if it
involved sub-agent delegation" — directly relevant to cross-vendor sub-threads). Cost + cache +
reasoning tokens first-class; **Comparison** diffs N traces against a baseline. [wandb-*]

**Arize AX / Phoenix** — *filtering DSL + saved views + sessions.* Tabs: **Traces / Sessions /
Spans** (three lenses — per-request tree, per-conversation thread by `session.id`, cross-cutting
op view). Filter bar with operators (`=,!=,<,>,IN,contains`, null-checks, `AND/OR`), **multi-span
queries (≤5, combined with `AND/OR/NOT/->/=>`)**, **AI Search** (NL→filter via `Cmd+L`), **Saved
Views** (filter+columns+sort+time persisted; built-in "Recent Errors (15m)"), **column groups**,
**time-selector presets**, **source-mapping** (tell the tool which attribute = Input/Output so
filters read `input contains 'refund'`). Token counts computed per-span (`llm.token_count.*`),
aggregated to trace; sort by tokens to find expensive requests. Open standard = **OpenInference**
span kinds (LLM/chain/agent/tool) driving the span icon + detail view. [arize-explore,
phoenix-*]

**Braintrust** — *unified logs/experiments + BTQL + Topics facets.* Logs table = one trace/row;
**Display → Row-type: Traces vs Spans**; **group-trace-by tag/metadata**; **Timeline vs Thread**
view; span hierarchy with expand/collapse; **Cached-tokens view** (LLM-only, bars scaled by
cache-read). Filtering = **BTQL** (`Name LIKE 'POST%'`), alerts on BTQL thresholds → Slack/PagerDuty.
Built-in views (Default/Errors/Non-errors/Unreviewed/Assigned-to-me). **Topics** auto-cluster logs
into named facets (intents/sentiment/issues) without manual review. CLI: `bt view logs`, `bt sync
pull`. [braintrust-*]

---

## 4. The OTel-GenAI standard (the shared data model + the native-vs-ours keystone)

OTel's GenAI SIG (since Apr-2024) is the vendor-neutral schema every tool above converges on.
As of 2026 it covers **LLM-client spans, agent spans, events (prompt/completion content), and
metrics**. [zylos, morphllm, uptrace, sitepoint]

**Span operations (the tree wfmon should speak in):** `create_agent` (CLIENT) · `invoke_agent`
(CLIENT=remote / **INTERNAL=local**) · **`invoke_workflow`** (deterministic, v1.41) · `chat` (LLM
call) · `execute_tool` (INTERNAL; v1.41 requires tool-name in span name) · `embeddings` ·
`generate_content`. A canonical trace: `invoke_agent(research-agent) → chat(anthropic) →
execute_tool(web_search) → chat(anthropic) → execute_tool(write_file) → chat(anthropic, synthesis)`.
[greptime-otel, otel-blog, morphllm]

**Core attributes (the fields wfmon should derive/emit-shaped):** `gen_ai.provider.name`
(vendor) · `gen_ai.request.model` · `gen_ai.operation.name` · `gen_ai.usage.input_tokens` /
`output_tokens` · `gen_ai.usage.reasoning.output_tokens` (v1.41) · `gen_ai.usage.cache_read.
input_tokens` / `cache_creation.input_tokens` (v1.40) · `gen_ai.response.finish_reasons` ·
`gen_ai.agent.name` · `gen_ai.conversation.id`. MCP spans add `mcp.session.id`, `mcp.method.name`,
`gen_ai.tool.name`, `mcp.protocol.version`. [greptime-otel, kong-otel, sitepoint, webfetch]

**Evolution timeline (why 2026 is the inflection):** v1.37 `gen_ai.system`→`gen_ai.provider.name`
· v1.38 evaluation event + tool-definition details + `invoke_agent` guidance · **v1.39 MCP
conventions** · v1.40 retrieval span + cache-token attrs + Anthropic input-token guide · **v1.41
`execute_tool` requires tool-name + reasoning tokens + `invoke_workflow` + split `invoke_agent`
into CLIENT/INTERNAL**. Two RFCs are actively extending it to full multi-agent
teams/tasks/handoffs (`gen_ai.team.*`, `gen_ai.task.*`, `gen_ai.workflow.*`, `gen_ai.session.*`).
[greptime-otel, rfc-3460, rfc-35]

**Privacy note (matches wfmon's redaction discipline):** the spec warns prompt/tool payloads are
large + sensitive → content capture is **opt-in, redact/truncate by default**. wfmon's fail-closed
export redaction is already aligned with this. [sitepoint, cohorte]

**Why this is the keystone:** wfmon does not need to *emit* OTel — but adopting its *vocabulary*
(provider.name, INTERNAL-vs-CLIENT, invoke_workflow-vs-invoke_agent, MCP-span = cross-vendor)
gives Axis-C a principled, standards-backed basis for the native-vs-ours field, and makes any
future bridge to a real OTel backend (Phoenix/Weave/LangSmith) a rename, not a rewrite.
Confidence: **HIGH**.

---

## 5. Frontier agent CLIs — the direct wfmon analogues (closest prior art)

These matter most because they solve *wfmon's exact problem* (a terminal-native, read-only,
multi-agent, multi-vendor monitor over on-disk session files) and are 2026-current:

| Tool | What it proves for wfmon |
|---|---|
| **agenthud** (neochoon) | Reads each agent's on-disk JSONL/SQLite, **merges into ONE tree**; **colored provider label per row** (claude/codex/kiro/opencode) + model + context gauge; **live `[working]`/`[waiting]` states override recency `[hot/warm/cool/cold]`**; **`follow --json` NDJSON** machine feed; `report`→`summary` LLM digest. [agenthud] |
| **agent-dashboard** (bjornjee) | tmux-native control plane via `capture-pane`; **state groups** (blocked/waiting/running/review/PR/merged); **subagent tree**; **per-agent token/cost + live rate-limit bars**; multi-backend (Claude+Codex) with per-spawn model/effort. [agentdashboard] |
| **agent-deck** (asheshgoplani) | **Status symbols** `●◐○✕`; **single-key status filters** `!@#$`; **`$` cost dashboard** (14 models priced, daily refresh, budget 80%-warn/100%-hard-stop); **conductor** = a supervisor session that monitors others and escalates. [agentdeck] |
| **agent-view** (doyled-it) | Richest **state vocabulary** (Draft/Paused/Compacting/Monitoring/Crashed/Stopped); **attention-first sort**; **activity feed** (`a`); **run-history replay** (`r`/`P`); account rate-limit bars. [agentview] |
| **seshions** (danhergir) | **Blueprints** = reusable role-based multi-agent spawn; command-palette (`/`) dispatch/broadcast; explicitly a **Claude+Codex mixed-agent** dashboard. [seshions] |
| **Claude Code native `claude agents`** (v2.1.x) | The UX bar to match: **state groups** (Ready-for-review / Needs-input / Working / Completed) · **peek panel** (`Space`, full status sentence + the exact question a waiting session asks) · **attach** (`Enter`) · **PR labels** (`#1234`) · **tab-title awaiting-input count** · **`claude agents --json`** (`state ∈ working/blocked/done/failed/stopped`, `waitingFor`) · **one-line self-report row summaries** (v2.1.205). [cc-agentview] |

**Two structural lessons:** (1) **provider identity is always a rendered per-row badge** — never
hidden; this is the empirical proof that wfmon's proposed vendor glyph is the right call. (2) The
CLIs increasingly ship a **`--json` / `follow` machine layer** beside the TUI so a *supervisor/
conductor* can consume the monitor — matching wfmon's plaintext `board` and suggesting a
`wfmon follow --json`. Confidence: **HIGH**.

---

## 6. Translation to wfmon — concrete, anti-overfit, ride-the-native-engine

Mapped to the four Axis-C monitor axes (views · filters · command-native · native-vs-ours), each
riding the EXISTING manifest read + shared `workflow_run.py` parser (no new runtime/DB):

**A. Native-vs-ours (headline).** Derive a pure `vendor(agent) ∈ {claude,codex,mixed}` +
`vendor_rollup(run) ∈ {native,cross-vendor,codex-only}` in `workflow_run.py` from **label-convention
∪ `mcp__codex__*` tool-scan ∪ `model` tiebreak** (the OTel `provider.name` + MCP-span + CLIENT/
INTERNAL semantics, §2.5/§4). Render as a **colored vendor badge on every agent & run line**
(agenthud/agent-deck pattern), a **vendor filter chip row**, a **vendor column in board + rollup +
export DAG legend**. Also derive a **run-kind** (gate-workflow vs fan-out vs execution) mirroring
OTel `invoke_workflow` vs `invoke_agent`. *One parser → TUI + export + recall-workflow-agent all
agree.* **[HIGH value, LOW cost, LOW risk — all signals already parsed.]**

**B. Views.** Add a **waterfall/timeline** representation over the existing tree (bars from
`startedAt`/`durationMs`; overlapping = parallelism; long/idle = latency/stall — Weave/AgentOps
pattern) and **sibling/peer jump** keybinds. Add a **journal scrubber** stepping through an agent's
already-parsed `TimelineEvent`s (LangGraph-style step-through, read-only, no state-edit).
**[HIGH value, MEDIUM cost.]**

**C. Filters + saved views.** Expand the two axes to a facet set computed from existing data —
**vendor · model · phase · session/project · has-error · stalled · retrying · token-threshold** —
with **single-key toggles** (agent-deck `!@#$`). Add **saved views** (persist chip+text+sort to a
dotfile) with built-ins **"Recent errors" / "Cross-vendor only" / "Stalled" / "Fable fan-out"**
(Arize/Braintrust pattern). Add a tiny **filter DSL** (`vendor:codex AND state:stalled`) the export
CLI also accepts (LangSmith copyable-filter pattern). **[HIGH value, MEDIUM cost.]**

**D. Token/cost.** Add a **cost estimate** via a small static `model→price` map (manifest has
`model`+`tokens`); **split the rollup bar by vendor** and add a **"top models/vendors by tokens"**
mini-breakdown (group-by on parsed data). Best-effort only (no cache/reason splits in the
manifest — flag honestly). **[MEDIUM value, LOW cost.]**

**E. Command-native + machine layer.** A **`/wfmon`** (or `/workflows monitor`) in-session entry
that opens the cockpit, and **align the status vocabulary to native `/workflows` + `claude agents`**
(state groups: Needs-input / Working / Completed) so native and ours are "monitored uniformly."
Add **`wfmon follow [--json]`** — an NDJSON event stream (agenthud `follow` pattern) the
codex-monitor or a conductor can consume, and cross-link a Codex lane's `mcp__codex__codex`
tool_use to `/codex-monitor`. *(Confirm "command-native" meaning with owner — inferred, §4 of the
ingest doc.)* **[HIGH value for the "uniform monitoring" anchor, MEDIUM cost, MEDIUM confidence on
exact intent.]**

**Non-goals (anti-overfit guardrails):** do NOT build state-editing time-travel (read-only
monitor), a vector-DB, an OTel collector/pipeline, or a second runtime. Adopt OTel *vocabulary*,
not OTel *infrastructure*. Every item above is a pure function of data wfmon already parses.

---

## 7. Ranked "top techniques" for the grill (highest yield first)

1. **Vendor badge + vendor chip + vendor rollup** from label ∪ `mcp__codex__*` ∪ model — the
   headline native-vs-ours deliverable, standards-backed (OTel `provider.name`) and CLI-proven.
2. **Saved views + expanded facet chips + a copyable filter DSL** — closes wfmon's biggest gap
   (2 axes → N), all from existing data.
3. **Waterfall/timeline view** beside the tree — reveals parallelism, latency dominators, stalls.
4. **`wfmon follow --json` machine layer** + `/wfmon` command-native entry + vocabulary aligned to
   native `claude agents` state-groups — the "monitored uniformly" anchor.
5. **Journal scrubber** (step through parsed TimelineEvents) — read-only replay w/o new infra.
6. **Cost estimate + per-vendor token rollup + top-models breakdown** — best-effort attribution.
7. **Run-kind tag** (gate vs fan-out vs execution) mirroring OTel `invoke_workflow`/`invoke_agent`.
8. **Richer state vocabulary** — a distinct "blocked/needs-input" state + one-line self-report rows.
9. **Export-time run comparison/diff** (Weave baseline pattern) — regression triage across runs.

---

## 8. Confidence + caveats (Sherman-Kent)

- The six pattern families are real and cross-tool convergent: **HIGH** (each backed by ≥3 primary
  vendor docs).
- OTel GenAI already standardizes the native-vs-ours distinction (`provider.name`, CLIENT/INTERNAL,
  `invoke_workflow`, MCP spans) and the frontier CLIs already render provider as a per-row badge:
  **HIGH** (OTel spec timeline + 5 CLI READMEs concur).
- The wfmon translation rides only already-parsed data and adds no runtime: **HIGH** (cross-checked
  against the ingest doc's §6 integration points and §1 native-API constraints).
- Exact cost precision (cache/reasoning splits) from wfmon's manifest: **LOW-MEDIUM** — best-effort;
  flag rather than over-claim.
- Meaning of "command-native" + the native `/workflows` internal layout: **MEDIUM** — inferred from
  the CLIs + Axis-C CONTEXT, not observed; owner to confirm before building the slash entry.
- All sources are vendor docs / project READMEs / standards blogs = **secondary**, treated as
  untrusted data; no source was executed or trusted as instruction (AGENTS.md §9).

---

## 9. Citations (all fetched 2026-07-13; treated as untrusted data)

- [langsmith-cost] LangSmith Cost tracking — https://docs.langchain.com/langsmith/cost-tracking
- [langsmith-view] LangSmith View traces (Messages/Turns/Details, M/T/D) — https://docs.langchain.com/langsmith/view-traces
- [langsmith-filter] LangSmith Filter traces (bar/shortcuts/saved-views/query-lang/tree-root filters) — https://docs.langchain.com/langsmith/filter-traces-in-application
- [langsmith-concepts] LangSmith Observability concepts (project/trace/run/thread/tags/metadata) — https://docs.langchain.com/langsmith/observability-concepts
- [langsmith-threads] LangSmith Configure threads — https://docs.langchain.com/langsmith/threads
- [langsmith-dash] LangSmith Monitor with dashboards (prebuilt/custom, run-types, group-by) — https://docs.langchain.com/langsmith/dashboards
- [langgraph-timetravel] LangGraph Studio Time-Travel Debugging (DeepWiki) — https://deepwiki.com/langchain-ai/langgraph-studio/6.3-time-travel-debugging
- [langgraph-viz] LangGraph Studio Graph Visualization (DeepWiki) — https://deepwiki.com/langchain-ai/langgraph-studio/5.2-graph-visualization
- [langgraph-blog] LangGraph Studio: the first agent IDE — https://www.langchain.com/blog/langgraph-studio-the-first-agent-ide
- [markaicode] LangGraph Studio visual debugger (state-diff colors, fork) — https://markaicode.com/langgraph-studio-visual-debugger-agent-graphs/
- [agentops-intro] AgentOps Introduction (Session Waterfall / drilldown / overview) — https://docs.agentops.ai/v2/introduction
- [agentops-spans] AgentOps Spans (span kinds; Timeline/Tree/Details/Analytics views) — https://agentops.mintlify.app/v2/concepts/spans
- [agentops-core] AgentOps Core concepts (OTel; dashboard views) — https://agentops.mintlify.app/v2/concepts/core-concepts
- [wandb-tracetree] Weave Navigate the Trace view (code-comp/flame/graph; scrubbers) — https://docs.wandb.ai/weave/guides/tracking/trace-tree
- [wandb-agents] Weave View agent activity (summary cards, waterfall, Spans tab, cache/reasoning) — https://docs.wandb.ai/weave/guides/tracking/view-agent-activity
- [wandb-traceagents] Weave Trace your agents (OTel gen_ai.*; invoke_agent/chat/execute_tool; sub-agent) — https://docs.wandb.ai/weave/guides/tracking/trace-agents
- [wandb-compare] Weave Compare traces (side-by-side/unified diff, baseline) — https://docs.wandb.ai/weave/guides/tools/comparison
- [wandb-costs] Weave Track costs (auto + custom pricing; add_cost) — https://docs.wandb.ai/weave/guides/tracking/costs
- [arize-explore] Arize AX Explore Your Traces (Traces/Sessions/Spans; filters; multi-span; saved views; columns; source-mapping; AI Search) — https://arize.com/docs/ax/observe/tracing/view-and-manage-traces
- [phoenix-spansearch] Phoenix Search spans (parent_id=null root; status_code; attribute key:value) — https://arize.com/docs/phoenix/sdk-api-reference/rest-api/api-reference/spans/search-spans-with-simple-filters-no-dsl
- [phoenix-openinference] Phoenix OpenInference best practices (span kinds; session.id; metadata filter; token/cost inline) — https://arize.com/docs/phoenix/cookbook/tracing/openinference-best-practices
- [phoenix-sessions] Phoenix Setup Sessions — https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-sessions
- [braintrust-viewlogs] Braintrust View your logs (row-type traces/spans; group-trace-by; timeline/thread; built-in views) — https://www.braintrust.dev/docs/observe/view-logs
- [braintrust-examine] Braintrust Examine traces (span hierarchy; Cached-tokens view; scale-by) — https://www.braintrust.dev/docs/observe/examine-traces
- [braintrust-observe] Braintrust Observe (BTQL; Topics facets; bt view logs / bt sync pull) — https://www.braintrust.dev/docs/observe
- [braintrust-otel] Braintrust OTEL logging (BTQL `Name LIKE 'POST%'`) — https://www.braintrust.dev/docs/cookbook/recipes/OTEL-logging
- [braintrust-best] Braintrust best AI observability tools 2026 (token/cost breakdown; expandable span tree) — https://www.braintrust.dev/articles/best-ai-observability-tools-2026
- [otel-blog] OTel "Inside the LLM Call" (invoke_agent→chat→execute_tool tree; gen_ai attrs) — https://opentelemetry.io/blog/2026/genai-observability
- [greptime-otel] OTel GenAI semantic-conventions evolution v1.37-v1.41 (invoke_workflow; CLIENT/INTERNAL split; MCP conv) — https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions
- [morphllm] Agent Tracing 2026 (OTel spans + tools) — https://www.morphllm.com/agent-tracing
- [zylos] OpenTelemetry for AI Agents (LLM/agent/tool spans; events; metrics) — https://zylos.ai/research/2026-02-28-opentelemetry-ai-agent-observability
- [uptrace] OpenTelemetry for AI Systems 2026 — https://uptrace.dev/blog/opentelemetry-ai-systems
- [sitepoint] OTel GenAI local instrumentation (attrs; content opt-in) — https://www.sitepoint.com/opentelemetry-genai-instrument-ai-agents-without-sending-data-to-the-cloud
- [kong-otel] Kong Guide to AI Observability (gen_ai.system=vendor; provider metadata) — https://konghq.com/blog/learning-center/guide-to-ai-observability
- [cohorte] OTel GenAI conventions (provider.name values; sensitive-content guidance) — https://www.linkedin.com/pulse/opentelemetry-genai-semantic-conventions-cohorte-inc-xgsuf
- [rfc-3460] OpenLLMetry RFC: Semantic Conventions for AI Agent Observability — https://github.com/traceloop/openllmetry/issues/3460
- [rfc-35] OTel semantic-conventions-genai issue #35 (agentic systems: tasks/actions/agents/teams) — https://github.com/open-telemetry/semantic-conventions-genai/issues/35
- [telerik] Progress Telerik Agent Tracing & Observability (filter by model/workflow/status; replay) — https://www.telerik.com/ai-engineering/agent-tracing-observability
- [agenthud] neochoon/agenthud (merged multi-agent tree; provider labels; working/waiting; follow --json) — https://github.com/neochoon/agenthud
- [agentdashboard] bjornjee/agent-dashboard (tmux; state groups; subagent tree; token/cost + rate bars) — https://github.com/bjornjee/agent-dashboard
- [agentdeck] asheshgoplani/agent-deck (status symbols; `!@#$` filters; `$` cost dashboard; conductor) — https://github.com/asheshgoplani/agent-deck
- [agentview] doyled-it/agent-view (state vocabulary; attention-sort; run-history replay; rate bars) — https://github.com/doyled-it/agent-view
- [seshions] danhergir/seshions (Claude+Codex mixed; blueprints; command-palette dispatch) — https://github.com/danhergir/seshions
- [cc-agentview] Claude Code Agent view docs (state groups; peek/attach; PR labels; `claude agents --json`; v2.1.205 one-line reports) — https://code.claude.com/docs/en/agent-view
- [webfetch] OTel GenAI attribute extraction (invoke_agent CLIENT/INTERNAL; provider.name; MCP attrs; cache/reasoning tokens) — synthesized from [greptime-otel]

---
*Design-gate deliverable. No code, config, or commits produced. All fetched content was treated as
untrusted data per AGENTS.md §9; none was executed or followed as instruction.*