---
title: AGENTIC-PERFECTION-PLAN
type: note
permalink: dqverify-repo-20261013/docs/agentic-perfection/agentic-perfection-plan
---

# Agentic-Perfection Plan — make the agent reliable / proactive / human-like / AGI-close (2026-06-29)
<!-- From the 12-lens exploration (wf wtu6j73mb; 11/12 lenses, AGI-gap lens schema-failed). Grounded in
     MAST failure taxonomy (arXiv 2503.13657) + the self-calibration LAW (Huang ICLR'24: intrinsic
     same-context self-correction FAILS — every check needs an EXTERNAL signal). -->

> **See also:** [AGENTIC-REPAIR-RELIABILITY.md](AGENTIC-REPAIR-RELIABILITY.md) — the functional-acceptance
> layer (2026-07-07): closes green-but-broken repair by requiring a held-out golden-journey run as the
> done-signal (extends `claim-guard` G1 + `test-tamper-guard` G2; SOTA-cited).

## STRUCTURAL DIAGNOSIS (the unifying insight)
The shipped B1 hooks (mcp-liveness, claim-guard, truth-verify, fresh-verify, orphan-commit, anti-degen,
goal-reinject, edit-checkpoints) already cover the famous IN-CONTEXT failure modes. The residual silent-
failure surface lives **BETWEEN turns and BETWEEN agents** — where in-context reasoning is blind. Every
reliable fix = write a durable EXTERNAL ledger (bg-registry, memory-spool, scope-contract, open-threads).
DISCIPLINE: stay under the ~6-active-hook latency ceiling — CONSOLIDATE checks into shared
PreToolUse/PostToolUse/Stop/SessionStart slots, never one always-on hook per check. Flat-file ledgers
only (NOT graph-memory/gateguard — they blew the budget before, per SELF-CALIBRATION-PLAN).

## TIER 1 — KEYSTONES (transformative, just-do-it) — the between-turns/agents durability spine
1. **Background-work registry + restart reconciler** — write-ahead NDJSON per Task/longrun spawn
   {id,kind,cmd,pid,artifact,scope,ts,status}; SessionStart reconciler checks pid-liveness + artifact,
   injects "ORPHANED BG WORK: agent-X died, artifact incomplete — resume/discard?". *Fixes the restart-
   killed-agents silent loss I hit repeatedly.* builds-on longrun + agent-monitor + stopfailure-notify.
2. **Memory write-ahead spool + continuity self-check** — DIFFERENT from mcp-liveness: liveness heals the
   SERVER, but a note you were writing during a 4h outage is GONE. Spool every intended write_note to a
   local file FIRST; SessionStart read-back-verifies the spool flushed to basic-memory, re-flushes/alerts
   if not. *The true fix for the 4h-silent-memory-loss.* builds-on mcp-liveness + the vault + precompact.
3. **Wire-check reachability gate (anti-slop keystone)** — Stop hook builds a static reference graph over
   the session diff (ripgrep/serena); flags any session-added symbol/component/route/handler referenced
   0x ("dead button / built-but-not-wired"), and *_v2/_new/_copy with no live v1 (the coupons_v2 case).
   *Enforces your PERFECT-work bar mechanically.* builds-on orphan-commit (file->code reachability).

## TIER 2 — HIGH VALUE
- **Subagent scope-contract + drift tripwire** (just) — record each agent's declared file-scope at
  dispatch; git-diff its worktree vs scope at handback; flag out-of-scope writes (the drift I hit).
- **Parallel-barrier watchdog + salvage** (confirm) — sibling-mtime relative-stall detection; on a hung
  lane, alert + auto-TaskStop(confirm) + proceed N-1 DEGRADED instead of 25-min deadlock.
- **Open-threads/commitment closed-loop resurfacer** (just) — Stop/SessionStart reads OPEN-THREADS,
  surfaces only relevant-NOW threads; closes the discussed-then-forgotten loop.
