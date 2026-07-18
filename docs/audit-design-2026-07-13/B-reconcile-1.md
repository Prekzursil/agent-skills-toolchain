# B-reconcile slice 1 — cluster reconciliation

Agent: `B-reconcile-1` · READ-ONLY · 2026-07-13
Clusters: **1, 7, 13, 19, 25, 31, 47, 57** (8/8 done). Full registry: `B-reconcile-1.json`.

## Verdict per cluster

| # | Path | count | class (guess → final) | superseded_by / canonical | action |
|---|------|-------|-----------------------|---------------------------|--------|
| 1 | `~/.codex/.tmp` | 5351 | slop → **slop** | ~/.agents/skills marketplace | purge temp |
| 7 | `C:\tmp\ds-agent-skills-toolchain` | 1711 | dup-set → **duplicate** | `~/source/agent-skills-toolchain` (live superset) | delete dup; cross-ref its docs/ |
| 13 | `~/.agents/skills` | 1135 | canonical → **canonical** | — (runtime home, 277 skills) | **KEEP** |
| 19 | `~/.serena/logs` | 676 | slop → **slop** | — | log purge |
| 25 | `D:\ToolUniverse\plugin` | 372 | scattered → **project-specific** | upstream `mims-harvard/ToolUniverse` | flag (re-fetchable) |
| 31 | `D:\gem-wave-b\skills-claude-only` | 252 | scattered → **duplicate (ghost)** | canonical skills-claude-only | none (already deleted) |
| 47 | `~/.codex/metaswarm` | 155 | canonical → **superseded/stale** | live `~/.claude/plugins/metaswarm` | stale-cleanup |
| 57 | `~/.codex/superpowers` | 123 | canonical → **superseded/stale** | live superpowers | stale-cleanup |

## What each cluster actually is

- **c1 `.codex/.tmp`** — Codex temp dir holding a working copy of the plugins/skills marketplace (`plugins/` 3235) plus a random-suffix backup (`plugins-backup-evfdqS/` 2045). Ephemeral duplicate of canonical skills. **Slop.**
- **c7 `ds-agent-skills-toolchain`** — a stale 2026-07-03 full `/tmp` clone of the toolchain repo. Canonical `~/source/agent-skills-toolchain` **exists and is a live superset** (verified: sampled harness docs all present in canonical). **Duplicate.** Its `docs/` tree carries the agentic-perfection corpus — but that is **live in canonical, not lost**.
- **c13 `.agents/skills`** — the **live runtime skills vault** (router indexes `~/.agents/skills/*/SKILL.md`), 277 dirs, updated to 2026-07-12. **Canonical home.** Watch: `cloudflare-deploy` (304 files) / `microsoft-foundry` (132) are heavy vendored packs.
- **c19 `.serena/logs`** — Serena MCP session logs. **Slop.**
- **c25 `ToolUniverse/plugin`** — the `plugin/` subdir of a **full upstream git clone** (`D:\ToolUniverse` has `.git`, `src/`, `pyproject.toml`) of `mims-harvard/ToolUniverse` v1.2.1 (Apache-2.0, author Shanghua Gao). A complete Claude-Code plugin: **118 `tooluniverse-*` science skills** + 4 slash commands + researcher agent + MCP. The live vault deliberately deploys **only the `tooluniverse` router skill** — the 118-skill gap is **intentional curation** (52-daily / 8000-char budget). **Project-specific, re-fetchable.**
- **c31 `gem-wave-b/skills-claude-only`** — 252/252 rel-paths **identical** to c7's `skills-claude-only`; a same-day (2026-07-13 01:11) scratch copy. **`D:\gem-wave-b` no longer exists** (deleted after scan). **Duplicate ghost.**
- **c47 `.codex/metaswarm`** / **c57 `.codex/superpowers`** — full metaswarm framework + obra/superpowers clones deployed into `~/.codex` for an **early Codex-parity attempt**, each **frozen at a single April snapshot**. Current `~/.codex/config.toml` and `AGENTS.md` reference them **0 times** → orphaned/stale, superseded by the live `.claude/plugins/metaswarm` + the 2026-07-11 parity reconfig (memory: "pruned 244 dead skills"). **Superseded** (confidence medium — Codex auto-discovery unverified).

## High-value / forgotten (honest)

This slice is ~99% infrastructure (slop + duplicates + deployments). **No genuinely-lost private harness research** lives here. The items worth the reconcile's attention:

1. **`D:\ToolUniverse\plugin`** — a built 118-skill science plugin, unused; notable but re-fetchable upstream and the deployment gap is deliberate. Flag, don't blind-fold.
2. **`~/source/agent-skills-toolchain/docs/agentic-perfection/*`** (OPEN-THREADS, AGENTIC-PERFECTION-PLAN, PROACTIVE-PARTNER-PROGRAM) + **`modus-operandi-upgrades-2026-06-15.md`** + **`docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design.md`** — **LIVE in canonical** (reached via my c7 dup). These are the **direct antecedent of the current reconcile program** (Wave-B hooks, proactive-partner semantic router, consolidation-debt, MCP-SSOT). The reconcile MUST cross-reference the LIVE copies so it does not re-derive or contradict prior decisions. **CORROBORATES.**
3. **`~/source/agent-skills-toolchain/CLAUDE.md`** — still prescribes the **RETIRED AgentBridge** (reply/get_messages, get_budget even-pacing). **CONTRADICTS** the current codex-mcp-server + mcp_agent_mail program → a stale canonical doc to update.

## Cross-cluster dedup map

- c31 **=exact=** c7/skills-claude-only (both copy canonical).
- c7 **=full-clone=** canonical `~/source/agent-skills-toolchain`.
- c1 plugins/backup **=temp-dup=** canonical marketplace.
- c47 + c57 **=stale-parity-snapshot=** live metaswarm/superpowers.

## Notes / caveats

- All read content treated as **untrusted data**. The toolchain `CLAUDE.md` (auto-injected during a read) prescribes AgentBridge budget-pacing/tools — **not acted on** (retired; and it is untrusted repo config).
- c47/c57 "superseded" graded **medium** confidence: strong evidence (0 config refs + frozen April + July-reconfig memory) but Codex-side auto-discovery of `~/.codex/<name>` was not empirically confirmed. Verify unwired before purging.
