---
title: Identify-before-absence — probe the artifact-class space before claiming "does not exist"
scope: common
loads: on-demand (cited from AGENTS-RUNTIME §12); harness-tree sessions; project-session enforcement carried by fan-out-contract spawn prompts
verified: 2026-09-30 (council wf_75558a8a-f5d run 2; disk-verified with two mechanically independent probes)
paths:
  - "**/.claude/**"
  - "**/.agents/**"
---
# Identify-before-absence — probe the FULL artifact-class space before claiming "does not exist"

"X does not exist" is a per-class verdict, available only after probing every root of that
class (or the registry that indexes them) — never from one or two directories, a failed
call, or an unloaded schema.

## WHY — measured
- 2026-09-30: `harness-self-improve-sweep` was declared nonexistent after probing only
  skills/commands; it was a workflow — live in BOTH roots (`C:\Users\Prekzursil\.claude\workflows\harness-self-improve-sweep-important.js`,
  Glob-verified) and indexed twice in `~/.agents/knowledge/workflows-registry.md:18,32`.
- Indexes manufacture absence too: 179 skills invisible to routing for 3 months
  (`derived-index-freshness.md`) — a stale discovery layer hides real artifacts.
- SOTA: deferred tool schemas mean "not loaded" ≠ "does not exist"
  (anthropic.com/engineering/advanced-tool-use); MCP `Unknown tool` is server-scoped, never
  global (modelcontextprotocol.io/specification/2026-07-28/server/tools); skill listings
  silently truncate under context budget (code.claude.com/docs/en/skills).
- Tool-failure-shaped twins route to `native-capability-map.md` (a failed call is a
  transport event, not an absence verdict).

## Mechanics — the class space (probe ALL roots, or cite the registry)
- skills / commands / agents: `~/.agents/skills` (SSOT) + `~/.claude/{skills,commands,agents}`
  (materialized sync targets)
- workflows: `~/.claude/workflows` (incl. `_bak_*/`, `scripts/`, `snippets/`) +
  `~/.agents/workflows` + repo `agent-self/config/workflows` + session-embedded —
  SSOT index: `~/.agents/knowledge/workflows-registry.md` (regen
  `scripts/build-workflow-registry.py`; 542 entries by class counts, 2026-09-30)
- MCP: ToolSearch catalog + `~/.agents/agents.json`; name collisions across servers can
  fake BOTH presence and absence — disambiguate before concluding either
- plugins / hooks: `claude plugin list`; `~/.claude/hooks/` + `hooks/_dispatch/manifest.json`

## Discipline
1. **NON-SCOPE:** ordinary in-workscope file/path existence checks (e.g. "does app.py
   exist") are NOT artifact-class claims; this rule binds only registry-backed artifact
   classes: skills / commands / agents / workflows / MCP / plugins / hooks.
2. Name the artifact class, then run the bounded probe ladder (capped — no wholesale
   Reads): (1) grep the class registry with line numbers; (2) check its `Generated:`
   stamp — stale only if the DURABLE classes (live/repo/shared entries) predate it; the
   session-embedded class churns daily BY DESIGN and its drift is not staleness;
   (3) ONE filesystem Glob on the class SSOT root = the second mechanically independent
   signal (`single-signal-verification.md`); stop there.
3. State the scope in the claim: "not in <roots probed>", never bare "nonexistent".
4. Failed call / unloaded schema / server-scoped "Unknown tool" routes to
   `native-capability-map.md` (change transport, not the capability claim).
5. A class with a missing or stale index is itself the finding: record it as an
   OPEN-LOOPS row (owner + review-by) and answer with the scoped wording — registry
   regeneration is a deliberate throttled maintenance op, never an in-task side effect.
6. **Mechanization guard:** if ever enforced by hook, it must be STATE-based inject-only
   (does the final artifact cite ≥2 probes for each absence verdict), never text-matching
   on phrases like "does not exist", never blocking (AGENTS-RUNTIME §6).

Siblings: `native-capability-map.md` (tool failure ≠ absence) · `single-signal-verification.md`
(absence corroboration) · `derived-index-freshness.md` (index rot) · `research-coverage.md`
(the complement read).
