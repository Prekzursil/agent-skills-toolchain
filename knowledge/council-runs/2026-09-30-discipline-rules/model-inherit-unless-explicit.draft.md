---
key: model-inherit-unless-explicit
paths:
  authored: C:\Users\Prekzursil\.agents\rules\common\model-inherit-unless-explicit.md
  runtime: C:\Users\Prekzursil\.claude\rules\common\model-inherit-unless-explicit.md
  s12_table: C:\Users\Prekzursil\.claude\AGENTS-RUNTIME.md §12
owner_resolution: 2026-09-30 (Q4) — inherit-by-default
---

# Subagents/workflow agents inherit the parent (session) model unless the owner explicitly pins a model — no silent downgrades, no auto-fallback pins.

## WHY (measured)
- **Owner resolution 2026-09-30 (Q4)** rules inherit-by-default even though estate memory measured a `[cyber]`-fallback subagent death mode: 6/29 fanned-out subagents died vs 0/60 main-loop calls, and pinning claude-opus-4-8 dodged it (auto-memory `reference_workflow_agent_model_pinning`, `reference_opus55_cyber_fallback_2026-09-25`). Pinning stays owner-authorized, never a standing reflex.
- **Claude Code SOTA is default-inherit**, 4-level ladder resolved at spawn: per-invocation `model` > agent frontmatter `model`/`inherit` > `CLAUDE_CODE_SUBAGENT_MODEL` env > main-conversation model. https://code.claude.com/docs/en/sub-agents + /model-config (each fetched 2x, consistent). Almost certain 90-99%.
- **Both failure modes are filed on one tracker, opposite directions:** inherit → Opus cost blowup (anthropics/claude-code #26179; 62-agent audit, ~0 subagents need Opus) vs pin-to-cheap → silent quality loss (#5456: parent Opus, children Sonnet, every config path ignored). Almost certain 90-99%.
- **Substitution is silent:** allowlist-blocked subagent models run "on a fallback model rather than failing"; no result object records the served model (OpenAI SDK `ModelResponse` has no model field) — the OTel `gen_ai.request.model` vs `gen_ai.response.model` pair exists to expose exactly this divergence. Highly likely 80-90%.

## Mechanics
- Omit `model:` in spawn prompts / agent defs → the child inherits the session model, resolved at spawn time (a later parent switch does not re-route live children).
- **Explicit pin — owner ask ONLY:** (a) an in-session owner instruction, or (b) an owner-recorded standing directive (the Opus-substantive / Haiku-trivial tiers, `performance.md:9-19`). Record pin + reason at dispatch (`model-pinned-by: owner @ <date>`).
- **Floor guard (bare-inherit regression):** apply inherit OR the standing Opus floor, whichever is HIGHER — a down-routed parent must not silently down-route a substantive child; down-routing is MEASURE-only (`context-reduction.md:22`, `cross-vendor-dispatch.md:77-81`).
- **Layer drift:** Workflow `agent(p, {model: 'claude-opus-4-8'})` takes full model IDs; the 4-alias enum is the Agent TOOL's, not Workflow's. Name the layer when pinning; aliases/enums rot silently.
- **Provenance:** wherever substitution is possible (allowlist fallback, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, fallback chains), stamp the actually-served model next to the result; unstamped divergence is UNVERIFIED on the model axis.

## Discipline
1. Never write `model:` into a spawn by reflex — omission IS the routing decision.
2. Never pin-to-cheap silently; cheap-tier routing is a per-tier call against `performance.md`'s audited exception list (deep-research tiers DO need frontier — #26179's own audit).
3. Never add a pin mid-flight to dodge a transient error (529 / [cyber]-fallback); escalate — the fix is a time-boxed owner-authorized fleet pin, never a silent one.
4. If the served model is not stamped, mark the result UNVERIFIED (model axis); do not assume the requested model ran.

## Siblings
`performance.md` (Opus floor + tiers) · `context-reduction.md` (MEASURE-only down-routing) · `cross-vendor-dispatch.md` §5 (dispatch model floor) · `fan-out-contract.md` (spawn prompts) · `single-signal-verification.md` (UNVERIFIED discipline)