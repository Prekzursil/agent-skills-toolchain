---
title: Session learnings 2026-07-25 (CSIE build + fleet campaign)
type: note
permalink: main/reference/session-learnings-2026-07-25-csie-build-fleet-campaign
tags:
- learnings
- detector-failure
- overclaim
- osv-scanner
- subagent-driven
- honesty
---

# Session learnings 2026-07-25 — CSIE foundation build + fleet quality campaign

Durable, generalizable lessons from a long autonomous `/loop` session (~30 agents, 3 tracks). Repo-specific state lives in [[consolidation-fleet-csie-checkpoint-2026-07-24b]] and [[fleet-triage-plan-2026-07-25-wf-081e0b4a-3bc]].

## 1. The C2 overclaim pattern hit SIX times — it is the dominant defect class
Every single one: **the code was correct and the SENTENCE was wider than the evidence.** Not one was a broken fix.
- "exactly ONE gate implementation" (false — a second impl was live in 2 call sites)
- "over-matching can make the verdict stricter, never greener" (false — a spurious green key flips `bool(platforms)`)
- "hardened workflow-path guard" (false — a `str` input bypassed it entirely)
- "neutralize … BEFORE any backend runs an agent/CI in the tree" (false — depth-0 only; `conftest.py` still auto-executes)
- "reason survives in `Result.reason`" (false — the Result is a discarded temporary)
- plan exit criterion "creates or modifies" (false — modified files still fail format)
**Rule that works:** fix the SENTENCE, quote the refuted wording, label it REFUTED, never silently delete. Scope claims to the path actually measured ("on the run_E production path", not repo-wide).

## 2. My own worst error: I verified the WRONG ARTIFACT
Task 8's fix was "doc-only"; I verified the three corrections were present **in the implementer's report** and marked it complete. The false claims lived in **shipped code** (a docstring + two test comments), in four places. The whole-branch review caught it.
**Rule:** when a fix corrects a CLAIM, grep for that claim in the SHIPPED ARTIFACT (code/docstrings), not in the report describing the fix.

## 3. Detector failures were everywhere — ~10 caught, most by the agents themselves
- `git archive` applies the CRLF smudge filter → an LF-verification probe reads CRLF and its green is meaningless. Use `git cat-file -p`, or `git -c core.autocrlf=false archive` with a `CR:0` control.
- `gh api repos/X/commits/main/status` returns `state: pending` with `contexts: []` when the repo reports via **check-runs**, not legacy statuses. That is "no statuses exist", NOT "checks pending". Use `commits/<ref>/check-runs`. (This one was mine.)
- `gh run view --log` can silently return **0 lines with exit 0**. Use `gh api repos/.../actions/jobs/<id>/logs`.
- `grep -c pattern || echo 0` — `grep -c` prints 0 AND exits 1, so the `||` also fires → `"0\n0"`.
- A mutation anchor matched a docstring **mention** instead of the compiled pattern (use-vs-mention), making a real mutant look like a survivor.
- `npm ci --dry-run` passed on the OLD lockfile too → the probe measured nothing (both-states rule).
- MSYS-bash `/tmp` and Windows-Python `/tmp` are **different directories** — a script wrote JSON one place and read it from another, returning empty forever.
- Searching for a vendored repo by its REPO NAME misses content vendored under RENAMED skill paths (`ghostwriter` → `voice-*`). Search by content/capability.
**The habit that saved it every time:** validate the probe against the KNOWN-BAD state before trusting its silence.

## 4. osv-scanner config: an unknown key silently voids the whole file
`internal/config/config.go` `tryLoadConfig` **rejects the entire file on ANY unknown key** and then **falls back to an empty config with no error**. Valid keys in `[[IgnoredVulns]]` are exactly `id`, `ignoreUntil`, `reason` (bare TOML date, unquoted). A helpful-looking extra field disables the ignore invisibly.
**Rule:** verify a config schema against the tool's SOURCE, and both-states test the config (run with it, then with it moved aside — the exit codes must differ).

