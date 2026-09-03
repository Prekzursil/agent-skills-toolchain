# Lens 03 — Competitive teardown of coding-agent harnesses

Date: 29.08.2026  
Scope: Cursor, Claude Code, Codex, Goose, OpenCode, Aider, Gemini CLI, Grok Build,
Devin, OpenHands, Amp, Windsurf/Devin Local, Zed, Roo Code, and current adjacent
harnesses. Discovery only; no live configuration was edited.

## Executive result

The estate is not missing another general-purpose coding agent. It already has the
strongest common primitives: shared Agent Skills, MCP, hooks, subagents, worktrees,
event ledgers, TDD/coverage gates, a fail-closed completion doctrine, and an emerging
ACP/acpx automation plan. Installing Devin, OpenHands Agent Server, Amp, Windsurf,
Zed, Cline, Kilo, Continue, Pi, or mini-SWE-agent as another primary runtime would
mostly duplicate those capabilities and split the control plane.

The highest-value gaps are narrower:

1. **Gemini CLI's native recovery and policy surface is materially underused.**
   Skills are enabled and Gemini now natively discovers `~/.agents/skills`, but the
   estate has not verified vault discovery; checkpointing is still absent; and the
   local policy is a priority-999 wildcard `allow` across default, auto-edit, and
   YOLO modes.
2. **The estate lacks a branchable, two-plane checkpoint model.** Cline separates
   restoring files from restoring conversation state, while Pi stores an append-only
   session tree with `id`/`parentId`. Combining those mechanisms would improve
   recovery without adding a runtime.
3. **The automation suite still needs an explicit execution-environment contract.**
   OpenHands' `Workspace` abstraction is the clearest prior art for declaring local
   vs cloud, writable roots, network, secrets, sandbox, and teardown behavior.
4. **Cursor cloud protection is incomplete.** The live user-level
   `~/.cursor/hooks.json` does not travel to cloud agents. Cursor only loads
   repository/team/enterprise hooks in cloud VMs, and recent cloud goal/subscription
   features should be used instead of building a polling loop.
5. **The shared hot path should exploit native asynchronous hooks where semantics
   permit.** Claude Code now supports command, HTTP, MCP-tool, prompt, and agent hooks,
   including `async: true`; the estate still starts synchronous Python dispatch for
   several record-only lifecycle events.
6. **A compact codebase map is still useful on this RAM-constrained machine.**
   Aider's deterministic, cached, graph-ranked repository map remains valuable even
   though the Aider product itself is now maintenance-only.
7. **Runtime discovery needs executable evidence.** Grok's `inspect --json`, Gemini's
   skills listing, OpenCode's LSP/MCP status, and ACP connection probes can turn the
   existing hand-written cross-runtime scorecard into a post-sync conformance receipt.

## Evidence discipline

Evidence labels used below:

- **LOCAL-MEASURED** — read from this machine or obtained by invoking a local binary.
- **OFFICIAL-DOC** — current vendor documentation; proves a supported interface, not
  that this estate has configured or successfully exercised it.
- **PUBLIC-CODE/RELEASE** — repository metadata, source, or a dated release.
- **VENDOR-CLAIM** — announcement language not independently benchmarked here.
- **EXTERNAL-BENCH** — a public benchmark result, but not reproduced on this machine.

Marketing was not treated as measured capability. In particular, phrases such as
"long-running", "production-ready", "best models", and "works out of the box" are
reported only as vendor claims unless backed by a local probe or inspectable public
mechanism. GitHub stars are maintenance/adoption signals, not quality scores.

## Ground and dedup

Read before teardown:

- `CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`
- `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md`
- `docs/agentic-perfection/OPEN-THREADS.md`
- `C:\Users\Prekzursil\AGENTS.md`
- `WAVE-ABCD-EXECUTION_2026-08-27.md`
- `CROSS-RUNTIME-SCORECARD_2026-08-27.md`
- `AUTOMATION-SUITE-DECISIONS_2026-08-29.md`

Already built or absorbed, therefore not proposed as new:

