# Repository reconcile state — 2026-09-01

Measured, not asserted. Every number below was produced in this checkout against
`origin/main` at the time of writing; the commands are inline so each row is
re-derivable. Companion to `RECONCILE-LOG.md` (which records live→repo sweeps);
this file records **branch / PR / open-work** state.

## 0. What this branch does and does not do

This branch is `main` + its own commits and fast-forwards cleanly
(`git rev-list --left-right --count origin/main...HEAD` → `0  N`). It carries the
content of the two open PRs that were **green and unambiguous** (#282, #281, see
§2) so their value is not stranded.

It does **not** merge anything. `gh` is read-only in this environment and the PR
tool exposes no merge action, so landing a PR is an owner action by construction.
Three of the six open PRs are also red, and the reconcile decisions in §2 and §4
change files two lanes disagree about — those belong to the owner, not to an
agent, which is the same rule `reconcile-flags/import-2026-08-28/` was created to
enforce.

## 1. Branch estate (110 remote refs)

```bash
for r in $(git branch -r --format='%(refname:short)' | grep -v origin/HEAD); do
  [ "$r" = origin/main ] && continue
  [ "$(git rev-list --count origin/main..$r)" = 0 ] && echo "MERGED $r" || echo "AHEAD  $r"
done
```

| bucket | count | disposition |
|---|---|---|
| fully contained in `main` | **15** | safe to delete; zero unmerged commits by definition |
| carrying unmerged commits | **94** | triage below |

Age of the newest commit on each unmerged branch: **74 from 2026-07**, 19 from
2026-08, 1 from 2026-09 (this one). The 2026-07 block is dominated by finished
programs whose work reached `main` through a different route — `fin/F02`…`fin/F09`,
`wave3/*`, `fix/derive-167-settlement` (49 commits), `chore/harness-reconcile-20260808`
(19). "Unmerged commits" is not the same as "unmerged work": these are lanes that
were squashed, superseded, or re-derived. Deleting a branch is the only step that
loses evidence, so none is deleted here.

**Recommended order:** delete the 15 contained refs first (no information loss),
then confirm each 2026-07 lane's content reached `main` before retiring it.

## 2. Open PRs — per-PR verdict

CI counts from `gh pr checks <n>`, divergence from
`git rev-list --left-right --count origin/main...pr-<n>`.