- **Tool-result sentinel** (just, LOW effort) — PostToolUse(*) classifier folds alongside anti-degen:
  every result -> SUCCESS/FAILED/AMBIGUOUS (exit code + MCP error-envelope + empty-on-expected); inject
  "TOOL X returned FAILURE — do not treat as success." The generic boundary guard.
- **Confidence-faith honest-signaling lint** (just) — Stop hook: the verbalized confidence band
  (VERIFIED/INFERRED/GUESSED) must match whether a verifying tool actually ran. Kills "I'm unsure" then act-certain.
- **Fatigue/energy estimator -> adaptive mode** (confirm) — detect focus-drop (shrinking prompts, typos,
  late hour, terse "just do it") -> COMPENSATE: terser/lede-first output + HIGHER confirm-bar.
- **Graded-autonomy gatekeeper (ONE consolidated PreToolUse hook)** (confirm) — classify each op by
  reversibility x stakes; known-OK'd scopes (authorization ledger, TTL) proceed silently, novel/irreversible
  ask. *Resolves always-confirm vs don't-fatigue-me.* Consolidates autonomy-gate + failure-matcher.
- **Failure-precondition matcher** (confirm) — activate the note.py failure preconditions: before an op
  matching a recorded dead-end, inject "you tried this, it failed because V."

## TIER 3 — POLISH
completeness/integrator fresh-context critic at "done" · stub-ledger (track every placeholder) · dup-guard
search-before-build · health heartbeat banner · activate the dormant oats.py (selection-learning) · sharded
user-model + dream-time idiolect inference · coherence-cliff self-overwrite sentinel · agent self-model card
("how I fail THIS user", injected before launches).

## GOLD-PLATING TO SKIP (honest — protects the latency ceiling)
per-check always-on hooks (consolidate) · auto-click-every-UI-element audit (destructive) · VLM clutter-judge
· DO-178C traceability · saga rollback engine · Darwin-Godel self-mod gate · per-suggestion proactivity-judge
model · contextual-bandit autonomy-learner · speculative prefetch · 25-question /onboard interview ·
re-enabling graph-memory/gateguard · context gas-gauge nudge.

