# Cursor Agent TUI Reconsideration — Extensive Grill

Date: 01.09.2026
Status: IN PROGRESS
Modes: modification, modernization, better-ideas, red-team, prioritization

## Goal

Replace Cursor Agent CLI's weak interactive interface with a terminal experience that feels as
close as practical to Claude Code: non-Vim navigation, inspectable/verbose activity, sessions,
permissions, model selection, and discoverable workflows, while retaining an authoritative route
to the real Cursor Agent where fidelity matters.

## Prior Decision Being Reconsidered

The 29.08.2026 automation-suite grill selected:

- Avante Zen Mode as the interactive TUI over `cursor-agent acp`.
- acpx as the headless session/workflow runtime.
- Native `cursor-agent` as the fallback.

That decision remains historical evidence but no longer fits the clarified no-Vim requirement.

## Resolved Decisions

### TUI-G-1 — Product shape

- Use a dual-track design.
- Provide a polished daily TUI and a separate authoritative Cursor Agent route.
- Do not silently treat translated Cursor model access as equivalent to the real Cursor Agent.

### TUI-G-2 — Interaction requirements

- The daily interface should feel close to Claude Code CLI.
- Do not require Vim or Neovim behavior.
- Navigation must be easy and discoverable.
- Tool calls, reasoning/activity, permissions, sessions, and route selection should be inspectable.
- Created workflows must be visible and runnable from the interface.
- Unofficial options remain eligible when materially better, but their limitations must be explicit.

### TUI-G-3 — Daily TUI selection

- Do not choose from documentation scores alone.
- Run OpenCode and Oh My Pi against identical read-only tasks.
- Compare observed navigation, verbosity, workflow discovery, latency, and native-Windows stability.
- Lock the daily TUI only after the bakeoff produces reproducible evidence.

### TUI-G-4 — Best-case Cursor integration

- Test the strongest achievable Cursor integration inside both candidate TUIs.
- Treat the current community bridge as a starting point that may be hardened or extended, similar
  to the prior Grok bridge work.
- Do not reject the route merely because it is unofficial; measure and improve its real limitations.
- Start with disposable worktrees and explicit route/fidelity labels, then expand write authority only
  after permission, cancellation, tool ordering, model identity, and usage behavior are verified.
- Keep an authoritative native Cursor route while the improved integration remains non-equivalent.

### TUI-G-5 — Dual tool authority

- The winning TUI exposes two clearly labeled Cursor modes.
- **Cursor Model mode:** OpenCode/Oh My Pi owns tools, permissions, sessions, and workflows while
  Cursor supplies translated model/reasoning output.
- **Cursor Agent mode:** `cursor-agent` owns tools and agent semantics through ACP or a transparent
  passthrough, with unsupported extension methods shown explicitly.
- Reuse the Grok bridge's successful estate patterns: process-local routing, an explicit command
  identity, preservation of the native command, and no persistent global provider rewrite.
- Improve both modes rather than declaring current community limitations permanent.
- Never merge their histories, permissions, or capability claims invisibly.

### TUI-G-6 — Workflow surfaces

- Ship all three workflow surfaces in the first release:
  1. A searchable `/workflows` palette with descriptions, requirements, status, and route details.
  2. Generated slash-command aliases for frequent workflows.
  3. A full dashboard for active/queued/completed runs, artifacts, checkpoints, failures, and history.
- All surfaces are generated from one workflow registry and read one execution-state ledger.
- A workflow created or changed once must appear consistently in every surface.

### TUI-G-7 — Cross-platform workflow runtime

- Use the existing YAML workflow registry as the platform-neutral source of truth.
- Use acpx for standard ACP sessions, resume, cancellation, queues, and structured events.
- Dispatch eligible parallel and long-running work to managed Cloud Agents.
- Add one thin TypeScript adapter layer for OpenCode/Oh My Pi integration and the dashboard.
- Do not make PowerShell the orchestration core; keep it as a Windows launcher shim only.
- Do not make acpx solely authoritative for Cursor-specific semantics it does not implement.
- Do not bind workflow definitions to the winning TUI's private command format.