- Cursor user hooks, Claude/Codex shared dispatcher hooks, lifecycle telemetry, the
  fail-closed/disk-provenance doctrine, MEL/tracer work, and the anti-degeneration
  exact-repeat plus pattern-repeat detector.
- Claude agent teams, subagents, worktrees, TaskCreated/TaskCompleted,
  SubagentStart/SubagentStop, TeammateIdle, WorktreeCreate/WorktreeRemove hooks.
- Codex native hooks, shell snapshot, workspace-write sandbox, Windows unelevated
  sandbox, multi-agent v2, apps, skills, memories, and the git-write exec-policy delta.
- Grok shared skills/rules bridge, ACP capability, explicit deny rules, and MCP setup.
- Cloud offload, scheduled automations, Bugbot/`codex review`, goal reinjection,
  focus-chain, `/rewind`/summarize/branch doctrine, per-hook ISR telemetry,
  verified-resume, skill lifecycle, and the deterministic runtime drift check are
  already built, planned, or named in the 27.08 queue.
- A second orchestration runtime, LangGraph/Temporal, another memory store, another
  vector database, another always-on daemon, Cursor BYOK, LiteLLM, and an OpenRouter
  MCP remain explicitly rejected.

### Local runtime inventory

`Get-Command` plus `--version` on 29.08.2026:

| Runtime | Local state |
|---|---|
| Cursor CLI | installed, `2026.08.28-e7f6d3b` |
| Claude Code | installed, `2.1.243` |
| Codex CLI | installed, `0.149.0-alpha.1` |
| Goose | installed, `1.47.0` |
| OpenCode | installed, `1.17.13` |
| Aider | installed, `0.86.2` |
| Gemini CLI | installed, `0.45.2` |
| Grok Build | installed, `1.0.5` |
| Devin, OpenHands, Amp, Windsurf, Zed | not found on `PATH` |
| Continue `cn`, Cline, Kilo, Pi, mini-SWE-agent | not found on `PATH` |

Additional local facts:

- Cursor hooks are present at user scope. They implement session memory checks,
  shell/MCP observation, subagent lifecycle logging, and edit logging. Cloud agents
  cannot read this user-level file.
- Codex has `multi_agent = true`, hooks and apps enabled, and a local maximum of eight
  concurrent subagent threads. Its shell environment inherits `"core"`.
- Claude has agent teams enabled and all major team/task/worktree lifecycle hooks
  wired into the shared dispatcher.
- Grok directly points at `.agents\skills` and `.agents\rules`; `grok inspect --json`
  is available but is not yet a standard post-sync receipt.
