# Runbook: settle every lane, make main green, make the harness durable

Written 2026-09-24 as the hand-off from the audit in `docs/AUDIT-2026-09-24-sota-transcript-and-lanes.md`. Execute in order; each phase has a done-check. Decisions marked OWNER are made by the owner once and recorded as a decision file (Phase 4a) before anything is deleted, purged or merged. Rules for the executing session: one branch at a time; no new research waves, grills, gem hunts, hooks or skills until Phase 5 exit criteria hold (the 30-day freeze); every deletion is archive-tagged first; every claim of "done" is a command output, not a sentence.

## Phase 0. Owner decisions (one sitting, recorded before Phase 1)

| id | Decision | Default recommended by the audit |
|---|---|---|
| D1 | Rotate the Context7 key in `tools/mcp/workstation-codex-bundle/env/private-env.windows.json`; move the file out of git or git-crypt it | Rotate today; git-crypt |
| D2 | `browser-profiles/` (Chrome/Edge Login Data, Cookies, Web Data): stop tracking, or git-crypt, or keep | Stop tracking; purge history when ready for the force-push |
| D3 | `cyberstrike/memory/*` engagement notes with credential material (gitleaks hit at `cyberstrike/memory/2026-09-03.md:35`, from PR #349) | Move all engagement memory out of this repo; purge |
| D4 | PR #350 (git-crypt removal, but carries a 1,571-file P2 snapshot) | Do not merge; keep git-crypt; take only its osv-scanner ignore block |
| D5 | P2 loop-to-green: continue or stop; if continue, `cursor/p2-loop-to-green-0db0` is the only lineage | Stop the fleet; salvage per Phase 3 |
| D6 | Cyber lanes #318, #319, #322 versus the cyberstrike tree already merged by #349 | Diff first; fold only what #349 lacks |
| D7 | gemhunt/* and #314, #320 decision queue (open since 2026-09-02) | Decide the queue or close it; no new lenses |
| D8 | Codex and Gemini parity as a hard requirement (Gemini CLI sunset 2026-06-18; 206 files still reference it) | Drop Gemini CLI; keep Codex |
| D9 | `permissions.defaultMode: bypassPermissions` in the tracked settings | Switch to auto mode with the sandbox where available |
| D10 | Which 30 to 40 skills form the model-invocable core, per project profile | Owner picks from `/skill-doctor` output after 30 days of telemetry; until then, the ten most used |

## Phase 1. Main green (blocks everything else)

```
git switch main && git pull
ruff check cyberstrike/ --fix            # clears 2 of 11; split the 8 E702 semicolon lines by hand; fix E731, F541
# D3: git rm the engagement note(s) from cyberstrike/memory/ ; record where they went
# D4: add the vendored-vitest ignore block from PR #350 to osv-scanner.toml with its reason
ruff check . && ruff format --check .    # pinned ruff 0.15.17 (pip install ruff==0.15.17)
```
Push, wait for the quality workflow. Done-check: three consecutive green runs of `quality.yml` on main (`gh run list --workflow quality.yml --branch main --limit 3`), then enable branch protection requiring the quality check before merge, so a red merge like #349 cannot recur.

## Phase 2. Merge what is ready (only after Phase 1)

1. Let Dependabot PRs #338 to #343 auto-merge (they include the CRITICAL anyio fix GHSA-82r6-8w77-94w6 and HIGH fast-uri/qs/hono fixes). Add the `ci` label to #344 and merge.
2. Merge #351 (statusline token HUD) as is.
3. `ruff format` the two files of #315 and merge; retarget #324 to main, format its lineage file, merge; close #312 as contained in #324.
4. Rebase #311 (process-hygiene supervisor, 433 tests) on green main, re-run CI, merge; then install its prevention half on the workstation (job-object launcher, direct-exec MCP configs). Done-check: `Get-Process` shows no `bridge-server`/`agentbridge` and no parentless `cursor-agent` trees older than an hour.

## Phase 3. Settle the lanes (each step: tag, then act, then record)

1. Rescue-tag first: `git tag rescue/2026-09/p2-0db0 origin/cursor/p2-loop-to-green-0db0` and the same for `p2/loop-to-green-2026-09-02`, `p2-loop-to-green`, `feat/tool-registry-governance`, `live-capture/2026-09-02`; push tags.
2. Neutralize the fleet on main: remove or disable `p2-agent-runner.yml`, `p2-loop-runner.yml`, `p2-agent-shard.yml` (they check out and push to the draft branch and re-arm each other); record D5.
3. Split `cursor/p2-loop-to-green-0db0` (317 commits, 1,571 files): one ledger PR (command-center receipts, probes, reviews, unit manifest) with a reviewer-authenticity sample, and six to eight code PRs (tools/plugin, tools/command-center, platform/lib, detectors, chrome-bridge hermetic tests, claude-science router, zai) each rebased on main with its own CI. Close #316 with the 2026-09-06 directive as the recorded reason. Delete `p2-loop-to-green` (fully contained). Then archive-tag and delete the roughly 130 `cursor/{imp,aud,cc,tst}-*-0db0` branches and close drafts #326 to #335.
4. Stranded production code: open small PRs from `feat/tool-registry-governance` for `tools/mcp/dbx-ai`, `tools/biomni-hub-mcp` (run its 67 offline tests), `tools/cursor-bridge`, and the audit record `harness-audits/2026-09-19-mcp-tui-audit/`; the live registry already points at the first two. Do not merge the branch whole. Delete after tagging.
5. Live-capture fold-back, documents first: port `knowledge/deep-thoughts/2026-09-23-*.md` and `knowledge/analyses/2026-09-23-*.md` and the 42 dated decision documents into `docs/decisions/` (Phase 4a format), then the registry delta (89 live versus 42 mirror rows) with provenance, then the 8 skills and 15 diverged SKILL.md files, then the harness module delta tests-first. Never merge the orphan; delete the branch after tagging once the fold-back PRs are merged.
6. Adjudicate the 21 closed-unmerged PRs and the 9 archive tags with files absent from main (`archive/2026-07/chore/enshrine-runtime-config` 97 files, `add-databricks-fanout-harness` 40, `wip/harness-workspace-supervisor` 10, `fix/deny-credential-gaps` 8, `monitorcore-codexsource` 4): for each, one line in a decision file: landed elsewhere (cite the commit), retired (reason), or salvage PR (opened). No silent drops.
7. #310 (search-hub reunion, 88 new files) and #336 (auto-synced grill): owner decides per D7; auto-synced branches stop syncing.
8. Cyber lanes per D6. Done-check for the phase: `git for-each-ref refs/remotes/origin | wc -l` under 30; every remaining branch has an open PR or is main; zero orphan lineages.

## Phase 4. Durability: the mechanisms that make the problems structurally impossible

a. Decision records with expiry. `docs/decisions/<date>-<slug>.md` with frontmatter `status, rationale, evidence, review_by`; a CI check (`ci/check_decisions.py`, new, under 100 lines) fails when any accepted decision is past `review_by` without a re-test note, and when a deletion or retirement commit has no decision file. This is the owner's R2 and R3 and the only cure for idempotent dismissal.
b. Stale-ref gate. A weekly workflow lists remote branches with no open PR and no archive tag older than 48 hours and fails; the fix is a tag or a PR, never silence. This is what keeps Phase 3 done.
c. Windows in CI. One `windows-latest` job that runs the real deploy (`scripts/sync-hooks.ps1`, `agent-self/sync-self.ps1`) into a temporary HOME, then `python scripts/hooksmoke.py --tool claude` and `--live <temp settings> --no-exec`, and asserts every marker fired and every command resolves. CI stops verifying a Linux projection of a Windows deployment. Replace absolute `C:/Users/Prekzursil` paths in hook commands with `%USERPROFILE%` or a resolver so the same tree runs on both.
d. Fail-closed where it matters, silent nowhere. The few safety gates (secret reads, force push, worktree removal, config edits) exit 2 with a reason; every other check emits JSON `additionalContext` or nothing; the dispatcher logs each check's exit status to the event ledger, and a weekly "zero-fire" report lists hooks and skills that fired zero times. A dead check must produce a visible line within a week.
e. One owner per capability. Delete: `hooks/hooks.json` and its twin (22 missing scripts); the 36 hook directories wired nowhere (tag first); two of three harness copies (keep `.agents/harness`; point `skills/harness-module-authoring/SKILL.md` at it); duplicates of ledger, goal-reinject, recall, anti-degen, claim-guard, secret-guard (keep the module or the hook, not both); two of three routers; five of six budget mechanisms; five of six monitors; `skills/` compatibility copy; `.agents/skills-retired-2026-07-03`; tracked generated data (WORK-UNIT-CATALOG backup, probe scripts no test imports). Each deletion: one decision file.
f. Context budget as a blocking gate. `rule-audit` fails when unscoped rules exceed 3K tokens; skill descriptions over 1,024 characters fail `check_skill_description_ratchet.py`; MCP config per project with at most 10 active servers; `skillOverrides` sets the long tail to `name-only` or `off`.
g. One direction of sync and one writer. The repo is edited, the live tree is deployed: `sync-hooks.ps1` becomes a mirror (delete on target) after archive-tagging the live superset once; the executing checkout fast-forwards to main on a scheduled task, and `ssot_drift_gate.py` exits non-zero when it cannot check (not SUCCESS).
h. Weekly whole-state snapshot into main (the owner's R1): settings, skill inventory, MCP roster, enabled/disabled state, hook wiring, as one small generated file, diffable across weeks.
i. Secrets policy: git-crypt or an OS keychain referenced by name; no plaintext keys, no browser state, no engagement material in the tree; gitleaks allowlist entries require a decision file.
j. Measurement loop: golden suite confirmed row by row by the owner, then `claude plugin eval` weekly with `--threshold`, `--max-cost-usd`, pinned model, results appended under `docs/results/`; `/skill-doctor` monthly; re-test with always-on files removed on every model release. This is the only instrument that decides whether any of the above helped.

## Phase 5. Exit criteria (numbers, so the freeze can end)

- quality.yml green on main for 14 consecutive days; branch protection on.
- Remote branches under 30; zero without PR or tag; zero orphan lineages; zero drafts older than 14 days.
- Always-on rules under 3K tokens; model-invocable skills 30 to 40 per profile; at most 10 active MCP servers per project; at most 10 wired hooks, each with a passing real-session smoke test on Windows and Linux.
- One harness copy, one router (or none), one memory path, one budget indicator, one monitor.
- Every retirement since 2026-09-24 has a decision file with a review date; the expiry check is green.
- Golden suite baseline recorded; at least two experiments from `docs/EXPERIMENTS-2026-09-24-preregistered.md` run with results appended.

## Entry prompt for the next session (paste as the first message)

"Read docs/RUNBOOK-2026-09-24-settle-and-harden.md and docs/AUDIT-2026-09-24-sota-transcript-and-lanes.md on branch claude/sleepy-pascal-pnlqwc (PR #353). Phase 0 decisions are: <fill D1 to D10>. Execute Phase 1 now and stop at its done-check. Do not start any phase whose prerequisite done-check has not printed. Record every decision as a file under docs/decisions/ before acting on it. No new lanes."