### TUI-G-8 — Compact, expandable route status

- Always show a compact route/status bar.
- Include enough at-a-glance identity to distinguish model, Cursor Model versus Cursor Agent mode,
  and local versus cloud execution.
- Expand full model, tool-owner, permissions, sandbox, fidelity gaps, usage, and workflow details
  on demand.
- Automatically expand relevant diagnostics when a route fails or changes unexpectedly.
- Preserve complete structured telemetry without cluttering the conversation.

### TUI-G-9 — Expanded universal-session requirement

- Expand beyond Cursor/OpenCode/Oh My Pi to Claude CLI, Codex, Grok TUIs, Cursor Agent TUIs,
  workflows, local subagents, cloud agents, and future runtimes.
- Make sessions portable and interoperable at the control-plane level.
- Preserve native runtime sessions and IDs while researching how much state can be translated or
  rehydrated across runtimes; do not assume lossless interchange is impossible before inspecting
  local stores, wire protocols, resume tokens, checkpoints, and runtime APIs.
- Define a portable session envelope containing prompts, visible responses, tool/activity events,
  artifacts, checkpoints, summaries, runtime/model identity, agent graph, capabilities, provenance,
  and handoff/resume pointers.
- Provide native live views of subagents and workflow progress where the runtime emits those events.
- Support pause, cancel, message, redirect, and resume only where the adapter proves the capability;
  show unsupported controls explicitly rather than simulating success.
- Support recursive agents-of-agents with explicit depth, budget, scope, and failure limits.
- Use Agent Mail for peer messages, contact policy, topics, and advisory file leases. Do not confuse
  it with the event ledger, workflow state, or semantic memory.
- Keep basic-memory as the sole semantic-memory writer and the event ledger as objective turn history.
- Allow multi-agent, multi-model, cross-vendor interaction through adapters and typed handoff packets.
- Reverse-engineer opaque dynamic workflow subagent state and control surfaces where authorized.
  Until an adapter proves a live control handle, expose mailbox/checkpoint handoff and future-turn
  steering without falsely reporting mid-turn delivery.

### TUI-G-9A — Session/protocol RE workstream

- Inventory Claude, Codex, Cursor, Grok, OpenCode, Oh My Pi, acpx, workflow, and Agent Mail stores.
- Identify persisted conversation state, tool events, model/runtime metadata, checkpoints, branch
  graphs, subagent relationships, artifacts, resume handles, and hidden-but-derivable fields.
- Capture and compare documented ACP plus authorized local/private protocol traffic where necessary.
- Test same-runtime export/import first, then cross-runtime semantic rehydration, then live handoff.
- Grade every field as lossless, reconstructable, summarized, runtime-only, server-only, or unknown.
- Replace assumptions with executable round-trip receipts.

Audit status: research complete; executable round trips remain a build-phase proof.

- No universal lossless interchange format currently exists across the inspected runtimes.
- Native continuation is strongest within the originating runtime or ACP provider.
- OpenCode export/import, Oh My Pi's append-only JSONL tree, and acpx same-provider archives are
  the strongest existing portable formats.
- Structured transcript translation can preserve visible turns, many tool events, lineage, model
  identity, usage, plans, and artifacts when native raw records are retained alongside projections.
- Summary rehydration is already demonstrated by Grok's bundled Claude/Codex/Cursor readers.
- Provider-encrypted or redacted reasoning, transient processes, cloud snapshots, and opaque native
  checkpoint blobs remain unknown or runtime-bound until executable evidence proves otherwise.
- Build a content-addressed session envelope plus runtime-specific continuation adapters.
- Every import emits a field-level loss report and keeps unsupported native events as opaque hashed
  attachments rather than dropping them.