## 5. A required "all-clean" scanner gate + subset-fixing dependabot PRs = structural deadlock
If the gate only passes when EVERY package is clean and each PR fixes a subset, **no PR can ever merge individually**. Detect it by reading branch protection, not by retrying merges. Exits: one comprehensive commit, or relax the gate. (Cost: an agent burned a full run discovering this by attempting merges.)

## 6. Advisory counts are timestamped facts, not stable ones
A count differing from a brief is often **DB drift** (new CVEs published between runs), not a regression. Compare the affected-package SET and check the advisory's publish time. One advisory published mid-campaign invalidated three separate briefed pin-sets.

## 7. Parallel committers in ONE worktree: use pathspec commits
`git commit -m "..." -- <paths>` commits only those paths regardless of index state. With that, two concurrent implementers in the same worktree stayed perfectly disjoint (verified per-commit). A bare `git commit` would have swept the sibling's staged work.

## 8. Blanket rules need an escape hatch for the case they weren't written for
I told agents "add no osv ignore entries" — correct when fixes exist, wrong for a genuinely unfixable advisory. Holding it would have left a **CVSS 9.2 Critical unfixed** to avoid an unfixable dev-only ReDoS. Overrode it narrowly (single GHSA, dated, justified), and **GitHub's own Dependabot independently auto-dismissed the same advisory as `scope=development`** — corroboration from a different system.
**Rule:** when a self-imposed constraint blocks a strictly better outcome, name the constraint, state why it doesn't apply, and record the override for review — don't silently keep or silently break it.

