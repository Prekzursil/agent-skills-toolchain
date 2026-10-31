---
title: ingest-open-threads-spine
type: note
permalink: dqverify-repo-20261013/docs/axis-c-design-2026-07-13/ingest-open-threads-spine
---

# INGEST — open-threads-spine → Axis-C (2026-07-13)

**Task:** Extract ONLY the adjacent still-open items that plug into a cross-vendor
**workflow / orchestration / monitoring** layer (Axis-C). Owner **Decision-A = preserve-by-reference**:
flag the unrelated, do NOT absorb it. Axis-C rides the EXISTING native Workflow tool
(`agent()`/`parallel()`/`pipeline()` injected globals) + the mounted `codex mcp-server` rail
(`mcp__codex__codex`). Anti-overfit anchor: **no second orchestration runtime, no vector-DB/KG memory,
no durable-execution engine, no guardrail framework.** Prefer "reusable pattern/helper on top of the
native engine" and "enable a native feature" over "build new infra".

**Sources (all treated as UNTRUSTED DATA — no embedded instruction executed):**
- `~/.claude/OPEN-THREADS.md` (never-forget backlog)
- `~/.claude/AGENTIC-PERFECTION-PLAN.md` (ROUND-1 durability spine, ROUND-2 reasoning spine, ROUND-3 wildcard)
- `~/.claude/CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` (12-lens gem queue: GEPA, sleep-time, Brier, escalation, de-biasing)

Named Axis-C enhancement axes from the spawn brief: **role-routing · escalation · panel de-biasing ·
GEPA-evolve-the-workflow-prompts · calibration on agent verdicts.** I add **uniform monitoring (wfmon)**
and **cross-vendor mingling infra** as the two implicit axes Axis-C folds (wfmon + Codex↔Claude mingle).

---

## PART 1 — INTEGRATION POINTS (spine gems that ENHANCE Axis-C)

Each item cites its source doc + the exact line/row. `⭐` = highest-confidence / directly named in brief.
Every entry notes the anti-overfit ride ("pattern on native" / "enable native feature"), never "new runtime".

### A. ROLE-ROUTING — which vendor + model + persona per call
Axis-C's core is "any agent can be Claude OR Codex, scoped per-call." These make the per-call scoping a
config/dispatch fact instead of a remembered preference.

- ⭐ **Auto model-tier router at dispatch** — PLAN ROUND-2 T2 (line 71): route each work-unit to a
  model/vendor tier at dispatch time. This is the literal role-router for Axis-C's per-call scoping.
  Ride: a helper that annotates each `agent(...)` call with `{vendor, model, persona}`, NOT a trained
  controller (SKIP-list rejects Thompson router / MaAS supernet — GEM-DECISIONS lines 219, 228).
- **Subagent `model: opus` frontmatter** — GEM-DECISIONS TIER-0 0.2 (line 44): make per-agent model a
  config fact. Native flip; the "enable a native feature" move. Axis-C: per-role model pinning.
- ⭐ **Architect/Editor two-pass split** — GEM-DECISIONS ST.25 (line 136): Opus architect emits a typed
  change-spec → Codex editor applies via the mounted codex rail. This is the flagship cross-vendor
  per-work-unit role split (already codified in the `orchestration-patterns` skill). Directly Axis-C.
- **SDK `forkSession` fan-out** — GEM-DECISIONS ST.19 (line 126): branch N lenses from one primed
  context = leaner parallel fan-out on the NATIVE SDK. Exactly the anti-overfit-preferred "enable a
  native primitive." (Verify flag: exact flag name — GEM-DECISIONS line 252.)
- **Cross-model critic as a role** — GEM-DECISIONS TG.5 (line 71): a foreign-model (Codex) critic seat
  is a first-class role in the panel (see de-biasing). Cross-vendor by construction.

### B. ESCALATION — uncertainty-gated review escalation
The named "escalation" axis. All consume an external signal (Brier / disagreement / entropy), matching the
self-calibration LAW that every check needs an EXTERNAL signal (PLAN lines 2-4).