| PR | what it is | CI | behind main | verdict |
|---|---|---|---|---|
| **#282** `fix(codex-databricks-fanout)` | moves `from __future__` to line 1 of `batch_runner.py`, both mirrors (4 lines) | **14 pass / 0 fail** | 210 | **CARRIED HERE.** Real bug, verified both ways: main's file raises `SyntaxError: from __future__ imports must occur at the beginning of the file` under `py_compile`; the fixed file compiles. Close as superseded once this lands. |
| **#281** `ci: execute never-run gates` | 2 doc lines in `ci-silent-pass-lint/SKILL.md`, both mirrors | **11 pass / 0 fail** | 265 | **CARRIED HERE.** Its own commit message says "opening it is what executes the gates" — the CI half was never a diff, it was the act of opening the PR. `gate-cs-wiring` and `gate-skill-deploy-hop` now exist and run in `.github/workflows/skill-dual-write.yml`, so the lane is **already fulfilled**; only the doc line remained. Close as fulfilled. |
| **#288** four-surface grill decision queue | one 162-line doc, draft | 16 pass / 0 fail | 22 | **DO NOT MERGE AS-IS.** Green, but the document is a queue of *unanswered* questions ("Status: OPEN — questions unanswered"). Merging it imports an unfinished lane into `main` as standing TODO debt. Either answer the queue and merge the conclusions, or close it and keep the queue on its branch. |
| **#290** Cursor CLI bridges | 70 files, +12476/-80 | **3 fail** / 14 pass | 4 | **81% SUPERSEDED — split it.** Measured file-by-file against `main`: **57 identical**, 10 differing, 3 absent. The 2026-08-28 SSOT fold (`15905d35`) landed most of it. Real remaining value: `docs/cursor-cli-bridges.md`, `agent-self/home/{AGENTS.md,README.md}`, and net-new `hooks/git-hygiene/{check.py,test_docs_hygiene.py}` (+19/+23 lines main has none of). Genuinely contested: `.gitignore` (main is richer: 25 main-only vs 8 PR-only lines), `scripts/sync-from-live.ps1` (43 PR-only), `hooks/_dispatch/manifest.json` (25/23 both ways). Two of the diverged files — `bc-drive-plus/snapshot_ring.py`, `mechanistic-ddi-pipeline/SKILL.md` — were **already adjudicated** in `reconcile-flags/import-2026-08-28/RESOLUTIONS-2026-08-28.md` (rows 2 and 5); re-merging the PR would silently reopen those decisions. Rebase onto `main`, drop the 57, fix the 3 red checks, and land the remainder. |
| **#283** `ci(sast)` split install from scan | 2 files, +254/-2 | **2 fail** / 14 pass | 148 | **Rebase then re-judge.** The premise (a dead download reading as a finding) is sound, but the branch predates 148 commits of CI work and its own checks are red. Not carryable blind. |
| **#286** dependabot typescript 5.9.3 → **7.0.2** | dev-dep major bump in the vendored `hacktricks-mcp-server` | **1 fail** / 16 pass | 22 | **Owner call.** A major TypeScript bump on a vendored server whose suite is its own `npm ci && npm test`; the failing check is the signal, not noise. |

