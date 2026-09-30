---
authored: C:\Users\Prekzursil\.agents\rules\common\task-list-above-session-context.md
runtime: C:\Users\Prekzursil\.claude\rules\common\task-list-above-session-context.md
sync: scripts/sync-rules.ps1 materialises the runtime copy; scripts/lint-rules-loading.ps1 asserts both exist
---

# task-list-above-session-context

**Rule:** Session context is NOT the boundary of work state — consult the cross-session registers (TASKBOX, OPEN-LOOPS, DIRECTIVES, the workflows registry) BEFORE starting work and AGAIN before declaring anything done; when in-session recollection and a register disagree on position, the register wins.

## WHY — measured evidence

- Owner directive 2026-09-30 (G-3/Q9 scope change): deferred items live above any single session; a session that never consults the registers silently drops in-flight work.
- The registers exist because lifetimes differ (AGENTS-RUNTIME §1d: TASKBOX = hours-days, OPEN-LOOPS = until someone does it, DIRECTIVES = never closes) — "conflating them is why things get lost."
- Precedence shape is already estate doctrine for the ledger: SessionStart replay is trusted "as ground truth, not any in-context summary" (AGENTS-RUNTIME §3). This rule extends that shape to the registers at both boundaries.
- SOTA corroboration (primary-source fetched this run, 2026-09-30):
  - Manus: file system = "the ultimate context: unlimited in size, persistent by nature"; the todo list is rewritten step-by-step as a deliberate attention mechanism — https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus (almost certain 93%).
  - Anthropic: compaction must preserve "architectural decisions, unresolved bugs"; agents re-read their own notes after context resets — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (almost certain 93%).
  - Claude Code memory docs: project CLAUDE.md is re-read from disk after /compact; instructions are "context, not enforced configuration"; subagents do NOT inherit auto memory — https://code.claude.com/docs/en/memory (almost certain 93%).
  - Beads: `bd prime` is the deterministic session-start re-anchor; "Do not use markdown TODO lists for task tracking" — https://github.com/gastownhall/beads README (almost certain 92%).

## Mechanics

- **Start boundary** (before the first substantive action, and after every compaction/resume): PULL — TASKBOX (in-flight), OPEN-LOOPS (owner + review-by), DIRECTIVES (standing, judged BENEFICIAL/CONDITIONAL/COSTLY), workflows registry (in-flight Workflow/fan-out runs and their journals, e.g. `bd prime --work-type recovery`, agent-monitor state). Pull, never assume.
- **Done boundary** (before any "done/complete/shipped" claim): re-read the registers. Anything the work touched but did not finish is resolved in-turn or written to a register with owner + review-by — never dropped.
- **Precedence scope:** register > session recollection for POSITION and STEERING (what is left, deferred, owned). Rebuild the plan from the register and say so. This NEVER extends to evidence — a register row is bookkeeping, not verification (hooks.md: "progress bookkeeping is NOT verification").
- **Subagents:** registers are not inherited — every spawn receives task state as an explicit structured handoff (AGENTS-RUNTIME §5); raw parent context is never the handoff.
- **Rewrite, don't append:** update the row as state changes; decay/archive closed items or the register becomes the bloat it prevents (context-reduction.md anti-bloat bar).
- **Enforcement pairing:** this rule is context, not enforcement — the gap-check Stop hook reads the registers mechanically; keep that lane intact.

## Discipline

- NEVER treat "not in my session" as "not my problem" — that is the orphaned-deferral defect (lane A defers, lane B edits, nobody owns).
- NEVER declare done while a register shows an in-scope open item you created or touched — finish it or re-register it with owner + review-by.
- NEVER let in-context recollection override a register on position; when they disagree, rebuild from the register.
- NEVER cite register state as completion EVIDENCE — position only; claims still need independent verification (single-signal-verification.md).
- ALWAYS hand register-derived position to every spawned subagent explicitly.
- ALWAYS end a boundary check with either "registers clean for this scope" or a register write — silence is not a check.

## Siblings

- `hooks.md` — in-session Task-tool tracking; the "NOT verification" boundary this rule respects.
- `context-reduction.md` — compaction preserves decisions/diffs/OPEN-LOOPS; the anti-bloat bar.
- `single-signal-verification.md` — done-claims need two independent signals.
- `agents.md`, `fan-out-contract.md` — structured subagent handoffs.
- `development-workflow.md` — plan-first entry where the start boundary fires.