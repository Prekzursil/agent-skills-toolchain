---
name: gem-hunt
description: 'Use when the user wants to DISCOVER high-value improvements to their
  OWN agentic workspace/toolkit - new hooks, behaviors, gems, skills, MCPs, or frontier-harness
  patterns - via a wide multi-lens agent fan-out, then a consolidated adopt/prune
  decision. The named "agentic-perfection sweep" / "extensive gem search". Triggers:
  "find more gems", "what are we missing vs other tools".'
permalink: dqverify-repo-20261013/reconcile-flags/import-2026-08-28/toolchain-root/skills/gem-hunt/skill
---

# Gem-Hunt — extensive multi-lens workspace self-improvement sweep

The repeatable form of the process that produced the agentic-perfection gems (open-loops,
contraindication-registry, iatrogenics-gate, the closed self-improvement loop, ACE, …).
Re-run it whenever the landscape moves (new papers, new tools, new domains) — the lenses
and discipline below are the winning formula; only the findings change.

**Core philosophy (the user's standing intent):** fan out **LARGE** and wide — *"there's no
reason to limit the search; a gold gem unfound is a waste."* Breadth-first across diverse,
independent lenses beats one deep pass, because the best finds come from angles you wouldn't
have prompted for. Be adversarially honest, cite, grade confidence, and converge to a
decision the user steers — never silently adopt.

## The method (7 steps)

1. **GROUND — build the dedup-set first.** Read the live workspace state (hooks in
   `~/.claude/hooks` + `settings.json`, skills, `~/.mcp.json`, `MEMORY.md`, the
   `AGENTIC-PERFECTION-PLAN.md` / `OPEN-THREADS.md` / `CONSOLIDATED-GEM-DECISIONS.md` docs)
   and recall memory. Assemble the explicit lists: **BUILT · PLANNED-unbuilt · ABSORBED ·
   ALREADY-FOUND-this-hunt**. Every lens agent gets this set so it dedups instead of
   re-proposing what exists. Without it, 80% of finds are duplicates.

2. **FAN OUT — one agent per DISTINCT lens** (the menu that works; pick/scale to the ask,
   default 6-9, go to 15-20+ for "be exhaustive"):
   - **cross-domain borrows** — mechanisms from unmined fields (clinical medicine, intel
     tradecraft, economics/mechanism-design, control theory, law/evidence, neuroscience).
     *Historically the highest-yield lens* (iatrogenics-gate, contraindication-registry, ACH).
   - **frontier-harness** — latest agent-reliability/memory/orchestration papers + repos
     (arXiv + GitHub): ACE, MaAS, Agent-as-a-Judge, GEPA, G-Memory, etc.
   - **competitive-teardown** — what the best harnesses (Cursor/Devin/Cline/OpenHands/Aider/
     Goose/Amp/Codex/Windsurf/Zed/Junie) have that we lack; **tag NATIVE-vs-BUILD**.
   - **native-capability audit** — what *our own tool* (Claude Code + Agent SDK) natively
     supports but we under-use (so we ENABLE, not BUILD). Load-bearing; do it every time.
   - **user-domain tools** — domain-specific gems for the user's actual work (here:
     RE/security, media/video, drug-discovery, BC-modding).
   - **meta** — the next self-improvement level (auto-gem-mining, capability-score, the
     closed failure→gem→verify→retire loop).
   - **prune/organize** — leanness: redundant hooks/skills/MCPs, latency, memory-layer
     consolidation. (A gem-hunt that only ADDS is a bloat engine — always prune too.)
   - **skills-in-wild · MCPs-in-wild** — high-value OSS skills/MCP servers to adopt.
   - **wildcard/gold-gem** — one agent told to find the genuinely novel cross-field thing.

3. **DON'T LET THEM DIE.** Transient API errors (429/529/socket-close) kill agents
   mid-run, especially in big fan-outs. The work usually persists in the transcript.
   **Resume from partial via SendMessage** (force synthesis from what they have) — recover,
   don't redo ([[feedback_workflow_orchestration]]). Watch for write-freeze >25min with
   quiet children = real stall → TaskStop + recover.

4. **SYNTHESIZE.** Dedup across lenses; **note cross-lens convergence** (a find surfaced by
   two independent lenses is highest-confidence — e.g. ACH appeared in cross-domain AND
   wildcard). Roll up into a **tiered consolidated decision-queue**: TIER-0 just-do-it
   (reversible) · top-gems · strong-techniques · tooling · planned-unbuilt · skip · with a
   per-item REC and value×effort tag.

5. **VERIFY before acting (peer-review).** Subagent findings are claims, not truth. Before
   adopting, verify the load-bearing factual claims against the real config/code — a prune
   audit once called a file "safe to delete" that the router actually referenced. Cross-model
   review for big calls ([[feedback_peer_review]]).

6. **DECIDE.** Present the decision-queue + a low-fatigue `AskUserQuestion` steer (recognition
   over recall). Write the queue to a **durable doc** (`CONSOLIDATED-GEM-DECISIONS.md`) so it
   survives compaction and is the audit trail + input to the build phase. A gem-hunt is
   discovery, not a build — don't implement mid-hunt.

7. **CAPTURE.** Version adopted gems + this process's learnings to the agent-skills-toolchain
   repo and write durable memory notes, so the next hunt starts from a richer dedup-set.

## The anti-overfit meta-anchor (gate every adopt decision)

Minimal architecture is deliberate (mini-SWE-agent: a 100-line bash loop scores 74% on
SWE-bench — elaborate scaffolding *overfits* as models improve). A find only counts if it
**(a) rides the existing hook/skill/MCP bus**, and **(b) does NOT reintroduce a rejected
component** (2nd orchestration runtime, vector-DB/KG memory, durable-execution engine,
trained critic, observability SaaS, guardrail framework). Prefer "enable a native feature"
and "fold into the existing dispatcher" over "new hook file / new MCP."

## Hard-won lessons (do these, they cost real reruns to learn)

- **Loose schema or plain-text agents, not strict StructuredOutput.** Broad/deep lenses
  produce long, shape-varying output that fails strict schemas and burns the retry-cap.
  Use a single `findings_markdown` string field, or plain-text agents.
- **Fan out LARGE** (the user wants 50-100 on "be exhaustive"); each lens blind to the
  others is a feature (independent coverage).
- **Per-find rubric:** name / what / why-THIS-user(-domain) / how-to-build-or-adopt /
  source(cite) / value×effort / novelty(-for-us) / NATIVE-vs-BUILD tag.
- **Cite + grade confidence;** flag post-cutoff/secondary-source items as lower-confidence.
- **Workflow vs Agents:** a `Workflow` (pipeline/parallel) is cleanest for a fixed lens set;
  parallel `Agent` calls are fine and easier to resume individually when one dies.

## Deliverable

A consolidated, tiered adopt/prune **decision-queue doc** + a steering `AskUserQuestion`,
from which the user picks the build wave. Related: [[grill-me-extensive]] (interrogate one
plan), `deep-research` (single-topic). This skill is the *discovery+decide* front-end to the
agentic-perfection program.