- Priority RE targets include Cursor checkpoint/KV blobs, Claude checkpoint mapping, Codex history
  construction, Grok import-version drift, OpenCode storage migration, and acpx provider-ID behavior.

### TUI-G-9B — Cloud research model selection

- Default managed-cloud research to `auto-smart` with `optimize_for=intelligence`.
- Before any explicit-model run, refresh the account's live model catalog and supported parameters.
- Present the recommended model first, then ask the owner to choose from currently available options.
- Record the requested model, parameters, resolved model/provider, usage, cost, and duration.
- If a selected model or required parameter is unavailable, stop and ask; never silently substitute.

Measured pilot:

- Composer 2.5 Hermes report: 322,491 ms, 13,096 output tokens, $0.6196646 charged.
- Fable 5.1 (`thinking=true`, `context=1m`, `effort=max`) Hermes report: 630,861 ms,
  33,906 output tokens, $13.50943049 charged.
- Fable was materially deeper but 1.96 times slower and 21.8 times more expensive in this A/B run.
- Four successful Composer research runs completed in 180–324 seconds for about $1.50 combined.
- One late-cancelled Composer run consumed 8.9M tokens and $1.86 without producing a terminal result;
  choose model policy before dispatch and do not treat cancelled work as a successful artifact.
- Managed-cloud execution added no persistent local agent-process working set in the pilot.
- My Machines worker startup remains blocked by a reproducible Cursor packaging mismatch:
  bundled Node ABI 137 versus bundled `better-sqlite3` ABI 127 in both 28.08 and 01.09 builds.
- Durable cloud agent (Fable 5.1, 1M, max) on a repo-repair task: 12 runs over 2h26m, 113.04 USD
  settled, 9 PRs merged and 2 closed, 14 branches deleted, all 8 `main` workflows green. A cloud
  agent's identity on GitHub is the owner's; merges, closes and deletions appear as owner actions.
  The cockpit must therefore show per-run cost as it settles, the agent's PR/branch actions as a
  live audit trail, and require an explicit owner gate before merge/delete classes of action.
- Cursor Cloud runs do not read `~/.cursor/mcp.json`; a cloud agent cannot observe local MCP
  discovery state, so local-integration diagnoses from cloud must be re-verified on the box.

### TUI-G-9C — Verbose cloud-worker observability

- Cloud workers receive the same first-class monitoring model as local subagents.
- Preserve and render provider-exposed thinking/reasoning events, assistant deltas, tool-call
  arguments and results, step boundaries, token deltas, usage/cost, workflow state, permissions,
  artifacts, failures, and terminal results.
- Show cloud workers in the same hierarchical agent/workflow tree, with lineage and execution host.
- Support drill-down from compact route/status bar to a fully verbose per-worker native-event view.
- Preserve raw native events in the dual-plane ledger while rendering normalized tool cards and
  summaries; collapsing UI content must never discard source events.
- Label reasoning visibility honestly as exposed summary, exposed trace, encrypted/opaque, or absent.
  Never label provider-emitted summaries as the model's complete private chain-of-thought.
- Provide pause, cancel, message, redirect, resume, attach, and artifact controls only when the
  runtime capability probe confirms them.
- A completed Fable cloud run replay proved 206 thinking events, 320 tool-call lifecycle events,
  3,747 rich interaction updates, step boundaries, partial tool arguments, and token deltas.
- Run a dedicated two-subagent cloud probe to verify child lineage, child progress, tools, and
  steering visibility before claiming parity with local subagent monitoring.

### TUI-G-9D — Side questions (`/btw`) as a first-class control

Scheduled 02.09.2026 (owner request). Prior art: Cursor CLI `/btw` (shipped April 2026; the
"internal blob error in long or compacted sessions" fix shipped in the 13.07.2026 release),
Claude Code `/btw`, Hermes `/btw` (read-only side question over a transcript snapshot), Codex
`/side` (ephemeral question that never contaminates the primary transcript).

