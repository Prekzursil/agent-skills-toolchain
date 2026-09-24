# Verified: agent-tooling claims (skills / MCP / hooks / harness / toolchain)

Lane: verify the strongest resume claims in `harvest-skills-scale.md` + `harvest-local-disk.md`.
Method: I re-ran every load-bearing measurement myself on this box and against the GitHub REST API.
I did **not** trust the harvest numbers. Where the two harvest files disagreed, I resolved it.

Evidence tags: **VERIFIED** (I ran the command / the API returned it, in this session) ·
**INFERRED** (my reading of verified inputs) · **COULD NOT DETERMINE**.

---

## 0. Corrections to the harvest files (I re-measured; both files are partly wrong)

| Thing | harvest-skills-scale | harvest-local-disk | **My measurement** | Resolution |
|---|---|---|---|---|
| `~/.claude/hooks` code | 148 files / 33,819 lines | 253 files / 60,683 LOC | **255 files / 60,852 non-blank; 148 non-test / 33,819; 107 test / 27,033** | Both right, different scopes. skills-scale counted implementation only; local-disk counted impl+tests. |
| Hook modules | 72 named + 3 infra | 76 | **78 top-level dirs = 72 named modules + `_dispatch`/`_shared`/`_golden` + `.pytest_cache`/`.ruff_cache`/`_fleet-backups`** | **72** is the correct module count. |
| `~/.agents/harness` | 31 files / 22,074 lines | 82 .py / 43,867 LOC | **82 files / 43,867 non-blank; 31 non-test / 22,074; 51 test / 21,793** | Same split artefact. |
| Authored skills | 145 OWN | ~158 (133+25) | **146 hard-positive union; 142 after removing contradicted rows** | See section 1. skills-scale is closest. |
| MCP servers written | 14 | ~23 | **18 with own source + 2 forks with substantial own work** | See section 2. Both off. |
| SKILL.md lines | 59,423 | (not given) | **59,422 raw / 45,196 non-blank / 2.94 MB over 413 files** | skills-scale used the raw line count. Fine if labelled "raw". |
| Commits | ~1,016 (UNTRUSTED-WEB) | 912 (DOC-CLAIM) | **1,016 on `main`, API-VERIFIED** | Link-header pagination, `per_page=1` gives `rel="last" page=1016`. No longer web-scraped. |
| 100%-coverage packages | 2 | 8 | **17 distinct `--cov-fail-under=100` steps in quality.yml; the charter says 2 "shipped packages"** | The charter is the conservative, citable number. |
| Contributors | inferred single (missing UI box) | (not checked) | **API: 6 rows = him x3 identities (906+35+3) + cursoragent 61 + dependabot 10 + cursor[bot] 1** | **Sole human author is now VERIFIED, not inferred.** |

---

## 1. THE decisive question: skills AUTHORED vs INSTALLED

### 1.1 What I ran

```
(Get-ChildItem ~\.agents\skills -Directory).Count                     -> 415
(dirs with a top-level SKILL.md)                                      -> 413
Compare-Object ~\.agents\skills vs ~\.claude\skills                   -> 0 differences
(Get-ChildItem ~\.claude\plugins\cache -Recurse -Filter SKILL.md)     -> 1,656
~\.agents\library\skills                                              -> 186 dirs
installed_plugins.json                                                -> 100 plugins
```

### 1.2 His own provenance ledgers (I re-parsed them; I did not copy the harvest tallies)

* `SKILLS-MANIFEST.md`, 354 unique rows: **unclassified 194 · custom 97 · built-in 42 · marketplace:superpowers 14 · vendored 7**.
  The file's own header says: *"`Origin` is curated provenance with no tracked source of truth, so rows the generator adds carry `unclassified` until a human classifies them."* So the 194 are genuinely unknown — not "his by default".
* `DEPLOYED-MANIFEST.json`, 105 rows: lane **first-party 51 / external 52** (+1 skipped, 1 stripped).
  Origins: none 50, ECC 37, community 12, and one each of ECC-port / forged / fork / local-control-plane / oh-my-agent-check / user.
* `.skill-lock.json`: **160 marketplace installs** (ToolUniverse 121, microsoft/azure-skills 28, Copilot-for-Azure 3, semgrep 3, DeepSource 2, am-will 1, cline 1, vercel-labs 1). **Only 36 are still in the live tree.**

