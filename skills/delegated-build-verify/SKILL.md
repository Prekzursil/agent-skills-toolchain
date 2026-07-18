---
name: delegated-build-verify
description: Use when delegating a large build to a generator (Codex fan-out, subagents, or a Workflow) and you must independently verify the result — the "agent builds X, then you evaluate" pattern. Turns a converged plan/grill into an authoritative build-spec that doubles as the evaluation rubric, fans out the generator, then verifies with an active fabrication hunt. Pairs downstream of grill-me-extensive (scope first). Triggers: "build X then evaluate", "fan out Codex to build this then check it", "generate it then grade it", spec-driven build + independent verify.
---

# Delegated Build + Verify

Generator–verifier delegation for big builds. The generator (Codex threads / a Workflow /
subagents) writes the code or data; **YOU are the independent verifier**. Never let the
generator grade its own homework — self-reported completion and coverage are gameable proxies.

## When to use
- The user says "build X, then evaluate it" / "fan out Codex to build this, then check it."
- A large multi-part build you will delegate but must not ship on the generator's say-so.
- Downstream of `grill-me-extensive`, once the scope has converged into decisions.

## The pattern (in order — do not skip step 1)
1. **Write the BUILD SPEC first — it IS the eval rubric.** Before any generation, author an
   authoritative spec with: (a) **prime directives** (the non-negotiables — never-fabricate,
   provenance, security/privacy boundaries); (b) the data/API contract + schema; (c) per-part
   sourcing; (d) an explicit **§ Acceptance Criteria** that enumerates *every* gate. It must be
   precise enough that a fresh reviewer can grade against it. Save it: the generator builds to
   it, you evaluate against it. No spec → you have no rubric → don't generate yet.
2. **Encode boundaries as STRUCTURAL gates, not per-item discipline.** e.g. a provenance /
   lawful-basis gate that auto-routes ungated data to a private/absent state; a first-class
   node so a forbidden attachment is impossible *by construction*. Invariants scale to 100k+
   records; reminders don't.
3. **Fan out the generator.** Codex threads / a Workflow / subagents, each carrying a scoped
   slice of the spec **plus the prime directives embedded in its prompt**. Sequence hard
   dependencies (schema before data). Worktree-isolate parallel writers so they don't collide.
4. **VERIFY independently — with an ACTIVE FABRICATION HUNT.** Do NOT trust the generator's
   self-reported completion/coverage. Re-run the gates yourself; spot-hunt for fabricated,
   unprovenanced, or derived-as-authoritative cells; read the actual test *summary* line, not
   the exit code. Report: **completion** (done / partial / absent per part), **honest coverage
   %**, and each **gate** pass/fail. **Fabrication or coverage-theater = automatic FAIL for
   that slice**, however "done" it looks. Incomplete-but-honest beats complete-but-fabricated.

## Red flags (STOP)
| Thought | Reality |
|---|---|
| "The generator said it's 100% covered." | Verify it yourself; self-reported coverage is a gameable proxy. |
| "No build-spec yet, I'll just start generating." | You have no rubric — write the spec first. |
| "I'll delegate without repeating the non-negotiables." | Drift + fabrication. Embed them in every slice. |
| "It looks complete, ship it." | Run the fabrication hunt before believing "complete." |

## Related
- Upstream scope: `grill-me-extensive`. Verify discipline: `verification-before-completion`.
- Anti-reward-hacking rationale: basic-memory `agentic-repair-reliability`,
  `verified-green-read-summary-not-coverage`.