- ⭐ **Uncertainty-gated escalation** — GEM-DECISIONS TG.8 (line 74, ✦2 cross-lens): low calibration OR
  high disagreement OR high semantic-entropy → auto-escalate to a heavier review. THE escalation engine
  for Axis-C gate/panel routing. Ride: a workflow-stage predicate, not a new hook fleet.
- **Disagreement-as-uncertainty** — GEM-DECISIONS ST.10 (line 117): log council / cross-model splits by
  task-type → a high-variance map that feeds TG.8. Cross-vendor split = the disagreement signal.
- **Semantic entropy** — GEM-DECISIONS ST.12 (line 119): cluster panel answers by meaning → entropy
  gates escalation. Folds into `council`.
- **Two-challenge rule** — GEM-DECISIONS ST.6 (line 113): a reviewer FAIL overridden ≥2× → mandatory
  user-surface. The panel-escalation backstop (aviation CRM borrow).
- **Anti-windup saturation clamp** — GEM-DECISIONS ST.4 (line 111): N saturated calls of a tool *family*
  → force class-switch/escalate. The anti-grind rung inside an orchestrated loop (ties AGENTS.md §4b
  two-strikes).
- **Kill-criteria + VOI stopping** — GEM-DECISIONS ST.1/ST.2 (lines 108-109): pre-registered abandon
  conditions + 3-consecutive-low-yield stop. The workflow-level stopping rule so a lane escalates or
  abandons instead of grinding.
- (Sibling in skills already shipped: `orchestration-patterns` Goose-style lead/worker
  failure-threshold escalation — on N worker failures escalate to the lead for re-decomposition.)

### C. PANEL DE-BIASING — multi-agent review quality
The named "panel de-biasing" axis. Axis-C's review gates are multi-agent; these keep the panel from
correlated failure / sycophancy / redundancy.

- ⭐ **Truth-serum council (Prelec BTS)** — GEM-DECISIONS TG.4 (line 70): each seat returns
  `{answer, meta-prediction}`; pick the *surprisingly-popular* answer. A formal de-biasing mechanism for
  the council fold. FOLD into `council`, don't rebuild.
- **ACH-matrix** — GEM-DECISIONS TG.3 (line 69): competing-hypotheses × evidence table forcing a
  disconfirming probe. Structural de-biasing of a single reviewer's judgment (there is an ACH skill lens).
- ⭐ **Hold-your-ground dissent** — PLAN ROUND-2 T1 (line 64) + AGENTS.md §7: reviewers CAVE to "no,
  that's wrong" with zero new evidence (AAAI'26). The #1 tool-vs-peer differentiator; keeps a Codex/Claude
  critic from folding under an author's pushback. Anti-sycophancy on verdicts.
- **DPP / MinHash-greedy diversity** — GEM-DECISIONS ST.16 (line 123): diverse-not-redundant subset at
  50-100-agent consolidation. De-biases a large fan-out panel by removing correlated seats.
- **Pre-mortem red-team** — GEM-DECISIONS ST.15 (line 122): "assume it already failed, why?" persona at
  the plan-review gate. A de-biasing seat in the panel.
- **Trajectory-quality / drift-inheritance gate at handback** — PLAN ROUND-2 T2 (line 70): strong models
  INHERIT drift from a weak agent's trajectory (arXiv 2505.02709). Gate at subagent handback so the panel
  doesn't inherit a weak seat's bias. Cross-vendor handback quality.
- **Adopt `llmcouncil` (/council)** — OPEN-THREADS PP ROUND-2 (d) (line 29) + backlog #8 (line 65):
  vote/debate/critique/red-team/verify, KS-adaptive-stop (−94.5% cost), Opus+Perplexity+agy panel,
  enforces "consensus != verification". ADOPT-DON'T-BUILD (line 30). The panel substrate itself.