### 1.3 My independent authorship computation

Hard-positive set = `manifest Origin == custom` UNION `DEPLOYED lane == first-party`:

```
custom 97 + first-party 51 - overlap 2 = 146 ; all 146 present in the live tree
```

Falsification tests I then ran against that set:

* **Marketplace-cache name collision: 1 of 146** (`firecrawl`). The whole 415-tree collides on 27 names.
* **skill-lock membership: 4 of 146** (`autofix-bot-api`, `create-tooluniverse-skill`, `microsoft-foundry`, `tooluniverse`) — these are mislabelled in his own ledgers. `microsoft-foundry` even carries `author: Microsoft` in frontmatter.
* **Upstream text markers ("vendored from / forked from / upstream: / ported from / copyright (c)"): 3 of 146**, all weak (`ida-multi-mcp`, `qiling-emulation`, `trail-of-bits-re` say `upstream:` about the *tool they drive*, not about the skill).

**142 skills survive every falsification test. VERIFIED.**

Size of that authored set (measured, not estimated):

* SKILL.md text: **12,925 non-blank lines / 1,027,095 bytes** (~1.0 MB of instruction text).
* **43 of the 146 bundle executable code: 44,465 non-blank LOC.** Two deductions before quoting that:
  * `microsoft-foundry` 4,683 LOC is Microsoft's (mislabelled), and
  * `workflow-monitor` 15,122 LOC contains **9,137 lines of his own `monitorcore` package re-vendored into the skill** — his code, but double-counted against `tools/monitorcore`.
  Net non-duplicated bundled code in the authored set is about **30.6K LOC**. INFERRED (arithmetic over verified inputs).

### 1.4 Verdict on the phrasings

| Phrasing | Verdict |
|---|---|
| "Wrote 400+ / 2,000 skills" | **DROP.** 415 is a *deployment* count; 1,656 further SKILL.md sit in the marketplace plugin cache, authored by other people. |
| "Built a 415-skill library" | **DROP** if it reads as authorship. Safe only as "curates / deploys". |
| "Authored 145+ agent skills" | **SUPPORTED** — 146 by his own two ledgers, 142 after removing every contradicted row. |
| "Authored 240 skills" (the harvest ceiling) | **UNSUPPORTED.** The 194 `unclassified` rows are unclassified by his own generator's rule, not unclaimed-but-his. |
| Floor claim "97 skills" | **SUPPORTED** and bulletproof (his `custom` count alone). |

**Strongest true wording:** *"Authored ~140 Claude Code agent skills (~1 MB of instruction text; 43 ship executable tooling) inside a 415-skill deployed tree curated with a machine-checked provenance manifest; a further ~1,650 marketplace skills are installed, not authored."*

---

## 2. MCP servers: BUILT vs CONFIGURED

### 2.1 Configured (VERIFIED)

`~/.claude.json` user scope **88** `mcpServers` (+45 project rows) · `~/.agents/agents.json` **94** · the repo README claims "40+ MCP server configs" and `release/platforms/windows` snapshots Codex 40 / Claude 39 / Gemini 33.
**"40+ MCP servers" in his own README is a CONFIG count and must never be read as servers written.**

### 2.2 Built — I measured every directory under `tools/mcp/` plus the three top-level ones

Non-blank LOC over py/js/mjs/ts/rs, excluding `node_modules`, `.venv`, `__pycache__`, `dist`; test files counted as `test_*.py` / `*_test.py` / `*.test.ts|js`.

| Server | LOC | test files | upstream marker in README |
|---|---|---|---|
| cloud-hub (11 cloud backends; 5 own FastMCP sub-servers + one vendored) | 12,727 total / **10,806 own** | 12 | ovh-mcp is MIT, author **Hleb Tkachenko**, 1,921 LOC — vendored |
| schrodinger-mcp | 8,193 | 2 | none |
| omniaudit-mcp *(separate public repo, MIT)* | 5,183 | 26 | none |
| mcp-http-host | 4,455 | 6 | none |
| social-hub | 2,617 | 7 | none |
| scholarly-access-mcp | 2,126 | 6 | none |
| fb-messenger-mcp | 2,068 | 6 | none |
| search-hub | 1,909 | 5 | none |
| linkedin-mcp | 1,756 | 2 | none |
| openmm-md-mcp | 1,536 | 1 | **LICENSE "Copyright (c) 2026 Prekzursil"** |
| abbyy-finereader-ocr-mcp *(separate public repo, MIT)* | 1,299 | 4 | none |
| codex-fleet-github | 1,283 | 2 | none |
| qdx-rush-mcp | 1,187 | 1 | none |
| patent-search-mcp | 965 | 2 | none |
| closed-batch | 799 | 1 | none |
| mcp-host-supervisor | 731 | 1 | none |
| fb-reels-uploader | 548 | 0 | none |
| tiktok-mcp | 413 | 1 | none |
| *(`_shared` accounts/hardening library, 1,152 LOC — a library, not a server)* | | | |