## ROUND-2 DEEPER ADDITIONS (gold-gems; 4/8 lenses succeeded — background/per-project/security/wildcard re-running plain-text)
KEYSTONE INSIGHT: the 2026 AGI-gap closer is an EXTERNAL substrate the model REASONS OVER (not bigger models): authoritative file-state + backtracking + tool-growth + external-signal checks. ROUND-1 built the between-turns DURABILITY spine; ROUND-2 adds the REASONING spine.
- **T1 File-centric WORLD-MODEL state ledger** (architectural root): per-project .beads/context/world-model.md {entities,state,invariants}; reconstruct context FROM it (not the scrolling transcript) -> long-horizon coherence + bounded context + an invariant-checker that injects "STATE VIOLATION" when a new observation contradicts a recorded fact. (InfiAgent/MAGE.)
- **T1 HOLD-YOUR-GROUND dissent** (transformative, the #1 tool-vs-peer differentiator): models CAVE to "no, that's wrong" with ZERO new evidence (AAAI'26). A hook: when the user pushes back on a load-bearing claim WITHOUT new evidence, hold ground + ask for the disconfirming signal instead of flipping. Directly kills sycophancy.
- **T1 Code-mode (mcp-code-orchestrate) as DEFAULT** for high-volume MCP tools (ghidra/jadx/binja/paper-search/ocr/schrodinger) — not opt-in.
- **T1 Planning-with-backtracking executor** (branch-explore, ~3x3 capped + call-budget) — fixes the documented sunk-cost-grinding-on-a-wrong-but-consistent-anchor (BC RE stall, HGT trap).
- **T1 Project-identity resolver bugfix** (ledger keyed by canonical project root, not cwd drift).
- **T2 Capability-gap tool-FORGE** (confirm): when a needed capability has no tool, BUILD+persist a real first-class tool (scaffold+schema+pytest+sandbox+adversarial-test -> promote to ~/.claude/tools, versioned) — NOT a throwaway script. The no-faking/grows-with-you bar. (CAR/ARISE/Agenvoy.)
- **T2 Empirical variant-archive self-improvement** (confirm, safe DGM distillation): archive prompt/skill/config VARIANTS, validate each vs a held-out eval BEFORE adoption, keep Pareto-wins, auto-revert regressions; NEVER touches live hooks/settings. (DGM ICLR'26 / SEAL / ADAS.)
- **T2 Trajectory-quality / drift-inheritance gate** at subagent handback (strong models INHERIT drift from a weak agent's trajectory — arXiv 2505.02709).
- **T2** Trust-calibration BRIER ledger ("90% sure" actually means 90%) · belief-state w/ verbalized uncertainty · auto model-tier router at dispatch · semantic research cache (web/paper/firecrawl) · intent-mirror (1 italic line before 3+ file work) · unprompted-gem pass (rate-limited, idle/checkpoint-gated) · crisp repair ritual (zero groveling) · LSM rapport dial · relationship-continuity callbacks.
- ⚠️ **CONCRETE BUG**: AGENTS.md is physically 3 DIVERGENT files (~/.codex 1502fd, ~/.claude 1df3eb, ~/ 350e5a stale) — the "single behavioral contract" is broken on disk. FIX: single-canonical + copy-sync + hash-drift tripwire (NOT symlinks — fragile on this FS).
- **CROSS-TOOL**: port ledger-replay+recall into Codex hooks.json; register shared basic-memory MCP into Codex (+ agy); tool-neutral <project>/.agent/HANDOFF.md cold-resume baton.
- SKIP (round-2 gold-plating): live self-mod of running hooks/settings · graph-DB/FalkorDB memory · a new always-on hook per feature (consolidate onto seams) · full-width MCTS · auto-delete/merge memory notes (review-queue only) · below-threshold gems · mid-task interrogation · hardcoded model-tier/cost guesses · AGENTS.md symlinks.

## ROUND-3 WILDCARD GEMS (cross-domain borrows the 2026 field has NOT absorbed; wildcard lens)
Design law for ALL: put the discipline in the HARNESS (a hook/file/2nd-agent your tired mid-task self can't override), not the model's good intentions.
- **Gem 1 — CALIBRATED SILENCE (Signal Detection Theory) — HIGHEST-COMPOUNDING**: proactivity = an adaptive SDT operating-point. Log each interjection {context,type,user-reaction}; slide the threshold by rolling hit-rate + a fatigue-proxy (correction-rate, terseness, caveman-mode, time-of-day). DISSOLVES proactive-vs-don't-fatigue-me; the precondition that makes every other proactive feature sustainable. (clinical alarm-fatigue lit.)
- **Gem 2 — ANDON CORD (Toyota jidoka)**: every subagent gets ONE cross-scope HALT (.beads/HALT file + PreToolUse exit-2) to stop the orchestration on a cross-cutting disaster (sibling committing a secret, a poisoned base offset). Retires parallel-contamination + deadlock.
- **Gem 3 — QUIESCENCE SEARCH (chess engine / horizon-effect)**: never declare done in a volatile state — require 2 consecutive identical clean verification passes; treat flaky-test / changed-mtime / live longrun / coverage-delta as a "capture" that forbids done. Extends verification-before-completion; kills false-done.
- **Gem 4 — OPEN-LOOPS + PROSPECTIVE MEMORY (Zeigarnik/GTD)**: trigger-action notes {condition,action,status} ("when we touch BC, re-assert event_0"; "when PR#2 merges, /self-reflect") fired on DETECTION not request. Bullseye on the forgotten-thread stress.
- Gem 5 cgroup-style fleet memory-governor + OOM-killer (RAM-OOM pain; park fattest non-essential via .mcp.disabled.json). Gem 6 subagent apoptosis + fencing-tokens (deadlock + zombie-clobber). Gem 7 mise-en-place staging reflex (verify inputs/backends up BEFORE start — the "IDA not actually up" stall). Gem 8 sterile-cockpit + closed-loop readback for live-state ops (predict→confirm→verify→auto-rollback; the Aku-altar breakage). Gem 9 proactive blast-radius preview over RE offset dependency-chains (sunk-cost-grinding). Gem 10 Schmitt-trigger hysteresis on mode-switching (anti-thrash, 2 constants). Gem 11 two-key split-knowledge confirm for irreversible ops.
- ALREADY-ABSORBED by 2026 field -> ADOPT off-the-shelf, do NOT reinvent: saga/compensating-tx (SagaLLM, for BC device/save restores), abandon-primitive + circuit-breakers (expose `abandon` in the backtracking-executor), sleep-replay consolidation (SCM/Auto-Dreamer), stigmergy swarms (Many Tems, for 50-100 fan-out — pheromone field on shared FS NOT shared git index), PACE fallback-chains (each rung fails for a DIFFERENT reason), chaos-eng (GameDay the durability spine — an untested safety net fails when needed), Ulysses/behavioral-contracts.
- ⭐ CAPSTONE / THE MOAT — **DISCIPLINE-FORGE (#12, highest-strategic-leverage)**: cross-domain borrows are a DEPRECATING asset (the field mines the same analogy-vein in real time). So the durable win is NOT which discipline you adopt — it's a `/forge-discipline "<pattern>"` skill that takes any named pattern (a gem here, or tomorrow's arXiv paper) and emits the hook + memory-schema + tripwire + skill that installs it, + runs a chaos/GameDay self-test proving the tripwire/halt actually FIRES before declaring it installed. Generalizes the existing instinct->skill evolution (distinct from tool-forge which forges TOOLS; this forges BEHAVIORS). Reframes the program from "find every gem" to "consume any gem in a day" = antifragile; the closest thing to self-learning/AGI-adjacent. VERY-HIGH compounding x MED-HIGH effort.
- ⭐ ELEVATED — **TMS AUTO-RETRACTION for RE (Gem 1, kills the costliest recurring failure)**: a justification graph (SQLite) behind every load-bearing RE value (offset/address/pid/version); retract a premise -> cascade-flip every downstream finding to OUT + a `stale-anchor` PreToolUse hook BLOCKS a tool call that rests on a retracted/changed-hash premise ("0x… rests on the pre-rebase IDA base, retracted — re-derive"). Makes the wrong-but-consistent-anchor fix STRUCTURAL not reactive. `benthomasson/ftl-reasons` (Doyle-1979 TMS w/ retract/assert/explain/trace) = ~1 file to port. VERY-HIGH x MED. (Subsumes round-2's blast-radius-preview.)
- 💎 SLEEPER — **SMITH PREDICTOR (dead-time compensation)**: the root-cause fix behind the held-open-Frida + longrun + don't-re-run-to-check hacks — model the latency of a slow op (build/reboot/CI/Frida-settle), act on the PREDICTED result, suppress polling for ~expected_latency, reconcile when real feedback lands. MED-HIGH x MED, unclaimed for agents.
- NET-READ (wildcard): build #2 open-loops/prospective-memory (felt pain) + #1 TMS (costliest RE failure) + #3 Ulysses-tripwires (makes the rest stick) + #12 Discipline-Forge (the moat that outlasts the doc).

## SEQUENCING
T1 first (the durability spine — fixes the worst silent losses I actually hit). Then the cheap T2 just-do-its
(tool-result-sentinel, honest-signaling, resurfacer). Then the consolidated graded-autonomy gatekeeper +
fatigue-mode (confirm-first — they change interaction). T3 as capacity allows. Keep total active hooks ~6 via
consolidation. NOTE: AGI-gap lens (frontier-systems) failed the schema-retry — re-run on request for that angle.