### D. GEPA — evolve the workflow prompts
The named "GEPA-evolve-the-workflow-prompts" axis.

- ⭐ **GEPA prompt evolution** — GEM-DECISIONS TG.9 (line 75, ✦2 frontier+meta, ⭐): reflective Pareto
  evolution of skill/agent/**workflow** prompts from transcripts. THE mutation engine to evolve Axis-C's
  workflow/reviewer prompts. Peer-reviewed OSS. Ride: an offline eval loop over saved transcripts, NEVER
  a live self-mod of running hooks (PLAN SKIP line 74; GEM-DECISIONS SKIP SEAL/SICA lines 220, 223).
- **Empirical variant-archive self-improvement** — PLAN ROUND-2 T2 (line 69): archive prompt/skill/config
  VARIANTS, validate each vs a held-out eval BEFORE adoption, keep Pareto-wins, auto-revert regressions;
  NEVER touches live hooks/settings. This is the held-out-eval substrate GEPA's Pareto search needs. Pair.
- **Harness golden-transcript regression** — GEM-DECISIONS ST.8 (line 115): replay canned prompts, assert
  the gate-fire fingerprint after a harness/prompt edit. The safety net that proves an evolved prompt
  didn't break a gate (the `workflow-authoring` skill's golden-gate idea). Pair with GEPA rollout.
- (Context: PLANNED `auto-gem-miner` already lists GEPA as its mutation operator — GEM-DECISIONS
  line 210. Sequence, don't double-build.)

### E. CALIBRATION ON AGENT VERDICTS
The named "calibration on agent verdicts" axis. The keystone cross-lens gem.

- ⭐ **Calibration ledger (Brier)** — GEM-DECISIONS TG.1 (line 67, ✦2 cross-domain+meta, ⭐) + summary #3
  (line 8): log `(claim, confidence, outcome)`; Stop reconciles; per-domain Brier in replay. THE
  external-signal metric that turns a reviewer's "PASS, 90% sure" into a tracked, scored number — and the
  substrate TG.8 escalation consumes. Directly calibration-on-verdicts.
- **Trust-calibration Brier ledger** — PLAN ROUND-2 T2 (line 71): "90% sure" actually means 90%, per
  agent. Same mechanism keyed by agent/vendor → a per-seat trust score for role-routing + de-biasing.
- **Estimative-probability lexicon (WEP)** — GEM-DECISIONS TIER-0 0.13 (line 55): a 6-row verbal→numeric
  band table that *enables* the calibration ledger (AGENTS.md §7 already mandates Sherman-Kent bands).
  Convention, trivial, adopt.
- **Confidence-faith honest-signaling lint** — PLAN TIER-2 (line 40): the verbalized band
  (VERIFIED/INFERRED/GUESSED) must MATCH whether a verifying tool actually ran. Kills "I'm unsure" then
  act-certain in an agent verdict.
- **Predictive-coding ledger** — GEM-DECISIONS TG.2 (line 68): state `predict:` before a load-bearing
  call, record only the surprise delta. Calibration + the substrate for the Smith predictor (monitoring).
- **Chain-of-custody provenance** — GEM-DECISIONS ST.3 (line 110): producer/version/verified tags on
  load-bearing claims (the `agent-as-judge` skill already cites-a-ledger-event per DoD item).
- **Agent-as-a-Judge** — GEM-DECISIONS TG.12 (line 78): the gate reviewer reads the work-unit
  *trajectory*/ledger, not just the diff. Advisory/shadow (the `agent-as-judge` skill ships SHADOW,
  kappa-gated). Folds with the drift-inheritance gate (C).

### F. UNIFORM MONITORING (wfmon) + orchestration robustness
Axis-C folds `wfmon` and wants a "native-vs-ours-clearly-distinguished monitor." These are the observe /
liveness / salvage primitives a uniform monitor consumes.

