---
title: inventory-2
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/inventory-2
---

# Stale-Branch Triage + Config-Scatter Map (READ-ONLY census, 2026-07-13)

Scanned **49 git repos** across `C:/Users/Prekzursil/source`, `C:/Users/Prekzursil/Documents/GitHub`, and `D:`. Only read git commands were run (`status/branch/for-each-ref/rev-parse`); nothing was checked out, committed, or modified. `[gone]` = upstream branch deleted on remote (almost always = merged then pruned → safe to abandon). `[ahead/behind]` is vs the branch's own upstream.

---

## LEGEND / triage vocabulary
- **salvage-good-work** — unmerged local commits or uncommitted edits that look like real, wanted work not yet on remote/main.
- **superseded** — work overtaken by a later branch/PR or already merged (`[gone]`); safe to drop.
- **scope-changed-partial-salvage** — branch mixes wanted + abandoned intent; cherry-pick the good part.
- **stale-abandon** — old, merged, or dead-end; no salvage value.
- **possibly-live, DO NOT TOUCH** — recent mtime / today's commits / owned by a concurrent session.

---

## A. POSSIBLY-LIVE — concurrent-session owned, DO NOT TOUCH (catalog only)

| Repo | Branch | Last commit | Signal |
|---|---|---|---|
| `source/agent-skills-toolchain` | **chore/enshrine-runtime-config** | 2026-07-13 (today) | Matches THIS session's enshrine tasks; sibling agents `harness-fix`/`skills-enshrine`/`mcp-reconcile` active |
| `source/agent-skills-toolchain` | **feat/wfmon-export-core** | 2026-07-12 | wfmon export work, local-only, fresh |
| `source/agent-skills-toolchain` | **feat/codex-fleet-github-wave2** (CHECKED OUT, 12 dirty files) | 2026-07-11 | Currently checked-out branch of the live repo; tree mtime today. Dirty: cloud-hub/search-hub/social-hub hub.py + accounts.json, untracked `.claude/`, `hardening.py` |
| `D:/gem-wave-b` | **gem-hunt-wave-b** | 2026-07-13 (today) | Tree mtime 2026-07-13 03:49 — active gem-hunt wave-b |
| `D:/pr-b-clone` | feat/monitorcore-consolidation / -foundation | 2026-07-12 | Tree mtime 2026-07-12 23:52 — monitorcore work in flight |
| `D:/Research` | main (83 dirty files) | 2026-06-28 | Tree mtime today (phenibut FEP/compute); long-running research tree, not session-scoped but freshly touched — treat as live |

---

## B. STALE-BRANCH TRIAGE

### `source/agent-skills-toolchain` (30 local branches — the big scatter)
`main` is **[behind 9]** (local main lags origin — a fast-forward will fix, not a real fork). Most `feat/*` branches (2026-07-03…07) have upstreams and are **already-merged PR branches kept around**.
- **stale-abandon / superseded (merged, upstream present, no ahead):** `feat/multi-ai-mingle-skill`, `feat/codex-parity-runner`, `fix/stub-ledger-false-positive`, `feat/search-hub-rotator`, `fix/cloud-hub-count-reconcile`, `feat/cloud-hub-{compute-unified,modal-deepen,databricks,ovh,mcp}`, `feat/mcp-manager-presets`, `feat/video-watermark-qc`, `feat/claude-science-cli`, `feat/comp-pharm-cascade-skill`, `feat/qzt-lean-hardening`, `feat/memory-spool-autoreplay`, `docs/figma-mcp-ratelimit-fix`, `feat/social-hub-mcp`, `feat/research-harness-m16`, `feat/optimal-agentic-workspace`, `feat/quality-zero-platform-control-plane-skill` (2026-03-23, oldest).
- **salvage-good-work (unpushed commits ahead of upstream — verify before dropping):** `feat/cloud-hub-mcp` **[ahead 1]**, `feat/fb-reels-uploader-tool` **[ahead 1]**, `feat/drug-discovery-stack` **[ahead 1]** — each carries 1 local commit not on remote.
- **stale-abandon (upstream gone/none, old):** `feat/skills-leaderboard-grill` **[gone]**, `feat/tu-wearables-phase0` (no upstream, 2026-06-16), `feat/social-media-mcp-skills` (no upstream, 2026-06-05).

