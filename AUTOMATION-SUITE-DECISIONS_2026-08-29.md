# Cursor Automation Suite — Extensive Grill Decision Log

Date: 29.08.2026  
Status: IN PROGRESS  
Modes: expansion, modification, modernization, better-ideas, red-team, simplification, prioritization

## Goal

Define an auditable command-line and Cursor-integrated automation system for research, ideation,
decision-making, optimization, implementation, verification, security review, and recovery.
The grill produces decisions only; implementation follows later gates.

## Verified Baseline

- Fabric version: 1.4.470.
- `fabric` with no prompt or stdin is non-interactive and can legitimately return no output.
- `fabric -setup` is parsed as short flags; `fabric --setup` or `fabric -S` is correct.
- Fabric strategy configuration incorrectly uses an absolute local repository path where the
  repo-relative `data/strategies` folder is required. `fabric --liststrategies` finds none.
- Live Fabric inference probes currently fail: OpenRouter 402, Anthropic 401, OpenAI 401,
  Gemini 404. Therefore no working default model is proven.
- Provisional post-repair Fabric default: `qwen/qwen3-coder-next`; high-stakes override:
  `anthropic/claude-sonnet-5`; cheap bulk override:
  `qwen/qwen3-coder-30b-a3b-instruct`.
- The prior-session recommendation was the distinct Hugging Face checkpoint
  `huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated`, not Fabric's base Qwen model.
- Cursor CLI build: `2026.08.28-e7f6d3b` (current local install).
- Windows Terminal is active and output encoding is UTF-8; poor appearance is not explained by
  stale codepage or raw conhost.
- Command collision: `agent` resolves to Grok CLI 1.0.5; `cursor-agent` resolves to Cursor CLI.
- Cursor's official ACP surface can support a custom or Neovim terminal frontend while retaining
  Cursor authentication, models, tools, sessions, permissions, and MCP.
- Estate constraints: one local `cursor-agent`, no worker under 8 GB free RAM, Basic Memory remains
  enabled, no credential rotation, no silent capability downgrade, completion requires disk evidence.

## Candidate Portfolio (24)

### Intake and evidence
1. Start-task intent router
2. Multi-source deep research
3. Brainstorm concept matrix
4. Extensive decision grill

### Decisions and review
5. Provider-native multi-model council
6. Design-review gate
7. Plan-review gate
8. Evidence-citing advisory judge
9. Security/threat-model review

### Planning and execution
10. Work-unit/dependency decomposer
11. TDD red-green loop
12. Dual-model builder/verifier split
13. Isolated experiment/worktree runner
14. Metric-driven autoresearch loop

### Deterministic verification
15. Coverage SSOT enforcer
16. Static analysis and secret scanner
17. Scope-boundary guard
18. Disk-artifact provenance validator

### Delivery and continuity
19. CI/PR shepherd
20. Self-reflect knowledge capture
21. Basic Memory decision/research capture
22. Compaction/recovery reloader
23. Agent/process/RAM queue guard
24. Run monitor, quota breaker, and resumable status

## Decision Queue

1. **RESOLVED:** Primary product is a unified on-demand launcher/registry.
2. **RESOLVED:** Primary success metric is research/evidence quality.
3. **RESOLVED:** acpx automation runtime plus Neovim/Avante Zen interactive ACP TUI.
4. **RESOLVED:** Eliminate generic `agent`; use explicit product and bridge command names.
5. **RESOLVED:** Preserve the 24-recipe roadmap; stage six validated core recipes first.
6. **RESOLVED:** Assign execution mode per recipe risk and interaction needs.
7. **RESOLVED:** Adaptive multi-model breadth: three minimum, no fixed maximum.
8. **RESOLVED:** Hybrid domain router with intensity and distribution previews.
9. **RESOLVED:** Fabric is a pattern/strategy engine behind the registry.
10. **RESOLVED:** Use an adaptive recursive workflow graph with durable phase artifacts.
11. **RESOLVED:** Evidence-first, risk-tiered approval with advisory LLM judges.
12. Workflow engine: acpx-only, LangGraph layer, or LangGraph as an isolated leaf?
13. Autoresearch boundary: which explicit metrics and repositories qualify?
14. Local/cloud split: which workflows may access local files, memory, credentials, and browsers?
15. Security boundary: defensive-only unattended workflows and owner-present dual-use workflows?
16. Browser policy: agent-persistent default with mandatory per-run profile selection?
17. Hook policy: deterministic hot-path checks only versus LLM hooks?
18. Artifact and checkpoint schema: where runs, hashes, provenance, cost, and resume state live?
19. Budget policy: per-run cap, daily cap, provider fallback, and failed-to-run semantics?
20. Rollout sequence: foundations, research/decision lanes, build lanes, then optimization?
21. Acceptance criteria: what proves the suite is better than invoking existing skills directly?