## 9. Good agents correct their orchestrator — design for it
Agents caught: a bug in a fix *I* proposed (my regex would have collapsed to a family key I'd forbidden), a wrong version in my brief (0.15.18 was never CI-green; 0.15.21 was), a missing package in my pin set, three rows my brief said to add that were already pinned to the VULNERABLE version, and a gap in the *reviewer's* own evidence. Briefs should invite this explicitly ("re-verify before relying on it; REFUTED with evidence is a success").

## 10. "0 Dependabot alerts" ≠ "the scanner gate passes"
Different systems: osv-scanner reads lockfiles directly; Dependabot alerts are GitHub's own analysis with its own scope rules. One repo showed 0 alerts while its osv gate was red.


## 11. A drift warning can point you at the WRONG sync direction — check which side is correct first
After merging PR #203 (skill provenance + humanizer port) the git-hygiene hook reported **49 skill files drifted** and recommended `sync-from-live.ps1 -Drift`, which syncs **live → repo**. Running it would have **reverted the merged fix**: live `~/.agents/skills/voice-*/SKILL.md` still carried the FALSE `upstream_author: Prekzursil (ghostwriter)` while the repo had the corrected `angelarose210`; live humanizer had 30 patterns vs the repo's 33.
**The drift was real but the arrow was backwards** — the repo had moved forward, not the live tree. Did a targeted **repo → live** sync of exactly the 5 changed files instead (verified after: live now `angelarose210`, 33 patterns).
**Rule:** when a sync tool reports drift, establish WHICH SIDE IS AUTHORITATIVE before syncing. If you just merged a change into the repo, the repo is newer and a live→repo sync will silently revert your work. Also: don't leave `.bak` files inside a synced tree — a later sync can sweep them into the repo; git is already the backup.

## 12. `.github/workflows/*` existing ≠ CI running
`ralph-orchestrator` has **6 workflow files** on main with `pull_request` triggers, and `design-extract` has 1 — but `GET /actions/workflows` returns **only "Dependabot Updates"** for both, because GitHub does not register workflows on a **fork**. Every PR head: **0 check-runs**. So `mergeStateStatus: CLEAN` there certifies nothing and every merge is UNVERIFIED-NO-CI by construction.
**Rule:** to know whether CI exists, query `/actions/workflows` and the head commit's `check-runs` — never infer it from the presence of workflow files.

## 13. A single-path lockfile read under-reports vulnerabilities
An agent judged an esbuild advisory "likely stale" because the ROOT `esbuild` was 0.25.12 — then scanning **every** lockfile copy found a vulnerable nested `0.18.20` (pulled by `drizzle-kit@latest` → deprecated `@esbuild-kit/esm-loader`). Same shape as momentstudio, where the flagged `postcss` was the NESTED `@angular-devkit/build-angular` copy, not the top-level one a bump would touch.
**Rule:** resolve the advisory against every copy in the tree, not the first match.

## 14. A PR body can under-declare what the diff actually does
`ralph-orchestrator#9` declared only a subset of #8 in its body while **silently carrying `vitest ^3.2.6 → ^4.1.10`, a MAJOR**. And `#3` would have *regressed* `yaml` 2.9.0→2.8.4 and `rollup` 4.61.1→4.60.2 while closing **zero** alerts.
**Rule:** classify a dependency PR from its manifest/lockfile diff, never from its title or body.


## 15. A dependency upgrade can INTRODUCE a vulnerability the alert list cannot yet see
`mcp-funnel` PR #7 (lockfile-only, within declared ranges) closed **109 of 137** alerts including both criticals — and moved `react-router` **7.9.1 → 7.18.1**, which is inside `GHSA-qwww-vcr4-c8h2` (HIGH, `>=7.12.0 <8.3.0`, published 2026-07-24T16:44Z). Pre-merge **safe**, post-merge **vulnerable**. It surfaced as alert **#177 about 20 seconds after the merge** — the repo's Dependabot list lagged the global advisory DB, so *no pre-merge analysis could have caught it*.
**Rule:** "moves every package forward within its declared range" does NOT imply "strictly safer". Before merging a bulk re-resolution, check each **upgraded** version against the *global* advisory DB (OSV/GHSA), not just the repo's own alert list — the repo list is a lagging index. And `first_patched` may be a MAJOR (8.3.0 here), unreachable from the declared range, so the only within-range escape can be to stay BELOW the vulnerable floor (7.11.x) rather than above it.

## 16. Sample a flaky suite TWICE before crediting a change with fixing anything
The first agent measured `develop` once (~27 failures) and reported PR #7 as fixing 2 tests. The independent verifier ran it twice — **run1: 25 failed/15 files, run2: 30 failed/19 files → 23 deterministic + 9 flaky** — and showed PR #7's 23 failures are **set-equal** to the deterministic baseline. **The "2 fixes" were flakes, not fixes.**
**Rule:** on a red/flaky baseline, compare failure SETS across ≥2 runs, never counts from a single run. A single sample cannot distinguish a fix from a lucky flake — and "it fails less" is not "it fixes something".

## 17. Independent verification is worth its cost — it changed two conclusions
The verifier was told refuting the original agent counted as success. It (a) caught the flake-vs-fix error above and (b) surfaced the introduced HIGH. Both were invisible to the authoring agent, which had correctly refused to self-certify. The owner's never-self-certify rule paid for itself here in one run.


## 18. `first_patched_version: null` does NOT mean "unfixable" — I reported that as fact and was WRONG
It means **the advisory names no patch release**, not that no safe version exists. I relayed "smolagents (incl. a CRITICAL) and biopython have no patch published" as a conclusion. Refuted by testing latest PyPI against each `vulnerable_version_range`: **0 of 7 remaining ToolUniverse alerts genuinely lacked a safe release.**
- smolagents: ranges `<=1.23.0` / `<=1.24.0` / `<=1.25.0.dev0`, all `patched=NULL` — **1.26.0 exists** and clears all three. `pyproject` declares `smolagents>=1.22.0`, **unbounded** ⇒ only the lockfile held it back.
- biopython: `<= 1.86`, `patched=NULL` — **1.87 exists**, `biopython>=1.80` unbounded.
**Rule: never treat `first_patched_version: null` as terminal. Resolve the vulnerable RANGE against the registry's current releases** — the advisory's metadata and the registry's reality are different sources. (Contrast the genuinely-unfixable `GHSA-mh99` brace-expansion case: there the only fix `5.0.8` was a breaking major AND the 1.x/2.x lines had no backport — that was verified by checking npm dist-tags, not by trusting a null field.)

## 19. Two more premise-refutations worth the pattern
- **"The uv updater went quiet"** → refuted: it runs and SUCCEEDS, but logs `Detected existing pull request … Deferring creation` because a **conflicted grouped PR** claims the group forever. A conflicted grouped-Dependabot PR silently freezes its whole update stream.
- **"All 11 DIRTY PRs are redundant regenerations"** (mine) → refuted: `main` satisfied **none** of the 18 advisories they carried; closing them would have discarded a critical fix.
**Meta-rule: state briefing premises as hypotheses to be tested, and explicitly authorise the agent to refute them.** Six briefs this session contained at least one materially wrong premise; every one was caught only because refutation was framed as success.

## 20. A 404 from a probe is a DETECTOR failure, not a verdict
Asked to confirm a Dependabot loop had broken, an agent found `dependabot/update_jobs` → 404 while a control `gh api repos/...` → 200, and correctly reported **"loop break NOT OBSERVED"** rather than inferring either outcome. It also noted a second reason the absence of new PRs proved nothing: zero of the remaining alerts were in that group's scope, so it had nothing to create regardless.
**Rule: distinguish "I measured X" from "my instrument could not measure" — and when an absence has two possible causes, name both.**


## 21. CORRECTION TO #15 — I over-reported the regression AND my proposed fix would have made it worse
Learning #15 said mcp-funnel PR #7 "introduced a HIGH". **Narrowly true, materially misleading.** Verified alert history: **11 react-router alerts FIXED** by that PR (1 critical + 6 high + 4 medium) and **1 opened** (#177). react-router went **12 vulnerabilities → 1**. I reported the single regression and omitted the eleven it replaced.
**Worse: my proposed remedy was a regression.** I proposed pinning `7.11.0` (satisfies `^7.9.1`, ≥7.9.4 keeps the critical closed, <7.12.0 dodges GHSA-qwww). All three claims verified TRUE — but the **unstated fourth premise failed**: there are **11** react-router-family advisories, not 2, and 7.11.0 sits inside **9** of them. It would have turned 1 open alert into **10**.
An OSV sweep of all 22 stable releases ≥7.9.1: `7.9.1–7.10.1` = 13 vulns · **`7.11.0` = 14, the WORST of the line** · `7.15.0–7.17.0` = 5–6 · **`7.18.0/7.18.1` = 1** · `8.3.0` = 0. **No clean version exists inside `^7.9.1`; 7.18.1 is the optimum.** The agent shipped nothing and posted the analysis instead — correct.
**Rules:**
- When reporting that a change introduced a vulnerability, **report the net** — count what it closed as well. A single-advisory view of a bulk upgrade is not a verdict.
- Before proposing a "safe version", enumerate **every** advisory affecting that package family and check the candidate against **all** of them. Verifying 3 true claims while missing a 4th premise is how a remedy becomes a regression.
- `first_patched` may sit outside the declared range (here 8.3.0 = a major needing React 18→19 + Vite 6→7 as well) — then the honest answer is "no in-range fix exists; here is the migration cost", not a pin that trades advisories.

## 22. Reachability can matter more than severity — but it is the owner's call
#177 is HIGH yet likely **unreachable**: the advisory affects only unstable RSC APIs, and the app is SPA mode (`ssr: false`) with zero RSC usage. The agent **control-tested its own matcher** (same pattern set finds 6 `react-router` hits in those paths, so a zero-hit RSC result is meaningful, not a broken grep) and recommended `dismiss as not_used` — **without doing it**. Dismissing a HIGH is a human decision.
**Rule: an agent may establish and argue unreachability; it must not act on it.**