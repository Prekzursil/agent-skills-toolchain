---
name: toolkit-gap-analysis-2026-05
description: Findings from the 2026-05-28 deep-research gap analysis — the user's
  context-loss root cause and the report location
metadata:
  node_type: memory
  type: project
  originSessionId: 9c274ad5-1d28-40fd-bfc0-e434ac596a9c
permalink: main/claude-memory/root/project-toolkit-gap-analysis
---

2026-05-28: ran a 7-parallel-agent deep-research gap analysis ("what Claude Code skills/MCPs/workflows am I missing"). Report: `~/source/agent-skills-toolchain/docs/claude-toolkit-gap-analysis-2026-05-28.md` (~390 tools cataloged, ~170-200 unique NET-NEW gaps; raw per-domain files in `~/research-staging/`).

**Root-cause diagnosis of the user's recurring "Claude loses context / flow breaks" pain (this is the load-bearing finding):**
- **NOT a missing tool.** It's self-inflicted context rot: their global `~/.claude/CLAUDE.md` + 9 `rules/common/*.md` + 8 `rules/web/*.md` + project CLAUDE.md + large MEMORY.md ALL load every turn (Anthropic target <200 lines/file), fragmenting the cache + diluting attention.
- **Four overlapping memory layers** (auto-memory + `remember` + `claude-reflect` + `memory` MCP) hook the same events and fight each other.
- **Ephemeral planning + reactive compaction** at 90% (collapses cache hit-rate 80%→<20%).

**Why / How to apply:** When the user hits context/flow problems, FIRST suggest trimming the rule pile (path-scoped `.claude/rules/*.md` with `paths:` frontmatter, run `claude-md-improver`, enable `InstructionsLoaded` hook), consolidating to ONE memory layer, persisting plans to a file (`.beads/plans/active-plan.md`), proactive *steered* `/compact` at 40-60%, and a PreCompact+SessionStart survival hook — do NOT recommend adding more tools/memory layers (makes it worse). Top concrete net-new gaps for them: measurement layer (ccusage, ccstatusline — they have ZERO cost/context telemetry), sequential-thinking/filesystem/time MCPs, claude-code-action (CI), n8n-mcp. Aligns with [[feedback_full_rigor]] and [[feedback_peer_review]]. Report NOT yet committed to git (user's call).