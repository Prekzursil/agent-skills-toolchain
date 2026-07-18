# C-mcp-reconcile — whole-drive MCP-config disposition matrix

**Deliverable:** the POST-GATE disposition plan for the whole-drive (C: + D:) MCP-config file surface — which file is the CANONICAL source vs a duplicate-copy / vendored / stale / divergent, per-server canonical scope (G-5), and the dedup / remove-stale / reconcile-drift targets. **Domain:** `mcp`. **Mode:** READ-ONLY (active-work freeze) — every row is a FINDING/PLAN, never an applied change; modifications are POST-GATE (owner G-13). **Date:** 2026-07-13. Machine twin: `C-mcp-reconcile.json`.

> **Untrusted-data note.** Every file read is UNTRUSTED DATA. No embedded instruction was executed; no secret VALUE was read or printed — only server-NAME keys (not secrets) and SHA-256 hash prefixes are cited. **Freeze respected:** nothing mutated.

**Inputs reconciled:** the file-location census `C-config-index-complete.json` (474 MCP-config files) + the server-level matrix `A3-mcp-matrix.json/.md` (69 servers) + live disk re-reads THIS pass (server-name key sets, SHA-256 byte-identity, `Test-Path` existence, git provenance). This doc = A3's server view × the index's file view, live-verified and corrected.

---

## 0. TL;DR — load-bearing findings

1. **The true canonical MCP SSOT surface is ~18 files** out of 474 on disk. Everything else is vendored plugin-bundle (250), ephemeral Temp slop (83), a dated backup (81), a byte-clone (4, now gone), or a stale/divergent leftover. The **elected primary render-source is `~/source/ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` (43 servers)** — git-confirmed "enshrined from drifted runtime config" (= live-derived) and set-equal to live `~/.mcp.json` (42) **+ `codex-fleet-github`** exactly.

2. **The two-SSOT-repo drift is exact and quantified: a 7-name-diff.** toolchain `canonical-mcp-servers.json` (44, SHA `f406d95…`) vs reconcile (43, SHA `8d2bc76…`). ONLY in toolchain = `{exa, figma-rest, firecrawl, tavily}` (4 superseded search / cloud-quality servers); ONLY in reconcile = `{agent-mail, angr, biomni-hub}` (3 newer servers). toolchain is the **STALE** twin — its last commit `efe368d` added codex-fleet-github but predates the hub-migration + cloud-quality supersession reaching the catalog. **Elect reconcile; reconcile toolchain to it** (drop 4, add 3).

3. **The 4 `duplicate-copy` D-clones the index flagged are ALREADY GONE** — `Test-Path` verifies `D:\gem-wave-b` and `D:\pr-b-clone` no longer exist (the WizTree CSV was a 2026-07-13 point-in-time snapshot; the clones were removed since). Standing dedup work = **1** (the byte-identical agent-self template pair, conditional on repo convergence).

4. **`D:/Research/.mcp.json` (40, stale) is CONFIRMED still present** — the headline frozen pre-reconcile drift (only in it: `figma-rest`; missing from it: `agent-mail`/`angr`/`biomni-hub`; + playwright & cloud-hub-Kaggle value drift). Plus **2 dead April-2026 fragments** (`~/.claude/mcp-configs/` ≡ `~/.codex/mcp-configs/mcp-servers.json`, byte-identical `f6f5cbcc…`, a 24-server set of `clickhouse/cloudflare/supabase/vercel/…` none of which are current) and **3 abandoned mcp-funnel gateway files** → **6 stale files to remove**.

5. **The codacy/deepsource "resurfacing" is NOT a catalog regression** (A3-confirmed, re-verified): both `.mcp.json` catalogs correctly omit them; they live parked-disabled in `~/.mcp.disabled.json` (33-server companion) and resurface only via the `local-mcp-bridge` plugin twins in every `projects[*].disabledMcpServers`. Fix at the plugin + user layer, never by editing `.mcp.json`. **HOLD — do not prune on presence.**

---

## 1. Disposition summary (counts)