**Total: 18 MCP servers with own source, ~48.7K non-blank LOC, ~85 test files. VERIFIED.**

Forked with substantial own work — **say "hardened fork", never "wrote"**:

* `hacktricks-mcp-server` 3,297 LOC — README calls it a "derivative of the community" server; **LICENSE (c) 2025 Xplo8E**; npm name `@prekzursil/hacktricks-mcp-server`.
* `proxy-mcp` 743 LOC — README: adopts snapspecter/mitmproxy-mcp as the engine, adds redaction + `export_har`.

**Wrapper / config-only / empty — do NOT count these** (0-438 LOC each; README names the upstream): cheatengine-mcp-bridge (miscusi-peek), digitalocean-mcp (digitalocean/digitalocean-mcp), hexstrike-ai (0x4m4; 190 LOC of glue), graphql-mcp-bundle, reverse-engineering-mcp-bundle (438), workstation-codex-bundle (7), cyberstrike-mcp-kit, glm53-space, looker-mcp, biomni-hub-mcp (empty). `~/.agents/mcp-servers/video-agent-kit` (23,271 LOC) is third-party (Chinese-language README) and **must not be counted**.

### 2.3 The multiplexer claim — the best-evidenced one in this whole lane

cloud-hub / search-hub / social-hub are lazy, name-preserving MCP multiplexers that collapse many stdio servers behind a single client registration. Their READMEs claim 409 tools for cloud-hub (modal 41 / databricks 65 / biomni 25 / compute 10 / lightning 9 / ovh 27 / ...) and 88 for social-hub.

**First-hand corroboration: all three were live in MY OWN session.** `mcp__cloud-hub__*`, `mcp__search-hub__*` and `mcp__social-hub__*` are in this agent's tool list right now, several hundred tools deep. That is the rare claim I can demonstrate rather than merely count. VERIFIED.

---

## 3. Hooks and the lifecycle harness

### 3.1 `~/.claude/hooks` (VERIFIED, my own measurement)

**72 named hook modules**, plus `_dispatch` (a per-event manifest dispatcher), `_shared` and `_golden`.
255 code files / **60,852 non-blank lines**, split **148 implementation files / 33,819 lines** and **107 test files / 27,033 lines**, with **1,076 `def test_`**.
Third-party markers across the whole tree: **one file** (`git-hygiene/check.py`). No ECC / Affaan markers anywhere — unlike `~/.claude/commands` and `~/.claude/agents`, this tree is his.
**The suite was NOT executed** (some modules mutate live MCP config and I declined to run them). 1,076 is a static count.

### 3.2 Wiring (VERIFIED)

`C:\suite\settings.json` (25,912 bytes) contains **44 hook commands across 20 lifecycle events**: PreToolUse 14, PostToolUse 4, SessionStart 3, UserPromptSubmit 3, Stop 3, StopFailure 2, PostToolUseFailure 2, plus 12 events with one each (PreCompact, PostCompact, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, TeammateIdle, WorktreeCreate, WorktreeRemove, PermissionRequest, PermissionDenied, ConfigChange, SessionEnd).
16 of the 44 route through `harness/dispatcher.py`; 4 through `_dispatch/dispatch.py`.
Caveat: the **live** `~/.claude/settings.json` on this restore box is a 724-byte stub with **no hooks key**.

### 3.3 `~/.agents/harness` — the Shared Lifecycle Harness (VERIFIED, and **I executed the suite**)

82 code files / 43,867 non-blank lines; 31 implementation files / 22,074 lines; 51 test files / 21,793 lines; **1,400 `def test_`**.
Provider-neutral across Claude Code + Codex + Grok CLI (`dispatcher.py`, `adapters.py`, `modules.py`, typed `HookResult` schemas, an event ledger with an advisory lock, `recall_index`, `redaction`).

