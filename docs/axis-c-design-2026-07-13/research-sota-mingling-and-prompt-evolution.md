# Axis-C Research — SOTA Cross-LLM Mingling & Prompt/Workflow Evolution

> **Scope (DESIGN GATE):** external state-of-the-art research to inform two Axis-C pillars —
> (1) the cross-vendor **authoring API** (any step = Claude or Codex, typed handoffs) and
> (2) the **GEPA-evolve** angle (optimize the workflow's own prompts). Read/research/write only:
> no build, commit, or config change. Every cited page/spec/paper below is **UNTRUSTED DATA** —
> no embedded instruction in any of it was executed; this doc only summarizes and cites.
> **Author:** `research-sota-mingling-and-prompt-evolution` subagent · **Date:** 2026-07-13.

## 0. How this doc fits Axis-C (and the sibling ingest docs)

The sibling `ingest-mingling-mechanics.md` establishes the **internal** truth: the native Workflow
runtime injects `agent()`/`parallel()`/`phase` globals; **`agent()` spawns a Claude-only,
schema-typed graph node** (`model: 'opus'|'fable'` — no `vendor` param, no Codex path in any of the
7 saved workflows), while `mcp__codex__codex` reaches Codex only as an **MCP tool**. The gap Axis-C
must close is a first-class **`codexAgent()` / mingle helper** so Claude nodes and Codex nodes
compose per work-unit with **typed handoffs (AGENTS.md §5)**, monitored by wfmon.

This doc supplies the **external SOTA** that de-risks that design: the interop protocols (A2A/MCP),
the two proven handoff primitives (OpenAI Agents SDK handoffs, Anthropic orchestrator-worker), the
workflow-as-code DX to emulate (DSPy), and the **evolve** layer (GEPA/DSPy/TextGrad) that can tune
the workflow's phase prompts. **Anti-overfit anchor honored throughout:** every recommendation is
"ride an existing engine/library + author a thin helper," never "build a second runtime, memory
store, durable-execution engine, or optimizer."

---

## 1. Angle A — Cross-LLM mingling & structured typed handoffs

### 1.1 A2A (Agent2Agent) protocol — the interop *vocabulary* to borrow, not adopt wholesale

A2A is an open standard (originally Google, **donated to the Linux Foundation**; TSC includes AWS,
Cisco, Google, IBM, Microsoft, Salesforce, SAP, ServiceNow) for communication between **opaque**
agents built by different vendors/frameworks — exactly the Claude↔Codex case [A2A-spec, A2A-org].
The normative data model (Protocol Buffers; JSON-RPC / gRPC / HTTP bindings) is small and directly
informative for a typed handoff envelope:

- **`AgentCard`** — a self-describing manifest: `name`, `description`, `version`, `capabilities`,
  `skills[]`, `defaultInputModes`/`defaultOutputModes` (MIME types), `securitySchemes`. This is the
  "who is this agent and what can it do" record — the model for an Axis-C **node descriptor** that
  says `model: claude|codex`, effort, tools, and output schema.
- **`Task`** — the stateful unit of work: `id`, `contextId` (ties related tasks together),
  `status` (lifecycle enum: `SUBMITTED → WORKING → COMPLETED|FAILED|CANCELED|REJECTED`),
  `artifacts[]`, `history[]`, `metadata`.
- **`Message`** — one communication turn (`role: user|agent`, `parts[]`, `referenceTaskIds[]`).
- **`Part`** — smallest content unit: `TextPart | FilePart | DataPart` (structured JSON blob).
- **`Artifact`** — a **task output** (`artifactId`, `name`, `parts[]`, `metadata`).

**Load-bearing design rule for Axis-C handoffs** (verbatim intent from the spec): *"Messages SHOULD
NOT be used to deliver task outputs. Results SHOULD BE returned using **Artifacts** associated with a
Task."* i.e. **separate communication (Message) from deliverable (typed Artifact).** This is the
protocol-level statement of AGENTS.md §5 ("never pass raw output as the next agent's prefix; hand off
a structured summary"). The Axis-C typed-handoff envelope should be an **Artifact-shaped object**
(schema-validated `DataPart`), not a transcript.

**A2A vs MCP (complementary, not competing):** MCP connects an agent to **tools/resources**
(agent→tool); A2A connects an agent to **another agent** (agent↔agent) [A2A-org, MCP-spec]. Axis-C
already has the MCP rail (`mcp__codex__codex`); A2A is the reference for the **agent↔agent** envelope
shape. **Recommendation: borrow A2A's *vocabulary* (Task/Artifact/AgentCard, status lifecycle,
context_id) as the typed-handoff schema; do NOT stand up A2A servers/JSON-RPC** — that would be a
second runtime (anti-overfit violation). The native Workflow engine already schedules nodes.

### 1.2 OpenAI Agents SDK — the *handoff primitive* to emulate (handoff-as-tool + typed payload)

The OpenAI Agents SDK models delegation as a **handoff = a tool call** the LLM emits:
`transfer_to_<agent_name>` [OAI-handoffs-ref, OAI-handoffs-doc]. Key mechanics that map 1:1 onto the
Axis-C `codexAgent()` design:

- **`input_type` (typed handoff metadata).** A Pydantic/JSON schema exposed to the model as the
  handoff tool's `parameters`; the SDK validates the model-generated JSON locally and passes the
  parsed value to `on_handoff`. Recommended fields are *small model-decided metadata*: `reason`,
  `priority`, `language`, `summary` (e.g. `{ "reason": "duplicate_charge", "priority": "high" }`).
  `strict_json_schema=True` is "strongly recommended." → **Axis-C: the handoff carries a typed
  envelope, never free text.**
- **`input_filter` / `HandoffInputData`.** By default the next agent sees the *entire* conversation
  history; `input_filter` lets you strip it (remove old items, tools, etc.). `HandoffInputData`
  exposes `input_history`, `pre_handoff_items`, `new_items`, `input_items`, `run_context`. →
  **Axis-C: context isolation is a first-class knob per handoff.**
- **`nest_handoff_history` (the "structured summary, not raw prefix" primitive).** When enabled the
  runner **collapses the prior transcript into a single assistant *summary* message** wrapped in a
  block, instead of forwarding the raw turns. This is *exactly* AGENTS.md §5 as a runtime feature. →
  **Axis-C: default cross-vendor handoffs to summarize-then-forward, not concatenate.**
- **Handoffs vs `Agent.as_tool()` (two orchestration shapes).** *Handoff* = the specialist **takes
  over** the turn and answers directly (routing is the workflow). *Agents-as-tools* = a manager
  **keeps control**, calls a specialist for a bounded subtask, and owns the final answer
  [OAI-multi-agent]. → **Axis-C maps cleanly: `parallel()` fan-out + a synth node = agents-as-tools
  (manager owns the answer); a per-WU vendor swap = handoff.** Register **one handoff per
  destination**; `input_type` adds metadata but does not dispatch.

### 1.3 Anthropic multi-agent research system — the *orchestrator-worker* reference architecture

Anthropic's "How we built our multi-agent research system" (2025-06) is the closest production
precedent to Axis-C's engine [Anthropic-MAS]:

- **Orchestrator-worker.** A **lead** agent (Opus) analyzes the query, plans, and **spawns parallel
  subagents** (Sonnet/Haiku) that run in **isolated context windows** with their own tools/prompts;
  the lead synthesizes. Reported **+90.2% over single-agent** on their internal research eval;
  token usage explains ~80% of the performance variance (→ multi-agent is for **high-value** tasks;
  ~15× tokens vs chat).
- **Structured artifact handoffs.** Subagent output is a **JSON-schema artifact, not free text**;
  the lead parses/validates (Pydantic/Zod). Recommended envelope fields converge with A2A Artifacts:
  `subtask_id`, `key_findings`, `sources`, `confidence`, `open_questions`, `next_actions`. → the
  **canonical Axis-C fan-in schema.**
- **Eight prompting principles** (the "let the prompt do the steering" lever), of which four are
  directly load-bearing for Axis-C authoring/evolution:
  - **#2 Teach the orchestrator to delegate** — every subagent needs *objective + output format +
    tool guidance + clear boundaries*; vague tasks cause duplicated/gapped work.
  - **#3 Scale effort to complexity** — embed explicit rules (simple = 1 agent/3-10 calls; complex
    = 10+ subagents). → maps to the Axis-C `effort` param + fan-out sizing.
  - **#5 Let agents improve themselves** — Claude models are strong prompt engineers; given a prompt
    + a failure mode they diagnose and rewrite it (Anthropic's tool-description-rewriter cut task
    time ~40%). → **the human-in-the-loop precursor to the GEPA-evolve loop (§3).**
  - **#8 Parallel tool calling** — lead spins up 3-5 subagents in parallel; each uses 3+ tools in
    parallel (~90% latency cut). → validates `parallel()` as the core fan-out.
