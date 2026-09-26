---
title: Fleet triage plan 2026-07-25 (wf_081e0b4a-3bc)
type: note
permalink: main/projects/fleet-triage-plan-2026-07-25-wf-081e0b4a-3bc
tags:
- fleet
- triage
- osv-scanner
- dependabot
- quality-campaign
---

# Fleet triage plan 2026-07-25 (wf_081e0b4a-3bc)

READ-ONLY 10-agent workflow, 0 errors, 88 min, 1.47M tokens. Full result: the workflow journal + the task output file (153KB truncated in-context). Every claim below is agent-verified with cited CI job IDs.

## HEADLINE — the blocked PRs are mostly NOT the PRs' fault
For **TanksFlashMobile, momentstudio, pbinfo-scrape, ToolUniverse**, `main` ITSELF is red (osv-scanner advisory drift / unpinned-linter drift), proven with main-branch controls. **The fix belongs to the REPO, not the PRs.** Fixing main first also means **ZERO admin overrides** are needed anywhere — the correct, safe sequencing.

## Wave 1 — fix main (dispatched 2026-07-25 ~06:00 UTC, all PR-gated)
- **TanksFlashMobile** (agent af4cd87a671028369): main run 30119536694 job 89568442885 fails at *exactly* step 20 `gate-deps osv-scanner`, nothing else — `24 packages / 33 vulns (2 Crit, 26 High, 5 Med)`. Prior run 28683814409 was SUCCESS ⇒ newly-published-advisory drift, not a code regression. `quality / quality` is REQUIRED + strict=true ⇒ **all 18 open PRs blocked by it**. Merging all 18 CANNOT reach zero (brace-expansion flagged in ALL FOUR lockfiles = 10 rows, but only #179/#180 touch it; sharp 0.34.5 + shell-quote 1.8.4 in apps/web and js-yaml 4.2.0 in apps/desktop have NO open PR). Fix = npm `overrides` + regenerate 4 lockfiles. All 33 dev-only, all have a fixed version ⇒ **no `[[IgnoredVulns]]` is defensible**.
- **momentstudio** (af96e9d8a1e496470): main run 30122281252 job 89577588130, same shape — `14 packages / 22 vulns`. Two partial-fix traps CONFIRMED off the table: the flagged postcss is the **NESTED** `@angular-devkit/build-angular/node_modules/postcss@8.5.12` (so #662's top-level bump misses it), and there are **TWO** fast-uri rows (3.1.3→3.1.4 AND 4.1.0→4.1.1, so #659 clears only one). strict=false ⇒ no rebase cascade.
- **pbinfo-scrape** (a542f8f2a2c61f739): open PRs cover 9/10 flagged packages, so merging IS most of the fix — but **shell-quote GHSA-395f-4hp3-45gv (8.7) has NO PR at all**. Mechanism verified on the npm registry: `concurrently@10.0.3` pins shell-quote 1.8.4, `10.0.4` pins 1.9.0 — which is exactly why it survives PR #21 (targets ^10.0.3). Also needs brace-expansion→5.0.8 (GHSA-mh99-v99m-4gvg).
- **ToolUniverse** (a68fb8157be607539): `astral-sh/ruff-action@v3` with `version: "latest"` + a `[tool.ruff.lint]` that sets only `ignore` (no `select`) ⇒ ruff 0.16.0's expanded defaults drifted the gate red. Blameless-proof: PR #23's ruff error set is **byte-identical to main's** (21,481 vs 21,481; comm -13 = 0, comm -23 = 0). NOTE: this repo's `main` is **UNPROTECTED** (404 "Branch not protected") ⇒ zero required checks.

## merge_now (after wave 1; strict two-signal, NEVER --admin)
pbinfo-scrape **#15** (file-disjoint, workflow only, setup-node v6→v7 empirically green at all 3 call sites), then SEQUENTIAL on package-lock: **#20** (the fleet's single highest-value merge — the ONLY PR killing the **CVSS 9.2 Critical** tar GHSA-23hp-3jrh-7fpw; verified job 89568978355: 13 vulns/1 Crit → 9 vulns/0 Crit), **#18** (only PR fixing the sole RUNTIME-scope advisory, body-parser GHSA-v422-hmwv-36x6 — all others dev-scope), **#17** (postcss 7.5), **#19** (sharp 7.0; engine floor node>=20.9 safe, CI pins node 24), **#22** last (security-neutral; its osv shows 16 vs main's 13 purely from OSV.dev publishing 3 more brace-expansion advisories between 19:06 and 23:25 — **DB drift, not a regression**).
- **ToolUniverse #23**: conditional order — if #19 is kept, #19 MUST merge first (#23→#19 conflicts 4× UU in all four requirements.txt; #19→#23 is clean).
- **ralph-orchestrator #8** before #9 — ⚠️ but its green is **VACUOUS**: 0 check-runs/0 statuses on head 9188495826db, and the repo registers only a "Dependabot Updates" workflow ⇒ nothing compiled or tested it. Do NOT treat as verified.

## Durable lessons
- A required-check red can be **repo state, not PR state** — always run the main-branch control before blaming a PR.
- "Merge all the dependabot PRs" is not equivalent to "reach zero vulns": check which rows have NO PR, and watch for NESTED copies a top-level bump can't reach.
- An osv count differing from main can be **advisory-DB drift** (new CVEs published between two runs), not a regression — compare the affected-package SET, not the count.
- Unpinned tool versions in CI (`version: "latest"`, no explicit ruff `select`) turn an upstream release into a fleet-wide red.


## Wave-1 results + a FLEET-WIDE unfixable advisory (2026-07-25 ~04:00 UTC)

### `GHSA-mh99-v99m-4gvg` (brace-expansion) is the fleet's common blocker — and is GENUINELY UNFIXABLE
Published **2026-07-24T21:53:14Z** (mid-campaign — which is why briefed advisory counts went stale: Tanks' briefed 33 was really 43 on a pristine control 2h46m later). Vulnerable range `<= 5.0.7`; **5.0.8 is the ONLY patched version**. The 1.x line tops out at 1.1.16 and 2.x at 2.1.2 — **no backport exists**. Both escape routes were REPRODUCED as breaking, independently in two repos:
- force 5.0.8 tree-wide → `TypeError: expand is not a function` / `(0, brace_expansion_1.default) is not a function` (1.x/2.x export a bare function, 5.x an object)
- force `minimatch@10` → `TypeError: mm is not a function` (its CJS export is also an object)
Old copies are pinned by `minimatch 3.1.5/5.1.9/9.0.9` via `@electron/asar`, `@electron/universal`, `dir-compare`, `filelist`, `glob`, `test-exclude` — every consumer is a `minimatch <10`.

**ORCHESTRATOR DECISION (autonomous, /loop, flagged for owner review):** my blanket "add no osv ignore entries" constraint was written for advisories WITH an available fix. **Overridden for this ONE GHSA**, because refusing it left a **CVSS 9.2 Critical (tar) unfixed on pbinfo main** and kept **18 Tanks PRs blocked**. Implementing a narrow, dated (`expiry 2026-10-23`), fully-justified `osv-scanner.toml` ignore scoped to that single advisory — never blanket, gate never disabled, branch protection untouched. Consistent wording across repos. Re-check trigger recorded: *has minimatch/glob/electron-builder moved off brace-expansion <5?*

### Per-repo wave-1 outcomes
- **ToolUniverse #24 MERGED** (03:42Z). Pinned ruff **0.15.21** — NOT the 0.15.18 my brief claimed (that version was never in a CI run; 0.15.21 is the last actually observed green, run 29110337427). Explicit `select = ["E4","E7","E9","F"]` derived by DIFFING `ruff check --show-settings`: 56 rules pre-change vs **411** under 0.16.0 (372 added) — that IS the drift; with the explicit select, 0.15.18/0.15.21/0.16.0 all resolve 56, added=0/removed=0. CI: **21,647 violations → 0**.
- **TanksFlashMobile #193**: 33 → **6** vulns, both Criticals cleared; only `gate-deps` red, all other gates green. Residual = the 6 GHSA-mh99 rows → ignore+merge dispatched (a739b910b70b59297). Merging it unblocks 18 PRs.
- **pbinfo-scrape #23**: 13 → **2** vulns; the **9.2 Critical (tar)** and the sole RUNTIME advisory (body-parser) are GONE. Discovered `Dependencies (osv-scanner)` is a REQUIRED check with `strict:true` that only passes when ALL packages are clean ⇒ **no subset PR can EVER merge individually** (proved by an actual merge attempt: "base branch policy prohibits the merge"). Residual = 2 GHSA-mh99 rows → ignore+merge+supersede-closes dispatched (ae980fde1661b2c25).
- **momentstudio**: agent still running.

### Durable lessons added
- A required "all-clean" scanner gate + subset-fixing dependabot PRs = **structural deadlock**: no individual PR can ever pass. The only exits are one comprehensive commit, or relaxing the gate. Detect it early by reading branch protection, not by retrying merges.
- **Advisory counts are timestamped facts, not stable ones** — a count that differs from a brief may be DB drift; compare the affected-package SET and check the advisory's publish time.
- `gh run view --log` can silently return 0 lines with exit 0 — a DETECTOR failure. Use `gh api repos/.../actions/jobs/<id>/logs`.


## pbinfo-scrape CLOSED (04:16Z) — verified by me
`main` run on `b75a3e777` = **success** (prior `20f088372` = failure); **0 open Dependabot alerts**; osv log: `Loaded filter from: /github/workspace/osv-scanner.toml` → `Filtered 2 vulnerabilities from output` → `No issues found` → `Exit code: 0`. Merged **#23** (squash `3d8389ce6`) + **#15** (squash `b75a3e777`, needed `gh pr update-branch` first — it predated the new lockfile). Closed as superseded after a DETERMINISTIC differ (base→head lockfile vs post-merge main, NOT by title): #17 postcss, #18 body-parser, #19 sharp, #20 tar. **#22 was NOT superseded — the inherited list was wrong** (playwright 1.62.0 / react 19.2.8 are AHEAD of main); left open. #21 only partly superseded → left open; dependabot then closed it itself.

### The osv-scanner.toml trap that would have silently voided the fix
`internal/config/config.go`: `tryLoadConfig` **REJECTS THE WHOLE FILE on ANY unknown key**, then **silently falls back to an empty config** — i.e. a typo'd or invented field disables the ignore with no error. My suggested "re-check" field had to become a COMMENT. Valid keys inside `[[IgnoredVulns]]` are exactly `id`, `ignoreUntil`, `reason`. `ShouldIgnore` matches one exact ID; `shouldIgnoreTimestamp` re-reds the gate after the date. **Always verify a config schema against the tool's SOURCE, and both-states test the config (control with it moved aside).** The agent did: control → `Exit code: 1`, with config → `Exit code: 0`, in the exact CI image `ghcr.io/google/osv-scanner-action:v2.3.8`.

### Independent corroboration of the ignore decision
**GitHub's own Dependabot auto-dismissed GHSA-mh99-v99m-4gvg as `scope=development`** — the same dev-scope reasoning behind the ignore, reached independently by a different system. Also confirmed no backport exists: npm dist-tags `maintenance-v1=1.1.16`, `maintenance-v2=2.1.2` (both published 2026-07-08, BEFORE the advisory), and v5.0.8's CJS entry exports `{EXPANSION_MAX, EXPANSION_MAX_LENGTH, expand}` with `typeof .default === "undefined"` — hence the TypeError under `minimatch <10`.
Caveat recorded: the advisory is only ~1 day old, so a 1.x/2.x backport may land well before the 2026-10-23 expiry — worth re-checking sooner.


## momentstudio wave-1 result (PR #663) — 22 → 2, same GHSA-mh99 residual
BEFORE `14 packages / 22 vulns (1 Crit, 10 High, 9 Med, 2 Low)` → AFTER `2 packages / 2 vulns (0 Crit, 2 High)`. Mechanical row diff: **22 cleared, 0 carried over**; steps 12-19 (lint, types, tsc, basedpyright, py+jsts coverage, SAST, secrets) all stayed green. Closure agent dispatched (abc38673a674c35ab) with the pbinfo-proven ignore procedure + the schema trap pre-loaded.

### What the momentstudio agent found that my brief got WRONG
- **`dompurify >=3.4.12` was MISSING from the briefed pin set** — a real 15th row.
- **Three flagged rows were being force-pinned to the VULNERABLE version by the repo's EXISTING `overrides` block** (`tar 7.5.16`, `hono 4.12.25`, nested `dompurify 3.4.11`) — so the work was EDITING an overrides block, not just adding one. Lesson: read the existing overrides before assuming a pin is additive.
- A plain top-level `postcss` override is **illegal against a direct devDep** → must use `$postcss`. npm's `name@range` key form scopes correctly (verified with a forced non-latest control), so nested-path scoping was unnecessary — and blanket pins would have DOWNGRADED production `body-parser@2.3.0` and build-path `sass`→`immutable@5.1.9`.
- brace-expansion: it pinned ONLY the `minimatch@10` copies to `^5.0.8` and left `minimatch@3/@9` alone — correct, because minimatch@3 is what eslint/karma/karma-coverage/glob/resp-modifier request (the lint AND test toolchain).

### Detector failure it caught in itself (worth keeping)
It initially claimed the lockfile regeneration fixed `npm ci`. **CI refuted it** — still fails identically (`Missing: chokidar@5.0.0`), because CI's npm 10 resolves differently than local npm 11, AND its `npm ci --dry-run` probe **passed on the OLD lockfile too**, so the probe measured nothing. Pre-existing, neither introduced nor fixed → separate follow-up issue. (Same shape as the both-states rule: a probe that passes in the known-bad state proves nothing.)


## TanksFlashMobile CLOSED (verified by me): main ALL GREEN, 18 open PRs → 1
`#193` merged (`4eabfb8f3`). Final main run 30144791513 / job 89644412507 (`9c1f9c47f`): `Filtered 5 vulnerabilities` / `No issues found` / `PASS gate-deps: osv-scanner found 0 actionable CVEs.` Residual dropped 6→5 because #179's eslint-10 bump genuinely eliminated the `apps/remake-web` copy.
**Per-PR disposition:** 5 MERGED (179, 177, 173, 172→recreated as #196, 178→recreated as #195) · 8 CLOSED-superseded **verified in the MERGED MAIN LOCKFILE, not inferred from the override declaration** (181, 182, 185, 186, 187, 188, 189, 192) · 4 closed by dependabot itself (183/184/190/191) · **1 SKIPPED: #180** — real `npm ERESOLVE: Conflicting peer dependency: vitest@4.1.10` (bumps `@vitest/coverage-v8`→4.1.10 but leaves `vitest`→3.2.7); diagnosis posted on the PR. Fixing it would take the residual 5→4.

**New root cause for the unfixable residual:** `app-builder-lib@26.15.3` (latest electron-builder) **EXACT-PINS** `@electron/asar 3.4.1` + `@electron/universal 2.0.3` (no semver range), so the fixed majors are unreachable; `dir-compare@5.0.0` and `@eslint/eslintrc@3.3.6` (both latest) still require `minimatch ^3.x`. → worth an UPSTREAM issue; unfixable downstream.

## REGRESSION I INTRODUCED (caught by the agent, fix dispatched aea160cf8dd006085)
**A security override must be a FLOOR, not a CEILING.** My wave wrote exact-version pins (`"postcss": "8.5.18"`, `"tar": "7.5.22"`, `brace-expansion@1/@2/@5`), which **permanently freeze those packages**: postcss capped at 8.5.18 while 8.5.23 exists, shell-quote at 1.9.0 while 1.10.0 exists — and **dependabot then closed PRs #183/#184/#190/#191 saying "up-to-date now" because the cap MISLED it.** Gate is green today, but a FUTURE CVE in any pinned package would be silently un-actioned. Fix = convert the #193-added pins to `>=` floors across all 4 workspaces, prove per-package that no resolved version went backwards, keep the GHSA-mh99 ignore untouched. (`bl`/`esbuild` pins pre-date #193 — left alone.)
**Durable rule: write transitive security overrides as `>=<patched>`, never `=<patched>`. Then verify dependabot can still see past them.**


## Pin→floor regression FIXED (PR #197 merged `ab3fce3f`) — and my instruction was REFUTED by measurement
I said "convert to `>=` floors". The agent shipped **BOUNDED** floors (`>=X <NextMajor`) after measuring three things — and it was right:
1. A bare `>=` floor silently crossed **fast-uri 3.1.4→4.1.1** and **js-yaml 4.3.0→5.2.2** — majors no consumer declares (`^3.0.1`, `^4.1.0`); js-yaml 5 drops 6 exported APIs.
2. The repo's own `.github/dependabot.yml` ignores `version-update:semver-major` for `*` in all 4 dirs — a bare floor contradicts repo policy.
3. **My "harmless" premise about `brace-expansion@1` was FALSE**: `">=1.1.16"` collapsed all six nested 1.x/2.x copies into ONE hoisted 5.0.8, **reproducing the exact `TypeError: expand is not a function` that #193 existed to prevent**. The bounded form preserves the tree byte-for-byte.
**My literal instruction would have re-broken the build.** Third time this session an agent caught an error in my own guidance.

**VERIFIED BY ME on main:** overrides are bounded; **postcss resolved 8.5.18 → 8.5.23** (the ceiling genuinely lifted, not just the declaration); main ALL GREEN. Resolved deltas: postcss →8.5.23 (×3 locks), sharp →0.35.3, shell-quote →1.10.0, nanoid →3.3.16. **0 backwards, 0 added, 0 removed.**

**Dependabot question settled with a proven mechanism (both directions, on pre-#197 blobs):** exact pin + `npm update postcss` → stays **8.5.18** (ceiling proven); bounded floor + same command → **8.5.23**. #183/#184/#190/#191 need NO reopening — their targets are satisfied on main NOW; dependabot's "up-to-date now" was **false when stated** and is **true now**.

**Owner sign-off wanted (deliberate trade-off):** the bounded UPPER bound means a CVE fixed *only* in a next major turns the gate **RED** instead of auto-resolving. Chosen as visible > silent, and it matches the existing brace-expansion precedent — but it is a real trade-off.

**Durable rule (revised):** transitive security overrides should be **bounded floors** `>=<patched> <<next-major>` — a bare `>=` can silently cross a major and break the build; an exact `=` freezes the package and blinds dependabot. Verify by checking the RESOLVED version in the lockfile moved, not that the declaration changed.


## ToolUniverse: 14 open PRs → 3, and MY PREMISE WAS REFUTED
**I briefed "all 11 DIRTY PRs are dependabot regenerating the same PR — likely all superseded". FALSE.** `main` satisfies **NONE** of the 18 advisories those PRs carry.
**The agent's own near-miss (textbook detector failure, caught by itself):** its first alert probe returned **exactly 100 rows** — a `per_page` cap, not a total. Properly paginated: **332 open** at the time. That inverted the plan; closing #1/#6/#10 as originally planned would have discarded real remediation **including a CRITICAL `langchain-core`**. *A count of exactly 100 is a cap, not a total — always `--paginate`.*

**Landed:** #23 MERGED (`88930d5b`) — the only remediation for the `mistune` HIGH advisory (<3.3.0) across 4 manifests; verified `mistune==3.3.0` on main. Its earlier failure was the ruff-0.16.0 drift; after `update-branch` onto the post-#24 main, step 9 went green and the core tests + doctor CLI ran for the first time.
**Closed as genuinely superseded (10):** #3, #5, #6, #10, #13, #14, #15, #16, #17, #19 — each fully DOMINATED by {#1, #12} (every package it raises is pinned ≥ by one of them), with a per-PR pkg→version→covering-PR table posted on each.
**LEFT OPEN deliberately (3):** **#1** + **#12** = the minimal pair covering all 14 requirements.txt advisories (#1 uniquely: langchain-text-splitters, langchain-openai, nbconvert, simpleeval, filelock; #12 uniquely: pyarrow, idna, urllib3). Both CONFLICTING — the agent deliberately did **NOT** `@dependabot rebase` them, because dependabot's two newest runs re-resolved much NARROWER and dropped pyarrow/langchain-core/urllib3/idna/orjson; a rebase would silently destroy those fixes. Correct call, owner decision. **#4** = abandoned non-dependabot bundle.

**MEASURED BY ME (paginated): 276 open alerts — 11 critical, 111 high, 113 medium, 41 low.** Hotspot: **`uv.lock` = 147**, then 32 each across 4 `remote/*/requirements.txt` (same set ×4).

### Owner calls surfaced
1. **Major bumps block merging #1/#12** — pyarrow 19→23, langchain-core 0.3→1.3, langchain-openai 0.3→1.1, pytest 8→9. Each is the LOWEST version closing its advisory, so unavoidable. (pyarrow isn't imported in source nor declared in pyproject — only pinned in remote requirement files CI never exercises, so blast radius was untestable.)
2. **4 advisories NO open PR can fix**: `h11` **CRITICAL** (needs ≥0.16.0, main 0.14.0), `langchain-community` high, `marshmallow`, `pygments`.
3. **`uv.lock` = 147 alerts with no live PR**; dependabot has opened no uv-group PR since **2026-05-06**. Needs `uv lock --upgrade` + a diagnosis of why the updater went quiet.
4. **No `.github/dependabot.yml`** ⇒ only SECURITY updates run, never version updates. (This is also why closing was safe — dependabot re-opens while an alert is open; observed #22 merged 19:06 → #23 opened 19:11.)
5. **PR #4 commits auto-loading agent config** (`.codex/config.toml`, `.claude/` hooks) into the repo — CVE-2026-47751-class auto-load surface — and the ECC plugin was already uninstalled per the owner's own notes, so it looks obsolete. Untouched.

→ Dispatched af2a632a47fd1ecff for TWO independent PRs: (A) `uv lock --upgrade` for the 147, (B) bounded-floor pins for the 4 no-PR advisories (h11 critical first). Both CI-gated on the real `Run Tests (3.12)` job.


## momentstudio BLOCKED — on a THIRD-PARTY OUTAGE, not on the fix
The ignore is written, pushed and **CI-verified working** (`Filtered 2 vulnerabilities` → `Total 0 packages affected`), but `gate-deps` fails **exit 127** / `rpc error: code = Unavailable` — **deps.dev's gRPC resolver is down** for `backend/requirements*.txt`. Proven UPSTREAM five independent ways: an earlier main run resolved the same files with zero rpc errors · the manifests are byte-identical since (`git diff --quiet`) · **osv-scanner 2.4.0 fails identically** · CI hit it at 04:29Z *before* any local probing · ~25 local probes over 90 min all 127. No in-repo fix exists (`--no-resolve` is CLI-only; the 2.3.8 config schema is only `IgnoredVulns`/`PackageOverrides`/`GoVersionOverride`). Agent correctly did NOT merge #663 and did NOT close the dependabot PRs. I re-ran the failed job at ~09:00Z to test recovery.
- **Load path proven:** `reusable-quality.yml` runs `osv-scanner scan source --config=osv-scanner.toml --recursive .` — an explicit `--config`, so ONE root file governs `frontend/package-lock.json` too. (`steps.detect` gates the whole step on `file_exists osv-scanner.toml` — the file must be at repo root.)
- **Correction to the inherited count: there are 5 dependabot PRs, not 4.** #659/#660/#661/#662 verified SUPERSEDED (lockfile path+version comparison, not titles) but only **conditional on #663 merging**, so closing now would be wrong. **#651** (backend pip) is **NOT superseded** — main has zero changes to `backend/requirements*.txt`; needs `update-branch` + a fresh run.

## CORRECTION TO SOMETHING I STATED AS FACT
I wrote that "GitHub's own Dependabot auto-dismissed GHSA-mh99 as scope=development" as general corroboration for the ignore decision. **That was a pbinfo observation that I over-generalised.** In momentstudio the advisory has **no alert at all yet**. What IS measured there: 5 auto-dismissed alerts, all `scope=development`, and 22 osv − 5 = **17** = the exact open-alert count — so the *mechanism* is live, but applying it to this specific GHSA in this repo is a **prediction, not an observation**. Corroboration for the ignore decision stands for pbinfo; it is weaker elsewhere.

## FLEET-WIDE PLATFORM DEFECT FOUND → fix dispatched (aef7a515e08616250)
`quality-zero-platform`'s `gate-deps` treats **any** non-0/128 exit as "vulnerabilities found", so a **third-party outage renders as a security regression** in every consumer repo. False alarm today; alarm-fatigue risk tomorrow (an operator who learns the gate lies stops reading it). Fix must: keep FAILING on a real vulnerability, report a scan-infrastructure failure distinguishably (`ERROR … this is NOT a vulnerability finding`), consider a bounded retry for the transient class, and be BOTH-STATES demonstrated. PR only — shared infra, owner reviews. Caveat briefed: this repo's own CI has 4-5 permanently-red checks from missing secrets, so a main-branch control is required before blaming the change.

## Also disclosed (momentstudio, not fixed)
`npm ci` fails `Missing: chokidar@5.0.0` **identically on main before the pins** (5 occurrences in both logs) — masked because the gate runs `{ npm ci || npm install; }`. Root cause: lockfile written by npm 11, CI runs npm 10, differing nested placement for `@angular-devkit/core`'s `chokidar ^5.0.0` peer. Pre-existing; separate follow-up.


## ralph-orchestrator 26→15 alerts · design-extract 34→5 (verified by me, paginated)
**STRUCTURAL FINDING — both are FORKS with genuinely ZERO CI.** Verified myself: `isFork=true` (ralph parent = `mikeyobrien/ralph-orchestrator`), **6 workflow FILES on ralph's main / 1 on design-extract's, but `/actions/workflows` registers ONLY "Dependabot Updates"** — GitHub never registered fork workflows. Every PR head has **0 check-runs**; `main` unprotected (404). So every merge in these repos is **UNVERIFIED-NO-CI by construction**, and the agent labelled each one that way instead of calling it green. *Lesson: `.github/workflows/*` existing ≠ CI running. Check `/actions/workflows`, not the file tree.*
- **ralph:** #8 + #10 MERGED (UNVERIFIED-NO-CI, closes 11). #9 closed superseded — and it **silently carried `vitest ^3.2.6→^4.1.10` MAJOR** behind a body declaring only a subset. #6/#3 closed after per-package verification: both close **ZERO** alerts (their vite/fast-uri sit BELOW the patched floors) and **#3 would REGRESS `yaml` 2.9.0→2.8.4 and `rollup` 4.61.1→4.60.2**. Opened #11/#12 (would reach 5 alerts) — left OPEN, self-authored, not self-merged.
- **design-extract:** #7 MERGED (UNVERIFIED-NO-CI) — **closes 29 of 34**. Opened #8 with bounded floors, deliberately NOT merged (edits a manifest; sharp 0.x-minor is npm-breaking → needs a real build). Root cause worth keeping: **Next.js itself freezes them** — `next` requires `postcss 8.4.31` EXACTLY and `sharp ^0.34.5`, and `next@latest` IS the installed 16.2.11, so no lockfile regen can reach those floors; only an `overrides` block can.
- **`uv` dependabot job CONCLUDES FAILURE** in ralph (run 30147056766) — that is WHY its uv.lock alerts have no PR. **Same shape as ToolUniverse's uv updater going silent since 2026-05-06.** Two repos, one broken ecosystem updater → worth a single diagnosis.
- **Detector correction the agent owed:** it first called an esbuild alert "likely stale" because the ROOT `esbuild` is 0.25.12; scanning **all** lockfile copies found a vulnerable nested `0.18.20`. **A single-path lockfile read under-reports** — scan every copy.
- Upstream-blocked (no downstream fix): esbuild via `drizzle-kit@latest` → deprecated `@esbuild-kit/esm-loader` → esbuild 0.18.20; `serde_with` pinned by `teloxide-core`; `@hono/node-server` needs 2.0.5 major but `@modelcontextprotocol/sdk@latest` still declares `^1.19.9`.

## OWNER CALL I declined to make: enabling Actions on the 2 forks
The obvious "fix" for no-CI is enabling Actions — **I did NOT do it.** Those workflow files are **upstream-authored**, so enabling them runs third-party CI on the owner's runners inside the owner's secrets scope (the same untrusted-auto-load class as CVE-2026-47751), and ralph's `claude-code-review.yml` would consume the owner's Claude quota. Real security tradeoff → owner decides. The durable fix is enabling Actions, NOT adding workflow files (they already exist).


## ToolUniverse 276 → 9 alerts (VERIFIED BY ME, paginated) — the campaign's largest single result
PRs **#25** (uv.lock, +1464/−929, closed 139/147 incl. 3 critical + 57 high) and **#26** (the 4 `remote/*/requirements.txt`, closed all 128) both MERGED; main green at `2abba955` with `841 passed, 15 skipped`. 267 alerts closed (96.7%).
**Residual 9, all owner decisions not oversights:** `smolagents` ×3 (1 **CRITICAL**, 2 low) + `biopython` ×1 → **no patched version exists**; `transformers` ×3 (2 high) → needs `huggingface-hub 0→1` major; `setuptools` ×2 → needs 83.0.0 but **PR #25's own `<81.0.0` bound blocks it** (self-inflicted; follow-up dispatched aea965a8b4098764c).

### Durable lessons
1. **Measure blanket vs targeted before choosing.** A blanket `uv lock --upgrade` closed 3 MORE alerts but produced **85 majors (74 closing nothing)**, **3 silent DOWNGRADES** (`numba 0.63.1→0.53.1`, `llvmlite 0.46→0.36`, `pynndescent 0.6.0→0.5.13`), `pandas 2→3`, `openai 1→2`, and a **CUDA 12→13** swap. Shipped `--upgrade-package` × 34 advisory packages instead.
2. **"Cappers" — a direct dep can pin a transitive below its patched version.** `fastapi` pinned `starlette<0.48` (blocking 3 HIGH); `sentence-transformers` pinned `transformers<5`; `markitdown` pinned `mammoth~=1.10`. You must bump the CAPPER to reach the fix.
3. **A manifest can already be UNSATISFIABLE before you touch it.** main's 4 requirements.txt had **5 contradictions** (`langchain==1.3.14` needs `langchain-core>=1.4.9` vs pinned `0.3.51`, etc.) — caused by Dependabot's own per-package bumps. `uv pip compile` rejected them outright. So `langchain-community` could never be fixed by a one-line bump; it took finishing the 1.x migration. 5 → 0.
4. **`h11` couldn't be fixed alone** — `httpcore==1.0.7` declares `h11<0.15`, so the patched `h11==0.16.0` beside it is unsatisfiable. Co-bump the constrainer.
5. **THE npm RULE DOES NOT TRANSFER TO PYTHON.** My "never exact-pin, it blinds dependabot" instruction is **npm-specific** — Dependabot demonstrably bumps `==` pins in these Python files (#22/#23 merged, #12 open). The agent deliberately kept `==` to match the fully-frozen convention and applied the *intent* only where it mattered (`marshmallow` bounded). Correct deviation.
6. **`marshmallow` has TWO vulnerable ranges** (`<3.26.2` AND `>=4.0.0,<4.1.2`) — an unbounded `>=3.26.2` floor lands back on a vulnerable version. Always read the full range set.
7. **CI validated NEITHER shipped artifact** — `tests.yml` runs `uv pip install -e .[dev] --system`, never consuming `uv.lock` nor installing the remote requirements. Green CI meant "declared deps still work", not "the artifacts we shipped work". Compensated with `uv lock --check`, `uv pip compile` on all 4 files, and both-states controls (baseline FAILS, so the probe discriminates). *Know what your green actually covers.*
8. **The agent's own checker failed twice and it caught both**: a GitHub range `= 0.6.1` is not valid PEP 440 (misclassified `pyasn1`), and a pin-graph walk can't see edges through *unpinned* packages (missed `langchain→langgraph→orjson`). uv's resolver was the stronger signal.

### THE SELF-BLOCKING DEPENDABOT LOOP (premise REFUTED + real root cause)
"The uv updater went quiet since 2026-05-06" is **FALSE** — it ran today 05:54 (`job_1480869903`) and SUCCEEDED. Its own log: `Detected existing pull request # for the dependency group 'uv'` → `Deferring creation of a new pull request` → `Marking group 'uv' as handled`. **PR #1** (open since 2026-04-28, CONFLICTING/DIRTY) is the claimed group PR: its existence suppresses new PRs, its conflict prevents it ever carrying fixes. **The `pip` group logged the identical deferral to #12**, so that stream just entered the same trap. No `.github/dependabot.yml`; `dependabot_security_updates` enabled ⇒ GitHub-default grouping.
**Rule: a conflicted grouped-Dependabot PR silently freezes its entire update stream.** Check the updater's log for `Deferring creation` before concluding an updater is broken or a repo is current.


## mcp-funnel — 137 alerts, and "merge NOTHING" was the correct outcome
**STEP 0: no CI at all.** No `.github/workflows/` (404 on `develop`; upstream has none either); only the auto-generated "Dependabot Updates" — all 65 Actions runs ever are that one workflow. **`main` DOES NOT EXIST** (`branches/main/protection` → 404 *"Branch not found"*); default is **`develop`**, unprotected ⇒ zero required checks. The per-PR check-runs that DO exist (3-4, all success) are `Socket Security` ×2, `semgrep`, `cubic`, `qlty check/fmt` — supply-chain/SAST/lint only; **none compiles TS or runs vitest** although the repo has both. The agent's own PR #7 is `CLEAN` with **0 check-runs** — CLEAN proven meaningless here.
**So it BUILT the missing signal locally** (node 24.16.0, yarn 4.9.2) against a measured baseline of `develop` — **which is itself RED: 27 tests / 16 files already failing** (some Windows path/keychain). Without that control every PR result would have been misread. Usable criterion becomes *no NEW failures vs baseline*, not "tests pass".

**ALL FOUR dependabot PRs BREAK THE BUILD** — #1/#5/#6 via `@modelcontextprotocol/sdk` 1.26+ (`CallToolResult.content` no longer exposes `.text`; `tsc` fails in `command-ts-validate`, which others depend on); #4 via vitest-4 mock types. **Zero merges was therefore correct**, not conservatism.
- **#5 CLOSED** — exactly equivalent to #6 (symmetric difference EMPTY in both directions, 92 alerts each) while adding two major runtime bumps, one of which (`@hono/node-server ^2.0.4`) is **STILL vulnerable** to GHSA-frvp-7c67-39w9 (needs 2.0.5). #1/#4 deliberately NOT closed — they fix `glob`/`js-yaml` that #6 misses.
- **PR #7 opened** (lockfile-only, within declared ranges, cannot cross a major, no exact pins): closes **109 alerts incl. BOTH criticals** — `@react-router/node`→7.18.1 (GHSA-9583, **which no dependabot PR closes**, because `@react-router/dev`/`serve` at `^7.9.1` transitively pin 7.9.1) and `vitest`→3.2.7. install+build pass; 24 test failures = **0 new vs baseline**. Also found `uuid` patched at 13.0.1 and `undici` at 6.27.0 **inside existing ranges** — so the PRs' 13→14 and 6→8 majors are unnecessary; and Express 4.22.2 relaxes its exact `qs`/`path-to-regexp` pins, clearing 4 more.
- **It refused to self-merge #7** (own change + no CI gate). Correct — matches the owner's never-self-certify rule. → dispatched an INDEPENDENT verifier (a759e7d1a6aecf938) to re-measure the baseline and the PR itself, merge only if it confirms, plus add the missing minimal CI gate (install+build only — NOT test, since the baseline is red and a red-on-arrival gate gets ignored).
- **Alerts 137 → 137** (nothing merged). Honest reporting of no movement.

### LATENT LANDMINE (worth acting on independently)
`@modelcontextprotocol/sdk` is declared `^1.18.0`, which **already permits 1.29.x** — so **any lockfile-less install breaks the build TODAY**, no dependabot PR required. Fixing needs a *source* change at 4 `.text` sites (`autofix.test.ts:53,76`, `compact-output.test.ts:52,72`).

### Owner calls (residual 28 after #7)
`@anthropic-ai/claude-code` 1.0.128→2.x = **24 alerts** (major, devDep) · `@modelcontextprotocol/sdk`→1.24/1.26 = 2 (needs the source fix above) · `@hono/node-server`→≥2.0.5 = 2 (major, runtime) · PR **#3** adds `.codex/config.toml` (`sandbox_mode=workspace-write`, 5 `npx` MCP servers) + `.claude/` into the tree — auto-loading agent config (AGENTS.md §9), and the ECC App was already uninstalled. Left alone.

**The real defect here is not dependency lag — it is that green checks cannot catch a broken build.**


## Small-repo sweep: 15 → 8 open PRs, 10 → 3 alerts
| repo | PRs | alerts | outcome |
|---|---|---|---|
| **Airline-Reservations-System** | 4 → **0** | 3 → **0** | opened #89 (bounded floors + `glob>=11.1.0<12` unifying the chain) → merged; #87/#88/#90 rebased → merged; #85/#86 **closed by dependabot itself**. main `3b1c8fae` **success**; `npm ci` exit 0, coverage **100%** stmts/branch/funcs/lines |
| **SWFOC-Mod-Menu** | 3 → **0** | 4 → **0** | opened #197 → merged `c2db63aa` (**success**); #192/#195/#196 closed superseded, **content-verified against merged main** |
| **WebCoder** | 4 → 4 | 3 → 3 | all four unique/disjoint, none superseded — owner call |
| **Personal-Finance-Management** | 2 → 2 | 0 | #52 BROKEN (diagnosed), #48 owner call |
| **ai-sessions-render** | 2 → 2 | 0 | #12 BROKEN (diagnosed), #4 owner call |

### DETECTOR CORRECTION — a 404 on `/branches/main/protection` does NOT mean "ungated"
Modern **rulesets** are a separate API. Verified by me:
- **Airline / SWFOC** → classic protection **404** BUT `gh api repos/<r>/rulesets` returns active rulesets (`CodeQL security red-blocker (any severity)`, `quality…`), **strict** ⇒ genuinely gated.
- **ralph-orchestrator / design-extract / mcp-funnel** → 404 **AND empty rulesets** ⇒ genuinely ungated. My earlier "no required checks" calls for those three **hold**, because they rested on zero check-runs per PR head, not on the 404 alone.
**Rule: check BOTH `/branches/<b>/protection` AND `/rulesets` before concluding a branch is ungated.**

### Two self-caught errors from that sweep (both high-value)
1. **A green osv gate hid a runtime break.** Its first #197 push forced `brace-expansion` 5.0.8 and **quality PASSED** — but 5.x exports `{expand}` with no callable default, so minimatch 3.x/9.x throw `TypeError: expand is not a function`; it broke Airline's coverage provider outright. Caught **before merge**. Real fix = move consumers UP (SWFOC: drop the `fork-ts-checker`→minimatch chain, **343→113 packages**; Airline: floor `glob` at 11 → minimatch 10). No suppressions — respecting SWFOC's `CLAUDE.md` Iron Law.
2. **The deps.dev outage is fleet-wide and intermittent.** SWFOC main's first post-merge quality run showed **failure**, and it correctly did NOT report a regression: log = `Total 0 packages affected by 0 known vulnerabilities` + `exited 127` — the same RPC outage. Re-run → **success**. Independent confirmation of the momentstudio diagnosis, and exactly what PR #279 relabels.

### WebCoder — "green" that means nothing
main's quality green is **commit `477b7aec` from 2026-06-27 — stale-green, predating all 25 current advisories**. Also `npm ci` is broken **on main itself** (reproduced on a clean clone): `Invalid: lock file's ws@7.5.11 does not satisfy ws@7.5.13` (a `^7.5.11` override drifted). And `react-router-dom` GHSA-jjmj has **no patched 6.x** (`last_affected: 6.30.4`; fix only in react-router **7.13.0**) ⇒ a v6→v7 major migration. The agent deliberately opened **no** PR there: it could not merge and would only add clutter. Correct restraint.
Other diagnoses: **PFM #52** — AGP `9.2.1→9.3.0` lint calls `List.removeLast()` (Java 21, JEP 431) while `verify.yml:22` pins `java-version: '17'` → `NoSuchMethodError`; note `verify` is *not* a required context so it is technically mergeable and should not be. **ai-sessions #12** — not a patch bump at all: `typescript ^5.7.2→^7.0.2` + `@types/node ^22→^26`, hence mass `TS2591`/`TS2584`.


## momentstudio LANDED (07:48Z) — the deps.dev outage cleared on attempt 4
Attempt 4 of run 30144541486: `conclusion=success`, log `Filtered 2 vulnerabilities` → **`PASS gate-deps: osv-scanner found 0 actionable CVEs.`** So the blocker really was a transient third-party outage (~3h+, spanning attempts 2-3), exactly as diagnosed — not a defect in the fix.
- **#663 MERGED** (two-signal: `OPEN mergeable=MERGEABLE CLEAN draft=false` + zero non-pass checks).
- **#659/#660/#661/#662 CLOSED as superseded — re-verified post-merge against RESOLVED LOCKFILE VERSIONS, not titles.** My first check nearly under-verified: a plain grep for `fast-uri` found nothing because the override key is **`fast-uri@^3`** (and `fast-uri@^4` for the second nested copy); and `postcss = $postcss` is a deliberate **indirection to the declared devDep** (because the flagged copy was the NESTED `@angular-devkit/build-angular` one) which resolves to **8.5.23**. Evidence per PR: fast-uri resolved **3.1.4** · fast-xml-parser override **^5.10.1** · find-my-way override **^9.7.0** · postcss resolved **8.5.23** (target was 8.5.20).
- **#651 NOT superseded** (#663 touched only `frontend/`; #651 targets `backend/requirements*.txt`) → commented + `update-branch` to re-run against the now-green gate.
- **Alerts 17 → 0.** Remaining open PRs are #650/#625/#624 — substantive feature work (admin decompose, frontend 100% coverage, reconcile), NOT dependabot and NOT part of this campaign. Left untouched.

### Lesson: an override KEY may not equal the package name
`fast-uri@^3` / `fast-uri@^4` (per-major keys) and `postcss = $postcss` (npm's reference-to-declared-dep syntax) both defeat a naive `grep <package>` over `overrides`. **Verify supersession from the RESOLVED version in the lockfile, never from the override key or the PR title.**


## ToolUniverse COMPLETE: 276 → 3 alerts (0 critical), 14 → 1 open PR
**The CVSS 10.0 RCE is CLOSED.** Alert #299 `GHSA-q9r5-6hrr-9ph7` / CVE-2025-14931, **cvss=10**, `state=fixed fixed_at=2026-07-25T08:02:01Z` — verified by me. It had been sitting open because **I wrongly called it unfixable** from `first_patched_version: null`. Two minor bumps closed it plus 3 siblings: `smolagents 1.22.0→1.26.0`, `biopython 1.86→1.87` (PR #28 `e284c48a`). No majors, no downgrades, 362 resolved before and after; `huggingface-hub` stayed **0.34.4** (smolagents 1.26.0 only needs `>=0.31.2`, so the feared 0→1 never happened). CI `841 passed, 15 skipped` — exact baseline match.
**Remaining 3** (all `transformers`, 0 critical): #465 needs 5.5.0, #449 needs 5.3.0, #279 needs 5.0.0rc3.

### PR #1 CLOSED — breaking the dependabot deadlock
Verified before closing (my first probe was WRONG — I grepped `pkg==version` against a **uv.lock TOML** file and got a false empty; re-probed with `name = "transformers"`):
- It carried `transformers 4.56.1 → **5.0.0rc3**` — which closes only the **medium** #279, and reaches **neither HIGH** (5.3.0 / 5.5.0).
- Its other unique item, `biopython 1.87`, already landed via #28.
- It was `DIRTY`, dated 2026-04-28, ~90 packages behind main — merging would **downgrade** `aiohttp 3.14.3→3.13.4`, `idna 3.18→3.10`, `cryptography 49→46` and drop `cuda-*`/`fastmcp-slim` (main's current values verified: aiohttp 3.14.3, idna 3.18).
- **Deciding factor:** while it stayed open, Dependabot's uv group logged `Deferring creation of a new pull request` against it — so no fresh uv PR could ever be cut, and being conflicted it could never carry the fixes itself. Closing releases the group to cut a fresh PR from current main carrying transformers ≥5.5.0.
Only #4 remains (abandoned ECC bundle, commits auto-loading `.claude/`/`.codex/` config — owner call).

### Lesson: match the probe to the FILE FORMAT
A `grep '^[+-].*pkg=='` over a **uv.lock** (TOML: `name = "x"` / `version = "y"`) returns empty and reads as "this PR doesn't touch it". I nearly concluded PR #1 had no transformers content on that basis. **A format-mismatched grep produces a false ABSENCE, which is the most dangerous kind of detector failure** — it looks like evidence.