- Provide `/btw <question>` in the universal TUI for every session type: local runtimes, cloud
  workers, subagents, and workflow nodes.
- Semantics: read-only; answers from a snapshot of the target session's visible context plus the
  cockpit ledger; never appended to the target session's history; never steers the running turn.
- Works mid-turn without interrupting or queueing work; runs on the same model/route as the parent
  by default with an explicit override; reuse the parent's cached prefix where the provider allows.
- Presentation: dismissible overlay/panel with streaming answer, `Esc` to close, scrollable,
  clickable links, working in minimal/linear terminal mode; answer optionally committed to the
  cockpit's own scrollback, never to the agent transcript.
- Reliability: retry on transient model overload; no dependence on session length (compacted or
  very long sessions must not break it); per-question cost/usage shown in the details drawer.
- For cloud workers: implement over the cockpit's mirrored event ledger plus a fresh one-shot model
  call, or a provider-side fork/snapshot where the adapter proves that capability; label which.
- Capability grading applies: if a runtime cannot provide a true read-only snapshot, offer the
  ledger-based variant and say so rather than silently sending a normal turn.

Observed defect to reproduce: in this Cursor CLI session (build 2026.08.28-50f0823, resumed,
extremely long, many background jobs) `/btw` was reported as not working properly. The July fix
is included in that build, so remaining candidates are resume/length-specific behaviour or a
regression fixed only in 2026.09.01-cd08a95. Discriminating test: `/btw` in a fresh short session
on the updated build, then in a resumed long session.

## Twenty-Agent Research Convergence

Status: all 20 original competitive, protocol, provider, workflow, UX, security, and architecture
lanes completed on 02.09.2026.

- Build a universal control plane/cockpit, not another proprietary agent loop.
- Use stable ACP v1 for current local agent sessions; design and feature-flag ACP v2 support.
- Preserve every native event beside normalized projections; unknown events become typed or opaque
  extensions and are never dropped merely to fit the canonical schema.
- Nori provides the strongest permissively licensed standalone ACP TUI architecture.
- acpx provides the strongest permissively licensed headless ACP session-owner, recovery, flow, and
  Windows named-pipe patterns.
- HAPI is the only inspected client implementing all five Cursor-specific ACP methods; because it is
  AGPL, reimplement the public wire semantics and tested nested outcome shapes clean-room.
- OpenCode is a strong host/reference with mature TUI, server, SDK, session, provider, and event
  layers, but currently acts as an ACP agent rather than a universal ACP client.
- Hermes contributes the strongest open-source patterns for nested delegation, live subagent
  steering, busy-input modes, multi-surface sessions, scheduling, and provider breadth.
- Pi contributes clean TUI/component and provider/event boundaries; Oh My Pi contributes hashline
  editing, LSP/DAP, persistent runtimes, Agent Hub, nested-agent observability, and rich RPC.
- Reuse runtimes through adapters; do not fork one fast-moving application as the whole product.
- Keep agent runtime, model provider, MCP tool, workflow engine, semantic memory, event ledger, and
  Agent Mail as distinct layers with explicit ownership.
- Support Hugging Face, OpenRouter, vendor-native APIs, and local runtimes through negotiated
  transport × wire × engine/model profiles.
- Never infer tool calling, reasoning, structured output, multimodality, context, or privacy merely
  from an OpenAI-compatible endpoint; probe effective capabilities per route.
- Use a dual-plane, event-sourced ledger with native raw records, reversible canonical projections,
  stable correlation IDs, replay cursors, content-addressed artifacts, and materialized views.
- Normalize approval presentation without erasing each protocol's distinct resolution mechanism.
- Expose compact status by default and full reasoning/tool/subagent/workflow telemetry on demand for
  both local and cloud execution.
- Adopt deterministic deny-precedence policy, external sandbox enforcement, scoped credentials,
  signed/pinned extensions, and tamper-evident audit events.
- Mine source-available or restrictive projects for interaction ideas only; reuse code only from
  compatible permissive components with notices preserved.