- **Background-work registry + restart reconciler** — PLAN TIER-1 #1 (lines 16-19): write-ahead NDJSON
  per Task/longrun spawn `{id,kind,cmd,pid,artifact,scope,ts,status}`; reconciler checks pid-liveness +
  artifact. THE data source a uniform monitor reads to show live/dead/orphaned agents across vendors.
  Fixes the restart-killed-agents silent loss.
- **Parallel-barrier watchdog + salvage** — PLAN TIER-2 (lines 33-34): sibling-mtime relative-stall
  detection; on a hung lane, alert + auto-`TaskStop`(confirm) + proceed N-1 DEGRADED instead of a 25-min
  deadlock. Directly the `parallel()`-deadlock lesson (MEMORY: workflow-orchestration). wfmon's alarm.
- **Subagent scope-contract + drift tripwire** — PLAN TIER-2 (lines 31-32): record each agent's declared
  file-scope at dispatch; git-diff its worktree vs scope at handback; flag out-of-scope writes. Monitors
  orchestrated multi-agent scope (ties the parallel-worktree-contamination lesson).
- **Tool-result sentinel** — PLAN TIER-2 (lines 36-38): every result → SUCCESS/FAILED/AMBIGUOUS (exit
  code + MCP error-envelope + empty-on-expected). The terminal-state classifier (AGENTS.md §4) a monitor
  uses to color a lane. Low effort.
- **statusLine HUD** — GEM-DECISIONS TIER-0 0.3 (line 45, ✦2): native, ~zero-token self-observability
  (goal + context% + ledger-turn + loops + ckpt-age). The "native monitor" half of Axis-C's
  native-vs-ours distinction. Already partly live (GEM-DECISIONS line 293).
- **Smith predictor (dead-time compensation)** — PLAN ROUND-3 SLEEPER (line 86): model a slow op's
  latency (build/CI/Frida/long Codex gen), act on the PREDICTED result, suppress polling for
  ~expected_latency, reconcile when real feedback lands. How wfmon watches long agent calls without
  busy-polling (the "don't re-run to check" rule, AGENTS.md §4a). Unclaimed-for-agents.
- **Shadow-hook A/B** — GEM-DECISIONS TG.6 (line 72): a new gate/monitor runs observe-only, logs
  would-fire, promotes on outcome-correlation. The rollout discipline every Axis-B skill already ships as
  "SHADOW mode" — use it to introduce Axis-C monitors safely.
- **Andon cord (jidoka)** — PLAN ROUND-3 Gem 2 (line 79): every subagent gets ONE cross-scope HALT
  (`.beads/HALT` + PreToolUse exit-2) to stop the orchestration on a cross-cutting disaster (sibling
  committing a secret, poisoned base offset). Retires parallel-contamination + deadlock.
- **Subagent apoptosis + fencing-tokens** — PLAN ROUND-3 Gem 6 (line 82): deadlock + zombie-clobber
  prevention; fencing tokens isolate a stale lane's writes. Orchestration lifecycle hygiene.
- **cgroup-style fleet memory-governor + OOM-killer** — PLAN ROUND-3 Gem 5 (line 82): at 50-100 fan-out,
  park the fattest non-essential (`.mcp.disabled.json`). The RAM guard for large Axis-C fan-out (RAM-OOM
  pain). MEASURE-FIRST (GEM-DECISIONS TG.17 line 83).
- **Stigmergy pheromone field on shared FS (NOT shared git index)** — PLAN ROUND-3 absorbed (line 83):
  50-100-agent coordination via a shared-FS field, explicitly avoiding the shared-git-index contamination.
  The scale-out coordination substrate + the worktree-isolation fix (MEMORY: parallel-agent-worktree).
- **PACE fallback-chains** — PLAN ROUND-3 absorbed (line 83): each rung fails for a DIFFERENT reason.
  Maps to cross-vendor fallback (Claude fails → Codex, genuinely independent failure modes). Axis-C's
  resilience pattern.
