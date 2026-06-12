# Workspace Curation — Single Source of Truth

**Last curated:** 2026-06-11 · **Backup of pre-cleanup config:** `~/.claude/_config-backups/cleanup_2026-06-11_045014/`

This file documents the deliberately-curated plugin/MCP state and the **rule that keeps it from re-bloating**. Read this before installing plugins or "fixing" context overhead again.

---

## Why things kept reappearing (root cause)

1. **Install = enabled-by-default.** A plugin in `installed_plugins.json` is ON unless something *explicitly* sets it `false`. ~86 of 100 installed plugins were never explicitly disabled, so every reload/update re-affirmed them.
2. **Scope mismatch.** Disabling via the `/plugin` UI (or `claude plugin disable` without a flag) writes to **project** scope → the plugin returns the moment your working directory changes. The fix is **`--scope user`** (global).
3. **Triple-layered MCP definitions.** Many capabilities existed as a standalone MCP in `~/.claude.json` **and** a project MCP in `~/.mcp.json` **and** a marketplace plugin — all at once.

## The rule (do this, every time)

- **Disable globally:** `claude plugin disable <name>@<marketplace> --scope user` — never rely on the UI toggle.
- **Re-enable:** `claude plugin enable <name>@<marketplace>`
- **New install = decision:** after `claude plugin install X`, immediately either keep it (note below) or `claude plugin disable X --scope user`. Don't leave it implicitly on.
- **One provider per capability:** if a capability exists as a standalone MCP, disable the plugin that duplicates it (and vice-versa).
- **Cost check before keeping:** `claude plugin details <name>` shows projected token cost.

---

## Enabled plugins (the allow-list of 12)