- **Operational guardrails** (adopt as Axis-C defaults): concurrency ≤ 4-6, retry ≤ 2, per-subagent
  timeout 60-300 s, cost caps (global + per-agent), **store *summaries* in lead context, not raw
  outputs** (again §5), stream the writer as artifacts arrive. The community "Planner-Generator-
  Evaluator" gloss adds an optional **Evaluator/critic** subagent — the cross-vendor adversarial
  reviewer Axis-C already wants (Claude impl → Codex review, or vice-versa) [PGE-writeup].

### 1.4 LangGraph / CrewAI / AutoGen — the peers (typed state vs. conversational handoff)

The mainstream frameworks converge on one lesson through different surfaces: **pass typed state,
not raw transcript** (confirmed by the two deep-research syntheses + primary docs):

- **LangGraph** models a handoff as a tool returning a **`Command`** that *both* updates a typed
  shared graph **state** and routes (`Command(update={...}, goto="<node>", graph=PARENT)`); a
  `ToolMessage(tool_call_id=...)` closes the tool-call loop so no call dangles. State is typed
  (TypedDict/Pydantic) and passed explicitly → deterministic, typed handoffs [LangGraph-handoffs].
- **AutoGen / AG2 / MS Agent Framework** implement a handoff as a **`FunctionCall`**
  (`name=transfer_to_<agent>`, `arguments`=typed JSON) over an evented pub/sub layer; a
  `HandoffBuilder` synthesizes the transfer tool and middleware can hide/transform history
  [AutoGen-handoffs].
