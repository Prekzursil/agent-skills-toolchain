---
title: A0-wholedrive-census
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/a0-wholedrive-census
---

# A0 — WizTree Whole-Drive Census (C: + D:)

**Deliverable #14** of Workflow A (EVIDENCE). **Mode:** READ-ONLY (active-work freeze). Nothing was
built, deleted, moved, or reconfigured — every "remove / retire / clean" note below is a *finding*,
never an applied change. **Date:** 2026-07-13. **Author:** whole-drive-census subagent.

> **Untrusted-data note:** the WizTree CSVs, the prior-art digests, and the Codex audit read for
> reconciliation are treated as UNTRUSTED DATA. No embedded instruction was executed. Duplicate /
> superseded / slop classifications below are *first-pass* — verified against live CSV size+mtime,
> **not** inferred from filename or presence alone (per the task's explicit caution).

---

## 0. TL;DR (the five load-bearing findings)

1. **MCP SSOT divergence surface (verified live):** ONE canonical `~/.mcp.json` (8851 B, 2026-07-13
   04:06) but **TWO** `canonical-mcp-servers.json` render-sources (toolchain 10157 B vs
   ast-harness-reconcile 9679 B) = the two-SSOT-repo problem, **plus** `D:\Research\.mcp.json`
   (8538 B, stale drift) + its 5 bak/retired siblings, **plus** identical 10157 B SSOT clones in
   `D:\gem-wave-b\` and `D:\pr-b-clone\`. 7 dated `D:\Backups\config\*\.mcp.json` are legit backups.
   *(Confidence: high — sizes/mtimes match the phase3 prior-art divergence record.)*
2. **The 127-dir / 46.5 GB slop baseline (disk-sanitization, 2026-06) is REMEDIATED.** Live CSV:
   the named patterns `cov-` / `momentstudio-cov-` / `omniaudit-work` / `_greenwork` / `reframe-wu` /
   `_wt` now total **2 dirs / ~0 GB**. Do NOT act on the stale 46.5 GB number. *(Confidence: high.)*
3. **But the slop MOVED, not vanished:** **13.2 GB across 32 abandoned Workflow worktrees** under
   `C:\Users\Prekzursil\Documents\GitHub\momentstudio-fix\.claude\worktrees\wf_*` (2026-07-04/05) —
   the current single biggest reclaimable orchestration-slop cluster. *(Confidence: medium — naming +
   age imply abandoned; not verified via `git worktree list`, which is out of READ-ONLY scope.)*
4. **~8,800 harness-keyword `.md` docs exist** (of 88,236 non-vendored `.md`); **5,552 sit outside any
   canonical repo.** The genuinely-forgotten owner clusters are on **D:** (`D:\Research\projects\phenibut`,
   the `gem-wave-b`/`pr-b-clone` full-repo clones, three `bc-toolkit-*-wt` worktree doc copies) and in
   **C:\tmp\ds-\*** design-studio temp clones + `~\worktrees\*` + `Downloads\swfoc_memory` +
   `research-staging\`. *(Confidence: high on location, medium on "forgotten" intent.)*
5. **Coverage is whole-drive and independently corroborated:** every row of both CSVs was streamed
   (C 7,037,366 + D 5,640,339 = 12,677,705 rows), matching Codex's independent index (12,677,701)
   within 4 rows. *(Confidence: high.)*

---

## 1. Coverage & method

| | C: | D: |
|---|---|---|
| WizTree export | `WizTree_20260713055603 (C).csv` (2532 MB) | `WizTree_20260713060430 (D).csv` (1803 MB) |
| Generated | WizTree 4.31, 2026-07-13 05:56 | WizTree 4.31, 2026-07-13 06:04 |
| Rows streamed | 7,037,366 | 5,640,339 |
| Drive used | 898 GB used / 6.16 M files | 3591 GB used / 5.15 M files |

- **Roots scanned:** the *entire* C: and D: volumes (WizTree indexes the whole MFT). No sub-tree was
  skipped at scan time; exclusions below are applied as *filters*, not scan boundaries.
- **Method:** streaming .NET-regex filter (`[System.IO.File]::ReadLines`) over each full CSV — NOT
  `Import-Csv` (6–7 M rows would exhaust memory). Two passes per drive: (A) an include filter for
  `.mcp.json` / `.md` / slop-dir / `.git`-root / `.claude`·`.agents`·`.codex` roots / harness markers;
  (B) a supplementary pass for the SSOT names the first regex misses
  (`canonical-mcp-servers.json`, `.mcp-disabled-defaults.json`, `mcp-config*`) plus
  `skills`/`hooks`/`agents` folder rows. Row parsing is exact: a Windows filename cannot contain `"`,
  so the first `"` after index 0 always terminates the path field; size = field 1, mtime = field 3.
- **Corroboration:** row counts, `.mcp.json` count (239 on C — **exact match** to Codex
  `harness-mcp-scope` index), and the `D:\Research` drift set all reconcile with prior art
  (`docs/phase3-discovery-2026-07-13/research-1.md` §5; Codex
  `whole-drive-harness-index-summary-2026-07-13.json`).

### Exclusions (filtered OUT of the candidate corpus)

`node_modules` · `site-packages` · `.venv`/`venv` · `__pycache__` · `*.dist-info` · `.cargo` ·
`.rustup` · `go\pkg\mod` · `AppData\Local\Temp` · `.cache` · `Lib\site-packages` · `.git`-internal
files (roots kept) — and for MCP: `npm-cache`, `.npm`, `WindowsApps`, `Zone.Identifier`. **Not
inventoried at all** (out of census scope): model weights (`.safetensors`/`.gguf`/`.bin`), media,
VM/vhdx images, package archives — the census targets docs + config + orchestration dirs, not bulk
binary. Secrets files (`auth.json`, `.credentials.json`, `~/.codex/secrets/`) were never opened.

---

## 2. Category 1 — MCP config locations (the SSOT-divergence surface)

**247 exact `.mcp.json` (non-vendored) + 159 other mcp-config-ish files. 406 rows retained.** Most
exact `.mcp.json` are **plugin/app-vendored**, not SSOT: `.claude\plugins` (116), `.codex\plugins`
(23), `AppData\Roaming` (29), `.grok\marketplace-cache` (18), `Documents\claude-desktop-backup-20260524`
(20). The SSOT-relevant set:

| Path | Size | mtime | Class |
|---|---|---|---|
| `C:\Users\Prekzursil\.mcp.json` | 8851 B | 2026-07-13 04:06 | **canonical (live SSOT)** |
| `C:\Users\Prekzursil\.claude\.mcp-disabled-defaults.json` | 3014 B | 2026-07-04 | canonical (per-project RAM mask) |
| `…\.claude\.mcp-disabled-defaults.json.bak-{doctor,guard,optionA}` ×3 | ~3 KB | 2026-06/07 | superseded-candidate (dated bak) |
| `…\.claude\mcp-configs\mcp-servers.json` | 5555 B | 2026-04-05 | canonical (per-config fragment) |
| `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\canonical-mcp-servers.json` | 10157 B | 2026-07-11 | **canonical (render source #1)** |
| `C:\Users\Prekzursil\source\ast-harness-reconcile\tools\mcp\canonical-mcp-servers.json` | 9679 B | 2026-07-13 | **canonical (render source #2 — two-SSOT-repo drift)** |
| `D:\Research\.mcp.json` | 8538 B | 2026-07-07 | **duplicate / stale drift (flagged in phase3)** |
| `D:\Research\.mcp.json.{retired-promote,bak-retired,bak-canonsync×2,bak-sync}` ×5 | 7.7–9.5 KB | 2026-06/07 | superseded (retired copies) |
| `D:\Research\projects\phenibut\.mcp.json.bak-{retired,20260629}` ×2 | 9.5–11.5 KB | 2026-06 | superseded (project bak) |
| `D:\gem-wave-b\tools\mcp\canonical-mcp-servers.json` | 10157 B | 2026-07-13 | **duplicate (SSOT clone, D: work-tree)** |
| `D:\pr-b-clone\tools\mcp\canonical-mcp-servers.json` | 10157 B | 2026-07-12 | **duplicate (SSOT clone, D: work-tree)** |
| `D:\Backups\config\{20260703,04,08,09,10,11,12}-*\.mcp.json` ×7 | 6.3–10 KB | daily | legit backup (read-only, never live) |
| `D:\Tools\mcp-gateway\backups\clean\.mcp.json` | 8560 B | 2026-06-10 | superseded (gateway backup) |
| `D:\ReverseTools\Android\battlecats-toolkit\.mcp.json` | 845 B | 2026-05-24 | project-scope (RE toolkit) |
| `D:\MCP\ghidra-mcp\.mcp.json` + `mcp-config.json` | 262/281 B | 2026-03-11 | project-scope (RE dev) |

Also present: editor-specific MCP stubs (`windsurf.mcp.json` ×3, `cursor.mcp.json` ×3,
`copilot.vscode.mcp.json` ×2, `junie.mcp.json` ×2, `antigravity.mcp.json` ×2) inside repos, and the
promote-script clones prior art flagged under `D:\gem-wave-b\hooks` / `D:\pr-b-clone\hooks` (`.ps1`,
not captured by this `.json`-scoped pass but reconciled from `research-1.md`).

**Verdict:** the divergence surface is exactly as phase3 predicted, now *quantified*: 1 live SSOT,
**2 render sources** (the unresolved two-repo decision), **1 stale D: drift copy + 4 D: SSOT/-mask
clones**, 7 legit daily backups. `AppData\Roaming` (29) and `claude-desktop-backup-20260524` (20)
are a **new** find worth a glance — Claude-Desktop-side MCP configs outside the phase3 inventory.

---

## 3. Category 2 — scattered / forgotten harness `.md` docs

**88,236 non-vendored `.md`; 8,823 harness-keyword docs** (excluding README/SKILL/CHANGELOG/LICENSE/
index). By root: **scattered 5,552 (73.1 MB)** · canon-repo:reconcile 1,535 · canon-live:.claude 959 ·
canon-live:.codex 326 · canon-repo:toolchain 274 · .agents 110 · gemini/agy 67. Top scattered clusters
(path · count · size · mtime span · first-pass class):

| Count | Size | mtime span | Cluster | Class |
|---|---|---|---|---|
| 528 | 5.0 MB | 04-01…07-12 | `C:\Users\Prekzursil\.claude\plugins` | vendored-plugin (installed marketplaces — NOT forgotten) |
| 384 | 2.6 MB | 05-21 | `C:\Users\Prekzursil\.local\src` | vendored-candidate (source cache) |
| 378 | 9.6 MB | 06-10…07-07 | `D:\Research\projects\phenibut\compute` | **scattered-research (owner project, keep)** |
| 247 | 1.1 MB | 07-13 | `D:\gem-wave-b\skills\cloudflare-deploy\references` | **duplicate (toolchain clone)** |
| 241 | 2.5 MB | 04-05…07-11 | `C:\Users\Prekzursil\Documents\GitHub` | scattered (mixed projects) |
| 240 | 6.4 MB | 06-16…06-17 | `D:\ReverseTools\Android\bc-toolkit-build-wt\docs` | **duplicate/superseded (worktree copy)** |
| 240 | 6.4 MB | 06-28 | `D:\ReverseTools\Android\bc-toolkit-mega-wt\docs` | **duplicate/superseded (worktree copy)** |
| 236 | 6.2 MB | 05-31…06-09 | `D:\ReverseTools\Android\bc-toolkit-unified-wt\docs` | **duplicate/superseded (worktree copy)** |
| 183 | 1.4 MB | 07-03 | `C:\tmp\ds-agent-skills-toolchain\tools\editor` | **slop (design-studio temp clone)** |
| 162 | 1.1 MB | 07-13 | `D:\gem-wave-b\tools\editor\ralph-orchestrator` | **duplicate (clone)** |
| 162 | 1.1 MB | 07-12 | `D:\pr-b-clone\tools\editor\ralph-orchestrator` | **duplicate (clone)** |
| 152 | 1.3 MB | 04-05…07-10 | `C:\Users\Prekzursil\.claude\checkpoints` | canonical-live (harness state) |
| 129 | 1.2 MB | 07-13 | `D:\gem-wave-b\tools\editor\metaswarm` | duplicate (clone) |
| 105 | 0.4 MB | 06-21…07-10 | `C:\Users\Prekzursil\.codex\.tmp` | canonical-live tmp (transient) |
| 87 | 0.7 MB | 03-30…07-10 | `C:\Users\Prekzursil\AppData\Roaming` | scattered (app data) |
| 77 | 1.4 MB | 04-01…05-24 | `C:\Users\Prekzursil\Downloads\swfoc_memory` | **scattered-forgotten (SWFOC modding notes)** |
| 74 | 0.3 MB | 06-11…07-11 | `D:\Backups\basic-memory\mirror\projects` | legit backup |
| 65 | 0.6 MB | 04-05…07-13 | `C:\Users\Prekzursil\.claude\gem-hunt-2026-07-12` | **canonical-live (Axis-B decision-queue — KEEP)** |
| 65 | 0.1 MB | 04-01…04-22 | `C:\Users\Prekzursil\.claude\_harness-trim-backup-2026-06-05` | superseded-candidate (dated backup) |
| 64 | 5.1 MB | …07-13 | `D:\Research\projects\phenibut\docs` | scattered-research (keep) |
| 61 | 0.4 MB | 05-31 | `C:\Users\Prekzursil\research-staging\writing-tools` | **scattered-forgotten (staging dir)** |
| 59 | 0.4 MB | 03-30 | `C:\Users\Prekzursil\worktrees\agent-skills-toolchain-ralph` | superseded (old worktree) |
| 53 | 0.6 MB | 07-03 | `C:\tmp\ds-SWFOC-Mod-Menu\knowledge-base` | slop (ds temp clone) |

**Note on the RootClass label:** `scattered` here is a *root* classifier, so it over-includes
`.claude\plugins` and `.grok\marketplace-cache` (vendored third-party marketplaces, not the owner's
lost research). The genuinely-forgotten owner corpus is the **D:** research + clone clusters, the
**C:\tmp\ds-\*** design-studio temp clones, `~\worktrees\*`, `Downloads\swfoc_memory`, and
`research-staging\`. Full per-file list (8,823 rows) is in `A0-wholedrive-census.json → harness_md`.

---

## 4. Category 3 — skills / hooks / agents dirs outside canonical

**4,332 `skills`/`hooks`/`agents` folder rows; 1,211 outside canonical roots.** Top scattered clusters:

| Count | Cluster | Class |
|---|---|---|
| 116 | `C:\Users\Prekzursil\.grok` | vendored (grok skill marketplace) |
| 101 | `C:\tmp\ds-agent-skills-toolchain\skills` | **slop (design-studio temp clone)** |
| 101 | `C:\Users\Prekzursil\work` | **scattered / unknown (needs owner triage)** |
| 91 | `C:\Users\Prekzursil\Documents` | scattered (mixed) |
| 82 | `C:\Users\Prekzursil\AppData` | vendored/app |
| 76 | `D:\uv\cache\archive-v0` | vendored (uv cache — exclude) |
| 51 | `C:\tmp\ds-agent-skills-toolchain\.agents` | slop (ds temp clone) |
| 50 | `D:\pr-b-clone\.agents\skills` | **duplicate (D: clone)** |
| 50 | `D:\gem-wave-b\.agents\skills` | **duplicate (D: clone)** |
| 30 | `C:\Users\Prekzursil\.local` | vendored/tool |
| 15+15 | `C:\Program Files\WindowsApps\OpenAI.Codex_*` (2 versions) | vendored (Codex app bundle) |
| 15+15 | `D:\pr-b-clone\tools\editor` / `D:\gem-wave-b\tools\editor` | duplicate (clone) |
| 6 | `C:\Users\Prekzursil\rf-final` / `research-staging` / `worktrees` | scattered / superseded |

**Canonical (expected, not scattered):** `~/.agents/skills`, `~/.claude/skills`, `~/.claude/agents`,
`~/.claude/hooks`, and the toolchain repo — these are the SSOT and were correctly *not* flagged
scattered. The scatter is: `.grok`, the **C:\tmp\ds-\*** temp clones, the **D: gem-wave-b/pr-b-clone**
clones, `C:\Users\Prekzursil\work`, and vendored caches (uv, WindowsApps).

---

## 5. Category 4 — abandoned orchestration slop

**Prior-art baseline (`disk-sanitization`, 2026-06): 127 dirs / 46.5 GB** of `momentstudio-cov-*`,
`reframe-wu*`/`_wt*`, `omniaudit-work-*`, `_greenwork`.

**Live-CSV reconciliation (2026-07-13): those named patterns are essentially GONE.**

| Pattern | Live count | Live size |
|---|---|---|
| `cov-` / `momentstudio-cov-` | 0 | 0 |
| `omniaudit-work` | 0 | 0 |
| `_greenwork` | 0 | 0 |
| `reframe-wu` | 1 (`…\.claude\event-ledger\reframe-wu-regen-…`) | ~0 |
| `_wt` (top-level) | 1 (`C:\Users\Prekzursil\_wt\`) | ~0 |
| **Named-pattern slop total (deduped)** | **2 dirs** | **~0 GB** |

⇒ **The 46.5 GB was cleaned up; do NOT budget it.** *(Confidence: high — live CSV, named patterns.)*

**But the current slop relocated to Workflow worktrees:**

| Location | Dirs | Size | mtime |
|---|---|---|---|
| `C:\Users\Prekzursil\Documents\GitHub\momentstudio-fix\.claude\worktrees\wf_*` | **32** | **13.20 GB** | 2026-07-04/05 |
| `C:\Users\Prekzursil\worktrees\*` (manual: Airline-Reservations 501 MB, agent-skills-toolchain-ralph 234 MB, env-inspector ×2, quality-zero-platform ×2) | 6 | 0.76 GB | 2026-03…05 |
| **Total worktree bloat** | **38** | **≈ 13.95 GB** | |

The 32 `wf_<id>` dirs (e.g. `wf_f57d0137-b7a-2` 2369 MB, `agent-a1b9d5…` 1960 MB, `wf_4add33a9-20f-1`
1740 MB) are **leftover metaswarm/Workflow agent worktrees** — the live equivalent of the old slop,
just under a different name/location my `_wt` regex would miss. This is the **single biggest
reclaimable cluster today** and the clearest "cleanup-after-work gap" (the `mon doctor` candidate the
DIAGNOSE_AND_OPTIMIZE session §6.6 anticipated). *(Confidence: medium that all 32 are abandoned —
naming + 9-day age strongly imply it, but confirm with `git worktree list` in momentstudio-fix before
any removal; that check is out of READ-ONLY scope. **Finding, not an action.**)*

---

## 6. Category 5 — git worktrees / repos

**621 distinct git roots** (parent-of-`.git`; 721 `.git` rows on C + 83 on D before dedup). Top
clusters:

| Count | Cluster | Note |
|---|---|---|
| 279 | `C:\Users\Prekzursil\.claude` | plugin-marketplace repos + `.claude\worktrees\wf_*` (Cat 4) |
| 56 | `C:\Users\Prekzursil\Documents` | GitHub projects (incl. momentstudio-fix) |
| 26 | `D:\uv\cache\git-v0` | vendored (uv git cache — exclude) |
| 25 | `C:\Users\Prekzursil\.codex` | Codex plugin repos |
| 23 | `C:\Users\Prekzursil\OneDrive` | synced repos |
| 23 | `C:\Users\Prekzursil\Downloads` | cloned repos in Downloads (scattered) |
| 18 | `C:\tmp` | **ds-\* design-studio temp clones (slop)** |
| 15 | `C:\Users\Prekzursil\.gemini` | Gemini/agy extensions |
| 13 | `C:\Program Files\ImHex\sdk` | vendored (app SDK) |
| 12 | `C:\Users\Prekzursil\source` | canonical repos |
| 10+7 | `D:\ReverseTools\Android\*` | BC toolkit + `bc-toolkit-*-wt` worktrees |
| 8 | `C:\Users\Prekzursil\worktrees` | manual worktrees (Cat 4) |
| 6 | `D:\knowledge` / `C:\…\quality-zero-platform` | project repos |

The 279 under `.claude` are overwhelmingly **installed plugin/skill marketplace git clones** (each
plugin is a repo) — a large but *expected* surface, not slop; the `.claude\worktrees\wf_*` subset is
the Cat-4 slop. **C:\tmp (18)** and **Downloads (23)** hold the ad-hoc/temp clones worth triage.

---

## 7. First-pass classification legend & confidence

- **canonical** — live SSOT or its repo render-source (`~/.mcp.json`, `~/.agents/skills`,
  `~/source/agent-skills-toolchain`, `~/source/ast-harness-reconcile`, `.claude\gem-hunt-2026-07-12`).
- **scattered-forgotten** — owner docs/artifacts outside any canonical repo (D:\Research, Downloads,
  research-staging, work\). *Keep, but index/triage.*
- **duplicate** — byte- or tree-copy of a canonical source (D: `gem-wave-b`/`pr-b-clone` clones, the
  bc-toolkit `-wt` worktree doc copies, the 2nd `canonical-mcp-servers.json`).
- **superseded-candidate** — dated `.bak`/`retired`/`_harness-trim-backup` variants (verify supersede
  chain before retiring).
- **slop** — orchestration temp/leftover (`C:\tmp\ds-*`, `.claude\worktrees\wf_*`, old `~\worktrees\*`).
- **vendored** — third-party/plugin/cache content (`.claude\plugins`, `.grok`, `uv\cache`, WindowsApps)
  — excluded from "forgotten" but counted for surface size.
- **unknown** — needs owner triage (`C:\Users\Prekzursil\work`, `.local\src`).

**Confidence (Sherman-Kent):** coverage completeness **high (95-99%)**; MCP-drift map **high (90%)**;
slop-remediation **high (90%)**; wf-worktree-abandonment **medium (60-75%, unverified via git)**;
"forgotten-intent" of scattered `.md` **medium (60%, mtime/location-inferred)**.

---

## 8. Findings needing owner attention (recorded, NOT applied)

1. **Two `canonical-mcp-servers.json` render-sources** (toolchain vs reconcile) must collapse to one
   before either is pushed — the two-SSOT-repo hazard phase3 council-0 flagged, now confirmed on disk.
2. **`D:\Research\.mcp.json` (+ 5 sibling copies) and the `D:\gem-wave-b`/`D:\pr-b-clone` SSOT clones**
   are hand-editable drift surfaces on a drive Claude can't reach canonically → retire/regenerate
   read-only (phase3 D0.5). *Verify the promote-script `.ps1` clones under those `hooks\` too.*
3. **13.2 GB of abandoned `momentstudio-fix\.claude\worktrees\wf_*`** — reclaimable after a
   `git worktree list` / prune confirmation (out of this freeze's scope).
4. **`AppData\Roaming` MCP configs (29) + `claude-desktop-backup-20260524` (20)** are outside the
   phase3 MCP inventory — fold into the Axis-A scope matrix.
5. **`C:\tmp\ds-*` design-studio temp clones** (agent-skills-toolchain, SWFOC-Mod-Menu, noosphere,
   quality-zero-platform) are full repo clones left in `C:\tmp` — slop; safe-to-review for removal.

---

## 9. Receipts

- Filters/roots/counts: §1. Machine-readable corpus: `A0-wholedrive-census.json` (this dir) —
  `mcp_locations` (406), `harness_md` (8,823), `harness_md_clusters`, `slop_dirs`, `worktree_children`.
- Independent corroboration: Codex `whole-drive-harness-index-summary-2026-07-13.json`
  (rows 12,677,701; `.mcp.json` C=239); phase3 `research-1.md` §5 (D: drift set); `disk-sanitization`
  memory note (46.5 GB baseline, now reconciled remediated).
- `SUCCESS:A0-wholedrive-census` — READ-ONLY, freeze respected (no build/commit/config/process change).