```
python -m pytest .agents/harness/tests -q --ignore=.../test_surface_reconciler.py
-> 17 failed, 873 passed, 12 skipped in 28.37s
```

**I ran this myself** and reproduced the harvest's figure exactly. All 17 failures are `AssertionError: 'allow' == 'inject'` in the basic-memory-nudge and sensitive-artifact modules — consistent with the memory daemon being down on this restore (`basic-memory` MCP is ECONNREFUSED in this very session) — but **I did not prove that**, so the suite is **98.1% passing, not green**.

---

## 4. The `agent-skills-toolchain` platform (GitHub API; all VERIFIED today)

```
GET /repos/Prekzursil/agent-skills-toolchain
  private=False  fork=False  stars=0  forks=0  watchers=0
  language=Python  license=NONE  created=2026-03-10  pushed=2026-09-23  size=241,441 KB
GET /repos/.../commits?per_page=1&sha=main  -> Link rel="last" page=1016      => 1,016 commits
GET /search/issues?q=repo:...+type:pr                -> 351 PRs
GET /search/issues?q=repo:...+type:pr+is:merged      -> 291 merged
GET /repos/.../actions/runs                          -> total_count 32,554
GET /repos/.../actions/workflows/quality.yml/runs?branch=main -> 416 runs
GET /repos/.../contributors?anon=1 -> Prekzursil 906 + Prekzursil <noreply@prekzursil.dev> 35
   + Prekzursil <mariusvisalon70@gmail.com> 3 + cursoragent 61 + dependabot[bot] 10 + cursor[bot] 1
GET /users/Prekzursil -> public_repos=68  followers=7  name="Andrei Mihai Visalon"
```

Companion public repos, also API-verified today:

```
Prekzursil/omniaudit-mcp              public, MIT, 0 stars, 6 commits,  109 Actions runs, created 2026-02-19
Prekzursil/abbyy-finereader-ocr-mcp   public, MIT, 1 star,  8 commits,   86 Actions runs, created 2026-06-10
Prekzursil/quality-zero-platform      public, no license, 0 stars, created 2026-02-19
```

### 4.1 What these numbers do and do not support

