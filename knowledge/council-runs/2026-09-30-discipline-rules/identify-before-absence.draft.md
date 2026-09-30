---
paths:
  - "**/*"
---

# Identify-before-absence — probe the FULL artifact-class space before claiming "does not exist"

"X does not exist" is a per-class verdict, available only after probing every root of that
class (or the registry that indexes them) — never from one or two directories, a failed
call, or an unloaded schema.

## WHY — measured
- 2026-09-30: `harness-self-improve-sweep` was declared nonexistent after probing only
  skills/commands; it was a workflow — live in BOTH roots (`C:\Users\Prekzursil\.claude\workflows\harness-self-improve-sweep-important.js`,
  Glob-verified this run) and indexed twice in `~/.agents/knowledge/workflows-registry.md:18,32`.
- Tool-shaped twin (2026-09-22, wf_c8e4c79c-1c8): a failed call is a transport event —
  owned by `native-capability-map.md`, not restated here.
- Indexes manufacture absence too: 179 skills invisible to routing for 3 months
  (`derived-index-freshness.md`) — a stale discovery layer hides real artifacts.
- SOTA: deferred tool schemas mean "not loaded" ≠ "does not exist"
  (anthropic.com/engineering/advanced-tool-use); MCP `Unknown tool` is server-scoped, never
  global (modelcontextprotocol.io/specification/2026-07-28/server/tools); skill listings
  silently truncate under context budget (code.claude.com/docs/en/skills).

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
1. Name the artifact class, then probe every root above (Glob/Grep) or read the registry —
   and check its `Generated:` stamp first: a stale index is not an absence oracle.
2. Absence needs a SECOND mechanically independent probe (`single-signal-verification.md`):
   registry grep + filesystem Glob, or ToolSearch + a different transport.
3. State the scope in the claim: "not in <roots probed>", never bare "nonexistent".
4. Failed call / unloaded schema / server-scoped "Unknown tool" routes to
   `native-capability-map.md` (change transport, not the capability claim).
5. A class with no index is itself the finding: build the registry before trusting absence.

Siblings: `native-capability-map.md` (tool failure ≠ absence) · `single-signal-verification.md`
(absence corroboration) · `derived-index-freshness.md` (index rot) · `research-coverage.md`
(the complement read).