- **SPC control charts / passive usage telemetry** — GEM-DECISIONS ST.13 (line 120) / TG.7 (line 73):
  run-rules + fire-counts on the monitor's ledger series → drift early-warn + dead-weight pruning. wfmon
  analytics, low priority.

### G. CROSS-VENDOR MINGLING INFRA (the Codex↔Claude fold)
- **Cross-tool HANDOFF baton + shared memory into Codex/agy** — PLAN ROUND-2 CROSS-TOOL (line 73): a
  tool-neutral `<project>/.agent/HANDOFF.md` cold-resume baton; register the shared basic-memory MCP into
  Codex (+ agy); port ledger-replay+recall into Codex `hooks.json`. The literal cross-vendor state bridge.
- **SBAR handoff schema** — GEM-DECISIONS TIER-0 0.14 (line 56): Situation/Background/Assessment/
  Recommendation as REQUIRED handoff fields = a typed cross-vendor handoff (AGENTS.md §5 "structured
  handoff, no raw-output prefix"). Convention, trivial.
- **Cross-tool instinct propagation** — GEM-DECISIONS ST.9 (line 116): export durable instincts into the
  shared AGENTS.md (Claude↔Codex↔agy). Keeps the behavior contract identical across vendors.
- **Backtracking-executor + abandon-primitive/circuit-breakers** — PLAN ROUND-2 T1 (line 66) + ROUND-3
  absorbed (line 83): branch-explore (~3×3 capped + call-budget), expose `abandon`. An orchestration-loop
  robustness PATTERN. ⚠️ **anti-overfit caution:** implement as a bounded helper on the native engine, NOT
  a second planning runtime (full-width MCTS is SKIP — PLAN line 74).

### H. NATIVE-WORKFLOW-SPECIFIC (direct Axis-C engine items)
- ⭐ **Fix the workflow StructuredOutput retry-cap** — OPEN-THREADS backlog #10 (line 67): broad/deep
  lenses fail the strict schema → use a looser/plain-text schema for deep-research workflows. A concrete
  bug in the NATIVE Workflow tool's fan-in — squarely Axis-C engine work (the `workflow-authoring` skill's
  "schema on every fan-in / typed Codex output-schema landmine" note).
- **Verifier-gated best-of-N** — GEM-DECISIONS TG.13 (line 79): N parallel derivations → pick by a
  rubric-verifier / deterministic check. The pick-best over a cross-vendor fan-out (the shipped
  `execution-grounded-bon` / `diff-blind-test-synth` skills — execution-consensus, not model-opinion).

---

## PART 2 — GAPS (stays a SEPARATE Axis-B wave — preserve-by-reference, do NOT absorb)

Per Decision-A these are FLAGGED, not pulled into Axis-C. Grouped by why they're out of scope.

**Reasoning-spine gems that are NOT workflow/orchestration (own Axis-B wave):**
- **DISCIPLINE-FORGE** (PLAN ROUND-3 CAPSTONE, line 84) — forges BEHAVIORS (hook+schema+tripwire+skill+
  chaos-test). The moat/self-learning capstone; meta-capability, not an orchestration engine. Separate.
- **TMS auto-retraction for RE** (PLAN ROUND-3 ELEVATED, line 85) — RE justification-graph / stale-anchor
  block. RE-domain-scoped; not cross-vendor workflow. Separate.
- **Capability-gap tool-FORGE** (PLAN ROUND-2 T2, line 68) — build a first-class tool when a capability is
  missing. Capability growth, not orchestration. Separate (and adjacent to the shipped tool-forge idea).
- **World-model state ledger** (PLAN ROUND-2 T1, line 63) — per-project `.beads/context/world-model.md`.
  Memory/context substrate → collides with the anti-overfit "no new memory" anchor. Separate.
- **Code-mode default for high-volume MCP** (PLAN ROUND-2 T1, line 65; GEM-DECISIONS TG.10 line 76) —
  token-efficiency lever, not orchestration.