## Verified Research Findings

- Cursor Agent CLI supports native Windows and exposes an official ACP server.
- No third-party TUI currently proves full Cursor parity.
- Generic ACP clients preserve the real Cursor agent loop but commonly omit Cursor-specific blocking
  methods such as plan/question extensions.
- OpenCode cannot consume an external ACP agent with its installed command surface; `opencode acp`
  exposes OpenCode as an ACP server.
- OpenCode and Oh My Pi best match the requested non-Vim, inspectable daily UX.
- The oakimov provider gives translated Cursor Connect-RPC model/tool access, not a native Cursor
  Agent ACP session. It is young and uses undocumented protocol surfaces.
- Avante Zen is explicitly Neovim underneath and is disqualified as the primary daily interface.
- Nori and Toad are standalone ACP TUI candidates, but currently require or favor WSL and do not
  prove Cursor-extension parity.
- acpx is a strong headless ACP session/workflow layer, not a TUI, and no Cursor-specific planning
  extension handlers were detected.
- Managed Cloud Agents improve parallel throughput and isolation, but do not inherit the local
  harness automatically. My Machines can execute through the local harness when explicit worker
  directories and local tools are exposed.

## Current Shortlist

1. OpenCode daily TUI + explicit native Cursor CLI authoritative route.
2. Oh My Pi daily TUI + explicit native Cursor CLI authoritative route.
3. OpenCode or Oh My Pi with the oakimov Cursor provider as an experimental translated route,
   never mislabeled as full Cursor Agent parity.
4. Nori/Toad ACP route under WSL as an experiment if standalone real-agent fidelity outweighs
   Windows-native simplicity.
5. A future custom OpenCode ACP-client bridge only after mapping every unsupported Cursor extension
   and proving that no capability is silently dropped.

## Decision Queue

3. **RESOLVED:** Bake off OpenCode and Oh My Pi on identical read-only tasks.
4. **RESOLVED:** Prototype and improve the best-case Cursor integration in both bakeoff candidates.
5. **RESOLVED:** Build explicit Cursor Model and Cursor Agent modes in the winning TUI.
6. **RESOLVED:** Ship palette, slash commands, and dashboard from the first release.
7. **RESOLVED:** Compose the YAML registry, acpx, managed cloud dispatch, and a TypeScript adapter.
8. **RESOLVED:** Always show a compact route/status bar; expand full details on demand.
9. Product scope: universal agent cockpit with Cursor as the first adapter, or Cursor-focused TUI
   with a later universal control plane?
10. Windows boundary: native-only daily path or permit WSL for fidelity experiments?
11. Cloud split: which long workflows move to managed Cloud Agents, and how is the private harness
    packaged without copying secrets or machine-local state?
12. Acceptance bakeoff: which real tasks, latency/UX measures, and failure cases determine the winner?
13. Version/update policy: pinning, canary tests, and fail-closed behavior for unofficial bridges.
14. Rollout order and fallback behavior.
15. Portable session-envelope and typed handoff schema.
16. Runtime adapter capability negotiation and truthful degradation.
17. Universal event ledger and replay model.
18. Interactive subagent control: pause, message, redirect, cancel, fork, and resume.
19. Recursive delegation limits and agent-of-agent graph visualization.
20. Agent Mail identity, topic, contact, and file-lease integration.
21. Multi-model council/debate/consensus interaction model.
22. Cross-runtime artifact, worktree, and file-ownership coordination.
23. Human cockpit: agent graph, workflow DAG, live events, messages, costs, quotas, and blockers.
24. Local versus managed-cloud versus My Machines execution placement.

## Candidate Direction

Run a short, read-only local bakeoff between OpenCode and Oh My Pi before permanently choosing the
daily TUI. Keep native `cursor-agent` as the authoritative route during the bakeoff. Evaluate the
oakimov provider separately as an experimental translated route; do not make it the only path.