| Plugin | Why kept |
|--------|----------|
| `codex@openai-codex` | Codex orchestration / cross-model review |
| `metaswarm@metaswarm-marketplace` | Project framework (this repo's CLAUDE.md is built on it) |
| `superpowers@claude-plugins-official` | brainstorming / TDD / debugging skills the workflow references |
| `remember@claude-plugins-official` | session handoff memory |
| `claude-reflect@claude-reflect-marketplace` | session reflection |
| `hookify@claude-plugins-official` | hook authoring |
| `document-skills@anthropic-agent-skills` | pdf/docx/xlsx/pptx generation |
| `exa@claude-plugins-official` | research (used by deep-research) |
| `ralph-loop@claude-plugins-official` | Ralph autonomous loops (BC RE work) |
| `security-guidance@claude-plugins-official` | secure-by-default prompt guidance |
| `explanatory-output-style` + `learning-output-style` | active output styles |

**Already off by prior choice (left as-is):** `ecc@everything-claude-code` (your "disable + cherry-pick" plan; ~28.9k tokens — biggest remaining win once cherry-picked), `pyright-lsp` and other language LSPs.

## MCP layers (deduplicated)

- **User scope** (`~/.claude.json` → always on, ~21): your own servers — `basic-memory`, `tooluniverse`, `scholarly-access`, `academia`, `insta-mcp`, `fb-messenger`, `tiktok`, `schrodinger`, `rdkit`, `ocr`, `gogcli-classroom`, `mcp-funnel` (gateway project), plus remote `github`/`huggingface`/`context7`/`figma`/`linear`/`notion`/`apify`/`playwright`/`firefox-devtools`.
- **Project approval-list** (`~/.claude/settings.local.json` → `enabledMcpjsonServers`, trimmed 28 → 18): RE stack (`ida-pro-mcp`, `ghidra-mcp`, `binary-ninja-mcp`, `frida-mcp`, `cheatengine`, `hexstrike-ai`), research (`firecrawl`, `tavily`), quality (`codacy`, `deepsource`, `sonarqube`), utility (`repomix`, `excel`, `pdf-reader`, `markitdown`, `meta-tool`, `memory`, `ralph-orchestrator`).
- **Removed as dups/unused from approval-list:** `huggingface`, `apify` (already in user scope), `github_cli` (redundant with `github` MCP + `gh` CLI), `browserstack`, `digitalocean`, `scrapegraph`, `mcp-graphql`, `docker`, `postgres`, `codecov`.
- **`local-mcp-bridge` plugin disabled** — it re-exposed `binary-ninja`/`frida`/`github_cli` that already exist standalone (Ralph uses its own project `.mcp.json`, so unaffected).

## Skills triage (2026-06-11) — 164 → 111
Archived (reversible) from `~/.claude/skills` → `~/.claude/skills-archived-2026-06-11/` (see its `RESTORE.md`):
- **34 `source-command-*`** — migration duplicates ("Use this skill when the user asks to run the migrated source command X"); the live `/X` commands + agents already exist separately.
- **13 enterprise/business templates** — carrier-relationship, customs-trade, energy-procurement, inventory-demand, logistics-exception, production-scheduling, quality-nonconformance, returns-reverse, investor-materials/outreach, market-research, content-engine, article-writing (no fit to RE/agents/infra/drug-discovery/social work).
- **5 unused domain/language** — swiftui-patterns, liquid-glass-design, java-coding-standards, clickhouse-io, foundation-models-on-device.
- **1 superseded** — continuous-learning (v1 → continuous-learning-v2 kept).

Skill changes take effect **immediately** (no restart). The 38 symlinked active skills (codex-*, agent-lanes-*, RE stack) and ~73 other real-dir tools were **kept**. NOTE: this only touched `~/.claude/skills` (Claude Code's load path). The mirror `~/.agents/skills` (Codex/Antigravity) and the git source `~/source/agent-skills-toolchain` were left untouched — prune those + re-run `scripts/sync-skills.ps1 -Prune` for cross-tool + git permanence.

Restore all: `Move-Item ~/.claude/skills-archived-2026-06-11/* ~/.claude/skills/ -Force`

## Optional further wins (not done — your call)
- **Cherry-pick + disable `ecc`** → reclaim ~28.9k (verify it doesn't provide your event-ledger/gateguard hooks first; those appear to live in `~/.claude/hooks`).
- **Browser consolidation:** you still have `playwright` + `firefox-devtools` + `claude-in-chrome`. Keep one.
- **`claude plugin uninstall <name>`** the disabled ones to also free disk (disable already removes the *context* cost).

## SOTA pass (2026-06-11, 9-agent audit + adversarial critique)
Second backup: `~/.claude/_config-backups/sota_2026-06-11_055957/` (+ `junction-restore.tsv` maps re-pointed junctions to old targets).
- **A5 (biggest fix):** 33 skill junctions in `~/.claude/skills` were pointing at a **2-month-stale** checkout (`work\agent-skills-toolchain-re`, frozen 2026-04-01) → re-pointed to live canon `source\agent-skills-toolchain`. Also enriched their descriptions. **2 stale junctions remain on purpose:** `agent-lanes-codex-consult`, `promptbridge-codex-consult` (no canon replacement live yet). Retire the `work-re` checkout only after migrating those 2.
- **A6:** removed `agent-lanes-codex-curate`, `agent-lanes-codex-review` (bare `codex-curate`/`codex-review` are live).
- **A7:** archived 7 redundant skills (agentic-engineering, ai-first-engineering, enterprise-agent-ops, continuous-agent-loop, iterative-retrieval, coding-standards, project-guidelines-example) → `skills-archived-2026-06-11`.
- **A8/A9/A10:** archived 13 unused-language agents → `agents-archived-2026-06-11`; 13 unused-language commands → `commands-archived-2026-06-11`; removed empty `commands\.sonar`.
- **A4:** removed 9 dup/dead user-scope MCPs (context7, figma, github, linear, notion, apify, gogcli-classroom, academia, firefox-devtools). **Kept** huggingface (sole HF access) + playwright (visual-review needs it). User MCP 21→12.
- **A1/A11:** settings.json — flipped circleback/greptile/data-agent-kit-starter-pack true→false (both-files-agree hygiene); removed redundant `voiceEnabled` scalar.
- **A2/A3:** settings.local.json approval-list 18→12 (dropped memory[orphan], deepsource, codacy, sonarqube, meta-tool, pdf-reader).
- **B4:** uninstalled stale `brightdata-plugin@brightdata-plugins` v1.4.0 + removed its local marketplace (dup of official v1.8.0).

**Critique-rejected (do NOT add — flagged so a later pass won't re-suggest):** Serena MCP "add" (already installed+enabled — the 13th plugin), `sequential-thinking`/vector-DB/2nd-memory MCPs (re-bloat), MCP-result token-guard + `mcp__.*` anti-degen matcher (false-positive/​truncate RE tools — `server_health`/`decompile` are idempotent-by-design). The proposed `permissions.deny` backstop was Windows-blind (matched `rm -rf` not PowerShell `Remove-Item -Recurse`) — rewrite for PowerShell verbs if adopted.

**Pending RELOAD/RESTART to fully apply:** A4 MCP removals + A1 plugin flips (skill/agent/command archives + junctions already live).

## Full restore (undo everything)
```powershell
Copy-Item {{USER_HOME}}\.claude\_config-backups\cleanup_2026-06-11_045014\* -Destination ... # see backup dir
```
Each file in the backup dir is named with `__` for path separators (e.g. `.claude__settings.json`).