| Bucket | Count | Meaning |
|---|---:|---|
| **canonical (keep as SSOT-for-scope)** | **18** | authoritative live/render/generated/project surface |
| **duplicates_to_dedup (standing)** | **1** | byte-identical redundant copy to collapse (+4 D-clones already GONE) |
| **stale_to_remove** | **6** | diverged-frozen + dead-fragment + abandoned-gateway |
| **drift_to_reconcile** | **9** | divergences to sync (named §4) |
| vendored (leave) | 250 | third-party plugin/marketplace bundles — mcp-fleet-curation posture, not delete |
| slop (bulk-prune) | 83 | AppData/Temp ephemeral clones — part of the 46 GB slop sweep (G-12) |
| superseded-backups (leave to rotation) | 81 | dated legit backups (D:\Backups daily, checkpoints, _config-backups) |
| scattered (keep project-local / triage) | 10 | project dev configs + Downloads clones |

*Index class-tally for MCP was: vendored 250 · slop 83 · superseded 81 · canonical 36 · scattered 10 · unknown 9 · duplicate-copy 4 · stale 1. This doc **re-classes 8 of those**: the 2 April fragments (canonical→stale), 3 funnel + 2 `.claude/.codex` stray (unknown→stale/slop), `~/.mcp.disabled.json` + `~/.mcp-presets.json` (unknown→canonical); and marks the 4 duplicate-copy as **resolved (GONE)**.*

---

## 2. CANONICAL SSOT surface — the 18 files to KEEP

Presence / scope keyed to G-5 (USER-scope default for broadly-useful concurrency-safe utilities; project/local only for a proven per-project need; heavy/niche = lazy flip-on).

### 2a. Elected repo render-source (the ONE authoritative catalog)
| Path | Servers | Role | Conf |
|---|---:|---|---|
| `~/source/ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` | 43 | **ELECTED canonical render-src** — git "enshrine drifted runtime config" (`5d2fca2`), = live `~/.mcp.json` + `codex-fleet-github`; SHA `8d2bc76…` | HIGH |

### 2b. Live per-provider control-plane (the actually-loaded state — keep)
| Path | Set | Role | Scope (G-5) | Conf |
|---|---:|---|---|---|
| `~/.mcp.json` | 42 enabled | LIVE SSOT, HOME-scope curated | USER-default | HIGH |
| `~/.mcp.disabled.json` | 33 parked | disabled companion — where cloud-quality family + SaaS extras sit parked | USER-default | HIGH |
| `~/.claude.json` | 63 user-scope | what every Claude session loads (= canonical + 22 drift-ins − angr) | USER | HIGH |
| `~/.claude/.mcp-disabled-defaults.json` | mask | per-project RAM mask (heavy-Python OFF per tree) | per-project overlay | HIGH |
| `~/.codex/config.toml` | 25 enabled | LIVE Codex `[mcp_servers.*]` | USER (Codex) | HIGH |
| `~/.codex/browser/config.toml` | tiny | Codex browser runtime | Codex-internal | MED-HIGH |
| `~/.gemini/config/mcp_config.json` | 33 | LIVE Gemini | USER (Gemini) | HIGH |
| `~/.gemini/antigravity-cli/mcp_config.json` | 0 (empty) | Antigravity placeholder | USER (agy) | MED |

### 2c. Generated projections (deterministic outputs of the catalog — keep, regenerable)
| Path | Editor | Conf |
|---|---|---|
| `~/.agents/generated/claude.mcp.json` | Claude | HIGH |
| `~/.agents/generated/antigravity.mcp.json` | Antigravity | HIGH |
| `~/.agents/generated/cursor.mcp.json` | Cursor | HIGH |
| `~/.agents/generated/windsurf.mcp.json` | Windsurf | HIGH |
| `~/.agents/generated/junie.mcp.json` | Junie | HIGH |
| `~/.agents/generated/copilot.vscode.mcp.json` | Copilot/VSCode | HIGH |

### 2d. Project-scoped + live tool (keep — do NOT promote to user)
| Path | Role | Conf |
|---|---|---|
| `~/source/repos/insta-mcp/.mcp.json` | genuine per-project dev server (placeholder creds) | HIGH |
| `~/Documents/GitHub/bilbo-app/.mcp.json` | bilbo-app `agent_handler` (perplexity proxy) — project-scoped | MED-HIGH |
| `~/.mcp-presets.json` | mcp-manager preset feature (live tool config) | MED-HIGH |

