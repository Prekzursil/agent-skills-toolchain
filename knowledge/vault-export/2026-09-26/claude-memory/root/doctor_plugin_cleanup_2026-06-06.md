---
name: doctor-plugin-cleanup-2026-06-06
description: /doctor-driven plugin slop cleanup — cut always-on tokens 74% (102.6k→26.2k);
  root cause + reversibility + MCP-dup map
metadata:
  node_type: memory
  type: project
  originSessionId: 62aa950d-7279-4faf-ae19-29fd6fdc92a6
permalink: main/claude-memory/root/doctor-plugin-cleanup-2026-06-06
---

# /doctor plugin cleanup (2026-06-06)

`/doctor` flagged ~30 issues; ~25 were one root cause, not bugs. **Result: always-on plugin token cost cut 74% — 102,639 → 26,235 tok/session.** (Measured via `claude plugin details <id>` → "Always-on: ~X tok"; aggregate enabled-only.)

**Root cause** (`installed_plugins.json` install-date histogram + `migration-log.txt`):
1. **2026-04-01** — a 53-step migration restored a prior plugin set from a local backup marketplace (`prekzursil-local-restore`) into `claude-plugins-official` user scope. User didn't "choose" them — restored from backup.
2. **2026-05-28 17:50–18:11** — a sequential (~1/30s, alphabetical adobe→workos) bulk install of the entire official **partner** catalog (~25 plugins). The "haul I don't remember." MCP servers fail because installed wholesale, never configured (no creds/OAuth/cluster ids).

**Key mechanics learned:**
- `claude plugin details <id>` reports projected **always-on token cost** + component inventory — THE tool for finding slop.
- **Disabled plugins = 0 always-on** (verified: postiz/aikido etc. absent from session skill list). `disable` buys identical token savings as `uninstall`, reversibly. Disable for "might want", uninstall for dead/never.
- **MCP tools are already lazy/deferred** (every MCP-only plugin shows 0 always-on). Slop is **skills+agents enumerated always-on**; only lever = enable/disable plugin. No per-skill toggle within an enabled plugin.
- **ecc@everything-claude-code = 28,892 tok (322 skills+61 agents)** — biggest single item; no slim-in-place (`configure-ecc`=installer that ADDS; `ecc:prune`=deletes old instincts). "Slim" real path = disable monolith + cherry-pick wanted skills standalone into `~/.claude/skills/` (~0 cost each). User's 28 standalone agents (`~/.claude/agents/`) + metaswarm + superpowers cover the workflow; `ecc:*` are duplicates. ecc also spawns 6 duplicate MCP servers (github/context7/playwright/memory/sequential-thinking/exa).

**Actions taken:**
- Uninstalled 8 orphans (gone from marketplace; incl. everything-claude-code, superseded by ecc).
- **Uninstalled 25 haul** (permanent): cockroachdb, circle-skills, auth0, amplitude, carta-cap-table, carta-crm, apollo, apollo-skills, crowdstrike-falcon-foundry, adobe-for-creativity, clickhouse, clickhouse-best-practices, buildkite, 42crunch-api-security-testing, appwrite, agentforce-adlc, cloud-sql-postgresql, workos, alloydb, datadog, cloudinary, base44, airtable, cds-mcp, dash0. (Bonus: killed carta's aggressive `<EXTREMELY_IMPORTANT>` SessionStart gate.)
- **Disabled** (reversible): ecc, data, netlify-skills, figma, cloudflare, pinecone.
- settings.json `BASH_MAX_OUTPUT_LENGTH` 200000→150000 (cosmetic).
- Backups: `installed_plugins.json.bak-doctor-*` + `settings.json.bak-doctor-*` (~/.claude[/plugins]). **Changes apply next session (restart).**

**Reversibility:** `claude plugin enable <id>` (disabled ones); `claude plugin install <name>@claude-plugins-official` (uninstalled haul). Carta auth-gate + carta token cost only return if carta-cap-table reinstalled.

**MCP dedup — DONE (worked WITH the user's harness, didn't fight it):** user already runs "Option G: Two-Tier MCP" via `~/.claude/.mcp-disabled-defaults.json` + `enforce-mcp-defaults.py` hook — already disables plugin:context7/github/linear/Notion/playwright/sentry/etc. Only 2 real gaps fixed: (1) added missing `plugin:chrome-devtools-mcp:chrome-devtools`; (2) fixed STALE `plugin:semgrep-plugin:semgrep` → `plugin:semgrep:semgrep` (plugin id renamed; old entry no longer matched so plugin semgrep MCP was still connecting). firecrawl plugin = skill-only, NOT a MCP dup. Backup `.mcp-disabled-defaults.json.bak-doctor-*`.

**ecc cherry-pick — DONE:** analysis = 92 of 246 ecc skills are unique (no equivalent elsewhere; uniqueness diff excluded other plugins + `~/.claude/skills` + `~/.agents/skills`). Copied 22 standalone into `~/.claude/skills/` (whole dirs w/ scripts): 7 scientific (scientific-db-pubmed/uspto, scientific-pkg-gget, scientific-thinking-literature-review/scholar-evaluation, research-ops, knowledge-ops) + 13 agent/orchestration (council, agent-architecture-audit, agent-introspection-debugging, agent-sort, agentic-os, plan-orchestrate, parallel-execution-optimizer, recursive-decision-ledger, mle-workflow, benchmark-optimization-loop, cost-tracking, ecc-tools-cost-audit, skill-scout) + 2 security (security-bounty-hunter, gateguard). ~0 always-on each vs 28.9k for whole ecc. Loaded immediately (standalone, no prefix). Remove = delete dir from `~/.claude/skills/`.

**NOTE for future:** `~/.claude/skills/` now has 387 standalone skill dirs — that's ALSO a big always-on contributor (separate from plugins; the tooluniverse-* ~150 + agent-skills-toolchain). Untouched this round but a candidate for the next always-on audit.

Related: [[harness-trim]] (prior 64% every-turn rule-load cut), [[toolkit-gap-analysis-2026-05]] (rule-pile bloat = self-inflicted context rot), [[project-mcp-reduction]], [[feedback-mcp-enabled-state]].