# GitHub harvest — Prekzursil (Andrei Mihai Visalon)

Harvested 2026-09-23 (UTC afternoon). Every claim is tagged **[VERIFIED]** (observed directly in an API
response, a git clone, a fetched page, or a file) or **[INFERRED]** (my reading of verified facts).
Nothing here was authenticated: api.github.com was called with no Authorization header; clones used
`git -c credential.helper=` over public HTTPS. No credential value was read or printed.

## 0. Method and evidence files

- API calls (unauthenticated, 60/h shared with other agents on this IP; quota hit 0 twice): `/users/Prekzursil`,
  `/users/Prekzursil/repos?per_page=100`, `/repos/Prekzursil/<orig>/languages` (x20), `/users/Prekzursil/orgs`,
  `/users/Prekzursil/events/public` (3 pages, 293 events), `/search/issues|commits` (8 queries).
  Raw JSON: `scratchpad\gh\user.json`, `repos.json`, `languages.json`, `orgs.json`, `events.json`, `search.json`.
- Non-API sources (not quota-metered): `github.com/<owner>/<repo>` HTML (star/fork counters),
  `github.com/Prekzursil/<repo>/releases.atom` (release history), `github.com/Prekzursil/<repo>/actions/workflows/<wf>/badge.svg`
  (live CI status), `github.com/users/Prekzursil/contributions` (calendar), registry.npmjs.org, pypi.org, momentstudio.ro,
  prekzursil.github.io. Results: `upstreams_html.json`, `releases_atom.json`.