**Total canonical (keep-as-SSOT-for-scope): 18.**

---

## 3. DEDUP + STALE — remove targets (POST-GATE)

### 3a. duplicates_to_dedup — byte-identical redundant copies
| Copies | SHA-256 | Standing? | Disposition |
|---|---|---|---|
| `agent-skills-toolchain/agent-self/config/mcp/mcp.json` ≡ `ast-harness-reconcile/…/mcp.json` | `c4406af5…` | **1 standing** | keep reconcile, drop toolchain copy **on repo convergence** (task #8 folds reconcile→toolchain → one repo → one template) |
| `D:\gem-wave-b\{tools/mcp/canonical…, agent-self/…/mcp.json}` (2) | (clone of `f406d95`/`c4406af5`) | **GONE** | already resolved — `Test-Path` = absent |
| `D:\pr-b-clone\{tools/mcp/canonical…, agent-self/…/mcp.json}` (2) | (clone) | **GONE** | already resolved — `Test-Path` = absent |

**Standing dedup = 1** (index found 4 D-clones; all 4 verified GONE → the only standing byte-dup is the conditional agent-self template pair).

### 3b. stale_to_remove — diverged-frozen / dead / abandoned
| Path | Servers | Why stale | Conf |
|---|---:|---|---|
| `D:\Research\.mcp.json` | 40 | frozen pre-reconcile drift; only-in = `figma-rest`, missing `agent-mail`/`angr`/`biomni-hub`; playwright + cloud-hub-Kaggle value drift. Superseded by user-scope promotion. **Still present.** | HIGH |
| `~/.claude/mcp-configs/mcp-servers.json` | 24 | **dead April-2026 fragment** — `clickhouse/cloudflare*/supabase/vercel/railway/…`, none in any current catalog; nothing loads `~/.claude/mcp-configs/`. Byte-identical to the codex twin (`f6f5cbcc…`). | MED-HIGH |
| `~/.codex/mcp-configs/mcp-servers.json` | 24 | byte-identical dead April fragment (`f6f5cbcc…`) | MED-HIGH |
| `~/.mcp-funnel.json` | — | abandoned mcp-funnel gateway config (2026-06-10); funnel approach evaluated + dropped (re-namespace wall) | MED-HIGH |
| `~/.mcp-funnel-master.json` | — | abandoned funnel master config | MED-HIGH |
| `~/.mcp-funnel-profiles.json` | — | abandoned funnel profiles | MED-HIGH |

**stale_to_remove = 6.** *Candidate 7th (MED, verify-before-remove): `~/.claude/.codex/config.toml` (3171 B, 2026-04-05) — a Codex config at an anomalous path under `.claude/`; likely a stray early-setup leftover.*

---

## 4. drift_to_reconcile — the 9 divergences to sync (POST-GATE)

| # | Drift | Reconcile action | Conf |
|---|---|---|---|
| D1 | **two-SSOT-repo 7-name-diff** — toolchain(44) vs reconcile(43) | elect reconcile; update toolchain: **drop** `{exa,figma-rest,firecrawl,tavily}`, **add** `{agent-mail,angr,biomni-hub}` (or converge repos via task #8) | HIGH |
| D2 | **22 user-scope drift-ins** in `~/.claude.json` not in canonical | prune-promote at the **plugin-bridge + user layer** (run promote `-PruneExtraUserServers` with Claude closed), NOT an `.mcp.json` edit: `apify, browserstack, claude-code-mcp, codacy, codecov, codex, deepscan, deepsource, digitalocean, figma-rest, firecrawl, github, linear, mcp-graphql, meta-tool, notion, postgres, scrapegraph, semgrep, sentry, sonarqube, tavily` | HIGH (list) / MED (keep-prune split, owner-EVPI) |
| D3 | **`angr` drift-OUT** — in canonical `~/.mcp.json` but never promoted to user-scope, backend DOWN | promote to user-scope + give it a health contract | MED-HIGH |
| D4 | **`codex` fan-out rail SSOT-orphan** — user-scope only, in no catalog | ADD to canonical catalog (it is the documented Layer-1 rail) | HIGH |
| D5 | **`codex-fleet-github`** — in BOTH repo catalogs, deployed to NO provider | decide deploy-or-drop; don't promote until owning runtime accepted | HIGH |
| D6 | **plugin-bridge `codacy`/`deepsource` resurfacing** — `local-mcp-bridge:*` twins in every `projects[*].disabledMcpServers` | reconcile at the plugin layer; owner decision: keep or retire the whole cloud-quality family (codacy/deepsource/sonarqube/codecov/deepscan). **HOLD, don't prune on presence** — already parked-disabled | HIGH |
| D7 | **agent-self template (37) wrong-set** — carries cloud-quality + SaaS family, LACKS hubs/basic-memory/RE-stack/paper-search | regenerate template from the elected catalog (G-1 SSOT engine) instead of hand-maintaining a stale copy | MED-HIGH |
| D8 | **provider value-drift** — `playwright` (`@playwright/mcp` vs `playwright-mcp` in Gemini/D:Research); `cloud-hub` Kaggle env (`KAGGLE_USERNAME`+`KAGGLE_KEY` vs `KAGGLE_API_TOKEN`); `github` vs `github_cli` de-dup (Codex already dropped `[mcp_servers.github]`); Gemini `memory` (@mcp/server-memory) vs `basic-memory` SSOT-conflict | reconcile to one value each; **document** the intentional hub-vs-raw + ralph-WSL adapter divergences so they aren't churned | MED-HIGH |
| D9 | **2 mcp-configs fragments** (`.claude` + `.codex`, byte-identical dead 24-set) | remove as stale (§3b) — or, if any provider still reads them, regenerate from catalog | MED-HIGH |

---

## 5. Per-server canonical SCOPE (G-5) — tiered policy

Full 69-server matrix is in `A3-mcp-matrix.json/.md`; this is the scope-tier rollup (what "user-default vs project vs lazy" means per class):

- **USER-scope default (light shared-catalog utilities, concurrency-safe):** `context7, deepwiki, docker, excel, figma, huggingface, markitdown, pdf-reader, perplexity, playwright, qlty, repomix, chrome-devtools, elevenlabs, gitlab, searxng, github_cli, cve-mcp`.
- **USER-scope hubs (Claude-canonical; Codex/Gemini use raw exa/firecrawl/tavily — documented divergence, do NOT "fix"):** `cloud-hub, search-hub, social-hub`.
- **USER-scope shared daemons (ONE process serves N sessions):** `agent-mail (:8812)`, `basic-memory (:8765)`.
- **USER-scope fan-out rail:** `codex` (add to canonical, D4).
- **Lazy flip-on / default-OFF per tree (heavy/niche — RE + science; cut the per-session-stdio RAM tax):** `apktool-mcp, binary-ninja-mcp, cheatengine, frida-mcp, ghidra-mcp, hexstrike-ai, ida-pro-mcp, jadx-mcp, angr` (RE) · `openmm-md, qdx-rush, rdkit, schrodinger, scholarly-access, tooluniverse, paper-search, ocr-suite, biomni-hub` (science). Parked via `~/.mcp.disabled.json` / `.mcp-disabled-defaults.json`.
- **Project-scoped (do NOT promote):** `insta-mcp`, `agent_handler` (bilbo-app).
- **Parked-disabled / owner keep-retire decision (superseded by local qlty+semgrep+CLI or by search-hub):** cloud-quality — `codacy, deepsource, sonarqube, codecov, deepscan, semgrep`; search — `firecrawl, tavily, exa, figma-rest`; SaaS/misc — `meta-tool, notion, linear, apify, browserstack, digitalocean, postgres, scrapegraph, mcp-graphql, sentry`; Gemini 2nd `memory`. Already parked-disabled in `~/.mcp.disabled.json`; the resurfacing is the plugin-bridge twin (D6), not a catalog regression.

---

## 6. Class disposition for the bulk (452 non-crown-jewel files)

- **vendored 250** → **LEAVE.** Third-party plugin/marketplace/editor bundles (`~/.claude/plugins` 141, `~/.codex/plugins` 27, `~/.grok/marketplace-cache` 20, VSCode/WindowsApps/`.local/src` mcp-server sources). Owned by installed marketplaces, not the harness. mcp-fleet-curation posture: disable-at-user-scope if unwanted; never bulk-delete.
- **slop 83** → **BULK-PRUNE (POST-GATE).** AppData/Local/Temp ephemeral session clones (70) + `.codex/.tmp` (10) + `C:/tmp/ds-*` (2) + worktree strays. Auto-GC'd; folds into the 46 GB slop sweep (G-12).
- **superseded 81** → **LEAVE TO ROTATION.** Dated legit backups: 7 daily `D:\Backups\config\*` sets, 11 `~/.claude/checkpoints/*/copies/*.mcp.json(.disabled)`, 8 `~/.claude/_config-backups`, 5 `~/.codex/backups`, 3 `~/.codex/stabilization-backups`, 4 `D:\Tools\mcp-gateway\backups`, 20 `claude-desktop-backup-20260524`, `~/.claude/_harness-trim-backup`. Auto-managed backup lifecycle — not manual-remove targets.
- **scattered 10** → **KEEP project-local / triage.** Keep: `bilbo-app/.mcp.json` (→ canonical §2d), `insta-mcp` (→ §2d), `Reframe/.codex/config.toml`, `D:\MCP\ghidra-mcp\*` (RE mcp-server dev), `D:\ReverseTools\…\battlecats-toolkit\.mcp.json`, `D:\ToolUniverse\plugin\.mcp.json`. Triage/leave: `Downloads/…` clones, `rf-final/.codex`, `D:\Tools\mcp-gateway\spike`.
- **unknown → triaged:** `~/.mcp.disabled.json` + `~/.mcp-presets.json` → **canonical** (§2b/2d); 3 funnel + (`~/.claude/.codex/config.toml` candidate) → **stale** (§3b); `~/.lmstudio/mcp.json` → **vendored** (LM Studio app-owned); `$Recycle.Bin/…/Office-Word-MCP-Server` → **ignore** (already deleted); `~/.claude/agent-worktrees/…/.codex/config.toml` → **slop** (worktree ephemeral).

---

## 7. Reconciliation ledger (verify, don't re-discover)

- **vs `C-config-index-complete.json`** — the index is the exhaustive file census (474). This doc keeps its taxonomy but **live-corrects 3 snapshot-vs-now deltas**: (a) the 4 D-clone duplicate-copies are GONE (`Test-Path`); (b) the 2 "canonical" `mcp-configs` fragments are dead April stale (byte-diff `f6f5cbcc`, server-set read); (c) 5 "unknown" reclassed (disabled+presets→canonical, funnel→stale). D:/Research stale = CONFIRMED present.
- **vs `A3-mcp-matrix.json`** — A3's 69-server disposition is adopted wholesale for §5. This doc ADDS the FILE-location layer A3 didn't: the exact 7-name repo diff with SHAs, the byte-identity hashes, the D-clone-gone verification, and the dead-fragment finding. A3's codacy/deepsource resurfacing verdict (plugin-bridge, HOLD) re-confirmed.
- **vs `A0`/`A4`** — A0 (406 MCP rows) and A4 (skills) are the sibling census lanes; no MCP conflict.

## 8. Confidence (Sherman-Kent)

- **7-name repo diff + reconcile=live+codex-fleet-github + SHA identities:** **HIGH (95-99%)** — read directly from the live files + `Get-FileHash` this pass.
- **D-clones GONE:** **HIGH** — `Test-Path` false, both dirs.
- **Dead April fragments stale:** **MED-HIGH** — server-set + mtime + non-load-path inferred (not a runtime trace under freeze).
- **Keep/prune split of the 22 drift-ins + cloud-quality family:** **MED** — owner-EVPI decision, explicitly NOT a silent bet (D2/D6).
- **stdio/remote server liveness:** **LOW** — not probed (read-only); several backends known DOWN (angr, searxng, ghidra, biomni-broker) per A3.

`SUCCESS:C-mcp-reconcile` — READ-ONLY, freeze respected; every row a finding/plan.