- Gemini has skills enabled, auto-edit as the default approval mode, `C:\` and `D:\`
  in sandbox-allowed paths, and a priority-999 wildcard `allow` policy. Checkpointing
  is not configured. Its separate generic memory MCP conflicts with the estate's
  basic-memory-only semantic-write rule.
- OpenCode and Aider are installed, but they are not primary estate runtimes.

## Product-by-product teardown

| Product | Current differentiated capability | Estate status and exact disposition | Maturity / evidence |
|---|---|---|---|
| **Cursor** | Cloud agents can subscribe to PR/Slack/schedule events, hold a goal, accept queued steering at the next tool boundary, spawn subagents in separate cloud VMs, and run repository hooks. Cloud environments can expose browser previews. | **NATIVE DELTA to an existing plan.** Do not build polling or local VM fan-out. When the already-planned cloud-offload trial runs, add a project `.cursor/hooks.json` that calls versioned project guards, use `/goal` plus PR subscription, and require a disk receipt from the cloud run. User-level hooks are local-only. | Commercial, rapid release cadence; current local build is dated 28.08. Official changelog through 27.08. Cloud autonomy claims are **VENDOR-CLAIM** until trialed. Confidence **high** on interfaces, **medium** on reliability. |
| **Claude Code** | Richest hook taxonomy in the set: command, HTTP, MCP-tool, prompt, experimental agent hooks; async command hooks; team/task/worktree events; isolated subagents and agent teams. | Most is **ALREADY BUILT**. The remaining action is a **NATIVE** async-hook audit: mark only proven record-only handlers async, leaving permission, completion, worktree, and provenance gates synchronous. | Public repo about 143k stars, pushed 28.08.2026; local 2.1.243. Agent teams remain research-preview despite being enabled locally. Confidence **high**. |
| **Codex** | Stable-by-doc multi-agent v2, native Windows sandbox, hook layers, shell snapshot, scheduled desktop tasks, cloud threads, app/connectors, and per-agent model/reasoning/sandbox controls. | Core surface is **ALREADY BUILT/ENABLED**. Add a **NATIVE low-RAM profile**, not a new runtime: local cap 2 spawned threads, read-only explorer/reviewer agents, existing eight-thread setting retained as an explicit high-capacity/cloud profile. This is a visible performance trade-off requiring owner selection. | Public repo about 120k stars, pushed 29.08.2026; local CLI is still labelled alpha. Docs call multi-agent v2 stable. Confidence **high** on mechanisms, **medium-high** on Windows reliability. |
| **Goose** | Reusable YAML recipes with parameters, extensions, retry, inherited `max_turns`, sub-recipes, sequential/parallel execution, and a local scheduler with session history. | Do **not** adopt Goose as a second scheduler. **BUILD/BORROW** its recipe budget and retry fields into the acpx registry schema. Verify native `.agents/skills` discovery before claiming skill parity; keep HTTP-only extensions and no Goose memory. | Redirected project `aaif-goose/goose`, about 54k stars, pushed 29.08.2026; local 1.47.0. Scheduler behavior is official-doc/code-backed. Confidence **high**. |
| **OpenCode** | Native `.agents/skills` discovery, pattern permissions, a deterministic `doom_loop` permission after three identical calls, optional LSP query tool, subagents, and a client/server API with session fork/abort/diff/status and SSE events. | `doom_loop` is **ABSORBED** by the stronger estate repeat detectors. **NATIVE TRIAL** the LSP tool only as an on-demand, read-only research leaf for one repo/language; no global auto-download and no resident server. Do not adopt its server as the control plane. | About 202k stars, pushed 29.08.2026; local 1.17.13. LSP/background-agent surfaces are explicitly experimental. Confidence **high** for stable permissions/server API, **medium** for LSP. |
| **Aider** | Deterministic cached repository map built from tree-sitter symbols and graph ranking; architect/editor split; automatic lint/test repair; exceptionally simple git-native interaction. | **NATIVE/BORROW only the repository map.** Run a pinned, isolated read-only map command on demand and save a hashed map artifact for research/planning. Do not switch the estate to Aider or copy its auto-commit behavior. | Local 0.86.2. Repo about 49k stars but last push 22.05.2026; last feature release 0.86.0 in Aug 2025 and patch 0.86.2 in Feb 2026. Stable but maintenance-only. Confidence **high** on repo-map mechanism, **high** on maintenance risk. |
| **Gemini CLI** | Native `~/.agents/skills` alias, link/list/reload commands, shadow-git checkpoints restoring both files and conversation, subagent-specific TOML policies, per-agent tool/MCP isolation, hooks, and extension-packaged agents/policies. | Largest underused **NATIVE** surface. First run `gemini skills list --all` and prove vault parity; if discovery fails, use `/skills link --scope user` to the canonical vault. Enable `general.checkpointing.enabled`. Replace the wildcard full-access policy with shared-rule-derived allow/ask/deny policy after a shadow trial. Preserve memory capability by replacing the generic memory MCP with basic-memory HTTP, not by simply deleting memory. | About 107k stars, pushed 29.08.2026; local 0.45.2. Skill alias and policy engine are current official docs; subagent architecture had preview releases before current docs. Confidence **high**. |
| **Grok Build** | `grok inspect --json` shows discovered instructions, skills, plugins, hooks, and MCPs; native ACP, headless JSON, worktrees, subagents, sandbox and deny rules; broad Claude/AGENTS compatibility. | Skills/rules are **ALREADY BRIDGED**. **NATIVE** action: make `grok inspect --json` one evidence source in the planned cross-runtime drift check. Keep experimental Grok memory off because basic-memory is SSOT. Review always-approve only through the owner-controlled policy wave. | Early beta announced May 2026, open-sourced July; about 26k stars, pushed 28.08.2026; local 1.0.5. High activity but short operating history. Confidence **high** on inspect/ACP, **medium** on maturity. |
| **Devin** | Isolated managed VMs, automations with event/schedule triggers, parallel managed sessions, playbooks with structured output, knowledge retrieval triggers, outcome analysis, metrics and v3 APIs. | **BUILD/BORROW**, do not subscribe merely for overlap. Add `structured_output_schema`, run insights, trigger provenance, and invocation limits to the local recipe schema. Basic-memory and `/self-reflect` remain the knowledge system. | Closed commercial service; v3 endpoints are documented as production. Product performance claims were not measured. Confidence **high** on API contract, **low-medium** on value for this estate without a trial. |
| **OpenHands** | Clean separation of Agent SDK, tools, `Workspace`, local/Docker/remote/cloud execution, event stream, security policies, skills at `.agents/skills`, and Agent Server APIs. | **BUILD/BORROW the Workspace contract**, not the server. Each recipe should declare executor kind, writable roots, network, secrets profile, sandbox, startup health, teardown, and artifact return. Do not add its local server or Docker daemon. | About 86k stars, pushed 28.08.2026; active SDK and release notes. The server calls itself production-ready, which remains a **VENDOR-CLAIM** here. Confidence **high** on architecture. |
| **Amp** | Plugin API can create agents/tools/modes, preserve `parentThreadID`, run async threads, and create durable webhook-driven orbs with signature checks, delivery deduplication, read-only wake-up, and persistent thread context. | **BUILD/BORROW** the event envelope and lineage fields into acpx/agent-mail; do not adopt Amp or hosted orbs. Require signature verification, source delivery ID, dedup receipt, read-only default, parent run ID, and explicit escalation before mutation. | Closed product, fast-moving. Neo/plugin permissions were still beta-paused in May 2026. Event-orb claims are official docs but untested locally. Confidence **medium-high** on API, **medium** on maturity. |
| **Windsurf / Devin Local** | Local worktree sessions with merge UI, hooks, skills, plugins/subagents in Devin Local, and a migration wizard from Cascade memories/workflows to skills. | **NO ADOPTION.** The estate already standardizes on `.agents/skills`, ACP, hooks, and worktrees. If Windsurf is ever installed, run the migration wizard once and export durable content to the canonical vault; do not enable a second memory layer. | Product is in a significant Cascade→Devin Local transition. Devin Local explicitly lacks Cascade memories/workflows. Confidence **high** on transition risk. |
| **Zed** | First-class ACP registry/UI, MCP forwarding to external agents, granular tool permissions, external-agent restart without restarting the editor, and explicit configuration-boundary documentation. | **REFERENCE/TEST, not primary adoption.** The acpx+Neovim decision stands. Add ACP conformance tests for reconnect, cancellation, resume, MCP forwarding, permission mediation, and token/checkpoint visibility; use Zed only as a comparison client if that plan fails acceptance. | About 89k stars, pushed 29.08.2026; weekly releases and recent Cursor ACP fixes show active development but also integration churn. Confidence **high**. |
| **Roo Code** | Historically offered modes, task orchestration, checkpoints, MCP and semantic indexing. | **SKIP.** Repository archived 15.05.2026 at v3.54.0. Do not install. If old Roo state exists, migrate to maintained Zoo Code or Kilo only if a real project requires that lineage. Never adopt Roo's Qdrant indexing because the estate bans another vector store. | Archived, no security fixes. Confidence **very high** from GitHub archive/release metadata. |

## Ranked enable/borrow queue

### 1. Prove and use Gemini's native Agent Skills alias

- **Tag:** NATIVE
- **Novelty:** correction to the 27.08 scorecard, which marked Gemini/Agy skills
  orphaned before current docs proved the `~/.agents/skills` alias.
- **Exact action:** run `gemini skills list --all`; compare names/count against the
  canonical vault. If the native alias is not discovered in local 0.45.2, use
  `gemini skills link --scope user C:\Users\Prekzursil\.agents\skills`, reload, and
  repeat the receipt. Do not copy 359+ skills.
- **Value × effort:** **very high × trivial**
- **Confidence:** **high**

### 2. Gemini recovery-and-policy correction

- **Tag:** NATIVE
- **Gap:** checkpointing is absent while writes are auto-edit and the highest-priority
  local policy allows every tool in every approval mode. The generic local memory MCP
  also violates the basic-memory-only writer rule.
- **Exact action:** in a later approved config wave, enable
  `general.checkpointing.enabled`; shadow-test a generated policy with read-only tools
  allowed, edits/shell asked or narrowly allowed, estate hard-denies enforced, and
  subagent/headless rules explicit. Replace generic memory with the existing
  basic-memory HTTP endpoint so capability is preserved. Re-run normal workflows
  before removing the wildcard rule.
- **Value × effort:** **very high × low-medium**
- **Confidence:** **high**
- **Caution:** this changes approval friction and therefore requires an explicit owner
  decision; it must not be applied as a silent reliability downgrade.

### 3. Branchable two-plane checkpoints

- **Tag:** BUILD, borrowing Cline + Pi
- **Gap:** current provenance distinguishes disk-verified from agent-claimed, but
  recovery remains mostly linear. Cline can restore files, task history, or both;
  Pi keeps immutable JSONL entries linked by `id`/`parentId`.
- **Exact action:** define the automation artifact schema with independent
  `workspace_state_ref` and `conversation_leaf_ref`, plus `event_id`, `parent_id`,
  `branch_id`, `source_session_id`, content hash, and provenance. Restore either plane
  without rewriting prior entries; append compaction summaries as children.
- **Value × effort:** **very high × medium**
- **Confidence:** **high**
- **Dedup note:** this implements, rather than re-proposes, the existing `/branch`,
  verified-resume, and G-18 artifact/checkpoint threads.

### 4. Explicit execution Workspace contract

- **Tag:** BUILD, borrowing OpenHands
- **Gap:** automation decision G-14 still asks which workflows may access local files,
  memory, credentials, browsers, and cloud.
- **Exact action:** require every recipe to declare:
  `executor_kind`, `workspace_root`, `writable_roots`, `network_policy`,
  `secrets_profile`, `browser_profile`, `sandbox`, `startup_probe`,
  `teardown_policy`, and `artifact_return`. Reject execution when the requested
  capability exceeds that envelope.
- **Value × effort:** **very high × medium**
- **Confidence:** **high**

### 5. Complete Cursor cloud protection with repo hooks and subscriptions

- **Tag:** NATIVE + small BUILD adapter
- **Gap:** local user hooks do not run in cloud VMs.
- **Exact action:** during the existing cloud-offload trial, place a thin,
  version-controlled `.cursor/hooks.json` in the test repository that invokes
  project-local guards; use `/goal` and the PR subscription instead of polling; require
  hook and final artifact receipts. Keep credentials/browser profile separate from the
  live owner profile.
- **Value × effort:** **very high × low-medium**
- **Confidence:** **high** on support matrix; **medium** on run reliability until trial.

### 6. Move record-only Claude hooks off the request path

- **Tag:** NATIVE
- **Gap:** the estate still pays Python startup synchronously on many lifecycle events.
- **Exact action:** classify every handler as `decision`, `injection`, or `record-only`.
  In a shadow wave, add `async: true` only to record-only handlers such as pure metrics;
  never async permission, TaskCompleted, Stop, worktree, or provenance gates. Compare
  event counts and p95 foreground latency before/after.
- **Value × effort:** **high × low**
- **Confidence:** **high** on native support; **medium-high** on Windows latency gain
  until measured.

### 7. Add executable cross-runtime conformance receipts

- **Tag:** BUILD, extending an already-planned drift checker
- **Exact action:** after shared-state sync, run read-only probes:
  `grok inspect --json`, `gemini skills list --all`, Codex hook/config inspection,
  OpenCode MCP/LSP status when active, Cursor hook schema/load status, and an ACP
  handshake/cancel/resume test. Emit counts, hashes, versions, and
  `disk-verified`/`agent-claimed` provenance. Warning-only until baselines are approved.
- **Value × effort:** **high × medium**
- **Confidence:** **high**

### 8. Use Aider's repo map as an on-demand context compressor

- **Tag:** NATIVE/BORROW
- **Exact action:** pin Aider 0.86.2 in an isolated invocation; generate a read-only
  repository map with a small token budget; record source commit, options, and output
  hash; inject it only into research/planning. If maintenance breaks on new parsers,
  vendor the Apache-licensed map component with tests rather than following the whole
  product.
- **Value × effort:** **high × low-medium**
- **Confidence:** **high**

### 9. Add event authenticity, deduplication, and run lineage

- **Tag:** BUILD, borrowing Amp event-driven orbs
- **Exact action:** every webhook/event-triggered recipe receives
  `source`, `delivery_id`, `signature_verified`, `received_at`, `parent_run_id`, and a
  replay/dedup decision. New external events start read-only; mutation requires the
  existing risk gate. Persist the event before launch.
- **Value × effort:** **high × medium**
- **Confidence:** **medium-high**

### 10. Add a native low-RAM Codex multi-agent profile

- **Tag:** NATIVE
- **Gap:** local config allows eight concurrent spawned threads despite the machine's
  known memory pressure.
- **Exact action:** add an owner-selectable low-RAM profile with two concurrent
  subagents and read-only explorer/reviewer definitions; retain the existing
  high-concurrency profile for remote/high-capacity execution. Record which profile a
  run used.
- **Value × effort:** **high × low**
- **Confidence:** **high**
- **Trade-off:** lower local breadth for stability; must remain selectable, not a
  silent global capability reduction.

### 11. Finalize one portable recipe capsule schema

- **Tag:** BUILD, borrowing Goose + Devin + Kilo
- **Exact action:** extend the acpx registry item with inherited `max_turns`, retry
  policy, execution mode, provider/model identity, cost/time cap, structured output
  schema, invocation limit, parent run, cancellation, resume pointer, and terminal
  receipt. Add a `roll-call` preflight that checks configured model routes and records
  latency without silently changing providers.
- **Value × effort:** **high × medium**
- **Confidence:** **high**
- **Dedup note:** directly closes automation open threads G-18/G-19 and the already
  resolved provider-health scheduling requirement.

### 12. Trial LSP as an on-demand read-only leaf

- **Tag:** NATIVE
- **Exact action:** for one typed repository, start only its already-installed language
  server, enable OpenCode's LSP tool for that process, allow read-only
  definition/reference/call-hierarchy queries, capture usefulness and RAM, then exit.
  No global server auto-download and no resident daemon.
- **Value × effort:** **medium × low**
- **Confidence:** **medium**, because OpenCode still labels the direct LSP tool
  experimental.

## Adjacent current harnesses

| Harness | Useful mechanism | Disposition |
|---|---|---|
| **Cline** | Local resumable tasks with cost/time history and independent Restore Files / Restore Task / Restore Both checkpoints. | Borrow the two-plane checkpoint semantics. Do not install another VS Code agent. |
| **Kilo Code** | ACP, session JSON import/export, `roll-call` model connectivity/latency tests, modes, skills, permission-first tools. | Borrow `roll-call` and portable run export into acpx. No primary adoption. |
| **Continue `cn`** | Unix-style headless final output with per-run `--allow`/`--ask`/`--exclude` and shared IDE/CLI config. | Already covered by acpx/Cursor headless and native policies. No action. |
| **Pi** | Append-only JSONL session trees, cheap in-place branches, explicit compaction entries, reloadable extensions. | Borrow the event/tree schema. Do not add Pi as another runtime. |
| **mini-SWE-agent** | Roughly 100-line core and public >74% SWE-bench Verified result. | Already the anti-overfit anchor. Use as a periodic baseline, not a production control plane. Result is **EXTERNAL-BENCH**, not locally reproduced. |
| **SWE-agent** | Inspectable action/observation trajectories and ACI research. | Maintenance-only and explicitly superseded by mini-SWE-agent. Borrow no new runtime. |
| **Zoo Code** | Maintained Roo successor with parent/child recovery, isolation, and destructive-command guard. | Mechanisms already exist in the estate. Consider only for migration from actual Roo state. |

## Do-not-adopt / prune conclusions

1. **Roo Code:** archived and receives no fixes.
2. **Aider as a primary runtime:** stable component source, but product cadence is
   maintenance-only.
3. **SWE-agent:** upstream itself recommends mini-SWE-agent.
4. **OpenHands Agent Server/Docker Workspace:** architecturally good prior art, but a
   resident server and Docker runtime violate the current no-new-daemon/RAM constraint.
5. **Devin, Amp or Cursor vendor memory as semantic SSOT:** duplicates basic-memory and
   violates the sole-writer rule.
6. **Windsurf Cascade memories:** legacy-only and not supported by the default Devin
   Local agent.
7. **Roo/Zoo semantic indexing with Qdrant:** explicitly conflicts with the estate's
   vector-store ban.
8. **OpenCode server, Goose scheduler, Continue CLI, Kilo orchestrator, Amp orbs as
   another control plane:** each duplicates the resolved acpx registry/serial-queue
   architecture.
9. **Unqualified auto-approve/YOLO:** several vendors advertise recovery as the safety
   net; recovery does not replace least privilege, deterministic denies, or the
   estate's no-force/no-secret rules.
10. **Cloud marketing as evidence:** no cloud agent was launched in this lens.
    Reliability, quota, secret handling, and browser isolation remain trial questions.

## Maintenance snapshot

GitHub API/release evidence gathered 29.08.2026:

- Active same-day or previous-day: Claude Code (~143k stars), Codex (~120k), Goose
  (~54k), OpenCode (~202k), Gemini CLI (~107k), Grok Build (~26k), OpenHands (~86k),
  Zed (~89k), Cline (~67k), Kilo (~27k), Continue (~36k), Pi (~99k).
- Aider: ~49k stars, last repository push 22.05.2026; maintenance-focused.
- Roo Code: archived 15.05.2026 at v3.54.0.
- SWE-agent: maintenance-only; mini-SWE-agent is the upstream-recommended successor.

These counts are only directional maintenance signals and should not be used to choose
an agent or model.

## Sources

Accessed 29.08.2026 unless dated in the page:

### Named products

- Cursor: [Cloud Agents and harness improvements](https://cursor.com/changelog/08-19-26),
  [latest changelog](https://cursor.com/changelog),
  [Automations](https://cursor.com/docs/cloud-agent/automations),
  [Hooks and cloud support matrix](https://cursor.com/docs/hooks).
- Claude Code: [Hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks),
  [subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents),
  [Desktop](https://docs.anthropic.com/en/docs/claude-code/desktop),
  [Opus 4.6 / agent-teams announcement](https://www.anthropic.com/news/claude-opus-4-6).
- Codex: [changelog](https://developers.openai.com/codex/changelog),
  [subagents](https://developers.openai.com/codex/subagents),
  [Windows sandbox](https://developers.openai.com/codex/windows/windows-sandbox),
  [scheduled tasks](https://developers.openai.com/codex/app/automations),
  [advanced configuration](https://developers.openai.com/codex/config-advanced).
- Goose: [recipe reference](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/recipes/recipe-reference.md),
  [session recipes and scheduler](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/recipes/session-recipes.md),
  [CLI commands](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/goose-cli-commands.md).
- OpenCode: [agents](https://opencode.ai/docs/agents/),
  [permissions](https://dev.opencode.ai/docs/permissions/),
  [skills](https://opencode.ai/docs/skills/),
  [LSP](https://opencode.ai/docs/lsp/),
  [server API](https://opencode.ai/docs/server/).
- Aider: [repository map](https://aider.chat/docs/repomap.html),
  [modes](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/usage/modes.md),
  [release history](https://github.com/Aider-AI/aider/releases),
  [v0.86.0](https://github.com/Aider-AI/aider/releases/tag/v0.86.0).
- Gemini CLI: [Agent Skills](https://geminicli.com/docs/cli/skills/),
  [checkpointing](https://geminicli.com/docs/cli/checkpointing/),
  [policy engine](https://geminicli.com/docs/reference/policy-engine/),
  [subagents](https://geminicli.com/docs/core/subagents/),
  [extension reference](https://geminicli.com/docs/extensions/reference/).
- Grok Build: [overview](https://docs.x.ai/build/overview),
  [CLI reference](https://docs.x.ai/build/cli/reference),
  [subagents](https://docs.x.ai/build/features/subagents),
  [worktrees](https://docs.x.ai/build/features/worktrees),
  [permissions](https://docs.x.ai/build/features/permissions),
  [open-source announcement, 15.07.2026](https://x.ai/news/grok-build-open-source).
- Devin: [advanced capabilities](https://docs.devin.ai/work-with-devin/advanced-capabilities),
  [scheduled sessions/automations](https://docs.devin.ai/product-guides/scheduled-sessions),
  [knowledge](https://docs.devin.ai/product-guides/knowledge),
  [API release notes](https://docs.devin.ai/api-reference/release-notes),
  [v3 overview](https://docs.devin.ai/api-reference/overview).
- OpenHands: [SDK architecture](https://docs.openhands.dev/sdk/arch/overview),
  [SDK package](https://docs.openhands.dev/sdk/arch/sdk),
  [skills](https://docs.openhands.dev/overview/skills),
  [cloud workspace](https://docs.openhands.dev/sdk/guides/agent-server/cloud-workspace),
  [release notes](https://docs.openhands.dev/enterprise/release-notes).
- Amp: [Owner's Manual](https://ampcode.com/manual),
  [custom agents](https://ampcode.com/news/custom-agents),
  [event-driven orbs](https://ampcode.com/news/event-driven-orbs),
  [Plugin API](https://ampcode.com/manual/plugin-api),
  [Amp rebuilt / Neo caveats](https://ampcode.com/news/neo).
- Windsurf/Devin Local: [Devin Local](https://docs.windsurf.com/windsurf/devin-local),
  [memories and rules](https://docs.windsurf.com/windsurf/cascade/memories),
  [Cascade overview](https://docs.windsurf.com/windsurf/cascade/cascade).
- Zed: [external agents / ACP](https://zed.dev/docs/ai/external-agents),
  [tool permissions](https://zed.dev/docs/ai/tool-permissions),
  [Agent Panel](https://zed.dev/docs/ai/agent-panel),
  [August 2026 stable releases](https://zed.dev/releases/stable).
- Roo Code: [archived repository](https://github.com/RooCodeInc/Roo-Code),
  [releases](https://github.com/RooCodeInc/Roo-Code/releases).

### Adjacent harnesses

- Cline: [tasks](https://docs.cline.bot/core-workflows/task-management),
  [checkpoints](https://docs.cline.bot/core-workflows/checkpoints).
- Kilo Code: [CLI](https://kilocode.ai/docs/cli),
  [tool permissions](https://landing.kilocode.ai/docs/basic-usage/how-tools-work).
- Continue: [CLI](https://docs.continue.dev/guides/cli).
- Pi: [session format](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/session-format.md),
  [sessions](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/sessions.md).
- mini-SWE-agent: [overview](https://mini-swe-agent.com/latest/),
  [official repository](https://github.com/SWE-agent/mini-swe-agent).
- SWE-agent: [ACI](https://swe-agent.com/latest/background/aci/),
  [trajectories](https://swe-agent.com/latest/usage/trajectories/).
- Zoo Code: [project](https://www.zoocode.dev/),
  [Roo migration](https://docs.zoocode.dev/roo-to-zoo-migration).

UNIT-COMPLETE: lens-03