- Clones: 20 originals (`--filter=blob:none`, checked out) + 18 forks with pushes (history only) + 2 third-party
  upstreams for a provenance check, all under `scratchpad\gh\clones\`. Analyzer: `gh\analyze.py` -> `gh\analysis.json`;
  READMEs copied to `gh\readmes\<repo>.md`.
- Blocked: GitHub Releases asset download counts (needs `/releases` API; quota was 0 on both attempts). Re-run
  `gh\api4`-style call for `Reframe`, `env-inspector`, `llm-anthology` after the hourly reset.

## 1. Profile facts [VERIFIED]

| Field | Value |
|---|---|
| login / name | `Prekzursil` / "Andrei Mihai Visalon" |
| location / bio / blog / company | Romania / (empty) / (empty) / (none) |
| hireable flag | `true` |
| created | 2019-08-28 |
| public repos / gists | 68 / 0 |
| followers / following | 7 / 16 |
| organizations | none |
| profile README repo (`Prekzursil/Prekzursil`) | does not exist |
| contributions calendar | **6,432 contributions in the last year** (2025-09-21..2026-09-19); 190 of 368 days active |
| active days by month | 2025-11:7, 12:7, 2026-01:27, 02:27, 03:27, 04:16, 05:5, 06:21, 07:26, 08:16, 09:11 |

Lifetime search-index totals [VERIFIED, search API]: **1,791 PRs authored (1,590 merged)**, **91 issues**, **3,648 commits**
on indexed default branches. Only 18 of the 1,791 PRs are outside his own account (section 6).

## 2. Inventory: 20 originals, 48 forks [VERIFIED]

Originals sorted by last push (stars/forks received in parentheses; all 0/0 unless shown):

| Repo | Lang (GitHub) | Created | Last push | Stars/forks | License | One-line |
|---|---|---|---|---|---|---|
| agent-skills-toolchain | Python | 2026-03-10 | 2026-09-23 | 0/0 | none | AI-agent skills/tools/hooks monorepo (described as "Private platform repo" though public) |
| TanksFlashMobile | TypeScript | 2026-02-07 | 2026-09-22 | 0/0 | MIT | Ruffle web wrapper + Capacitor mobile + Godot remake spike for the Flash game TANKS |
| WebCoder | TypeScript | 2023-11-29 | 2026-09-22 | 0/0 | none | Django + React online-judge style platform; no README |
| bilbo-app | Kotlin | 2026-04-09 | 2026-09-21 | 0/0 | MIT | Kotlin Multiplatform digital-wellness app (Android/iOS) |
| codeblocks-pretty-prints-stable | Python | 2026-03-23 | 2026-09-21 | 0/0 | MIT | Fetch-and-package installer control plane for a Code::Blocks toolchain |
| llm-anthology | Python | 2026-07-19 | 2026-09-20 | 0/0 | MIT | Offline archive/search of ChatGPT/Claude/Gemini/Codex exports; Tauri cockpit |
| momentstudio | Python | 2025-11-28 | 2026-09-20 | 0/0 | MIT | Live bilingual e-commerce (FastAPI + Angular), homepage momentstudio.ro |
| pbinfo-scrape | HTML | 2026-03-13 | 2026-09-18 | 0/0 | none | Electron/TS crawler for pbinfo.ro with 348 MB of crawled HTML committed |
| Airline-Reservations-System | Python | 2025-05-26 | 2026-09-18 | 0/0 | none | University OOP project: C++17 console + C++ API + React GUI |
| Reframe | Python | 2025-12-06 | 2026-09-18 | **4/1** | none | Local-first desktop video studio (Electron/React + Python sidecar) |
| quality-zero-platform | Python | 2026-02-19 | 2026-09-18 | 0/0 | none | Reusable-workflow GitHub governance control plane + admin dashboard |
| SWFOC-Mod-Menu | C# | 2026-02-15 | 2026-08-30 | 0/0 | MIT | WPF/C++ trainer + save tooling for Star Wars: Empire at War / FoC |
| DevExtreme-Filter-Go-Language | Go | 2025-05-26 | 2026-08-28 | 0/0 | none | Go + ent dynamic filter backend serving a React test UI |
| env-inspector | Python | 2026-02-18 | 2026-08-26 | 0/0 | MIT | Cross-platform env-var inspector/editor with EXE releases |
| Personal-Finance-Management | Java | 2025-05-26 | 2026-08-21 | **1/0** | none ("all rights reserved") | "Thrifty" Android finance app, labelled Bachelor's project (see 4.19) |
| Star-Wars-Galactic-Battlegrounds-Save-Game-Editor | Python | 2025-01-25 | 2026-08-12 | **1/0** | none | tkinter .ga2 save editor |
| omniaudit-mcp | Python | 2026-02-19 | 2026-08-07 | 0/0 | MIT | FastAPI MCP connector with 3 modules |
| grace-iberlef-2026 | Python | 2026-06-07 | 2026-08-02 | 0/0 | none | Spanish clinical argument mining experiments (GRACE @ IberLEF 2026) |
| abbyy-finereader-ocr-mcp | Python | 2026-06-10 | 2026-07-22 | **1/0** | MIT | Multi-engine OCR MCP server |
| tracelines | Python | 2026-07-13 | 2026-07-14 | 0/0 | AGPL-3.0 | Street View coverage extractor; PyPI + Pages GUI live |

Stars received across all originals: **7** (Reframe 4, PFM 1, SWGB 1, abbyy 1). Forks received: **1** (Reframe).

## 3. Cross-repo measurements

### 3.1 Commit activity over time [VERIFIED, from clones]

Owner-authored commits (author name/email matching prekzursil|visalon; default branch for originals, all branches for forks),
total **5,135** across the 38 clones:

| Month | Commits | Month | Commits |
|---|---|---|---|
| 2025-01 | 2 | 2026-02 | 619 |
| 2025-04 | 2 | 2026-03 | 750 |
| 2025-05 | 4 | 2026-04 | 683 |
| 2025-06 | 1 | 2026-05 | 11 |
| 2025-11 | 279 | 2026-06 | 437 |
| 2025-12 | 278 | 2026-07 | 502 |
| 2026-01 | 610 | 2026-08 | 855 |
| | | 2026-09 (to 23rd) | 102 |

Reading [INFERRED]: the public history is effectively **11 months old** (Nov 2025 onward) despite a 2019 account. Nine
commits total exist before Nov 2025 (Jan 2025 SWGB editor upload; May 2025 bulk uploads of three university projects).
The May-2026 trough (11 commits) coincides with the end of the BSc period. Per-repo owner commits: momentstudio 1,339;
agent-skills-toolchain 944; event-link (fork) 509; quality-zero-platform 464; Reframe 389; SWFOC 293; llm-anthology 262;
pbinfo-get-unsolved (fork) 250; Airline 129; env-inspector 123; TanksFlashMobile 88; bilbo-app 51; democracyos (fork) 49;
grace 32; DevExtreme 31; pbinfo-scrape 25; SWGB 25; WebCoder 22; codeblocks 21; PFM 20; tracelines 10.

Last four weeks [VERIFIED, events API]: 293 public events; 148 PullRequestEvents (68 momentstudio PRs opened AND merged;
agent-skills-toolchain 5 opened), 115 PushEvents, 7 forks created, 9 stars given.

### 3.2 Languages by volume [VERIFIED, `/languages` bytes]

Raw total across 20 originals: 435.1 MB, of which **347.0 MB is HTML in pbinfo-scrape** (crawled pages committed).
Excluding that repo's HTML (88.1 MB of real code):

| Language | Bytes | Share | Main repos |
|---|---|---|---|
| Python | 54.0 MB | 61% | agent-skills-toolchain (30.5 MB), Reframe (9.8), momentstudio (6.7), llm-anthology (2.0), QZP (2.0) |
| TypeScript | 15.6 MB | 18% | Reframe (6.0), momentstudio (5.8), llm-anthology (1.5), pbinfo-scrape |
| C# | 4.7 MB | 5% | SWFOC-Mod-Menu |
| C++ | 4.6 MB | 5% | SWFOC-Mod-Menu (4.4), Airline (0.19) |
| JavaScript | 3.1 MB | 4% | agent-skills-toolchain, Airline, TanksFlashMobile |
| PowerShell | 1.2 MB | 1.4% | agent-skills-toolchain, SWFOC |
| Kotlin | 1.2 MB | 1.4% | bilbo-app |
| Shell | 0.8 MB | | |
| CSS / Rust / Jupyter / C / Java / Swift / Go | 0.54 / 0.49 / 0.40 / 0.38 / 0.31 / 0.26 / 0.24 MB | | Rust=llm-anthology Tauri; Java=PFM; Swift=bilbo iOS; Go=DevExtreme |

Caveat [INFERRED]: agent-skills-toolchain vendors third-party code and corpora (see 4.9), so "30.5 MB of Python" there is not
all his. Without that repo: Python ~44%, TypeScript ~29%.

### 3.3 Tests and CI [VERIFIED]

- All 20 originals have GitHub Actions workflows (2 to 31 per repo). CodeQL workflow present in 16/20.
- Live badge status of the primary workflow: **18 passing, 2 failing** (agent-skills-toolchain `quality.yml`, WebCoder `quality.yml`).
- Test files exist in 19/20 (Personal-Finance-Management has **0**). Test-LOC / code-LOC ratio: Reframe 0.56, QZP 0.55, SWGB 0.55,
  abbyy 0.55, env-inspector 0.53, pbinfo-scrape 0.53, llm-anthology 0.51, Airline 0.49, omniaudit 0.45, codeblocks 0.42,
  momentstudio 0.41, SWFOC 0.38, WebCoder 0.35, agent-skills-toolchain 0.30, bilbo 0.24, DevExtreme 0.21, tracelines 0.18,
  TanksFlashMobile 0.12, grace 0.12, PFM 0.
- A `.coverage-thresholds.json` (100% line+branch gate) is committed in bilbo-app, llm-anthology, Reframe, quality-zero-platform,
  SWFOC-Mod-Menu, grace-iberlef-2026. Reframe also runs `mutation.yml` / `mutation-incremental.yml` and an opt-in `e2e.yml`.
- Almost every repo carries the same governance kit: SECURITY.md, `.gitleaks.toml`, `osv-scanner.toml`, `.pre-commit-config.yaml`,
  dependabot, `AGENTS.md`, PR template. Recent commits on most repos are Dependabot bumps; "last substantive non-bot commit" dates:
  agent-skills-toolchain 2026-09-22, momentstudio 09-06, Reframe 08-14, llm-anthology 08-12, QZP 08-12, PFM 08-12, TanksFlashMobile 08-01,
  bilbo 07-25, tracelines 07-14, omniaudit 07-11, codeblocks/Airline/SWFOC/env-inspector 07-04, grace 06-30, pbinfo-scrape 06-28,
  WebCoder/abbyy 06-27, DevExtreme/SWGB 06-26.

### 3.4 Releases [VERIFIED via releases.atom; download counts unknown]

| Repo | Real releases | Notes |
|---|---|---|
| Reframe | desktop-v0.1.0..0.1.7 (2026-02-04), v1.0.0 (06-28), v1.1.0, v1.2.0, v1.3.0, v1.4.0 (07-07), v1.4.1 (07-09) | Windows NSIS installer + portable zip; README/CHANGELOG state v1.4.1 is still a Draft and 1.5.0 is unreleased |
| env-inspector | v1.0.0 (02-18), v2.0.0 (03-04) | EXE via `env-inspector-exe-release.yml`; "maintenance mode" |
| bilbo-app | v1.0.0 (04-16), v1.0.1 (04-17) | |
| SWFOC-Mod-Menu | v1.0.0, v1.0.1, v1.0.2 (05-20) | portable release workflow |
| pbinfo-scrape | v0.1.0..v0.1.3 (03-14..03-27) | |
| llm-anthology | v0.1.0 (08-11) | **PyPI `llm-anthology` 0.1.0 live** |
| tracelines | v0.2.0 (07-14) | **PyPI `tracelines` 0.2.0 live**; README's "live on npm" claim is false (`@prekzursil/tracelines` -> 404) |
| TanksFlashMobile / codeblocks / PFM | v0.1.0 / v0.1.0 / v1.0.0 | |
| agent-skills-toolchain | 111 tags, all `archive/...` or `rescue/...`, 10+ shown as Releases | junk on the Releases page |
| momentstudio | 91 tags, all `rescue/...` (10 surfaced as Releases) | junk on the Releases page |
| quality-zero-platform | `v1` plus 23 `backup/...` tags | junk on the Releases page |

### 3.5 Adoption and outside contributors [VERIFIED unless noted]

- No repo has a star count above 4. No outside-authored PR or issue was found on any of his repos (all 91 issues and
  1,773 own-repo PRs are his). Forks received: 1.
- Human non-owner git authors on his originals: **one** recurring identity, "Daria Grama", with 1-5 commits in ~12 repos
  (momentstudio 3, TanksFlashMobile 4, WebCoder 5, SWFOC 4, DevExtreme 4, PFM 3, Reframe 3, SWGB 2, codeblocks 1,
  env-inspector 1, Airline 1, pbinfo-get-unsolved 4). Content of those commits (checked in momentstudio): "Adopt managed CodeQL and
  security baseline", "Sync managed QLTY baseline", "Always emit required visual checks", all 2026-03-30. [INFERRED] This is a
  fleet-governance sync run under a second person's identity, not independent adoption; whether it is a collaborator or a second
  account of his own is unknown.
- Bot authors everywhere: dependabot, ecc-tools[bot], deepsource-autofix, snyk-bot, Copilot/copilot-swe-agent, openai-code-agent,
  Cursor Agent, cursor[bot], github-actions.
- Live surfaces: **momentstudio.ro** (HTTP 200, nginx, `<title>momentstudio</title>`), **prekzursil.github.io/tracelines** (200,
  "street-level coverage cockpit"), **prekzursil.github.io/quality-zero-platform** (200, "Quality Zero Admin").
- Packages: PyPI `tracelines` 0.2.0 (author Prekzursil, homepage the Pages GUI), PyPI `llm-anthology` 0.1.0. `env-inspector` and
  `svcoverage` are not on PyPI. npm package claimed by tracelines README does not exist.

## 4. Per-repo dossiers and verdicts

Verdict scale: **A** = portfolio-grade, link it; **B** = neutral, describe or fix before linking; **C** = hurts if opened as-is.
"AI trailers" = share of commits (all branches) carrying a `Co-Authored-By` trailer naming Codex/Claude/Cursor/etc.

### 4.1 Reframe — A (flagship)
[VERIFIED] 4 stars, 1 fork. 417 commits on main (389 his), 1,016 on all branches, 63 branches, 17 tags, 10 releases with Windows
installers (NSIS + portable). Tree 1,342 files / 23.7 MB; LOC: Python 179,668, TSX 95,184, TS 51,297, CSS 15,369 (code total
~343K; docs 23,750 lines of Markdown). 550 test files / 190,807 test lines. Workflows: quality, e2e, mutation, mutation-incremental.
`.coverage-thresholds.json` (100% line+branch, sidecar and renderer), CHANGELOG (semver), SECURITY.md, QUALITY-CHARTER.md,
`docs/rpc-contract-v2.md`. README is unusually candid ("System requirements (honest)"; comments admitting a stale version string).
Architecture per README: Electron + React/TS renderer <-> Python sidecar over stdio JSON-RPC; faster-whisper, Qwen3-4B via llama.cpp,
YuNet face detector, ffmpeg/libass, vidstab, PySceneDetect, Kokoro/Chatterbox/edge-tts TTS. AI trailers 23%.
Flags: no LICENSE file (API `license: null`; a NOTICE file exists); v1.4.1 release is a Draft; `vendor/` dir present; 12 open issues.
[INFERRED] The strongest single item: shipped desktop software with releases, a coverage gate that actually blocks, and a real changelog.

### 4.2 momentstudio — A (product), with a mandatory cleanup
[VERIFIED] Homepage momentstudio.ro is live (200). FastAPI backend under `/api/v1` + Angular storefront/admin + `infra/` Docker Compose;
topics: angular, dam, ecommerce, fastapi, payments, postgresql, redis, seo. 1,429 commits on main (1,339 his; also 60 dependabot,
7 openai-code-agent, 6 snyk-bot, 5 Cursor Agent, 3 Copilot, 3 Daria Grama). LOC: Python 192,092, TS 150,733 (code ~350K); 447 test
files / 141,582 test lines; 31 workflows (backend, frontend, codeql, compose-smoke, chromatic-playwright, applitools-visual,
sentry-release, deploy-production-manual, dependency-review, codecov/codacy, quality-zero-*). README covers docker stack, Codecov/Codacy,
Playwright E2E, backups, GHCR release images, a release verification checklist, a "Sameday mirror" courier ops runbook.
MIT, CONTRIBUTING, CODEOWNERS, CODE_OF_CONDUCT, SECURITY. 68 PRs opened and merged in the last four weeks alone.
**Flags [VERIFIED]:** **63,362 remote branches**, 63,116 of them `cursor/*`, holding 63,360 commits authored "Cursor Agent"
(66,317 commits on all branches vs 1,429 on main); 22,986 commits carry a `Co-Authored-By: prekzursil1993` trailer; 91 `rescue/*`
tags surface as Releases. The Branches tab is unusable and screams "unattended agent runs".
[INFERRED] Best evidence of production engineering on the profile (payments, SEO, ops runbooks, visual regression), for a real client
("AdrianaArt" handmade products). Prune the cursor/* branches and rescue tags before putting the link on a resume.

### 4.3 llm-anthology — A
[VERIFIED] 269 commits on main in 2 months (262 his; AI trailers 4%). Python engine (42,259 LOC) + TypeScript/Tauri cockpit (35,135
TS + 5,227 Rust) + JS renderer. 103 test files / 45,146 test lines (ratio 0.51). Workflows: ci, codeql, format-drift-canary,
release (PyPI trusted publishing). v0.1.0 on GitHub and on PyPI. MIT, CHANGELOG, ARCHITECTURE.md, RELEASING.md, SECURITY.md,
`.coverage-thresholds.json`, 11 topics. README explains a "fidelity contract" and a security/privacy posture (offline, no egress).
Flags: 0 stars, one release, 10 open issues. [INFERRED] Cleanest "own idea, own code" repo; good for showing product thinking + polyglot.

### 4.4 env-inspector — A (small)
[VERIFIED] Python 21,198 LOC, 56 test files (ratio 0.53), v1.0.0/v2.0.0 with an EXE build workflow, README with release/build/license
badges and 3 screenshots, CHANGELOG, CONTRIBUTING, MIT, mypy/pylint/prospector/codecov/sonar/deepsource configs. Status line says
"Maintenance mode (v2.0.0): critical fixes only". AI trailers 66% (Codex 219, Claude 60). 134 commits on main.
[INFERRED] Small but complete; a reviewer sees a finished tool with releases.

### 4.5 tracelines — A (small, brand new)
[VERIFIED] 10 commits over 2 days (2026-07-13/14), 100% his, 0 AI trailers. Python 2,946 LOC + JS GUI; 13 test files; Dockerfile,
mkdocs, render.yaml, Cloud Run/HF Space proxy scripts; CI + nightly-canary + pages + release workflows; AGPL-3.0; DATA_LICENSES.md,
THIRD_PARTY_LICENSES.md, RESEARCH-REPORT.md; 10 badges, 8 images; PyPI 0.2.0 live; Pages GUI live.
Flag: README says "tracelines is live on npm" and adds an npm badge, but the package returns 404 [VERIFIED].
[INFERRED] Good example of "ship a complete small OSS tool with docs", if the npm claim is fixed.

### 4.6 SWFOC-Mod-Menu — A for RE/game-tooling audiences, B otherwise
[VERIFIED] C# (117,479 LOC) WPF app + C++ (71,966) native/bridge + Python tooling; `SwfocTrainer.sln` with App/Catalog/Core/DataIndex
projects; 307 commits (293 his; AI trailers 74%, Codex 381); v1.0.0-1.0.2 releases; workflows ci, codeql, dependency-review,
ghidra-headless, quality, release-portable; 230 test files; `.coverage-thresholds.json`; MIT, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.
Tree is 47,065 files / 293.6 MB because a reverse-engineering knowledge base is committed (`knowledge-base/callgraph_index.sqlite` 23.5 MB,
`decompile_corpus/ida_full/*.json`, 1.94M lines of JSON), plus `.github/PULL_REQUEST_TEMPLATE.md` and `pull_request_template.md`
colliding on case-insensitive filesystems.
[INFERRED] Demonstrates C#/WPF + native interop + RE workflow (Ghidra headless in CI). Topic ("trainer", "game-hacking") may not fit
every employer; the giant committed corpus makes the repo slow to clone.

### 4.7 bilbo-app — A/B
[VERIFIED] Kotlin Multiplatform (Kotlin 30,133 LOC, Swift 6,938, TS 2,528 for a Supabase backend), 8 workflows (android-ci, ios-ci,
shared-tests, backend-ci, codeql, quality, autofix-models, dependabot-auto-merge), v1.0.0/v1.0.1, 916-line README with 8 badges,
6 images, architecture/data-flow/domain-model/schema sections, CHANGELOG, CONTRIBUTING, MIT, `.coverage-thresholds.json`.
Flags: only 51 of 158 main commits are his (118 dependabot on branches; **77 commits authored "Test <test@example.com>"** on 2026-05-30
writing Robolectric/Compose tests); AI trailers 48%; 0 stars.
[INFERRED] Credible mobile sample; the "Test" identity in the contributor graph must be rewritten or explained.

### 4.8 quality-zero-platform — A/B (platform engineering)
[VERIFIED] 479 commits on main (464 his), Python 53,494 LOC, 178 test files (ratio 0.55), **31 workflows** of which 17 are
`reusable-*` (quality, codeql, scanner-matrix, remediation-loop, ruleset-sync, secrets-sync, bump-workflow-shas, chromatic,
applitools...), scheduled CVE scan, codex-fleet-wave, admin dashboard published to Pages (live). README describes a "hybrid ratchet +
strict-zero" governance model over a fleet of his repos; other repos consume it via `Prekzursil/quality-zero-platform/.github/workflows/reusable-codeql.yml`.
Flags: no license, 24 backup tags, 16 open issues, AI trailers 50%.
[INFERRED] Strong DevOps/GitHub-platform evidence; reads as internal tooling rather than a product.

### 4.9 agent-skills-toolchain — B (describe, do not link as-is)
[VERIFIED] Public repo whose description begins "Private platform repo". 1,016 commits on main (944 his), 2,319 on 221 branches
(868 authored "Cursor Agent"), 111 archive/rescue tags, 40 open issues, no license, **quality workflow failing**. 13,430 files / 282 MB
tree: `skills/` holds **372 `SKILL.md`** (+35 in `skills-claude-only/`), `tools/` 41 packages, `hooks/` 293 files, `commands/` 71,
`command-center/` 1,988 files, plus committed **browser profiles** (`browser-profiles/chrome-agent/...` 655 files incl. a 23 MB wasm
and Safe Browsing stores) and a 610-file `harness-sota-2026-07-18-corpus`. 16 workflows (codex-runner, p2-agent-runner/shard/loop,
pr-reconcile, mcp-audit, hook-audit, routing-benchmark...). README: "370+ skills"; quick start mentions git-crypt-encrypted
`accounts.json` stores; a 2026-09-22 commit is titled "Remove git-crypt filters: plaintext accounts stores (owner decision)".
[INFERRED] Enormous and genuinely his, but a reviewer opening it meets a red CI badge, committed browser-profile binaries, and
hints of credential stores. Summarize the numbers in prose; only link after cleanup.

### 4.10 TanksFlashMobile — B
[VERIFIED] Ruffle-based web wrapper for the Flash game TANKS (`assets/original/tanks.swf` committed), Capacitor Android/iOS shells,
a Godot/GDScript clean-room remake spike (961 GDScript lines), Playwright smoke; TS 5,689 LOC; v0.1.0; MIT; 3 workflows; README has
an "About assets / legality" section and store-readiness docs. No GitHub description; 45 branches; 34 dependabot + 11 ecc-tools commits.
[INFERRED] Fine as a hobby line item; the third-party SWF in the repo is the legal soft spot.

### 4.11 codeblocks-pretty-prints-stable — B (small)
[VERIFIED] Python 2,606 LOC + PowerShell + Inno Setup; 12 test files; v0.1.0; MIT; SUPPORT/CONTRIBUTING/THIRD_PARTY_NOTICES.
"Fetch-and-package control plane" for a curated Code::Blocks + MinGW/GDB pretty-printer installer. 37 commits (21 his).

### 4.12 omniaudit-mcp — B (thin)
[VERIFIED] 6 commits on main; Python 6,204 LOC; 27 test files; docker-compose; README with architecture diagram and ChatGPT connector
setup; MIT. Only tag is a smoke tag. [INFERRED] Presentable but obviously an early scaffold.

### 4.13 abbyy-finereader-ocr-mcp — B (small)
[VERIFIED] 1 star; 14 files; Python 1,638 LOC; 4 test files; MIT; README with engine comparison table (RapidOCR/Tesseract/ABBYY) and
CER/WER evaluation; 8 commits.

### 4.14 DevExtreme-Filter-Go-Language — B
[VERIFIED] Go 21,649 LOC with `ent` ORM (SQLite in-memory) + file-based dynamic tables; 49 `_test.go` files; 3 workflows; README ok.
Flags: a 7.5 MB React source map and 2 MB bundle committed under `static/app`; description literally says "For Testing"; 53 of 117
commits authored by a "917-Andrei-Visalon" identity; AI trailers 72%; created 2025-05-26 with the initial commit next day.
[INFERRED] Usable as the Go sample if the built bundle is removed.

### 4.15 Airline-Reservations-System — B (student project, mislabeled)
[VERIFIED] Description: "C++ App + GUI To Manage Airline Reservations." GitHub language bar: **Python 43%, C++ 34%, JavaScript 20%**.
The Python is quality-gate scripts and Python-side tests (32 `.py` files vs 20 `.cpp` + 12 `.h`). C++17 + CMake + Googletest console
app, C++ API server (cpp-httplib, nlohmann/json), React GUI; the course assignment PDF `OOP Projects_2025_v2_...pdf` and
`cline_docs/` (an AI "memory bank") are committed. 142 commits on main (129 his), AI trailers 63%, 36 test files, no license.
[INFERRED] Exactly the inconsistency a reviewer notices; fix with `.gitattributes` `linguist-vendored`/`linguist-language` and a
description that matches. As a 2025 OOP course project it is fine, not a headline.

### 4.16 Star-Wars-Galactic-Battlegrounds-Save-Game-Editor — B (tiny)
[VERIFIED] 1 star; Python 2,185 LOC (tkinter); 3 test files; README documents the .ga2 format and the byte pattern used; PyInstaller spec.
Initial commit 2025-01-25 titled "Initial + Final (hopefully)". [INFERRED] Honest hobby RE item.

### 4.17 pbinfo-scrape — C (do not link)
[VERIFIED] 48,907 files / 407 MB tree; 348 MB of crawled pbinfo.ro HTML plus 985,628 lines of JSON snapshots committed, so GitHub
labels it "HTML 99.6%". Actual code: TypeScript 33,898 + TSX 4,021 (Electron desktop "operator console"), 84 test files, vitest,
v0.1.0-0.1.3 releases. README calls it a "private PBInfo archival operator console"; 78 commits by "Test <test@example.com>".
[INFERRED] Scraped third-party educational content in a public repo is a legal/ethical soft spot and the repo is unclonable in practice.

### 4.18 WebCoder — C as it stands
[VERIFIED] No README on main **or on any of the 37 branches**; no description; quality workflow **failing**; main has 29 commits and
its last substantive commit is 2026-06-27, while the real work (Next 15.5 App Router port, "229/229 vitest", judge containerization,
Django CI fixes) sits on `origin/wave/nextjs-migration` (last commit 2026-09-22). A 10.9 MB `tree.txt` and `.idea/` are committed.
Repo created 2023-11-29 but history begins 2025-06-15 ("Fix authentication and permission issues"), i.e. history was rewritten.
Backend Django (Python 6,391 LOC), frontend React/TSX (6,033 LOC); 34 test files. AI trailers 37%.
[INFERRED] The project (an online judge / coding-problems platform) is resume-worthy; the repo is not, until the branch is merged
and a README exists.

### 4.19 Personal-Finance-Management — C (provenance problem)
[VERIFIED] README: "Thrifty ... This project was originally developed as a Bachelor's degree project" and "No license has been
declared ... all rights are reserved by the author." GitHub description says "written it Kotlin And Java" [sic]; code is Java 99.7%,
0 test files. `app/build.gradle` line 11: `applicationId "com.preethi.thrifty"`; Java package `com/thriftyApp/`.
Provenance check against **github.com/preethi-sv/Thrifty-app** ("Thrifty | Personal Expense Tracker App with OCR", 17 commits,
2019-04-27..2020-06-08, author Preethi Sureshkumar, no license): at his initial commit (2025-05-27, 191 files, one commit)
**63 files are byte-identical blobs at identical paths**, 102 paths coincide, the same `applicationId` and the same 19 Java class
files exist (AddBudgetActivity, AddReminderActivity, AlertsActivity, AlertsTable, ...). `samyukthagopalsamy/Personal_Finance_Management_Android_App`
is the same 118-file codebase (2020). His repo is not a GitHub fork and gives no attribution anywhere.
What he added [VERIFIED]: 17 new Java classes (BackupManager, DriveServiceHelper, LocaleUtils, ThemeUtils, ReminderReceiver,
BootReceiver, SettingsActivity/Fragment, ChartUtils, CustomPieChartRenderer, TextGraphic/GraphicOverlay, adapters, ThriftyApp) and
+3,527/-1,178 lines across the 19 shared classes; Java grew from 2,487 to 6,455 lines; 8 PlantUML diagrams; RO/EN localisation;
Google Drive backup; theme/settings. So roughly 60% of the Java at first commit is his [INFERRED from the line counts].
[INFERRED] As a bachelor's project that "extended an open-source expense tracker" it can be defended; as "my Bachelor's project"
with all rights reserved and no credit, it is the single most damaging thing on the profile, because a reviewer finds the upstream
with one search on the package name. Either attribute explicitly (README + resume wording) or leave it off.

### 4.20 grace-iberlef-2026 — C until fixed
[VERIFIED] Repo name/description: "GRACE @ IberLEF 2026 - Spanish clinical argument mining (Track 1) ... 27-cell transformer sweep on
Modal + softmax-probability ensemble". README title: **"bionlp - ToolUniverse Workspace"** (a generic ToolUniverse setup page) that
only mentions GRACE in a sub-section: `FINAL/` holds the "canonical competition submission" (9 models x 3 seeds on Modal,
"all-9 dev strict macro-F1 = 0.743"), `FINAL/report/` holds PPTX/DOCX/PDF, `grace/` is a coverage-gated reference library.
36 commits (32 his), Python 19,494 LOC, 1 notebook, 29 test files, no license, default branch `master`.
[INFERRED] Potentially the only research artefact on GitHub, but nothing here proves an official shared-task submission or a
working-notes paper (ORCID lists zero works). The README mismatch would make a reviewer doubt it.

## 5. Forks (48): what is real

Substantive (his commits verified in the fork's history):

| Fork | Upstream (stars/forks, HTML-scraped) | His commits | What |
|---|---|---|---|
| event-link | victormura/event-link (1/1) | **509 of 548** (356 of 383 on main); Nov 2025..Aug 2026 | React (Vite) + FastAPI + SQLAlchemy event-management app: Alembic, k6 load tests, 139 test files, 3 workflows, UML docs. 8 of his PRs merged upstream incl. "Implementation of Event Link MVP: core auth, event lifecycle, recommendations, email & CI" (#2) and "Static Code Polishing + 100% Line + Branch Coverage" (#12). Collaborator Victor Mura: 3 commits. [INFERRED: university team project hosted under the teammate.] |
| pbinfo-get-unsolved | ezluci/pbinfo-get-unsolved (6/2) | **250 of 291** (41 of 69 on main) | Romanian-language userscript for pbinfo.ro; 4 PRs merged upstream incl. "release: userscript-first v2.0.0 major rewrite" (#14, 2026-02-25). Upstream owner ezluci: 21 commits. |
| ZHMModSDK | OrfeasZ/ZHMModSDK (282/46), Hitman 3 modding SDK, C++ | 9 (8 on master) | "Add TitaniumBullets mod (shoot through walls)" **merged upstream as PR #241 on 2025-12-17**; two earlier attempts (#239, #240) closed. |
| democracyos | DemocracyOS (6,417 upstream commits) | 49 on `feat/m0-foundation`, 2026-08-18..26 | Prisma migrations (identity, forums/permissions, topics/tags) with raw-SQL constraints, schema tests, design docs; no upstream PR. In progress. |
| ToolUniverse | mims-harvard/ToolUniverse (1,701/257) | 9 (7 on main) | 2026-05-27 bug fixes (UniProt count, ClinVar fail-closed, CLI UTF-8...) and 2026-07-25 dependency-advisory closes; **no upstream PR**. |
| metaswarm | dsifry/metaswarm (419/55) | 1 | "perf(hooks): skip BEADS dedup scan outside metaswarm projects" = upstream **PR #51, open** (2026-09-19). |
| ralph-orchestrator, mcp-funnel, design-extract, BCSFE-Python, hexstrike-ai, Whisper_GUI | various | 1-9 each, all dated 2026-07-25 | Dependency-advisory bumps / CI pins from a fleet sweep; mcp-funnel got a "first CI in the repo" commit. Not resume material. |
| osds-lab, minitalk | course repos | 6 / 1 | OS lab solutions ("solved") and a governance-baseline commit. |

Zero owner commits (33): context-mode, humanizer, ghostwriter, Library-First-Engineering, CL4R1T4S, Fabric, OBLITERATUS, goose,
jina-ai, heretic, vdhlocales, OpenCut, build-your-own-x, Stirling-PDF, ladybird, DroidVM, Anthropic-Cybersecurity-Skills, VirtualApp,
OmniVoice-Studio, skills, FunClip, AToM-OpenMM, super-linter, paper-search-mcp, agentflow, awesome-android-root, SwitchAI, headless-ida,
FoCAPI, ovhcloud-mcp, AI-Youtube-Shorts-Generator, claude-code-proxy, Sci-Hub-MCP-Server, sec-tools.
[INFERRED] Profile-hygiene note: recent forks visible at the top of his profile include CL4R1T4S ("leaked system prompts"),
OBLITERATUS, heretic ("censorship removal for language models") and Sci-Hub-MCP-Server; a conservative reviewer may read these.

## 6. Contributions outside his account [VERIFIED, search API + events]

18 PRs on other people's repos, 1 issue, 2 comments, 21 threads involving him:
- Merged: OrfeasZ/ZHMModSDK #241; victormura/event-link #2, #3, #5, #6, #7, #10, #11, #12; ezluci/pbinfo-get-unsolved #11, #12, #14.
- Closed unmerged: event-link #1, #8, #9; pbinfo-get-unsolved #13; ZHMModSDK #239, #240; jhj0517/Whisper-WebUI #633 (title ".").
- Open: dsifry/metaswarm #51; jhj0517/Whisper-WebUI issue #544 (feature request, 2025-04-23).

## 7. Cross-cutting facts a reviewer will notice

1. **AI co-authorship is pervasive and visible** [VERIFIED]: `Co-Authored-By` trailers naming Codex / "Claude Opus 4.6|4.7" /
   "Claude Fable 5.1" / Cursor on 74% of SWFOC commits, 72% DevExtreme, 66% env-inspector, 63% Airline, 61% PFM, 53% codeblocks,
   50% QZP, 48% bilbo, 47% agent-skills-toolchain, 37% WebCoder, 36% momentstudio, 27% TanksFlashMobile, 23% Reframe, 4% llm-anthology,
   0% tracelines; plus commits *authored* by "Cursor Agent" (63,360 in momentstudio branches, 868 in agent-skills-toolchain branches),
   openai-code-agent[bot], copilot-swe-agent[bot], anthropic-code-agent[bot]. [INFERRED] This is not hideable; the resume should
   own it ("AI-assisted development behind strict CI gates") rather than let a reviewer discover it.
2. **Git identity sprawl** [VERIFIED]: at least six owner identities ("Andrei Mihai Visalon" noreply, "Prekzursil" at three different
   mail domains, "917-Andrei-Visalon", "prekzursil"), plus **"Test <test@example.com>"** commits in 7 repos (bilbo 77, pbinfo-scrape 78,
   QZP 13, codeblocks 11, Airline 10, env-inspector 9, PFM 8). Contributor graphs show "Test" as a top contributor in two repos.
3. **Junk tags/releases** in agent-skills-toolchain (111), momentstudio (91), QZP (24), SWFOC (`salvage/`, `recover/`), and the
   `archive/pre-lean-gate` tag in ten repos.
4. **Committed bulk**: pbinfo-scrape 348 MB HTML; SWFOC 293 MB RE corpus; agent-skills-toolchain browser profiles + corpora;
   DevExtreme 9.5 MB built bundle + source map; WebCoder 10.9 MB `tree.txt`.
5. **No license** on 10 of 20 originals (incl. Reframe, QZP, WebCoder, Airline, grace, PFM "all rights reserved").
6. **Descriptions vs reality**: Airline (says C++, shows Python), PFM (says Kotlin, is Java; typo "written it"), agent-skills-toolchain
   ("Private platform repo" on a public repo), grace (README for a different project), tracelines (npm claim false), WebCoder and
   TanksFlashMobile (no description).
7. **Two red CI badges** (agent-skills-toolchain, WebCoder) on the two repos with the most recent activity.
8. **No public history before 2025** despite the 2019 account; no orgs; no profile README; empty bio; `hireable: true`.

## 8. Resume-ready claims (with the exact evidence) and framing

Strong (link-safe today): Reframe; llm-anthology; env-inspector; tracelines (after fixing the npm line); ZHMModSDK merged mod.
Strong after a cleanup: momentstudio (prune 63K branches/91 rescue tags); bilbo-app (rewrite the "Test" identity);
quality-zero-platform (license, backup tags); SWFOC-Mod-Menu (optional).
Describe in prose only: agent-skills-toolchain (372 skills / 41 tools / 293 hook files / 16 workflows), event-link (hosted under the
collaborator; 509 commits, 8 merged PRs), pbinfo-get-unsolved v2.0.0.
Keep off or fix first: WebCoder (README + merge), Personal-Finance-Management (attribute the Thrifty upstream), grace-iberlef-2026
(README; confirm official participation), pbinfo-scrape (never link).

Quantified profile line that is fully verifiable: "20 original public repos, all with GitHub Actions CI (18/20 green today);
6,432 GitHub contributions in the last 12 months; 1,590 merged PRs; three shipped desktop/CLI tools with releases (Reframe v1.4,
env-inspector v2.0, llm-anthology 0.1 on PyPI); one production e-commerce site (momentstudio.ro)."

## 9. Gaps this source cannot fill

- Release download counts (Reframe installers, env-inspector EXE) - API quota exhausted by parallel agents; retry after reset.
- Whether GRACE @ IberLEF 2026 was an official submission / published working notes (ORCID shows zero works).
- How the Bachelor's project was presented to the university and whether reuse of preethi-sv/Thrifty-app was disclosed.
- Who "Daria Grama" is (collaborator vs second account) and who "917-Andrei-Visalon" is (looks like a university GitHub identity).
- Who the momentstudio client is and any traffic/revenue; deployment ownership beyond the live domain.
- Pinned repositories (GraphQL only), private repos, and any employment/internship evidence (no org memberships; LinkedIn not read here).
- Anything before 2025: the account is from 2019 but the earliest surviving commit is 2025-01-25.
- Exact human-vs-AI authorship split inside commits (trailers understate; Cursor-authored branches overstate).