## Resolved Decisions

### G-1 — Primary product

- One unified on-demand launcher/registry is the control plane.
- Cursor slash commands are aliases into the registry, not separate implementations.
- Heavy runs execute through a serial queue.
- The candidate portfolio remains available as recipes; it is not an always-on daemon fleet.

### G-2 — Success metric

- Optimize first for research and evidence quality, even when delivery is slower.
- Score source authority, independent corroboration, full-text reading, citation reproducibility,
  uncertainty disclosure, and claim-to-source coverage.
- Disk verification remains a mandatory validity gate, not the optimization target.
- Time, monetary cost, and automation breadth are secondary telemetry.

### G-3 — Terminal experience

- Use acpx as the headless orchestration/runtime layer for sessions, queues, flows, permissions,
  JSON events, cancellation, and resumability.
- Use Neovim with Avante Zen Mode as the polished interactive terminal UI over Cursor ACP.
- Invoke the locally verified `cursor-agent acp` backend; do not rely on the shadowed `agent` name.
- Keep native `cursor-agent` as the minimal fallback.
- Do not adopt codeye as a foundation unless its maturity and maintenance signals improve.

### G-4 — Command names

- Grok's canonical command is `grok`.
- Cursor's canonical command is `cursor-agent`.
- Cursor-backed proxy commands use explicit names: `cursor-grok`, `cursor-claude`,
  `cursor-codex`, and the same pattern for future bridges.
- Do not let any product claim the ambiguous generic `agent` command.
- ACP configuration invokes `cursor-agent acp` explicitly.
- Preserve every provider capability while removing PATH ambiguity.

### G-5 — Portfolio rollout

- Keep all 24 candidate recipes in the authoritative roadmap.
- Implement and expose six core recipes first to validate the shared registry, lifecycle,
  artifacts, permissions, queue, and terminal surfaces.
- Unimplemented recipes remain visibly planned but cannot be invoked.
- Expand based on measured research quality and operational value, not recipe count.

### G-6 — Execution policy

- Interactive/on-demand: extensive grill, decision council, browser runs, and approval gates.
- Explicit background through one serial queue: deep research, read-only audits, and report synthesis.
- Scheduled lightweight checks only: provider health, RAM/process guard, CI status, and cache staleness.
- Split mode: CI/PR triage may monitor automatically; mutations require an owner-triggered run.
- Owner-present only: autoresearch, git writes/resets, credential-bearing flows, live-profile browser,
  and dual-use security tooling.
- Every recipe declares its allowed execution modes in registry metadata.

### G-7 — Multi-model breadth

- Every multi-model run starts with at least three genuinely independent voices.
- Five voices are a useful standard starting point, not a mandatory count.
- There is no fixed maximum of ten; add as many voices as the decision or evidence gap needs.
- Stop expansion when additional voices no longer add a distinct source index, expertise lens,
  material dissent, or uncertainty reduction.
- Record model/provider identity and independence assumptions for every voice.
- Respect the one-local-Cursor-process rule; use provider-native remote fan-out or serialized turns.

### G-8 — Model routing and run intensity

- At run start, ask for `small`, `medium`, `high`, or `limitless` intensity.
- Small, medium, and high are situation-dependent throttles, not exact agent counts.
- Limitless deliberately exceeds normal saturation and exhausts planned lenses/corroboration paths;
  it minimizes uncertainty but cannot guarantee absolute certainty.
- Before execution, preview the selected distribution: voice count, roles, lanes, models, and providers.
- Route by domain fit while balancing reasoning quality, latency, refusal tendency, tool/JSON
  reliability, availability, and cost.