### `Documents/GitHub/Reframe` (**56 local branches** — the worst scatter; 13 dirty files)
`main` **[behind 13]**. Almost all are local-only (no upstream) version/WU branches from the v1.1→v1.5 program.
- **possibly-recent (2026-07-11/12):** `feat/v1.5-*` cluster (bundle-fonts, director-screen, export-screen, shell-polish, electron-43, caption-pilot, flagship-wu-l1-yunet, shorts-live-and-labels, shell-library), `pr292`, `mainref`, `pr277-fix`, `fix/codeql-sanitizer-hardening`, `fix/local-llm-model-path` → **scope-changed-partial-salvage**: v1.5 program branches, likely mid-integration; reconcile against whatever v1.5 branch is canonical before pruning.
- **superseded (shipped v1.4.1 per memory):** `fix/v1.4.1-*`, `fix/keystore-shred-false-success`, `feat/reframe-v1.4`, `feat/reframe-v1.3`, `pr250/pr251`, `wt/design-*`, `wt/keepcopy`.
- **stale-abandon (June, pre-v1.4, no upstream):** `feat/v1.1.0`, `docs/v1.1-feature-spec`, `feat/reframe-quality`, `feat/test-hardening`, `feat/spend-cap`, `feat/ui-redesign`, `feat/director-v1`, `feat/provider-hub`, `feat/phase8-moment-finding`, all `_wu*_review` / `review-intelligence-a5` / `_uxqol_review` scratch branches, `backup/pre-wu0-f7cbdd1`, `chore/retire-qzp-issue-machinery`.
- **Uncommitted (salvage-good-work):** 13 dirty files incl. new `sidecar/media_studio/features/{beatgrid,broll_index}.py`, `smolvlm2.py` edits, `mutation-incremental.yml` workflow, e2e fixtures — real feature work not on any branch; **salvage before any cleanup**.

### `Documents/GitHub/env-inspector` (13 branches + 3 untracked coverage files)
All 2026-04-27/29 CI-cleanup branches. `main` **[behind 3]**.
- **stale-abandon:** `fix/codacy-w1618-*` **[gone]**, `fix/sonar-generic-coverage-xml`, `fix/sonar-env-inspector-cov-fixup`, `fix/sonar-env-inspector-coverage`, `fix/deepsource-flk-e303-providers`, `fix/sonar-coverage-exclusions`, `fix/codacy-c0411-import-order`, `fix/codacy-import-order`, `fix/disable-r0801-pylint-fp`.
- **salvage-good-work (unpushed):** `fix/sonar-scan-workflow` **[ahead 4]**, `fix/codeql-37-alerts` **[ahead 1]** — verify these 5 commits landed elsewhere; superseded by sibling repo `env-inspector-fix` (clean main, 2026-06-05) which likely replaced this whole tree → **whole repo probably superseded**.
- Untracked `.coverage`, `coverage.xml`, `coverage-sonar.xml` = build artifacts, **stale-abandon**.

### `Documents/GitHub/event-link` (11 branches)
All 2026-04-22→29 Sonar/coverage fixes. HEAD is on `fix/semgrep-fastapi-false-positives-2026-04-29` **[behind 2]**.
- **superseded/stale-abandon:** `fix/sonar-39-issues-2-hotspots` **[gone]**, `fix/sonar-lcov-path-remap-verify-script` **[gone]**, `fix/sonar-lcov-path-remap` **[gone]**, `fix/bump-qzp-reusable-to-phase5` **[gone]**, plus `fix/sonar-event-link-alembic-env-coverage` (no upstream), `fix/sonar-coverage-exclusions-non-app-paths`, `fix/bump-reusable-codecov-sha` **[behind 3]**, `fix/flaky-admin-mega-page-tests`, `fix/coverage-gates-and-security`. No local-only commits worth salvaging.