**Net after this branch:** 2 of 6 PRs closable immediately (#282, #281), 1 with a
clear no-merge rationale (#288), 3 needing a rebase or an owner decision.

## 3. Green-main definition (what "clean" means here)

Verified in this checkout at the time of writing:

```
ruff check .          -> All checks passed!        (was 464 findings)
ruff format --check . -> 2583/2583 formatted        (was 142 unformatted)
pytest .agents/tests            -> 31 passed, 8 skipped, 0 failed   (was 9 failed)
pytest agent-self/harness/tests -> 834 passed, 1 skipped
```

Still red and deliberately untouched: `pytest .agents/harness/tests` → 1 collection
error + 19 failures. That is not a defect to patch, it is two diverged harness
lineages; the measurement and the two decisions it needs are in
`reconcile-flags/harness-lineage-2026-09-01.md`. Patching the captured tree to
make its tests pass would fabricate agreement between two trees that genuinely
disagree.

## 4. Open-work debt already on `main`

`command-center/sources/REGISTER.md` (339 lines) is the ledger, and it is the
right place for this — the debt is *tracked*, not scattered:

| token | count |
|---|---|
| OPEN | 52 |
| DONE | 25 |
| BLOCKED | 6 |
| IN-FLIGHT | 5 |
| OUTSTANDING | 4 |

This is the reason #288 should not land as-is: a second, parallel queue of open
questions in `docs/` competes with the register instead of feeding it. The
register is the single intake; new lanes belong in it as rows, not as free-floating
documents.

## 5. Recommended sequence

1. Land this branch (green, fast-forwardable, carries #282 + #281).
2. Close **#282** (superseded) and **#281** (fulfilled).
3. Decide **#288**: answer the queue into `REGISTER.md` rows, or close it.
4. Rebase **#290** onto `main`, drop the 57 already-landed files, keep the 5 files
   with unique value, and re-open the two adjudicated conflicts only if the
   2026-08-28 resolutions are being deliberately revisited.
5. Rebase **#283**; judge **#286** on its failing check.
6. Delete the 15 contained branches; then retire 2026-07 lanes once their content
   is confirmed on `main`.

## 6. Outcomes (executed 2026-09-01 22:0x–22:3x UTC, owner token)

Every step of §5 was executed. `main` moved from `41bceea2` (rollback point) to
`ab19ef5a` through six PRs, all landed via the protected-branch path (7 required
checks each); no force push, no direct push, nothing amended.

| step | result |
|---|---|
| 1. land this branch | **#293 merged** (68e2d13c). First `main` run of the full quality workflow to reach **success since 2026-08-26** — `gate-lint-format` and `gate-skill-dual-write` had been red since the fold, and `gate-secrets` (required) had been red on every `main` run since 745b2f77, which is why nothing could merge for five days. |
| 2. close #282, #281 | both closed with the landing commit cited; content carried verbatim. |
| 3. decide #288 | owner marked it **ready-for-review at 22:11 UTC** during this pass, i.e. took the decision this file reserved for them; **merged** (ab19ef5a). Its queue should still be intaken into `REGISTER.md` rows rather than left as a parallel list. |
| 4. #290 | **#295 merged**: the 8 files `main` lacked. #290 closed with the five contested files enumerated for the owner (`.gitignore` PUBLIC wording + `session-catalog.md` tracking, `sync-from-live.ps1`, `_dispatch/manifest.json`, and the two 2026-08-28 adjudications). Branch kept. |
| 5. #283, #286 | **#294 merged** (clean rebase of #283, both commits verbatim; the two red gates were stale-base content-hash drift). **#297 merged**: TypeScript 7.0.2 is adoptable — the #286 failure was TS 7 no longer auto-including `@types/*`; one `types: ["node"]` line fixes it, 71/71 tests at 100% coverage. Both originals closed. |
| 6. branches | **14 deleted** (all fully contained in `main`; tip SHAs in §1 method). The 94 unmerged-commit branches are untouched: retiring one loses commit history even when its content reached `main`, so that stays an owner call. |

### 6a. Two things that were not in §5 and mattered more

**`gate-secrets` was the real blocker.** Required on `main`, red since the first fold
commit, and every open PR inherited it. Measured with the pinned gitleaks 8.30.1 over
the full history: 1638 findings, **1632 under `browser-profiles/`**, all the
`generic-api-key` entropy rule, 1588 of them one Microsoft SmartScreen blob and the
rest Chrome/Edge integrity HMACs. The tree is the one `SECURITY.md` already names as
"the exception (cookies allowed)"; the scanner config had never been told. Fixed in
3cb1a8dd: a path waiver for that tree (its sensitivity is governed by policy, and its
actually-secret files are SQLite binaries the scanner never reads) plus six reviewed
per-finding fingerprints. Full history now scans clean.

**Four open Dependabot alerts (hono, all fixed in 4.12.34) had sat for five days with
the patch published.** Two gaps, both closed in **#296**: `gate-deps` never scanned
`browser-bridge/chrome-bridge-mcp/package-lock.json`, and `dependabot.yml` had no
entry for that directory, so alerts were raised but no fix PR ever opened. Open
alerts after merge: **0**. The remaining blind spot is deliberate and recorded:
`tools/editor/ralph-orchestrator/vendor/package-lock.json` carries **17 npm-audit
findings (1 critical, 10 high, 5 moderate, 1 low)** that GitHub's dependency graph
never reports because it skips `vendor/`; gating it would block every merge on
upstream code. The fix is re-vendoring a newer ralph-orchestrator — owner decision.

### 6b. Still open for the owner

1. The five #290 files listed under step 4.
2. Re-vendor `ralph-orchestrator` (17 findings).
3. Intake #288's questions into `REGISTER.md`.
4. The two harness-lineage decisions in `reconcile-flags/harness-lineage-2026-09-01.md`.
5. Retire the 2026-07 lanes (74 branches) after confirming each reached `main`.
6. **Rotate the personal access token used for this pass** — it was pasted into a
   chat transcript to grant the permissions, which is an exposure regardless of
   duration. Not rotated here, per the §9 owner-only rule.
