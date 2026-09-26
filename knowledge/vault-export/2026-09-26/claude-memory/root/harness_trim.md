---
name: harness-context-rot-trim
description: 2026-06-05 harness trim — cut every-turn instruction load 64 percent
  (15.6k to 5.6k tokens) by path-scoping rules + relocating reference tables; metaswarm
  gates kept inline; backup + rollback path
metadata:
  node_type: memory
  type: project
  originSessionId: 3cd9445a-ab17-4eec-ad05-c1d1bf411c40
permalink: main/claude-memory/root/harness-trim
---

2026-06-05: executed Objective ① of the four-front program — trimmed the every-turn `~/.claude` instruction load from 62,497 B / ~15,624 tokens to **22,328 B / ~5,582 tokens (−64%)**. Metaswarm-orchestrated, plan-gate-passed (`wceftatj1`), adversarially reviewed (0 gates dropped/weakened/leaked).

**What changed (all reversible; backup at `~/.claude/_harness-trim-backup-2026-06-05/`):**
- `rules/web/*.md` (7) + `rules/common/` code-rules (6: code-review, testing, patterns, performance, coding-style, development-workflow) + `rules/README.md` now carry `paths:` frontmatter → load only when a matching file is in context. KEPT GLOBAL: `common/{agents,git-workflow,hooks,security}.md`.
- Project `CLAUDE.md` 294→30 L: ALL metaswarm gates kept INLINE (terser); only the Tool-Routing tables + Code-Quality-Standards reference moved to `C:\Users\Prekzursil\guides\tool-routing-and-quality.md` (inline pointer kept so route-don't-refuse behavior survives).
- `settings.json`: added `InstructionsLoaded` diagnostic hook (logs `~/.claude/logs/instructions-loaded.log`) + SessionStart `compact` matcher → `compact-restore.ps1` re-injects the latest non-empty `.remember/tmp/precompact-*.md` (closes the compaction survival loop; write-side `snapshot.ps1` already existed). Hook scripts in `~/.claude/hooks/harness-trim/`.

**Why / How to apply:** This is the FIX for the [[toolkit-gap-analysis-2026-05]] context-rot diagnosis. `paths:` frontmatter is **native Claude Code** rule-gating (NOT ECC) — use **simple per-extension globs** (`**/*.tsx`…); brace-expansion `{a,b}` is unproven and silently matches nothing. Gates must stay INLINE — relocating them behind `--append-system-prompt` is a per-invocation flag that does NOT persist (a plan-review-gate caught this). DEFERRED: WU-H6 memory-layer consolidation (remember/claude-reflect plugins + ECC `ECC_DISABLED_HOOKS` Stop-hooks) — keep per-layer + reversible per [[feedback_mcp_enabled_state]]. Next-session check: the InstructionsLoaded log / session-start reminder should show the reduced set; if a scoped rule never reappears on a matching file the glob is wrong → fix or revert that file from backup. Records: `source/reports/PLAN-obj1-harness-2026-06-05.md` + `OBJ1-HARNESS-EXECUTION-RECORD-2026-06-05.md`. Part of the four-front program (master plan `source/reports/MASTER-AUDIT-AND-PLAN-2026-06-05.md`).