### `Documents/GitHub/DevExtreme-Filter-Go-Language` (5 branches)
- **stale-abandon:** 3× **[gone]** CodeQL/Codacy branches (`fix/codeql-http-error-sanitize`, `fix/codeql-log-injection-sanitize`, `fix/codacy-markdownlint-mdo22-md032`). `main` **[behind 1]**, HEAD on `chore/deepsource-config-2026-04-29`.

### `Documents/GitHub/quality-zero-platform` (9 branches, 9 dirty files)
`main` **[ahead 1, behind 17]** — real fork: 1 local commit + 17 behind origin → **reconcile main first**. Eight `fix/*`,`feat/*`,`test/*`,`chore/*` branches all 2026-06-15, no upstreams → **scope-changed-partial-salvage** (a quality-gate push; check which merged into the [ahead 1]). Dirty: `.beads/knowledge/decisions.jsonl`, generated rulesets, untracked `coverage-100/`, `deepscan-zero/`, `quality-rollup/` result dirs = **artifacts, stale-abandon**.

### `D:/ReverseTools/Android/battlecats-toolkit` (6 branches, 58 dirty files)
- **salvage-good-work:** `ralph-hardening` (CHECKED OUT) **[ahead 29]** of upstream, `feat/mega-program-v1` **[ahead 142]** of origin/main, `consolidate-unified` **[ahead 6]** — large unmerged bodies of BC RE work; **salvage/reconcile, do not drop**. 58 dirty files are mostly `.dat`/`.png` cache + `.superpowers/` scratch → artifact noise, but confirm no source among them.
- **stale-abandon:** `feat/progressive-degacha-gui` (no upstream), `chore/prune-re-scratch-2026-06-16`. `main` **[ahead 1, behind 412]** = badly diverged, reconcile-or-abandon.

### `D:/ToolUniverse`
- **salvage-good-work:** `main` **[ahead 34]** of origin/main + `fix/round-127-bugs` (has upstream). 34 unpushed commits — verify pushed/merged upstream or salvage.

### `D:/verdict-app-repo` — `master` **[ahead 2]** (2 unpushed commits, salvage-verify). `D:/ReverseTools/Android/verdict-app` (5 dirty, draft-v25 APK work → salvage) and `D:/ReverseTools/Android/BCSFE-Python` `feat/equipped-talent-orbs` (no upstream, `main` [behind 36]) → partial-salvage.

### Smaller repos — dirty trees to salvage/catalog (no branch fork, just uncommitted work)
- `source/repos/insta-mcp` — 12 dirty incl. `src/index.ts`, new `login*.mjs`/`SETUP-2FA.md` (IG 2FA login flow) → **salvage-good-work**.
- `source/repos/whatsapp-mcp` (SETUP.md + .gitignore), `source/repos/rdkit-mcp-server` (rdkit_mcp_launch.py), `source/repos/mattpocock-skills` (marketplace.json), `source/repos/ZHMModSDK` (untracked `Mods/ForceChallenge/` on `feature/titanium-bullets`) → **salvage/catalog**.
- `Documents/GitHub/pbinfo-fix-wave1` — 11 dirty (`fix/codeql-ssrf-pathinjection-wave1`, quality scripts) → partial-salvage. `pbinfo-scrape` `feat/full-archive-fix-20260423` (GUI edits + screenshots) → salvage.
- `Documents/GitHub/_verify_momentstudio` `feat/lean-quality-gate` (auth.service.ts edit) & `momentstudio-fix` (34 worktree-* branches, all 2026-07-04/05, no upstream — **workflow-orchestration worktree litter → stale-abandon en masse** except `feat/p1a-theme-foundation` + `ci/frontend-changed-files-coverage` which look intentional → partial-salvage).
- `D:/agentchattr` (7 dirty, new `start_*_best.bat` launchers → salvage), `D:/Tools/mcp-manager` (39 dirty — active tool dev, salvage), `D:/Tools/mcp-gateway` (5 untracked state/backup dirs → mostly artifacts), `D:/Tools/chromatic-playwright` (12 dirty = **node_modules churn only, stale-abandon**), `D:/mcp-servers/abbyy-finereader-ocr-mcp` (`_probe.png`/`_t.png` scratch → abandon).