- Calibrated-silence SDT proactivity, open-loops/prospective-memory, fatigue-adaptive mode, graded-autonomy
  gatekeeper, failure-precondition matcher, USER.md/dreaming, EVPI intent-hook, auto-skill-authoring,
  semantic body-level router (PLAN TIER-2/3, ROUND-3 Gem 1/4; OPEN-THREADS PP) — the **proactive-partner /
  interaction harness** wave. Adjacent but a different program.

**Harness hygiene / durability not specific to Axis-C:**
- Memory write-ahead spool (PLAN TIER-1 #2), wire-check reachability gate (TIER-1 #3), PreToolUse-dispatcher
  consolidation / MEASURE-FIRST (OPEN-THREADS #1, GEM-DECISIONS TG.16/TG.17, PR.6/PR.7), project-identity
  resolver (ROUND-2 T1), knowledge-staleness-GC, memory-spool content-capture (OPEN-THREADS GEM-REFINEMENTS).
- **AGENTS.md 3-divergent-files bug** (PLAN line 72; OPEN-THREADS #9) — a cross-tool CONFIG-hygiene fix.
  Adjacent to cross-vendor mingling (Axis-C benefits from one canonical contract) but it's a one-off
  bugfix, not an Axis-C feature. Flag for the mingle-infra wave; don't build it as Axis-C.

**Domain threads (fully unrelated — flag only):**
- UI/UX quality overhaul, media/video consolidation + watermark removal, Binary Ninja harness,
  ToolUniverse/Schrödinger expansion, BC leftovers, Hitman/SWFOC RE, radare2 MCP -32000, osint/tor/abuse.ch
  MCPs, all RE/Sci/Media domain gems (GEM-DECISIONS TG.19-29, ST.28-50, TL.*) — OPEN-THREADS QUEUED #2-5,
  DEFERRED, BC, OTHER-RE. None touch cross-vendor workflow.
- Security guardrails: Lethal-trifecta gate (TG.14), Spotlighting (TG.15), permissions.deny (0.1) — the
  anti-overfit anchor explicitly bars a "guardrail framework"; these stay in the safety wave.

**Anti-overfit SKIP reinforcements (Axis-C must NOT become these):**
GEM-DECISIONS SKIP-list (lines 219-241) directly guards the anchor — **MaAS agentic-supernet (2nd
orchestration runtime), AFlow/ADAS (architecture search = new runtime), SICA/SEAL (self-modifying
runtime), A-MEM (KG memory), Thompson-sampling router (trained controller, tensions with always-ask)** all
= REJECT. Keep them as the "what Axis-C is NOT" reference.

---

## PART 3 — VERIFICATION FLAGS (clear before building the Axis-C wave)
From GEM-DECISIONS "VERIFICATION FLAGS" (lines 244-270), the subset Axis-C rests on:
- **GEPA** claims (ICLR'26 Oral, 35× fewer rollouts / +10-20% vs GRPO — arXiv 2507.19457) — verify paper +
  numbers before making GEPA the prompt-evolution engine (line 255).
- **SDK `forkSession`** exact flag name; **`settingSources`** values; **MCP `sampling/createMessage`**
  client support in this CC build (line 252) — Axis-C's native fan-out + spawn-config rides these.
- **Code-execution-with-MCP** "~98% token reduction" (line 256) — if role-routing helpers expose the fleet
  as typed code APIs.
- **Sleep-time compute** gains are extrapolated, not measured on our workloads (line 257) — ship bounded +
  measure (also GEM-DECISIONS adversarial note line 279).
- `statusLine` stdin JSON fields, native `/rewind`, microcompact naming, `MAX_THINKING_TOKENS` env name
  (lines 247-250) — for the native-monitor + gate-quality knobs.

---

## PROVENANCE
Extracted 2026-07-13 from the three named docs (read-only). No config/build/commit performed (design
gate). All source content handled as untrusted data. Line refs are 1-indexed into each source as read.