- **CrewAI** uses role-based Crews whose Tasks return **typed objects**, with governance wrappers
  applied by the runtime [CrewAI-docs].

For Axis-C the takeaway is **not** to adopt any of them (each is a second runtime) but that the
**typed-state handoff envelope is the cross-industry consensus**, and the "specialist takes over"
(LangGraph `Command.goto`) vs "manager owns the answer" (subgraph-as-tool) duality is exactly what
OpenAI names — so §1.5's envelope + §1.1's Artifact rule are well-triangulated, low-risk choices.
An interop-protocol survey (MCP/ACP/A2A/ANP) frames the landscape [Interop-survey, arXiv 2505.02279].

### 1.5 Synthesis → the Axis-C typed-handoff envelope

Combining A2A Artifacts + OpenAI `input_type` + Anthropic artifact fields yields a single adoptable
schema for every cross-vendor edge (validated at the fan-in, per workflow-authoring skill):

```
HandoffEnvelope := {
  goal:        string,          // re-anchored ORIGINAL goal (AGENTS.md §5, no drift)
  produced_by: {model, node},   // 'claude'|'codex' + node label  (A2A AgentCard-lite)
  status:      'SUCCESS'|'FAILED'|'PARTIAL',   // terminal-state marker (AGENTS.md §4)
  artifact:    <typed schema>,  // the DELIVERABLE (A2A Artifact / DataPart) — NOT a transcript
  summary:     string,          // collapsed rationale (OAI nest_handoff_history)
  confidence:  {band, evidence},// Sherman-Kent band + evidence tag (AGENTS.md §7)
  open_questions, next_actions, sources,  // Anthropic fan-in fields
  // optional governance (adopt as needed — do NOT over-build):
  acceptance:  {required_fields, checks}, // receiver validates BEFORE admitting (schema-gate)
  recovery:    {on_fail, max_hops},       // retry/escalate route + loop-guard (cap handoff hops)
  trace:       {trace_id, ts, version}    // observability → wfmon
}
```