### Clean / no-action repos (catalogued, nothing stale)
`qzp-lean`, `openmm-md-mcp`, `tiktok-mcp`, `schrodinger-mcp`, `fb-messenger-mcp`, `Airline-Reservations-System` (1 [gone] branch), `bilbo-app` (2 bak files only), `cb-pretty`, `codex-session-manager` (main [behind 3]), `env-inspector-fix`, `momentstudio_fix`, `pbinfo-get-unsolved`, `pfm-fix`, `Star-Wars...Save-Game-Editor`, `TanksFlashMobile`, `WebCoder` (fix/ui-audit-a11y branch, no upstream — low-pri partial-salvage), `Tools/reframe/{claude-shorts,verthor}`, `MCP/ghidra-mcp`, `ReverseTools/mcp/cve-mcp`, `Research/_infra/lightning-a2d-fep`.
**Vendored 3rd-party knowledge clones (D:/knowledge/*, D:/ToolUniverse deps): NOT user work — leave as read-only reference:** atomic-red-team, gtfobins, hacktricks(+cloud), lolbas, owasp-cheatsheets, owasp-wstg, payloadsallthethings.

### Cross-cutting patterns
1. **CI-cleanup branch litter (biggest count):** dozens of `fix/sonar-*`, `fix/codacy-*`, `fix/codeql-*`, `fix/deepsource-*`, `chore/deepsource-config-*` (Apr 2026) across env-inspector / event-link / DevExtreme — `[gone]` ones are merged→prune; the rest are dead. ~35 branches.
2. **Reframe version-program litter:** 56 branches, mostly `_wu*_review`/`wt/*`/`pr*` scratch. ~40 abandonable.
3. **momentstudio-fix worktree litter:** 33 `worktree-wf_*`/`worktree-agent-*` branches from a workflow run — mechanical, all abandonable.
4. **Real unpushed work to salvage-verify (highest value):** battlecats-toolkit (+142/+29/+6), ToolUniverse (+34), Reframe uncommitted sidecar features, insta-mcp 2FA flow, mcp-manager, agentchattr launchers.

---

## C. CONFIG-SCATTER MAP (skills / MCPs / hooks / harness)

### SKILLS — three-tier fan with count drift
| Layer | Path | Count | Role |
|---|---|---|---|
| VCS source of truth | `source/agent-skills-toolchain/skills` | **192** | Git-tracked canonical skill definitions |
| Runtime vault (Claude) | `~/.agents/skills` | **278** real dirs | Full router vault (copied, NOT symlinked) — semantic-router indexes this |
| Claude session view | `~/.claude/skills` → symlink → `~/.claude/skills.daily` | **75** | Curated daily subset loaded into session context |
| Codex copy | `~/.codex/skills` | (sep.) | Codex CLI's own skill copy |
| Retired / backup lanes | `~/.agents/skills-retired-2026-07-03`, `~/.claude/skills-archived-2026-06-11`, `~/.claude/skills.pre-agents-20260401-062109`, `~/.codex/superpowers` | — | Parked/archive |

**Drift flag:** 192 (VCS) vs 278 (runtime vault) vs 75 (daily) — the runtime vault has 86 skills NOT in the VCS source (locally-added, un-enshrined). This is exactly what the live `chore/enshrine-runtime-config` branch is reconciling. Copy-not-symlink means the three can silently diverge.

### HOOKS
| Path | Role |
|---|---|
| `~/.claude/hooks` | **LIVE hook set** — ~68 hook subdirs (goal-reinject, semantic-router, skill-router, mcp-canonical-sync, mcp-userscope-sync, mcp-liveness, mcp-defaults, stub-ledger, event-ledger, wire-check, edit-validate, tool-result-sentinel, etc.) + `hooks.json` + `create-worktree.ps1`/`remove-worktree.ps1` + `.bak` files |
| `~/.agents/harness` | **Harness ENGINE** the hooks dispatch into (`dispatcher.py`, `adapters.py`, `modules.py`, `registration.py`, `ledger.py`, `models.py`, `storage.py`, `recall_index.py`, `redaction.py`, `injection_grammar.py`, `schemas/`, `tests/`). **NOT a git repo** (canonical, edited in place per memory). |
| `~/.codex/hooks` + `~/.codex/hooks.json` | Codex-side hook copy (parity) |
| Enshrine target | `agent-skills-toolchain` `ci/harness` (in-flight via today's branch) — VCS mirror of `~/.agents/harness` + `~/.claude/hooks` |

### MCP CONFIG (most-scattered surface)
| Path | Size / updated | Role |
|---|---|---|
| `~/.mcp.json` | 8.8 KB, today 04:06 | **Canonical per-user MCP source** (~49 servers per memory) → promoted to user scope via `promote-mcp-userscope.ps1` |
| `~/.claude.json` | 146 KB, today 04:59 | **LIVE Claude state** (project+user MCP scope) — the file clobbered on session exit; user-scope promotion is Claude-CLOSED-only |
| `~/.claude/mcp-servers/mcp-servers.json` | — | Secondary MCP server registry |
| `~/.claude/mcp-configs/` | — | Per-config MCP fragments |
| `~/.codex/config.toml` (+ ~10 `.bak-*`) + `~/.codex/mcp-configs`, `mcp-wrappers`, `mcp-oauth-locks` | today | **Codex MCP config** (separate stack, own env_vars) |
| Per-repo `.mcp.json` + `.mcp-disabled-defaults.json` | — | Per-tree RAM curation (e.g. `bilbo-app/.mcp.json.bak-canonsync`); rule: never hand-edit, regen from canon |
| MCP server SOURCE code | `source/agent-skills-toolchain/tools/mcp/{cloud-hub,search-hub,social-hub}` + `source/repos/*-mcp` + `D:/MCP/ghidra-mcp`, `D:/ReverseTools/mcp/cve-mcp`, `D:/mcp-servers/*`, `D:/Tools/mcp-gateway`, `D:/Tools/mcp-manager` | Implementations behind the configs — scattered across all 3 partitions |

### PARTITION SPLIT (physical scatter)
- **`C:` `~/.claude` + `~/.agents` + `~/.codex`** = all live agent config, hooks, harness engine, runtime skill vault, MCP live state.
- **`C:/source`** = VCS source of truth for skills + harness-enshrine + core MCP servers (cloud/search/social-hub).
- **`C:/Documents/GitHub`** = app repos (Reframe, momentstudio, WebCoder, bilbo, pbinfo, env-inspector, event-link, QZP…).
- **`D:`** = RE toolkits, MCP servers, research compute, tool dev (mcp-manager/gateway), gem-wave-b, pr-b-clone, vendored knowledge clones.

**Key risks in the scatter:** (1) skills copied-not-symlinked → 192/278/75 three-way drift; (2) `~/.agents/harness` is canonical-but-un-versioned (only just being enshrined today); (3) MCP truth split between `~/.mcp.json` (canonical) and `~/.claude.json` (live, clobber-prone) plus a fully parallel Codex stack; (4) `~/.codex` holds ~15 `config.toml`/`AGENTS.md` backup variants — its own mini-scatter.