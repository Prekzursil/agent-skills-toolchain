---
paths:
- '**/.claude/**'
- '**/.agents/**'
- '**/source/agent-skills-toolchain/**'
permalink: dqverify-repo-20261013/rules/common/derived-index-freshness
---

# Derived-index freshness — semantic routers rot silently

> Fail-soft builders never fail; they just keep serving an index of the past.

**Rule:** any DERIVED index whose builder is fail-soft MUST be (1) rebuilt by the
pipeline that mutates its sources, (2) gated by a freshness check that fails closed
on count-drift, `built_at`-precedes-newest-source, or a silently emptied lane, and
(3) never trusted silent. Adding a skill/agent/command/MCP without rebuilding means
the router that every session consults cannot see it.

**The family on this estate:** semantic-router index
(`~/.claude/hooks/semantic-router/index/`), recall-inject index
(`~/.claude/hooks/recall-inject/index/`), lexical `skills-index.md`,
`skills/SKILLS-MANIFEST.md`, `DEPLOYED-MANIFEST.json`, marketplace indices.

**Measured 2026-09-30 (why this rule exists):** router `built_at` 2026-06-29 with
358 units while the tree held 422 skills — **179 skills invisible to semantic routing
for 3 months** (academy-badge-runner would have joined them); the file mtime (Aug 10)
was a full cache-reuse run (`embedded: 0`) and proved nothing. Same class: recall-inject
`built_at` ≈ 2026-07-10; and the router's MCP lane silently emptied when the fleet moved
`~/.mcp.json` → `~/.claude.json` — the builder read a dead path (source-path drift is
part of this rot; builders must follow their sources or fail loud, never skip).

## Mechanics (semantic router)

- Rebuild: `python ~/.claude/hooks/semantic-router/build_index.py`
  (incremental, sha-keyed, fail-soft). Requires local Ollama `nomic-embed-text`
  running: start with `ollama serve` if the build reports
  `FAILED:build-index ollama-health`.
- Gate: `pwsh ~/source/agent-skills-toolchain/scripts/check-index-freshness.ps1`
  — exit 1 on skill-drift > 8, `built_at` older than newest SKILL.md, or an empty
  MCP lane while a source file exists. Red-proven: a missing meta path exits 1.
- Deploy wiring: `scripts/sync-skills.ps1` runs the gate after copying, attempts one
  rebuild, and on a still-failing gate prints `WARN:semantic-index-stale` without
  failing the deploy (loud, fail-open — same posture as the router itself).

## Discipline

1. After ANY change to skills/agents/commands/MCP sources: run the gate; FAILED →
   rebuild → re-gate. A stale index is never "probably fine".
2. When moving/renaming a config file any builder reads, grep builders for the old
   path IN THE SAME CHANGE (the `.mcp.json` move was not, and cost the whole MCP lane).
3. File mtime on an index artifact is not freshness — read `built_at`/manifest counts.
4. A new index in this family ships with its gate wired into the pipeline that feeds
   it, or it does not ship.

Sibling: `rules/common/research-coverage.md` (cross-run coverage register),
`rules/common/harness-vcs-hygiene.md` (live-tree reconciliation). Evidence:
`index/meta.json` before/after 2026-09-30 (358 → 545 units, mcp 0 → 34).