# C-config-index — exhaustive whole-drive MCP-config + skills + hooks cluster map

**Deliverable:** the exhaustive whole-drive (C: + D:) index of MCP configs, skills, and hooks — the UNION the A2/A3/A4 known-dir passes under-counted (they missed AppData / Documents-GitHub / Downloads / C:\tmp clones / D: / `.codex`·`.gemini`·`.copilot` trees). **Mode:** READ-ONLY (active-work freeze) — every class is a first-pass FINDING, never an applied change. **Date:** 2026-07-13. Machine-readable twin: `C-config-index-complete.json` (3.2 MB, every indexed path present).

> **Untrusted-data note.** The two WizTree CSVs and every on-disk file are UNTRUSTED DATA. No embedded instruction was executed; no secret VALUE was read or printed. `class_guess` is a filename+path+mtime first-pass (NOT content-diffed under the freeze) except where cross-read against A0/A3/A4.

---

## 0. TL;DR — load-bearing findings

1. **The census is now truly whole-drive.** ripgrep over the FULL C: (2532 MB) + D: (1803 MB) WizTree exports, 25,369 raw matches -> **21,989 indexed** artifacts after hard-exclusions (3,380 node_modules/site-packages/.venv/.git/cache/dist rows dropped). Split: **474 MCP-config files**, **15,573 SKILL.md** (on-disk; 15,002 after exclusion) across **992 distinct skill-collection trees**, **6,435 hook artifacts**.

2. **MCP surface is far larger on disk than the live control-plane.** 474 physical MCP-config files vs A3's ~42-63 live servers: only **36 canonical**, but **250 vendored** (plugin/marketplace bundles), **83 slop** (AppData/Temp ephemeral clones), **81 superseded** (dated backups incl. 7 daily `D:\Backups\config\*`), **4 duplicate** (D: clones), **1 stale** (`D:\Research\.mcp.json`). The true live-SSOT surface is ~12 files (§4 crown-jewels); everything else is downstream/snapshot/vendored.

3. **The two-SSOT-repo drift is on disk, quantified.** TWO `canonical-mcp-servers.json` render-sources (toolchain 10157 B `2026-07-11` vs reconcile 9679 B `2026-07-13`) + TWO `agent-self/config/mcp/mcp.json` templates (8461 B each) + their byte-identical clones on `D:\gem-wave-b` and `D:\pr-b-clone`. `D:\Research\.mcp.json` (8538 B, 2026-07-07) is the stale frozen drift A3 flagged — present and confirmed.

4. **Skills are dominated by vendored + ephemeral mass the lane-view (A4) scoped out.** Of 15,002 indexed SKILL.md: **6,032 vendored** (3,469 `~/.claude/plugins`, 941 `~/.grok/marketplace-cache`, 690 `~/.codex/plugins`, +VS/WindowsApps), **5,693 slop** (4,302 AppData/Temp session clones, 1,021 `~/.codex/.tmp`, 352 `C:\tmp\ds-*`), **753 duplicate** (D: gem-wave-b/pr-b-clone), only **1,353 canonical**. A4's 8 live lanes (union 491 names) are the canonical core inside this mass.

5. **Hooks: 6,435 artifacts, but only 538 are harness-canonical and just 167 are the actual `~/.claude/hooks` scripts** (the '65 dirs / 2 wired' set). The other 4,292 are plugin-vendored `hooks/*.js|.py`, 1,147 slop (Temp/ds/codex-tmp), 331 D-clone copies, 165 reconcile + 160 toolchain repo-source. The wired-vs-present gap is enormous.

---

## 1. Coverage & method

| | C: | D: |
|---|---|---|
| WizTree export | `WizTree_20260713055603 (C).csv` (2532 MB) | `WizTree_20260713060430 (D).csv` (1803 MB) |
| Raw matched rows | 22,730 | 2,639 |