- Moving `latest` aliases may nominate current candidates, but each run resolves and records concrete
  model/provider IDs for reproducibility.
- Permit explicit per-run overrides.
- Fallbacks are policy-controlled, visible, and logged; never silently downgrade or change model family.

### G-9 — Fabric role

- Fabric provides reusable prompt patterns and prompting strategies; it is not the agent orchestrator.
- acpx/Cursor owns agent sessions, tools, permissions, queues, and lifecycle.
- Add a process-local Cursor-backed Fabric wrapper later; do not globally repoint provider settings.
- Repair the strategy source to `data/strategies` and prove a working inference route before the
  Fabric recipe is exposed.
- Leave Fabric's default model unset while every configured provider fails live preflight.

### G-10 — Adaptive research and decision graph

- Workflows are composable directed graphs, not fixed linear recipes or opaque mega-runs.
- Research, brainstorm, grill, council, synthesis, refutation, and targeted re-research may occur
  in different orders and may recur when evidence or critique exposes a gap.
- Council and grill may both choose what to research and decide among researched options.
- Each node may use different vendors/models through provider-native lanes.
- Every phase emits a durable artifact and checkpoint before another phase builds on it.
- Design and implementation enter independent adversarial repair/re-review loops until approved
  or a concrete blocker is surfaced.
- After implementation, wire/integrate, rerun deterministic verification, then obtain a fresh
  adversarial review against the original requirements and evidence.
- Complexity is permitted where it raises evidence quality; unverifiable monolithic runs are not.

### G-11 — Approval semantics

- Deterministic gates run first against the final artifact/revision; any failed, missing, stale,
  interrupted, untrusted-source, or budget-aborted required check blocks.
- Use a blinded core panel of three cross-family, role-diverse reviewers for conformance,
  defect/security, and regression/evidence review.
- Small/medium/high/limitless extra voices are evidence scouts, not additional approval votes.
- LLM and agent judges remain advisory. A potentially blocking finding gains authority only when
  an independent execute-to-confirm step reproduces it and records a disk-verified receipt.
- One reproduced blocker cannot be outvoted. Material disagreement after one focused rebuttal or
  repair round escalates instead of accumulating debate rounds.
- R0 reversible internal work may clear automatically when all receipts pass and no material
  subjective residue remains.
- R1 protected merge requires an independent human/CODEOWNER covering the final revision.
- R2 sensitive code/policy requires a second independent human with security or separation-of-duty
  responsibility.
- R3 deploy/publication/irreversible action requires an accountable deployer or domain expert
  distinct from the author/merger.
- Overrides are explicit, time-bounded, reasoned, and audited; the failing actor cannot self-override.
- Full evidence and source rationale: `RESEARCH-APPROVAL-GATES_2026-08-29.md`.

## Research Notes

Six independent model/role scouts converged on:

- Use one registry/router rather than 24 unrelated implementations.
- Keep deterministic safeguards as hooks/scripts and expensive reasoning as on-demand workflows.
- Do not make all 24 automations always-on; serialize heavy work.
- Preserve independent dissent; more voices do not automatically improve confidence.
- A better terminal experience requires persistent run state, artifacts, cancellation, resume,
  provider/model visibility, and plain/JSON modes—not merely more color.
- Consensus research warns that nominal panel size badly overstates independent evidence when
  models share providers, prompts, training data, or failure modes.
- G-11 must distinguish exploratory breadth from approval authority: extra voices may discover
  issues, but cannot manufacture confidence through voting.
- Candidate approval semantics pending remaining lanes: deterministic evidence outranks opinion;
  one reproducible blocking finding cannot be outvoted; unresolved disagreement escalates.
- Software-delivery standards separate analysis from authority: agent reviewers and scanners may
  clear internal workflow loops, while protected merge/release requires independent trusted-human
  review of the final revision plus deterministic control-plane checks.
- Risk-tier approval must be explicit; sensitive code, policy/CI configuration, and production
  deployment require stronger separation of duties than documentation or advisory research.
- Missing, stale, aborted, or untrusted-source checks are blocking—not implicit passes.