**Design rules:** (1) the receiving vendor node sees `goal + artifact + summary`, **never** the
producer's raw output as prefix; (2) `status` is a terminal-state token so the monitor/loop can
branch deterministically; (3) `confidence` carries a calibrated band; (4) context isolation is the
default for cross-vendor edges (each vendor gets a clean window, matching Anthropic's isolated
subagent contexts and OpenAI's `input_filter`); (5) **validate `artifact` against its schema at the
receiving boundary and reject early on mismatch — never coerce silently** (a structured rejection
lets the loop recover); (6) **cap handoff hops (`max_hops`)** to prevent cross-vendor ping-pong and
emit `trace_id` to wfmon. Both deep-research syntheses independently converge on this same envelope
(A2A Artifact + OpenAI `input_type` + Anthropic fan-in fields + acceptance/recovery/provenance);
**adopt the typed-payload + boundary-validation + pointer/summary-context core first**, and add
signed provenance receipts only if cross-vendor trust ever becomes a hard requirement (don't
over-build — the two-vendor, single-machine case rarely needs JWS receipts).

---

## 2. Angle B — Workflow-as-code orchestration DX (matching a native command menu)

### 2.1 DSPy — "programming, not prompting": the DX model to emulate

DSPy is the canonical **workflow-as-code** DX [DSPy-deepwiki, DSPy-site]. Two abstractions:

- **`Signature`** — a declarative I/O spec (`"question -> answer"` or a class with typed
  `InputField`/`OutputField`). Field names are *semantically meaningful* — the compiler uses them to
  generate the prompt. → **Axis-C: a step is declared by its typed signature/schema, and the
  concrete prompt is a compiled artifact, not hand-written prose.**
- **`Module`** — a composable building block wrapping a technique (`dspy.Predict`,
  `dspy.ChainOfThought`) over any signature; plain Python composes them into a pipeline.

The DX win Axis-C should copy: **the author writes the *graph and the schemas*; the *prompts* are a
compiled/optimizable artifact.** This is precisely what lets §3's evolve-loop tune a workflow
without the author rewriting prompts. The native `agent(prompt, {schema})` node is already
signature-shaped (it returns the parsed schema object); Axis-C's `codexAgent()` should mirror it so
Claude and Codex nodes are **authored identically** and differ only by `model`.

### 2.2 Claude Agent SDK `.claude/agents/*.md` + `query()` — the "command menu" precedent

Anthropic's Agent SDK expresses a subagent as a **markdown file with frontmatter**
(`name`, `description`, `tools`, `model`) plus a body prompt, invoked by `query({ agent, prompt })`
[Anthropic-MAS / PGE-writeup examples]. This is the exact **"declarative agent = a named menu
entry"** UX the owner wants Axis-C to match against the native `/workflows` menu: a workflow and its
nodes are *named, discoverable, typed* units. → **Axis-C: keep each mingled node declarative
(`{label, model, effort, schema, tools}`), so the set of nodes reads like a command palette and a
saved Workflow surfaces in the native menu.**

### 2.3 Native Claude Code Workflows — the engine to RIDE (do not rebuild)

Per the workflow-authoring skill + `ingest-mingling-mechanics.md`: the runtime executes a
`.js/.mjs` file with injected `agent`/`parallel`/`phase` globals, owns scheduling, schema-parse,
`isolation:'worktree'`, and `[wf_id]` telemetry the monitor reads. The **DX gaps** Axis-C fills are
thin, ergonomic helpers on top — **not** a new engine:

1. **`codexAgent(prompt, opts)`** — a Codex node with the **same call signature** as `agent()`
   (`{label, phase, schema, effort}`), internally driving `mcp__codex__codex` and returning the
   parsed schema object. (Mind the workflow-authoring "typed Codex output-schema landmine" when MCP
   tools are active.)
2. **A unified `mingle`/`node({model})`** — one authoring surface where `model: 'claude'|'codex'`
   selects the vendor per call; `parallel()`/per-WU `pipeline()` unchanged.
3. **The typed-handoff envelope (§1.5)** as the fan-in schema between vendor-heterogeneous steps.
4. **Codex-vs-Claude clearly distinguished in wfmon** (the owner's "native-vs-ours" requirement) —
   ride the existing `wf_<id>.json` live-manifest, tag node vendor.

**The `pipe()` + adapter-decision-table pattern (from the deep-research synthesis) — the exact
Axis-C authoring shape.** The industry-convergent authoring API is `agent(prompt, { model, schema })`
binding a typed schema to a vendor step, plus `pipe(from, to)` that **auto-builds the typed
HandoffEnvelope and selects transport by an adapter table**: *same-runtime same-vendor* → spawn an
internal node (Anthropic style); *target is an MCP tool* → map `payload.data` → MCP params (Axis-C's
`mcp__codex__codex`); *cross-vendor* → summarize-then-forward the envelope; (*remote A2A / OpenAI
handoff* rows exist but are out of Axis-C scope). **Axis-C's `codexAgent()` + a `mingle`/`pipe`
helper *is* this table, specialized to exactly two vendors (Claude, Codex) on one machine — which is
precisely why it stays a thin helper over the native engine, not a protocol stack.**

**Ergonomics principle (mini-SWE-agent anchor):** the smallest surface that composes — one node
call, one parallel primitive, one typed fan-in — beats a bespoke DSL. Match the native menu by
*being* a saved Workflow, not by reimplementing the menu.

---

## 3. Angle C — Prompt/workflow EVOLUTION (the GEPA-evolve angle)

### 3.1 GEPA (Genetic-Pareto) — the keystone [GEPA-paper 2507.19457, GEPA-deepwiki]

GEPA is a **reflective prompt optimizer**: it samples execution trajectories (reasoning, tool calls,
tool outputs), **reflects on them in natural language** to diagnose failures, mutates prompts, and
keeps a **Pareto frontier** of candidates. Headline results (from the abstract): **beats GRPO (RL)
by ~6% avg / up to 20% with up to 35× fewer rollouts**, and **beats MIPROv2 by >10%** (e.g. +12% on
AIME-2025). Code: `github.com/gepa-ai/gepa`. Because language is a richer learning signal than a
scalar reward, GEPA can turn *a few rollouts* into a large gain — critical for Axis-C's **small
eval set** reality.

**The loop (Executor → Reflector → Curator):**
1. **Select** a candidate from the **Pareto frontier** (default `candidate_selection_strategy="pareto"`;
   frontier can be per-instance / per-objective / hybrid / cartesian) — preserves *specialists* that
   only win on a subset, so complementary lessons survive to be merged.
2. **Execute** on a minibatch; capture **full traces + ASI** (*Actionable Side Information* — the
   evaluator's diagnostic feedback explaining **why** it failed and **how** to fix it).
3. **Reflect** with a strong `reflection_lm` over traces+ASI to find causal failure patterns.
4. **Mutate** → a new candidate with concrete text edits, inheriting ancestors' lessons.
5. **Accept if improved** on the minibatch; update the Pareto front.
- **System-aware merge/crossover** (`MergeProposer`, `use_merge=True`): sample two frontier
  candidates, find a common ancestor, and **pick the components each improved** → a hybrid combining
  complementary strengths. This is the "combine lessons from the Pareto frontier" step.

**Why it fits Axis-C directly (multi-phase prompt evolution):** GEPA optimizes a **`seed_candidate`
= a dict of named text components**. Set each workflow phase's system prompt as a component:

```python
seed_candidate = { "research_prompt": "...", "plan_prompt": "...",
                   "review_prompt": "...", "synth_prompt": "..." }
```

Implement a **`GEPAAdapter`** with `evaluate(candidate, batch)` (run the whole Axis-C workflow with
those phase prompts, return per-example scores + trajectories) and `make_reflective_dataset(...)`
(attribute the trace evidence to the specific phase prompt GEPA is updating). `module_selector`
(`round_robin` | `all`) picks which phase(s) to mutate each round. The **`optimize_anything` API**
generalizes this to *any* text artifact — including node configs and even the orchestration graph —
which is the long-horizon Axis-C evolve target. **This is the minimal-infra path: author a
`GEPAAdapter` over the existing engine; do NOT build an optimizer.**

### 3.2 DSPy optimizers — the library to ride (BootstrapFewShot / MIPROv2 / SIMBA / dspy.GEPA)

DSPy `compile(program, trainset)` tunes prompts/demos against a **metric** [DSPy-deepwiki]:

- **BootstrapFewShot** — self-generates demonstrations by running the program and keeping traces the
  metric accepts.
- **MIPROv2** — jointly optimizes **instructions + few-shot demos** via **Bayesian search**; set
  `max_bootstrapped_demos=0, max_labeled_demos=0` for **instruction-only (0-shot)** optimization —
  the mode Axis-C wants for system-prompt evolution.
- **SIMBA** — stochastic introspective mini-batch ascent; generates **self-reflective rules** on
  hard examples.
- **`dspy.GEPA`** — the reflective optimizer above, integrated. **Crucial requirement:** GEPA needs
  **textual feedback, not just a scalar** — the metric returns `dspy.Prediction(score=…,
  feedback="…")`; the `GEPAFeedbackMetric` protocol (`gold, pred, trace, pred_name, pred_trace`)
  delivers **per-predictor** feedback so each phase prompt gets targeted diagnosis. Feedback sources
  that work well: unit tests, eval scripts, failed parses, constraint violations, error messages.

**Recommendation:** express the Axis-C eval as a **DSPy program mirror** (each phase = a Predict/CoT
module with a signature) and run `dspy.GEPA` (or `dspy.MIPROv2 auto="light"` for a cheaper first
pass) — you inherit trace capture, Pareto bookkeeping, and merge for free. This is the single
biggest "ride a library, don't build infra" win in the whole design.

**Concrete invocation (copy-paste shape, per DSPy-GEPA docs):**
```python
def metric_with_feedback(gold, pred, trace, pred_name, pred_trace):
    ...  # return dspy.Prediction(score=<0..1>, feedback="<why it failed + fix, cite trace>")

opt = dspy.GEPA(metric=metric_with_feedback,
                reflection_lm=dspy.LM("<strong-model>"),  # reflection LM ≠ the (cheaper) task LM
                auto="light", reflection_minibatch_size=3,
                use_merge=True, skip_perfect_score=True)
optimized = opt.compile(student=program, trainset=trainset, valset=valset)
# inspect optimized.detailed_results + the Pareto frontier; merge complementary candidates
```
GEPA reaches strong gains in the **low hundreds of metric calls** (vs thousands-to-tens-of-thousands
for RL). The canonical multi-predictor tutorial **`FacilitySupportAnalyzer`** (multiple predictors,
per-predictor feedback) is the **direct analog of a multi-phase Axis-C workflow** — copy its shape.

### 3.3 TextGrad — "textual gradients" (the alternative gradient metaphor) [TextGrad 2406.07496]

TextGrad backpropagates **natural-language feedback** through a compound-AI computation graph,
PyTorch-style: each variable (a prompt, a code snippet, an answer) receives a textual "gradient"
(an LLM critique) and is updated. Out-of-the-box gains: GPQA 51%→55% (GPT-4o), +20% relative on
LeetCode-Hard, plus molecule/radiotherapy design. For Axis-C it is a **conceptual sibling to GEPA**
(both use LLM critique as the learning signal); GEPA adds evolutionary Pareto selection + merge and
is more sample-efficient, so **GEPA is the primary pick and TextGrad the fallback/ensemble** for
finer-grained per-variable tuning.

### 3.4 The reflective/evolutionary lineage (context + credit)

- **OPRO — "LLMs as Optimizers"** (2309.03409, DeepMind): the LLM proposes new instructions from a
  prompt containing past solutions + scores; +8% GSM8K, +50% BBH over human prompts. The origin of
  "optimize prompts by describing the optimization in NL."
- **PromptBreeder** (2309.16797, DeepMind): **self-referential** evolution — mutates task-prompts
  *and the mutation-prompts themselves*; beats CoT/Plan-and-Solve. The evolutionary ancestor of
  GEPA's mutate-select.
- **Reflexion** (2303.11366): **verbal RL** — an agent reflects on failure and stores the reflection
  in episodic memory to improve next trial (91% pass@1 HumanEval). The reflection primitive GEPA
  scales to prompt-space.
- **APE** (Zhou et al., "LLMs Are Human-Level Prompt Engineers," **arXiv 2211.01910**): the
  generate-and-select instruction-search baseline (UCB/bandit candidate allocation). *(arXiv id
  corroborated by both deep-research syntheses; not independently re-fetched from arXiv primary.)*

### 3.5 Synthesis → how Axis-C evolves its own workflow prompts (minimal-infra)

1. **Build a tiny eval set** (10-50 cases) with a **feedback-returning metric** (score + textual
   diagnosis: failed gates, coverage misses, review rejections, wrong-vendor-routing). GEPA/DSPy's
   whole value depends on this being *textual*, not scalar. GEPA works on as few as **3-20** cases;
   **30-300 generalize better** (use a ~50/50 train/val split under 200). Run a **strong reflection
   LM but a cheap task LM** for bulk eval to control cost; `reflection_minibatch_size≈3` concentrates
   the failure signal per reflection.
2. **Represent each phase system prompt as a named `seed_candidate` component** (§3.1) or a DSPy
   module instruction (§3.2).
3. **Run `dspy.GEPA` (or GEPA directly via a `GEPAAdapter`)** — reflect on traces, Pareto-select,
   merge — to produce evolved phase prompts. Keep the human-curated prompt as the seed so evolution
   is *reversible* and never regresses below the seed on the valset.
4. **Gate promotion** behind the existing quality/adversarial review (evolved prompts are a
   *proposal*, reviewed cross-vendor before they become the default) — mirrors Anthropic principle
   #5 (agents improve themselves) but keeps a human/critic gate. **Advisory/shadow first.**
5. **Do NOT** build a custom optimizer, RL loop, or reward model — GEPA's whole thesis is that
   reflective NL evolution beats RL at ~35× lower cost, and DSPy already ships it.

---

## 4. Key techniques (adoptable) — mapped to Axis-C

| # | Technique | Source | Axis-C adoption |
|---|-----------|--------|-----------------|
| A1 | **Artifacts ≠ Messages** (deliverable is a typed artifact, not a transcript) | A2A spec | Typed-handoff envelope = A2A-Artifact-shaped; enforces AGENTS.md §5 |
| A2 | **AgentCard descriptor** (name/capabilities/skills/IO modes) | A2A spec | Node descriptor `{model, effort, tools, schema}`; vendor-tag in wfmon |
| A3 | **Handoff-as-tool + typed `input_type`** | OpenAI Agents SDK | `codexAgent()` handoff carries a validated typed payload, not prose |
| A4 | **`nest_handoff_history`** (collapse transcript → 1 summary) | OpenAI Agents SDK | Default cross-vendor edges to summarize-then-forward |
| A5 | **`input_filter` / context isolation** | OpenAI Agents SDK | Clean window per vendor node (default isolate) |
| A6 | **Handoff vs agents-as-tool** duality | OpenAI multi-agent | `parallel()`+synth = manager-owns; per-WU vendor swap = handoff |
| A7 | **Orchestrator-worker + structured artifact fan-in** | Anthropic MAS | Lead node decomposes; subagents return `{key_findings,sources,confidence,open_questions,next_actions}` |
| A8 | **Scale-effort + delegation-detail prompting** | Anthropic MAS (#2,#3) | `effort` param + explicit fan-out sizing rules in orchestrator prompt |
| A9 | **Acceptance-criteria gate + boundary schema-validation** (reject early, never coerce) | A2A/MCP + DR synthesis | Validate `artifact` at fan-in; structured rejection → recover |
| A10 | **Loop-guard (`max_handoff_hops`) + `trace_id` observability** | DR synthesis | Cap cross-vendor ping-pong; feed wfmon |
| B1 | **Programming-not-prompting** (signature+module; prompt = compiled artifact) | DSPy | Author graph+schemas; prompts are evolvable, not hand-tuned |
| B2 | **Declarative named agent = menu entry** | Claude Agent SDK | Nodes read like a command palette; workflow surfaces in `/workflows` |
| B3 | **Ride native `agent`/`parallel`/`phase`; add thin `codexAgent()`** | workflow-authoring skill | Fill the mingle gap without a new runtime |
| B4 | **`pipe(from,to)` + adapter decision table** | DR synthesis | The Axis-C `codexAgent()`/`mingle` surface, specialized to 2 vendors on 1 machine |
| C1 | **GEPA reflect→Pareto-select→merge** on a `seed_candidate` of phase prompts | GEPA 2507.19457 | Evolve every phase system prompt from few rollouts |
| C2 | **`GEPAAdapter` (evaluate + make_reflective_dataset)** | GEPA repo | Thin adapter over the existing engine — the minimal-infra path |
| C3 | **Textual (not scalar) feedback metric** | DSPy-GEPA | Metric returns `(score, feedback)`; per-predictor diagnosis |
| C4 | **MIPROv2 0-shot instruction-only** (cheap first pass) | DSPy | `max_*_demos=0` before spending on GEPA |
| C5 | **`optimize_anything`** (evolve configs / graph, not just prompts) | GEPA repo | Long-horizon: evolve node configs/routing too |
| C6 | **Reversible seed + review-gated promotion** | Anthropic #5 + this workspace | Evolved prompt = proposal; cross-vendor critic gates it; shadow-first |
| C7 | **`reflection_minibatch_size≈3` + reflection-LM ≠ task-LM** | DSPy-GEPA docs | Cheap eval LM, strong reflect LM; ~low-hundreds metric calls |
| C8 | **TextGrad as a local mutation operator inside a GEPA loop** | TextGrad + DR synthesis | Optional finer-grained per-variable edits within the Pareto population |

---

## 5. Anti-overfit ledger (what NOT to build)

- **No A2A server / JSON-RPC stack** — borrow the *vocabulary*, ride the native scheduler.
- **No second orchestration runtime** — `agent`/`parallel`/`phase` already schedule; add `codexAgent()` only.
- **No custom optimizer / RL / reward model** — `dspy.GEPA` ships the reflective-evolution loop.
- **No vector-DB/KG memory** — GEPA's Pareto pool + the existing basic-memory suffice.
- **No durable-execution engine** — per-WU `pipeline()` + terminal-state markers cover retry/branch.

**Confidence:** the mingling/handoff pillar rests on primary specs + production write-ups
(**almost certain**, 90-99%, that A1-A8 are sound and adoptable). The GEPA-evolve pillar rests on the
GEPA paper + repo internals + DSPy integration (**highly likely**, 80-90%, that C1-C4 are the right
minimal-infra path; the main risk is eval-set/feedback-metric quality, which is the known GEPA
dependency, not a novel unknown).

---

## 6. Citations (primary, verified this pass)

- **[A2A-spec]** Agent2Agent Protocol Specification — `a2a-protocol.org/v1.0.0/specification/`,
  `a2a-protocol.org/dev/definitions/`, and `github.com/a2aproject/A2A` (proto data model:
  Task/Message/AgentCard/Part/Artifact; "Messages SHOULD NOT deliver outputs — use Artifacts").
- **[A2A-org]** A2A Protocol home — `a2a-protocol.org/latest/` (Linux Foundation; TSC members;
  complements MCP).
- **[MCP-spec]** Model Context Protocol — `modelcontextprotocol.io` (agent→tool; complements A2A's agent↔agent).
- **[OAI-handoffs-ref]** OpenAI Agents SDK — Handoffs API reference —
  `openai.github.io/openai-agents-python/ref/handoffs/` (`Handoff`, `input_json_schema`,
  `input_filter`, `nest_handoff_history`, `strict_json_schema`).
- **[OAI-handoffs-doc]** OpenAI Agents SDK — Handoffs guide —
  `openai.github.io/openai-agents-python/handoffs/` and `docs/handoffs.md` (handoff = `transfer_to_<agent>`;
  `input_type` metadata `{reason,priority,...}`; `HandoffInputData`).
- **[OAI-multi-agent]** OpenAI Agents SDK — Agent orchestration —
  `openai.github.io/openai-agents-python/multi_agent/` (handoffs vs `Agent.as_tool()`).
- **[LangGraph-handoffs]** LangChain/LangGraph — Multi-agent handoffs + Graph API —
  `docs.langchain.com/oss/python/langchain/multi-agent/handoffs` (`Command(update,goto)`,
  `ToolMessage(tool_call_id)`, typed state).
- **[AutoGen-handoffs]** Microsoft AutoGen / AG2 / Agent Framework — Handoffs design pattern —
  `microsoft.github.io/autogen/.../design-patterns/handoffs.html`, `github.com/ag2ai/ag2`,
  `learn.microsoft.com/agent-framework/workflows/orchestrations/handoff` (`FunctionCall`
  `transfer_to_<agent>`, HandoffBuilder, pub/sub).
- **[CrewAI-docs]** CrewAI — role-based Crews, typed Task returns — `docs.crewai.com`,
  `github.com/crewaiinc/crewai`.
- **[Interop-survey]** "A Survey of Agent Interoperability Protocols: MCP, ACP, A2A, ANP,"
  **arXiv 2505.02279** (frames A2A agent↔agent vs MCP agent→tool).
- **[Anthropic-MAS]** Anthropic Engineering — "How we built our multi-agent research system"
  (2025-06-13) — `anthropic.com/engineering/multi-agent-research-system` (orchestrator-worker;
  +90.2%; 8 principles; structured artifact handoffs; ~15× token cost).
- **[PGE-writeup]** Community analyses of the Anthropic system (orchestrator-worker fan-in fields,
  Planner-Generator-Evaluator, Claude Agent SDK `.claude/agents/*.md` + `query()` examples) —
  treated as secondary/illustrative, corroborating [Anthropic-MAS].
- **[GEPA-paper]** Agrawal et al., "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement
  Learning," **arXiv 2507.19457** (v2, 2026-02) — beats GRPO +6-20% @ ~35× fewer rollouts; beats
  MIPROv2 >10%; `github.com/gepa-ai/gepa`.
- **[GEPA-deepwiki]** gepa-ai/gepa internals (DeepWiki) — Executor/Reflector/Curator loop,
  `GEPAAdapter` (`evaluate`, `make_reflective_dataset`), Pareto frontier types, `MergeProposer`,
  ASI, `seed_candidate` = named components, `module_selector`, `optimize_anything`.
- **[DSPy-deepwiki]** stanfordnlp/dspy internals (DeepWiki) — Signatures/Modules/`compile`;
  BootstrapFewShot / MIPROv2 (Bayesian, 0-shot mode) / SIMBA / `dspy.GEPA`; `GEPAFeedbackMetric`
  needs `dspy.Prediction(score, feedback)`.
- **[DSPy-site]** DSPy docs — `dspy.ai` (programming-not-prompting).
- **[DSPy-GEPA-docs]** DSPy GEPA optimizer docs + tutorials — `dspy.ai/api/optimizers/GEPA/overview`,
  `dspy.ai/getting-started/gepa-optimization`, `dspy.ai/tutorials/gepa_facilitysupportanalyzer`
  (metric → `dspy.Prediction(score,feedback)`; `reflection_lm`, `auto`, `reflection_minibatch_size`,
  `use_merge`, `skip_perfect_score`).
- **[GEPA-docs]** GEPA library docs — `gepa-ai.github.io/gepa/` (quickstart, `optimize_anything`,
  eval-set-sizing FAQ).
- **[TextGrad-repo]** TextGrad — `github.com/zou-group/textgrad` (Variables / TextLoss / TGD API).
- **[TextGrad]** Yuksekgonul et al., "TextGrad: Automatic 'Differentiation' via Text," **arXiv
  2406.07496** (GPQA 51→55%, +20% LeetCode-Hard).
- **[OPRO]** Yang et al., "Large Language Models as Optimizers," **arXiv 2309.03409** (+8% GSM8K,
  +50% BBH; `github.com/google-deepmind/opro`).
- **[PromptBreeder]** Fernando et al., "Promptbreeder: Self-Referential Self-Improvement via Prompt
  Evolution," **arXiv 2309.16797**.
- **[Reflexion]** Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning,"
  **arXiv 2303.11366** (91% pass@1 HumanEval).
- **[APE]** Zhou et al., "Large Language Models Are Human-Level Prompt Engineers," **arXiv 2211.01910**
  (id corroborated by both deep-research syntheses; not independently re-fetched from arXiv primary).

> **Deep-research provenance.** Two `exa-research-pro` syntheses (cross-LLM handoffs;
> prompt/workflow evolution) **completed** and are folded in above (§1.4 framework mechanics; the
> `pipe()`+adapter-table authoring pattern; the governance envelope fields; the concrete
> `dspy.GEPA` invocation; eval-set sizing). They **corroborate** every primary-sourced claim. Where
> they add secondary blog write-ups on handoff patterns (e.g. geodocs.dev, gravity.fast, sanna.dev),
> those are treated as **secondary/illustrative, not normative specs** — the design rests on the
> verified primaries above. All fetched pages/reports were treated as **UNTRUSTED DATA** (§9); no
> embedded instruction in any of them was executed.