ripgrep -i over both full CSVs with a 14-pattern name-filter (SKILL.md; *.mcp.json/mcp.json/mcp-servers.json/mcp-config.json/canonical-mcp-servers.json/.mcp-*.json/.mcp.toml; .claude.json/claude.json; config.toml; settings.json/settings.local.json; hooks.json; /hooks/*.py|.sh|.js|.ps1|.mjs|.cjs|.ts). 25,369 raw matched rows -> Python classifier: parse col1, categorize by basename, apply hard-exclusions, cluster by (category+domain+dir), assign first-pass class. rg pass = ~12s over 4.3GB.

**Column-1 parse is exact:** a Windows filename cannot contain `"`, so the first `"` after index 0 terminates the path field; size=field 2, mtime=field 4. (rg also matches the quoted FOLDERNAME column, which surfaced 7 false-positive rows from a dir literally named `settings.json` in gem-hunt staging — correctly discarded because category is re-derived from the true col-1 basename, so **no false negatives**.)

### Exclusions (hard-filtered OUT — reported, not indexed)

| Reason | Rows |
|---|---:|
| site-packages | 1808 |
| node_modules | 1385 |
| uv-cache | 165 |
| cargo | 12 |
| dot-cache | 6 |
| dist | 3 |
| pycache | 1 |
| **TOTAL excluded** | **3380** |

Hard-excluded from the index per task scope (node_modules/.venv/site-packages/.git-internal/language+pkg caches/dist). model-weights: N/A (no weight file matches a config/skill/hook name pattern). Agent plugin/marketplace caches (.claude/plugins, .grok/marketplace-cache, .codex/plugins) were NOT treated as excludable "caches" — they hold real vendored skill/mcp trees and are INDEXED as class=vendored (documented judgment call).

---

## 2. Headline totals

| Metric | Value |
|---|---:|
| mcp_locations_indexed | 474 |
| config_toml_nonmcp_indexed | 71 |
| skill_md_total_ondisk | 15,573 |
| skill_md_indexed_nonexcluded | 15,002 |
| skill_leaf_dirs | 15,002 |
| skill_collection_trees | 992 |
| hook_artifacts_indexed | 6,435 |
| hook_canonical_harness | 538 |
| hook_scripts_in_~claude_hooks | 167 |
| total_rows_indexed | 21,989 |
| total_clusters | 164 |

---

## 3. MCP configs (474)

**By class:** vendored 250, slop 83, superseded 81, canonical 36, scattered 10, unknown 9, duplicate-copy 4, stale 1.

**By name-type:** `.mcp.json` 268, `config.toml (.codex, mcp_servers)` 78, `mcp.json` 48, `claude.json/.claude.json` 31, `.mcp-*.json (funnel/preset/disabled)` 20, `mcp-servers.json` 16, `canonical-mcp-servers.json` 7, `mcp-config.json` 6.

_Plus 71 non-MCP `config.toml` (rust/tool configs outside `.codex`) captured as candidate name-pattern matches and classed away from MCP._

### 3a. Clusters

| Count | Class | Domain | Cluster (dir + name) | mtime span |
|---:|---|---|---|---|
| 141 | vendored | claude | vendored: ~/.claude/plugins (installed marketplaces) | 2026-04-01…2026-07-12 |
| 70 | slop | appdata | slop: AppData/Local/Temp (ephemeral session clones) | 2026-07-03…2026-07-11 |
| 40 | vendored | appdata | vendored: AppData/Roaming/Claude (Claude Desktop sessions/config) | 2026-03-30…2026-06-15 |
| 32 | superseded | appdata | superseded: Documents/claude-desktop-backup-20260524 | 2026-03-30…2026-05-24 |
| 27 | vendored | codex | vendored: ~/.codex/plugins (installed marketplaces) | 1970-01-01…2026-07-11 |
| 21 | superseded | D-backups | superseded: D:/Backups (dated legit backups) | 2026-07-03…2026-07-12 |
| 20 | vendored | grok | vendored: ~/.grok/marketplace-cache (Grok skill marketplace) | 2026-05-26…2026-07-04 |
| 13 | canonical | claude | canonical: ~/.claude/checkpoints (harness live state) | 2026-06-29…2026-07-07 |
| 11 | superseded | codex | superseded: ~/.codex/backups | 2026-03-23…2026-07-11 |
| 10 | slop | codex | slop: ~/.codex/.tmp (transient plugin staging) | 2026-06-21…2026-07-10 |
| 9 | unknown | other | unknown: unmatched location | 2025-05-26…2026-07-12 |
| 9 | superseded | claude | superseded: ~/.claude/_config-backups (dated config bak) | 2026-06-10…2026-06-16 |
| 7 | vendored | tool | vendored: ~/.local/src\|opt (mcp-server source, e.g. agent-mail) | 2026-07-11…2026-07-11 |
| 6 | canonical | agents | canonical: ~/.agents/generated (per-editor projection) | 2026-06-15…2026-07-12 |
| 5 | canonical | codex | canonical: ~/.codex/* (Codex config tree) | 2026-02-22…2026-07-11 |
| 4 | superseded | D-tools | superseded: D:/Tools/mcp-gateway/backups | 2026-06-10…2026-06-10 |
| 3 | vendored | appdata | vendored: AppData/Roaming/Code (VSCode) | 2025-12-17…2026-07-13 |
| 3 | vendored | D-tools | vendored: D:/Program Files (app bundles, e.g. VS) | 2026-05-26…2026-05-26 |
| 2 | scattered | downloads | scattered: Downloads (cloned/downloaded repos) | 2026-03-11…2026-04-09 |
| 2 | scattered | documents-github | scattered: Documents/GitHub (mixed projects) | 2026-07-06…2026-07-11 |
| 2 | vendored | tool | vendored: ~/scoop (scoop apps) | 2026-07-07…2026-07-07 |
| 2 | vendored | gemini | vendored: ~/.gemini extensions/antigravity-cli | 2026-03-20…2026-05-24 |
| 2 | canonical | gemini | canonical: ~/.gemini MCP config | 2026-05-24…2026-06-18 |
| 2 | superseded | appdata | superseded: ~/backups (metaswarm/gemini sync snapshots) | 2026-03-30…2026-03-30 |
| 2 | vendored | codex | vendored: WindowsApps (Codex app bundle skills) | 2026-07-10…2026-07-10 |
| 2 | slop | ctmp-ds | slop: C:/tmp/ds-* (design-studio temp clones) | 2026-07-03…2026-07-03 |
| 2 | duplicate-copy | D-clone | duplicate: D:/pr-b-clone (full repo clone) | 2026-07-12…2026-07-12 |
| 2 | duplicate-copy | D-clone | duplicate: D:/gem-wave-b (full repo clone) | 2026-07-13…2026-07-13 |
| 2 | scattered | D-tools | project: D:/MCP (RE mcp-server dev, e.g. ghidra-mcp) | 2026-03-11…2026-03-11 |
| 1 | vendored | appdata | vendored/scattered: AppData/Roaming (mixed app data) | 2026-06-12…2026-06-12 |
| 1 | canonical | claude | canonical: ~/.claude/.mcp-disabled-defaults.json (per-project RAM mask) | 2026-07-04…2026-07-04 |
| 1 | superseded | claude | superseded: ~/.claude/_harness-trim-backup-2026-06-05 | 2026-06-05…2026-06-05 |
| 1 | canonical | claude | canonical: ~/.claude/mcp-configs (fragment) | 2026-04-05…2026-04-05 |
| 1 | vendored | vscode | vendored: ~/.vscode/extensions | 2026-06-30…2026-06-30 |
| 1 | canonical | codex | canonical: ~/.codex/config.toml (Codex mcp_servers) | 2026-07-13…2026-07-13 |
| 1 | canonical | toolchain | canonical: toolchain tools/mcp/canonical-mcp-servers.json (render src #1) | 2026-07-11…2026-07-11 |
| 1 | canonical | toolchain | canonical: toolchain repo (skills/hooks/mcp source, feat branch) | 2026-07-06…2026-07-06 |
| 1 | canonical | source | project: source/repos (per-project dev, e.g. insta-mcp) | 2026-06-05…2026-06-05 |
| 1 | canonical | reconcile | canonical: reconcile tools/mcp/canonical-mcp-servers.json (render src #2, two-SSOT drift) | 2026-07-13…2026-07-13 |
| 1 | canonical | reconcile | canonical: ast-harness-reconcile repo (de-facto source of deployed) | 2026-07-13…2026-07-13 |
| 1 | scattered | scattered | scattered: ~/rf-final | 2026-07-03…2026-07-03 |
| 1 | superseded | agents | superseded: ~/.agents/backups | 2026-07-12…2026-07-12 |
| 1 | vendored | claude | vendored: ~/.claude-runtime (local mcp marketplace) | 2026-07-12…2026-07-12 |
| 1 | canonical | claude | canonical: ~/.claude.json (user-scope mcpServers, live) | 2026-07-13…2026-07-13 |
| 1 | canonical | claude | canonical: ~/.mcp.json (live MCP SSOT) | 2026-07-13…2026-07-13 |
| 1 | slop | ctmp-ds | slop: C:/tmp (ad-hoc temp clones) | 2026-07-03…2026-07-03 |
| 1 | stale | D-research | stale: D:/Research/.mcp.json (frozen pre-reconcile MCP drift) | 2026-07-07…2026-07-07 |
| 1 | scattered | D-reverse | project: D:/ReverseTools (RE toolkit) | 2026-05-24…2026-05-24 |
| 1 | scattered | D-tools | scattered: D:/Tools | 2026-06-10…2026-06-10 |
| 1 | scattered | D-other | scattered: D:/ (other) | 2026-05-27…2026-05-27 |

---

## 4. MCP crown-jewels — the live / near-live SSOT surface

The ~12 files that actually drive the MCP control-plane (everything else in §3 is a vendored bundle, a dated backup, a checkpoint snapshot, or an ephemeral Temp clone). Sizes/mtimes are live-CSV.

| Path | Size | mtime | Class | Role |
|---|---:|---|---|---|
| `~\.mcp.json` | 8851 | 2026-07-13 | canonical | LIVE SSOT — hand-curated, loaded at HOME scope |
| `~\.claude.json` | 146159 | 2026-07-13 | canonical | LIVE user-scope mcpServers (what every session loads) |
| `~\.claude\.mcp-disabled-defaults.json` | 3014 | 2026-07-04 | canonical | per-project RAM mask |
| `~\.claude\mcp-configs\mcp-servers.json` | 5555 | 2026-04-05 | canonical | claude mcp fragment |
| `~\source\agent-skills-toolchain\tools\mcp\canonical-mcp-servers.json` | 10157 | 2026-07-11 | canonical | RENDER SRC #1 (toolchain, feat branch) |
| `~\source\ast-harness-reconcile\tools\mcp\canonical-mcp-servers.json` | 9679 | 2026-07-13 | canonical | RENDER SRC #2 (reconcile) — two-SSOT drift |
| `~\source\agent-skills-toolchain\agent-self\config\mcp\mcp.json` | 8461 | 2026-07-06 | canonical | repo {{USER}} template (toolchain) |
| `~\source\ast-harness-reconcile\agent-self\config\mcp\mcp.json` | 8461 | 2026-07-13 | canonical | repo {{USER}} template (reconcile) |
| `~\.codex\config.toml` | 16197 | 2026-07-13 | canonical | LIVE Codex mcp_servers |
| `~\.codex\mcp-configs\mcp-servers.json` | 5555 | 2026-04-05 | canonical | codex mcp fragment |
| `~\.gemini\config\mcp_config.json` | 178 | 2026-06-18 | canonical | LIVE Gemini mcp |
| `~\.gemini\antigravity-cli\mcp_config.json` | 0 | 2026-05-24 | canonical | Antigravity mcp |
| `~\.agents\generated\claude.mcp.json` | 8239 | 2026-07-12 | canonical | generated projection (claude) |
| `~\.agents\generated\antigravity.mcp.json` | 1734 | 2026-06-15 | canonical | generated projection (antigravity) |
| `~\.agents\generated\cursor.mcp.json` | 862 | 2026-06-15 | canonical | generated projection (cursor) |
| `~\.agents\generated\windsurf.mcp.json` | 816 | 2026-06-15 | canonical | generated projection (windsurf) |
| `~\.agents\generated\junie.mcp.json` | 816 | 2026-06-15 | canonical | generated projection (junie) |
| `~\.agents\generated\copilot.vscode.mcp.json` | 859 | 2026-06-15 | canonical | generated projection (copilot) |
| `~\source\repos\insta-mcp\.mcp.json` | 235 | 2026-06-05 | canonical | project-scoped dev (insta-mcp) |
| `D:\Research\.mcp.json` | 8538 | 2026-07-07 | stale | STALE frozen drift (pre-reconcile) |
| `D:\gem-wave-b\tools\mcp\canonical-mcp-servers.json` | 10157 | 2026-07-13 | duplicate-copy | DUPLICATE clone (D:) |
| `D:\pr-b-clone\tools\mcp\canonical-mcp-servers.json` | 10157 | 2026-07-12 | duplicate-copy | DUPLICATE clone (D:) |

**Snapshot/backup MCP copies (NOT live, summarized):** 11 `~/.claude/checkpoints/*/copies/*.mcp.json(+.disabled)` (session checkpoint snapshots), 8 `~/.claude/_config-backups/*` (dated), 7 daily `D:\Backups\config\*` sets (`.claude.json`+`.mcp.json`+`.mcp.disabled.json`), 5 `~/.codex/backups/*/config.toml`, 4 `D:\Tools\mcp-gateway\backups\clean\.mcp-funnel*`, 20 `claude-desktop-backup-20260524` extension/session configs, 70+ AppData/Temp ephemeral `.mcp.json`. Full list in the JSON `mcp_configs` array.

---

## 5. Skills (15,573 on disk / 15,002 indexed / 992 trees)

**By class:** vendored 6032, slop 5693, canonical 1353, duplicate-copy 753, superseded 536, scattered 323, stale 163, unknown 149.

### 5a. Clusters (top 30 by count)

| Count | Class | Domain | Cluster (dir + name) | mtime span |
|---:|---|---|---|---|
| 4302 | slop | appdata | slop: AppData/Local/Temp (ephemeral session clones) | 2026-06-30…2026-07-12 |
| 3469 | vendored | claude | vendored: ~/.claude/plugins (installed marketplaces) | 2026-04-01…2026-07-12 |
| 1021 | slop | codex | slop: ~/.codex/.tmp (transient plugin staging) | 2026-05-17…2026-07-10 |
| 941 | vendored | grok | vendored: ~/.grok/marketplace-cache (Grok skill marketplace) | 2026-05-26…2026-07-04 |
| 690 | vendored | codex | vendored: ~/.codex/plugins (installed marketplaces) | 1970-01-01…2026-07-11 |
| 461 | canonical | reconcile | canonical: ast-harness-reconcile repo (de-facto source of deployed) | 2026-04-05…2026-07-13 |
| 376 | duplicate-copy | D-clone | duplicate: D:/gem-wave-b (full repo clone) | 2026-07-13…2026-07-13 |
| 374 | duplicate-copy | D-clone | duplicate: D:/pr-b-clone (full repo clone) | 2026-07-12…2026-07-12 |
| 370 | canonical | toolchain | canonical: toolchain repo (skills/hooks/mcp source, feat branch) | 2026-03-10…2026-07-11 |
| 366 | vendored | appdata | vendored: AppData/Roaming/Claude (Claude Desktop sessions/config) | 2026-03-30…2026-06-15 |
| 352 | slop | ctmp-ds | slop: C:/tmp/ds-* (design-studio temp clones) | 2026-07-03…2026-07-03 |
| 283 | canonical | agents | canonical: ~/.agents/skills (deployed vault, router src) | 2026-03-10…2026-07-12 |
| 255 | scattered | D-other | scattered: D:/ (other) | 2026-05-27…2026-07-06 |
| 221 | superseded | codex | superseded: ~/.codex/backups | 2026-02-03…2026-04-01 |
| 213 | superseded | appdata | superseded: Documents/claude-desktop-backup-20260524 | 2026-03-30…2026-05-24 |
| 163 | stale | agents | stale: ~/.agents/library (dormant SWE-pattern import, 2026-04-05) | 2026-04-05…2026-06-10 |
| 120 | unknown | unknown | unknown: ~/work (needs owner triage) | 2026-03-31…2026-04-01 |
| 92 | vendored | D-tools | vendored: D:/Program Files (app bundles, e.g. VS) | 2026-05-26…2026-05-26 |
| 75 | canonical | claude | canonical: ~/.claude/skills.daily (LIVE-loaded curated subset) | 2026-04-04…2026-07-12 |
| 74 | vendored | gemini | vendored: ~/.gemini extensions/antigravity-cli | 2026-03-20…2026-07-03 |
| 62 | vendored | vscode | vendored: ~/.vscode/extensions | 2026-06-29…2026-07-10 |
| 60 | superseded | claude | superseded: ~/.claude/skills-archived-2026-06-11 | 2026-04-05…2026-06-10 |
| 60 | vendored | codex | vendored: ~/.codex/.agents (codex-side skills) | 2026-03-30…2026-07-11 |
| 57 | vendored | appdata | vendored: AppData/Roaming/Code (VSCode) | 2026-05-31…2026-07-10 |
| 56 | canonical | gemini | canonical: ~/.gemini/skills (Gemini/agy skill lane) | 2026-05-31…2026-07-10 |
| 56 | vendored | copilot | vendored: ~/.copilot (Copilot skills lane) | 2026-05-31…2026-07-10 |
| 39 | vendored | codex | vendored: ~/.codex/vendor_imports | 2026-04-09…2026-07-10 |
| 37 | superseded | claude | superseded: ~/.claude/skills.pre-agents-* | 2026-04-01…2026-04-01 |
| 35 | canonical | codex | canonical: ~/.codex/* (Codex config tree) | 2026-02-18…2026-07-10 |
| 30 | canonical | source | project: source/repos (per-project dev, e.g. insta-mcp) | 2026-06-11…2026-07-03 |

_Full per-cluster path lists in JSON `skills_by_cluster`._ A4 verified the canonical core (8 live lanes, union 491 names: daily 75 / deployed 277 / wt_top 224 / external 54 / tc_top 192 / claude_only 36 / library 186 / retired 5) — those sit inside the `canonical`/`stale` rows here; the vendored+slop+duplicate rows are the whole-drive mass A4 scoped out.

---

## 6. Hooks (6,435)

**Subtype split:** settings.json/settings.local.json 227, hook-script(.py/.sh/.js/.ps1/...) 6043, hooks.json 165.

**By class:** vendored 4292, slop 1147, canonical 538, duplicate-copy 331, unknown 61, scattered 47, superseded 19.

**Canonical-harness subset (538):** 167 scripts in `~/.claude/hooks` (the wired-engine dir), 165 reconcile-repo + 160 toolchain-repo source copies, 22 `~/.codex` + 7 `~/.codex/hooks`, 9 checkpoint copies, 2 `~/.claude/settings*.json` hook-registration files, +misc. The settings.json hook-registration SSOT is `~/.claude/settings.json` (+`settings.local.json`); the ECC/hooks.json registrations are within the repo-source and `~/.claude` sets.

### 6a. Clusters (top 22 by count)

| Count | Class | Domain | Cluster (dir + name) | mtime span |
|---:|---|---|---|---|
| 3897 | vendored | claude | vendored: ~/.claude/plugins (installed marketplaces) | 2026-04-01…2026-07-12 |
| 995 | slop | appdata | slop: AppData/Local/Temp (ephemeral session clones) | 2026-01-14…2026-07-13 |
| 167 | canonical | claude | canonical: ~/.claude/hooks (harness hook scripts) | 2026-04-01…2026-07-12 |
| 165 | canonical | reconcile | canonical: ast-harness-reconcile repo (de-facto source of deployed) | 2026-04-05…2026-07-13 |
| 161 | duplicate-copy | D-clone | duplicate: D:/pr-b-clone (full repo clone) | 2026-07-12…2026-07-12 |
| 161 | duplicate-copy | D-clone | duplicate: D:/gem-wave-b (full repo clone) | 2026-07-13…2026-07-13 |
| 160 | canonical | toolchain | canonical: toolchain repo (skills/hooks/mcp source, feat branch) | 2026-04-04…2026-07-11 |
| 148 | slop | ctmp-ds | slop: C:/tmp/ds-* (design-studio temp clones) | 2026-07-03…2026-07-03 |
| 142 | vendored | grok | vendored: ~/.grok/marketplace-cache (Grok skill marketplace) | 2026-05-26…2026-07-06 |
| 141 | vendored | appdata | vendored/scattered: AppData/Local (editors, tools) | 2025-07-01…2026-07-13 |
| 61 | unknown | other | unknown: unmatched location | 2025-10-12…2026-07-13 |
| 31 | vendored | codex | vendored: ~/.codex/plugins (installed marketplaces) | 1970-01-01…2026-07-11 |
| 25 | scattered | downloads | scattered: Downloads (cloned/downloaded repos) | 2024-04-06…2026-06-15 |
| 24 | vendored | appdata | vendored/scattered: AppData/Roaming (mixed app data) | 2025-10-23…2026-07-12 |
| 22 | canonical | codex | canonical: ~/.codex/* (Codex config tree) | 2026-03-15…2026-07-11 |
| 15 | vendored | vscode | vendored: ~/.vscode/extensions | 2025-10-18…2026-07-08 |
| 11 | vendored | tool | vendored: ~/.local/src\|opt (mcp-server source, e.g. agent-mail) | 2026-05-21…2026-07-11 |
| 11 | vendored | tool | vendored: Program Files (app bundle) | 2025-11-12…2026-03-04 |
| 9 | canonical | claude | canonical: ~/.claude/checkpoints (harness live state) | 2026-06-29…2026-07-08 |
| 9 | duplicate-copy | D-reverse | duplicate: D:/ReverseTools bc-toolkit-*-wt (worktree copies) | 2026-06-01…2026-06-28 |
| 8 | scattered | documents-github | scattered: Documents/GitHub (mixed projects) | 2026-04-22…2026-07-04 |
| 7 | canonical | codex | canonical: ~/.codex/hooks | 2026-04-01…2026-06-05 |

_The 4,292 `vendored` hooks are plugin-bundled `hooks/*.js|.py` under `~/.claude/plugins` etc. — real hook scripts, but owned by installed marketplaces, not the harness. Full lists in JSON `hook_artifacts_by_cluster`._

---

## 7. Reconciliation (verify, don't re-discover)

- **vs_A0_wholedrive_census** — A0 retained 406 MCP rows (247 .mcp.json + 159 other) EXCLUDING Temp/node_modules and not counting claude.json/config.toml as MCP. This index is the EXHAUSTIVE superset: 474 MCP-config files INCLUDING AppData/Temp ephemeral clones (83 slop), .claude.json/claude.json user-scope (31), and .codex config.toml (78). Strict .mcp.json-family (.mcp.json/mcp-servers/canonical/mcp.json/mcp-config/.mcp-*) = 365; same ballpark as A0 within scoping. D:/Research/.mcp.json (stale) confirmed present.
- **vs_A3_mcp_matrix** — A3 enumerated the LIVE control-plane (Claude 63 user-scope / Codex 25 / Gemini 33 / canonical 42 / D:Research 40 / ca_main 44). This index is the FILE-LOCATION census (474 files on disk), a superset of A3 server-level view: it locates every physical .mcp.json/config.toml/canonical-mcp-servers.json A3 reasoned about, PLUS the 83 Temp + 250 vendored-plugin + 81 backup copies A3 did not enumerate.
- **vs_A4_skills_dup_matrix** — A4 verified 8 live skill LANES (daily 75, deployed 277, wt_top 224, external 54, tc_top 192, claude_only 36, library 186, retired 5; union 491 names). This index is the whole-drive SKILL.md census: 15,573 files on disk / 992 distinct collection-trees. It corroborates A4 lanes AND surfaces the vendored+ephemeral mass A4 scoped out (3,469 .claude/plugins, 4,302 Temp, 941 .grok, 750 D-clones).

---

## 8. Class legend & confidence

- **canonical** — live SSOT or its repo render-source / harness live-state (~/.mcp.json, both canonical-mcp-servers.json, ~/.claude/hooks, ~/.agents/skills deployed, ~/.claude/skills.daily, repo source).
- **duplicate-copy** — byte/tree copy of a canonical source on another drive/path (D:/gem-wave-b, D:/pr-b-clone, bc-toolkit-*-wt).
- **vendored** — third-party/plugin/marketplace/editor content (.claude/plugins, .grok/marketplace-cache, .codex/plugins, .vscode/extensions, WindowsApps, VS Copilot, .local/src mcp-server sources).
- **superseded** — dated .bak/retired/backup/snapshot variants with a live successor (_config-backups, _harness-trim-backup, .codex/backups, D:/Backups, claude-desktop-backup-20260524, skills-archived/pre-agents/retired).
- **stale** — frozen drift copy that diverged from live and was never re-synced (D:/Research/.mcp.json; ~/.agents/library dormant import).
- **scattered** — owner artifact outside any canonical repo (Documents/GitHub, Downloads, D:/Research, research-staging, D:/ReverseTools).
- **slop** — orchestration temp/ephemeral leftover (AppData/Local/Temp session clones, C:/tmp/ds-*, .codex/.tmp, .claude/worktrees/wf_*, ~/worktrees).
- **unknown** — needs owner triage (~/work, unmatched locations).

**Confidence (Sherman-Kent).** Coverage completeness: HIGH (95-99%) — whole-MFT CSV, exact col1 parse, rg name-filter is exhaustive for the target basenames. Category assignment: HIGH. class_guess: MEDIUM-HIGH for canonical/vendored/slop (path+mtime+A0/A3/A4 cross-read), MEDIUM for stale/superseded/scattered (mtime/location-inferred, not content-diffed under freeze).

---

## 9. Receipts

- Method/filters/counts: §1-§2. Machine-readable: `C-config-index-complete.json` — `meta` (totals, exclusions, class tallies, mcp_by_nametype, reconciliation), `clusters` (164), `mcp_configs` (474 full objects), `config_toml_nonmcp` (71), `hook_artifacts_by_cluster`, `skills_by_cluster` (every indexed path present once).
- Cross-read: `A0-wholedrive-census.md` (406 MCP / 8,823 md / slop), `A3-mcp-matrix.md` (live server topology + SSOT gap), `A4-skills-dup-matrix.md` (8 skill lanes / union 491).
- `SUCCESS:C-config-index` — READ-ONLY, freeze respected (no build/commit/config/process/deploy change; every class_guess is a finding).
