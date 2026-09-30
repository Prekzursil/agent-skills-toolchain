---
paths:
  - "**/.claude/**"
  - "**/.agents/**"
---

# Method-proposal-before-execution (propose the shape before spending tokens)

**Rule:** for any non-trivial task, PROPOSE the method/architecture — topology (loop | pipeline/DAG | parallel barrier | loop-until-dry | judge-panel | map-reduce | tree search), sequencing, and verification shape — BEFORE executing or writing, so the owner can steer the shape while steering is still cheap. Owner directive, 2026-09-30.

## WHY — measured evidence
- MAST, "Why Do Multi-Agent LLM Systems Fail?" (arXiv 2503.13657; 150 traces, kappa 0.88):
  2 of the 3 failure classes are **system design issues** and **task verification** — the exact
  fields this proposal forces into the open before any tokens are spent on the wrong shape.
  [almost certain 0.90-0.95 — abstract fetched + corroborated]
- ReWOO (arXiv 2305.18323): plan-once-upfront = **5x token efficiency, +4% accuracy** (HotpotQA)
  vs observe-per-step. [almost certain 0.90-0.95]
- LLMCompiler (arXiv 2312.04511): plan-as-DAG + replanning = **up to 3.7x latency, 6.7x cost
  savings** vs sequential ReAct — SOTA is plan + replan path, not one static plan. [almost certain]
- Anthropic multi-agent research system: multi-agent ≈ **15x chat tokens**; fits breadth-first
  parallelizable work, NOT dependency-dense coding — topology choice IS the cost decision.
  [almost certain — primary fetched]
- Claude Code plan mode and LangGraph plan-and-execute both institutionalize
  proposal → approval → execute → replan with an explicit gate. [almost certain — official docs]

## Mechanics — the 6-field proposal (one block, before first execution)
[Format is a derived synthesis of the sources above — estate convention, not a cited spec — UNVERIFIED as a single-source format]
1. **GOAL** — one line, restated (AGENTS-RUNTIME §1).
2. **TOPOLOGY** — from the vocabulary above + a one-line task-shape rationale:
   parallelizable? context-exceeding? dependency-dense? verifiable?
3. **STEPS** — ordered/DAG list, named tool + model per step, ReWOO-style #E1/#E2 references
   so downstream steps compose without re-feeding observations.
4. **VERIFY** — accept criteria + who/what checks them (the MAST "task verification" class).
5. **REPLAN** — trigger (step fails / evidence contradicts plan) + fallback topology.
6. **BUDGET** — step/token ceiling, justified against the 15x multi-agent datum.

## Discipline
- **Non-trivial tasks only.** Trivial/routine ops proceed directly (§1 EVPI gate; owner-ops
  doctrines 7-8 — permission theater is banned). The proposal is a steering surface, not a brake.
- **Wide or irreversible scope ⇒ blocking approval gate** (plan-mode semantics); otherwise
  propose-and-proceed in the same turn.
- Proposal happens BEFORE execution, never mid-task (§1); once approved, execute to completion
  and replan only on the declared trigger.
- **Single-agent loop is the DEFAULT topology**; tree/DAG/panel must earn their ~15x cost in the
  task-shape rationale line. Judge-panel is the exception that scales with agent count
  (arXiv 2402.05120) — use it when verification-by-diversity is the bottleneck.
- The proposal FOLDS IN §1's goal restate and §1b's assumption ledger for the task it covers —
  it replaces those artifacts, it does not stack on top of them.
- Fan-out chosen ⇒ `fan-out-contract.md` governs the spawn prompts; cross-vendor dispatch ⇒
  `cross-vendor-dispatch.md`; research task ⇒ `research-coverage.md` digest first.

## Siblings
`development-workflow.md` (step-1 Plan First names the METHOD, not just steps) ·
`fan-out-contract.md` · `agents.md` · `cross-vendor-dispatch.md` ·
`single-signal-verification.md` (VERIFY floor) · `owner-ops-authorization.md` (the scope cut).
Sources: arXiv 2305.18323 / 2312.04511 / 2503.13657 / 2402.05120;
anthropic.com/engineering/built-multi-agent-research-system + /building-effective-agents;
langchain.com/blog/planning-agents; code.claude.com/docs/en/permission-modes.