* **1,016 commits, 351 PRs / 291 merged, 32,554 CI runs over ~6.5 months** — a very strong, click-through-checkable sustained-engineering signal. After pbinfo this is the best artifact in the lane.
* **Sole human author: VERIFIED.** All three human contributor rows are his own identities; the other three rows are bots (`cursoragent` 61 commits is Cursor's background agent, plus dependabot and cursor[bot]). Nobody else has committed.
* **0 stars / 0 forks / 0 watchers, 7 followers.** Any adoption or community wording is dead.
* **No LICENSE file.** "Open-source" is **not** supportable for the toolchain repo. Use `omniaudit-mcp` and `abbyy-finereader-ocr-mcp` (both MIT) for the open-source line instead.
* **Main is frequently red.** Of the last 20 `quality` runs on `main`: **3 success, 9 failure, 8 cancelled**; the two most recent `quality` runs on any branch both failed (2026-09-23). The gate exists, is pinned and runs — but "all gates green" would be false and is one Actions-tab click from being caught.
* Both published MCP repos are **thin on the surface**: 6 and 8 commits, 0 and 1 star. The code inside is real (5,183 LOC / 26 test files and 1,299 LOC / 4 test files), but a reviewer's first impression will be "small repo".

### 4.2 CI content (read from `origin/main` via the `.agents` checkout's packed objects)

12 in-repo workflows. `quality.yml` is **1,726 lines / 121,811 bytes**, with jobs `lint · types · test-node · test-python · test-platform · sast · secrets · deps`.
`QUALITY-CHARTER.md` defines a closed set of **6 deterministic pinned gates**: ruff 0.15.17, basedpyright 1.39.8 (standard mode), pytest 100% line+branch (`--cov-fail-under=100`), opengrep 1.23.0 on a curated in-repo ruleset (clean-zero, no baseline), gitleaks with a committed allowlist, osv-scanner 2.x. Actions are SHA-pinned and `.quality/charter_check.sh` fails CI if the charter and the workflow diverge.
The charter scopes 100% coverage to **two shipped packages** (`tools/mcp-manager`, `tools/scholarly-access-mcp`) and explicitly states that the hundreds of skill/hook helper scripts are "not a 100%-coverage target". **Quote the charter — it is the honest number** — even though `quality.yml` in fact carries 17 `--cov-fail-under=100` steps (monitorcore, mcpctl, mcpapply, agentspec, agentrail, stdin_server, harness_drift, reap, wf_gate, wearables, ...).

### 4.3 Test-function totals (static counts on the local mirror; VERIFIED)

`tools/` 4,834 (excluding the vendored `tools/editor` tree, which has 15) · `platform/` 2,191 · `skills/` 943 · `scripts/` 69 = **8,037 in the repo mirror**, plus harness 1,400 and hooks 1,076 outside it.
Caveat: the `skills/` 943 includes tests bundled inside vendored skills, so quote **"~8,000"** and never a precise figure.

### 4.4 Other verified structure

`platform/` = architecture, coordination, corpus, council, lib, marketplace, plugin, registry, routing, schema, workflows; **126 JSON workflow blueprints**; `rules/` has **90 markdown rule files**; `tools/` has 46 top-level projects and `tools/mcp/` has 27.
`~/.claude`: **74 slash commands** (mostly everything-claude-code + metaswarm; roughly 13 his), **20 subagents** (15 carry ECC names, 9 of those have `.bak-gembuild-*` backups proving a local rewrite, 5 are his), 6 Workflow scripts.
`tools/mcp-manager` is a genuine PySide6 desktop app (`pyside6>=6.11.1` in its pyproject) with **331 `def test_`**.

---

## 5. Claims that DIE

| Dead claim | Why |
|---|---|
| "Open-source platform" (the toolchain) | API says `license=NONE`; no LICENSE file at the repo root. Its own GitHub description calls it *"Private platform repo ... I use"*. |
| "Adopted by / used by the community" | 0 stars, 0 forks, 0 watchers, 7 followers. |
| "400+ / 2,000 skills authored" | 415 is a deployment count; the 1,656 cached SKILL.md files are other people's work. |
| "40+ MCP servers built" | 40 is the *config snapshot* count; 88/94 are configured; **18** are written. |
| "556K lines of code" | Includes a 150K-line vendored Rust fork (`ralph-orchestrator`), metaswarm, hacktricks, ovh-mcp and vendored skill payloads. Never quote it ungrossed. |
| "All quality gates green" | 9 of the last 20 `quality` runs on `main` failed; the two most recent runs failed. |
| "Contributor to community MCP servers" | No upstream-merge evidence anywhere; his forks are local hardening. |
| "Team" / "led a team" | Only bot co-contributors. |

---

## 6. Two things the parent agent must handle before publishing

1. **Identity collision.** `skills/owner-ops-authorization/SKILL.md` names the owner as *"Prekzursil / **Marius Valentin Visalon** / costin.ionescu@bolt.eu"*, and the GitHub contributor list carries a **`mariusvisalon70@gmail.com`** identity with 3 commits on the toolchain. The ground truth for this document is **Andrei-Mihai Visalon**. I cannot reconcile these — **COULD NOT DETERMINE**. Ask him before anything derived from that skill is used.
2. **The Bolt signal.** Three skills (`codex-databricks-fanout`, `estate-offensive-doctrine`, `owner-ops-authorization`) reference a corporate Databricks workspace `bolt-datascience` and a `@bolt.eu` address, and `codex-databricks-fanout` documents a **608-unit production Codex fan-out** as "MEASURED". If that is his own employment it is the single strongest engineering-scale claim in this lane. But it is attached to a different name, sits on infrastructure he does not own, and is probably confidential. **Do not put it on the resume without him confirming the engagement and clearing disclosure.** Treat the harvest files' silence on this as a gap, not as clearance.

---

## 7. Blanket caveat that belongs in the final document

Every tree above was produced *through* Claude Code / Codex sessions he designed, prompted and orchestrated — the hooks README calls it "the session-built agentic-perfection hook set", and `cursoragent` has 61 commits. The git author identity is his, and the architecture, the gates and the provenance discipline are his decisions.
**"Designed, built and maintains"** is honest. **"Hand-wrote 60,000 lines"** is not — and an AI-engineering interviewer is exactly the person who will ask.
