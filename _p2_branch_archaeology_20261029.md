---
title: _p2_branch_archaeology_20261029
type: note
permalink: dqverify-repo-20261013/p2-branch-archaeology-20261029
---

# P2 Branch Archaeology — agent-skills-toolchain — 2026-10-29

READ-ONLY audit. No branches were deleted, merged, pushed, or rebased; no worktrees touched.
Repo: `C:\Users\Prekzursil\source\agent-skills-toolchain` (origin: `https://github.com/Prekzursil/agent-skills-toolchain.git`).

## Bases and caveats

- **Local `main` = `88584d2a` (2026-10-01) is STALE**: it is a strict ancestor of origin main (0 ahead / 65 behind; fast-forward only, not diverged).
- **True origin main tip = `7a1393ca4`** (2026-10-24, "ci(imp0014): workflow_dispatch-only macOS evidence probe"), verified via `git ls-remote origin` and present in the local object store.
- Ahead/behind in the FULL BRANCH TABLE below is measured against **stale local main** (as the task's `main...<branch>` formula specifies). "behind" therefore understates by 65 for every branch; "ahead" is unaffected except for branches that merged post-10-01 main (notably `wt/pr325-fix`: 373 ahead of stale main = 338 ahead of origin main).
- Push-parity compares the LOCAL tip against the LIVE `git ls-remote origin` value, never remote-tracking refs (several were verified stale, e.g. `refs/remotes/origin/cursor/p2-loop-to-green-0db0` still points at its own tip but `origin/feat/p2-program` tracking ref lagged).

## PR #404 state (item 4)

```
state: OPEN | mergeable: MERGEABLE | base: main | head: feat/p2-program @ 68b125576e486def7afa7a6a843f8afc20743cac
title: "feat(p2): P2 program snapshot - 296-agent fail-closed run state (delivered 1392/2007)"
created 2026-10-27T12:45:16Z, updated 2026-10-27T13:36:53Z
```

- PR head OID `68b125576` **equals** local `feat/p2-program` tip **equals** `ls-remote origin feat/p2-program`. Push-parity: exact.
- `feat/p2-program` = origin main + exactly **2 commits** (`a979cde5a` snapshot, `68b125576` partition script). The owner's "1 commit ahead" was true at PR-open time; the partition-script commit landed after PR creation (15:23 vs 12:45).
- The PR diff is 20,081 files / +8,197,999 / **0 deletions** — purely additive. 20,080 files are a single new top-level envelope `p2-g1/` (layout: `p2-g1/command-center` 8,941, `p2-g1/tools` 3,704, `p2-g1/skills` 1,783, `p2-g1/platform` 1,372, corpus 610, docs 343, hooks 308, …). One path carries a quoted/non-ASCII name (forensics artifact of the partition-script commit).

## P2 lineage (all measured, cited by SHA)

All September P2 branches fork from main at **`acb040577`** (merge of PR #308, 2026-09-02):

```
acb040577 (fork, PR #308 merge)
├── p2/loop-to-green-2026-09-02  44c54b68f (140 ahead, 2026-09-19 06:06)  ← separate line, ancestor of NOTHING later
└── pr-325 == p2-loop-to-green    a49fdf879 (273 ahead, 2026-09-19 15:02) ← SAME tip, two names
    └── cursor/p2-loop-to-green-0db0  e75ce1ff9 (323 ahead, 2026-09-24)
        ├── backup/sticky-57f4c924a  57f4c924a (326 ahead, 2026-09-24; +3 McpHub commits)
        └── wt/pr325-fix  41b42625e (338 ahead of originMain, 2026-10-22; remerged main at 782f68ec0/PR #378, 2026-10-18; +150 commits over cursor/p2-loop; LOCAL-ONLY, never pushed)

origin main 7a1393ca4 (2026-10-24)
└── feat/p2-program 68b125576 (2 ahead; PR #404; the p2-g1/ state envelope)
```

Ancestry verified with `git merge-base --is-ancestor`: `a49fdf879` ⊂ `e75ce1ff9` ⊂ {`57f4c924a`, `41b42625e`}; `44c54b68f` ⊂ nothing; `57f4c924a` ⊄ `41b42625e`. None of the five historical tips is an ancestor of origin main or of feat/p2-program.

## Owner's four numbers, identified

| Owner's count | Branch | Tip | Status |
|---|---|---|---|
| 273 | `pr-325` (local+remote) | `a49fdf879` | pushed, parity OK |
| 273 (same tip) | `p2-loop-to-green` (remote-only) | `a49fdf879` | byte-identical duplicate of pr-325 |
| 323 | `cursor/p2-loop-to-green-0db0` | `e75ce1ff9` | pushed, parity OK |
| 140 | `p2/loop-to-green-2026-09-02` (remote-only) | `44c54b68f` | pushed, no local branch |
| 1 | `feat/p2-program` at PR-open | now `68b125576` (2 ahead of origin main) | PR #404 OPEN/MERGEABLE |

Related but distinct: `backup/sticky-57f4c924a` (326, = cursor + 3 McpHub commits) and `wt/pr325-fix` (373 vs stale main / 338 vs origin main, **never pushed**).

## Unique-content analysis (item 2)

Method: changed-since-fork file sets per branch (`git diff --name-only <merge-base> <tip>`), mapped by normalized path into the `p2-g1/` envelope (`command-center/X → p2-g1/command-center/X`, `harness/ast-integrate/X → p2-g1/X`), with blob-hash comparison (`git ls-tree`) for identical-vs-evolved. `p2-g1/` tree = 20,080 files; full feat/p2-program tree = 35,254 files.

| Branch | Changed since fork | Mapped into p2-g1 (by name) | Identical blob | Evolved | Unmapped |
|---|---|---|---|---|---|
| p2/loop-to-green-2026-09-02 | 45,263 (`harness/ast-integrate/**`) | 16,288 (9,053 still present as blobs; rest deleted in-flight) | 8,426 | 627 | 28,975 |
| pr-325 | 1,448 (`command-center/**` 1,335) | 186 | 1 | 185 | 1,262 |
| cursor/p2-loop-to-green-0db0 | 1,587 | 223 | 1 | 222 | 1,364 |
| backup/sticky-57f4c924a | 1,591 | 223 | 1 | 222 | 1,368 |
| wt/pr325-fix | 1,806 | 285 | 13 | 272 | 1,521 |

Key structural facts:

- origin main carries **no** root `command-center/` or `tools/` — the program state exists ONLY inside `feat/p2-program`'s `p2-g1/` envelope (and in the historical branches).
- Directory FAMILIES line up across generations (`p2-wave`, `receipts`, `schema`, `slop-report`, `ssot`, `adversarial`, `p2-next`…), but exact-path mapping is low because the snapshot is a LATER, REGENERATED state: `p2-g1/command-center/p2-wave` = 4,570 files vs `wt/pr325-fix` 1,607 vs pr-325 ~1,337. `tools/` basename overlap wt↔p2-g1: 1,725 of 1,822.
- **Probe corpus**: the 140-branch carries 29,854 files under `command-center/p2-wave/probes/**`; only 3,327 exist in any later carrier (p2-g1: 4,143 probes total; wt: 1,293). **26,527 probe/fixture files exist NOWHERE else** (largest: ADV-0002/fixtures 1,249; WFA-0032/fixtures 568; TST-0091/runtime 516; WFA-0135/estate 481).
- **The 3 McpHub commits in backup/sticky carry ZERO unique content**: `git diff originMain..backup/sticky -- .agents/scripts/mcp_control_plane.py` = 2 insertions / 6 deletions, and every hunk is a line-REWRAFF (Black formatting) — current main already contains the `transport in ("http", "sse")` validation. `agents.json` delta = 35 deletions (main's newer consult-offsec entry absent in sticky). `guard_parked_stdio.py` = 5+/17- (main newer). wt/pr325-fix and feat/p2-program blobs for all three files equal origin main's exactly.

## VERDICTS (item 3, 4-way, evidence-cited)

| Branch | Verdict | Evidence |
|---|---|---|
| `feat/p2-program` `68b125576` | (reference — current carrier, PR #404) | originMain + 2 commits; additive-only 20,081-file snapshot; parity exact local=remote=PR head |
| `pr-325` `a49fdf879` | **SUPERSEDED** | Strict ancestor of `e75ce1ff9`/`57f4c924a`/`41b42625e` — all content reachable from later lines; command-center families regenerated larger in p2-g1 |
| `p2-loop-to-green` `a49fdf879` (remote-only) | **SUPERSEDED** (pure duplicate) | ls-remote tip byte-identical to `pr-325` — zero unique commits by definition |
| `cursor/p2-loop-to-green-0db0` `e75ce1ff9` | **SUPERSEDED** | Strict ancestor of `57f4c924a` and `41b42625e` (merge-base --is-ancestor both ways); 323 commits all reachable |
| `backup/sticky-57f4c924a` `57f4c924a` | **SUPERSEDED** | Only delta over cursor = commits `911caeeb1`/`06b5b0e44`/`57f4c924a`, whose files (mcp_control_plane.py, agents.json, guard_parked_stdio.py) differ from CURRENT main by formatting rewraps + missing newer main content; sse fix already in main |
| `wt/pr325-fix` `41b42625e` | **UNIQUE-WORK** (and UNPUSHED — single copy) | 150 commits beyond `e75ce1ff9` (fixer-r1 rounds: `41b42625e`, `d76847547`, `2153384fd`…) in NO other branch; NOT ancestor of feat/p2-program; 1,521 changed paths unmapped in p2-g1; exists ONLY in local repo + worktree `ast-pr325` — no origin ref |
| `p2/loop-to-green-2026-09-02` `44c54b68f` (remote-only) | **UNIQUE-WORK** (historical value; keep) | Separate lineage (ancestor of nothing); 26,527 probe/fixture files in no other carrier; 8,426 blobs byte-identical in p2-g1 prove partial carry, remainder orphaned |
| `wave3/{ci-trigger,command-center,monitor,program-b,skill-gate}` | **STALE-ABANDONED** | 2026-08-09 stubs, 720 behind originMain, 1–31 changed files each — pre-P2 program stubs superseded by the September program |
| Name-matches excluded as non-P2 (measured, not inferred): `wave/blocking-mode-consolidation` (2026-10-18, 57 ahead — recent unrelated work), `lane-cigreen/*` (Aug CI-lane work), `ci/unignore-wave3`, `reconcile/harness-drift-wave2` (July) | — | dated/small and topically unrelated to the P2 program |

## Branch-table flags (item 1 highlights; full table below)

- **`wt/pr325-fix` — 373 ahead of stale main, LOCAL-ONLY (never pushed).** The only P2-line content not on origin. Single-copy risk while it lives only in the local repo + `ast-pr325` worktree.
- Other LOCAL-ONLY branches (not P2, listed for completeness): `feat/modal-budget-ledger-measured` (64), `sessions-vault` (58), `uber-sandbox-research-20260930` (16), `claude/fix-agents-mcp-merge-regressions` (0), `codex/monitor-unify-20260819` (0), `cyberstrike-config-fold2` (0), `feat/cv-studio-skill` (4), `feat/proxy-mcp-mitmproxy` (1), `fix/gate-battery-20260928` (0), `fix/gitleaks-fingerprints-20260928` (0), `fold/vm-link-estatesync` (0), `harness/upgrade-2026-07-17` (0), `rescue/*` (4+1), `salvage/codex-profiles-config-lint` (0).
- DIVERGED local-vs-remote (local has commits remote lacks, or vice versa): `main` (stale local), `lane-cigreen/sast-install-split`, `fix/estates-secrets-relocate-20261022`, `fix/hollow-output-gate-202601021`, `chore/reunite-mcp-control-plane-live-tests`, `fix/grok-sensitive-artifact-stop-loop`, `feat/vm-link-skill`.
- 189 remote-only branches (no local ref), dominated by the `cursor/aud-*`/`cursor/cc-*`/`cursor/imp-*`/`cursor/tst-*` audit fleet and `gemhunt/hosted-models-*`; P2-relevant ones are `p2-loop-to-green` and `p2/loop-to-green-2026-09-02` (analyzed above). Full list appended.

## Recommended reconcile order (recommend only — nothing executed)

1. **BEST — Push `wt/pr325-fix` to origin as-is** (`git push origin wt/pr325-fix`). It is the only unpushed P2 line (150 unique commits, single-copy risk). Downside: adds one more branch to an already 300-head remote and its 22,240-file tree diff vs p2-g1 makes any later review noisy.
2. **Merge PR #404** (`feat/p2-program` → main; MERGEABLE, additive-only). Downside: 20,081 files / +8.2M lines land in main permanently — clone/diff/ls-tree cost on every future checkout; a squash-merge keeps history at 1 commit but erases per-wave commit granularity.
3. **Then verify, then archive the superseded septet** — `pr-325`, `p2-loop-to-green`, `cursor/p2-loop-to-green-0db0`, `backup/sticky-57f4c924a` carry zero unique content once wt is pushed and #404 merged; rename to `archive/…` rather than delete. Downside: none content-wise; deleting instead would violate the D-10 never-delete-branches rule and lose the "pr325-green" era labels.
4. **Keep `p2/loop-to-green-2026-09-02` on the remote permanently** (or tag `archive/p2-loop-2026-09-02`): its 26,527-file gen-1 probe/fixture corpus exists nowhere else. Downside: none — it costs only a ref name; it is the sole recoverable copy.
5. **WORST — delete/force-prune any of the above now.** Downside: irreversible loss of the 150-commit fixer line (step 1) or the 26,527-file corpus (step 4); explicitly against D-10 and the ALWAYS-PUSH doctrine.

## Reproducibility (commands used; all read-only)

`git for-each-ref refs/heads refs/remotes`, `git ls-remote origin`, `git rev-list --left-right --count main...B` and `7a1393ca4...B`, `git merge-base`/`--is-ancestor`, `git log/diff --name-only/--shortstat`, `git ls-tree -r`, `git show`, `gh pr view 404 --json state,mergeable,headRefOid,headRefName,baseRefName,title,createdAt,updatedAt`. `GIT_OPTIONAL_LOCKS=0` on index-touching reads.

---
## FULL BRANCH TABLE — 122 local branches (ahead/behind vs STALE local main `88584d2a`; parity vs live ls-remote)

Format: `branch | last-commit-date | behind=main-only | ahead=branch-only | parity`add-databricks-fanout-harness|2026-07-24|behind=755|ahead=1|OK
agent/detector-fix-fp|2026-07-24|behind=775|ahead=1|OK
backup/sticky-57f4c924a|2026-09-24|behind=100|ahead=326|OK
chore/accounts-store-followups|2026-07-25|behind=741|ahead=2|OK
chore/ci-selfhosted-hardening|2026-09-29|behind=33|ahead=9|OK
chore/deps-consolidated-20260809|2026-08-09|behind=655|ahead=4|OK
chore/enshrine-runtime-config|2026-07-13|behind=882|ahead=15|OK
chore/harness-reconcile-20260808|2026-08-09|behind=656|ahead=19|OK
chore/hygiene-academic-skills-20260825|2026-08-26|behind=649|ahead=2|OK
chore/hygiene-academic-skills-20260826|2026-08-26|behind=191|ahead=4|OK
chore/remove-gitcrypt-minimal|2026-10-18|behind=0|ahead=23|OK
chore/retire-brace-expansion-ignore|2026-07-25|behind=744|ahead=1|OK
chore/reunite-mcp-control-plane-live-tests|2026-09-02|behind=109|ahead=1|DIVERGED(local=664512a13411d557460e99d4167fdcf88b733b95 remote=d284890b7063169bdc5830de8046bc2c4391c680)
chore/statusline-gotchas-and-goal-short-20260724|2026-07-24|behind=765|ahead=2|OK
chore/sync-from-live-20260725|2026-07-25|behind=814|ahead=8|OK
ci/gate-cloud-hub-full|2026-07-25|behind=721|ahead=1|OK
ci/hardening|2026-10-18|behind=0|ahead=21|OK
ci/hook-separator-tripwire|2026-10-18|behind=0|ahead=25|OK
ci/red-canary|2026-10-18|behind=0|ahead=21|OK
ci/unignore-wave3|2026-07-25|behind=723|ahead=2|OK
ci/unmap-estate-gitlinks|2026-10-18|behind=0|ahead=19|OK
ci/wire-harness-suites|2026-07-25|behind=732|ahead=2|OK
ci/wire-hooks-regression-harness|2026-07-25|behind=731|ahead=1|OK
ci/wire-mcp-hub-suites|2026-07-25|behind=727|ahead=2|OK
claude/fix-agents-mcp-merge-regressions|2026-09-29|behind=34|ahead=0|LOCAL-ONLY
codex/monitor-unify-20260819|2026-08-17|behind=208|ahead=0|LOCAL-ONLY
consult-offsec-registration|2026-09-04|behind=100|ahead=30|OK
cursor/p2-loop-to-green-0db0|2026-09-24|behind=100|ahead=323|OK
cyberstrike-config-fold|2026-09-22|behind=88|ahead=0|OK
cyberstrike-config-fold2|2026-09-19|behind=89|ahead=0|LOCAL-ONLY
docs/ci-coverage-gap-report|2026-07-25|behind=741|ahead=2|OK
docs/cursor-cli-bridges|2026-08-27|behind=190|ahead=15|OK
docs/cyberstrike-fullpower-2026-09-06|2026-09-06|behind=100|ahead=1|OK
docs/estate-runtime-runbooks|2026-10-21|behind=0|ahead=36|OK
feat/1password-ops-skill|2026-10-21|behind=0|ahead=36|OK
feat/agent-detail-pane|2026-10-24|behind=0|ahead=66|OK
feat/aws-cloud-hub|2026-07-25|behind=748|ahead=2|OK
feat/consult-offsec-registration-restacked|2026-10-18|behind=0|ahead=24|OK
feat/cookie-bridge-skill-20260724|2026-07-24|behind=775|ahead=1|OK
feat/credential-forge-skill|2026-10-22|behind=0|ahead=36|OK
feat/cv-studio-skill|2026-07-19|behind=868|ahead=4|LOCAL-ONLY
feat/durable-checkpoint|2026-10-25|behind=0|ahead=70|OK
feat/fb-instagram-parity|2026-07-19|behind=825|ahead=2|OK
feat/grok-lane-skill|2026-10-21|behind=0|ahead=38|OK
feat/hooks-docs-cleaning|2026-07-19|behind=820|ahead=3|OK
feat/hopper-launch|2026-10-24|behind=0|ahead=64|OK
feat/linkedin-mcp-userscope-registration|2026-07-20|behind=814|ahead=1|OK
feat/modal-budget-ledger|2026-10-24|behind=0|ahead=65|OK
feat/modal-budget-ledger-measured|2026-10-24|behind=0|ahead=64|LOCAL-ONLY
feat/p2-program|2026-10-27|behind=0|ahead=67|OK
feat/proxy-mcp-mitmproxy|2026-07-20|behind=814|ahead=1|LOCAL-ONLY
feat/repo-map-grounding-pack|2026-07-24|behind=775|ahead=1|OK
feat/social-corpus-extraction-skill|2026-07-19|behind=828|ahead=3|OK
feat/taskwatch-reconcile|2026-10-25|behind=0|ahead=67|OK
feat/tg1-detector-self-test-toolchain|2026-07-24|behind=755|ahead=1|OK
feat/tg2-mutation-gate-toolchain|2026-07-24|behind=755|ahead=1|OK
feat/tool-registry-governance|2026-09-19|behind=100|ahead=9|OK
feat/variant4-increment1-dbx-monitor-20260721|2026-07-24|behind=804|ahead=1|OK
feat/vm-link-skill|2026-10-01|behind=15|ahead=2|DIVERGED(local=3ae41988220bdf7384b36ea3cf30458873cfc707 remote=a5ae766a58c33cd32302ed079554d9c370c54eb6)
feat/zcode-plugin-official|2026-10-22|behind=0|ahead=36|OK
feat/zcode-ssot-cyberstrike-2026-09-03|2026-09-03|behind=100|ahead=35|OK
fix/absent-field-blocks-20261021|2026-10-21|behind=0|ahead=59|OK
fix/accounts-clear-gitcrypt-error|2026-07-25|behind=746|ahead=1|OK
fix/cyber-clean-profile-gate|2026-10-24|behind=0|ahead=61|OK
fix/dead-mcp-detector-honours-disabled|2026-07-25|behind=746|ahead=2|OK
fix/deep-research-scope-gate|2026-10-24|behind=0|ahead=66|OK
fix/estates-lf-normalize-20261022|2026-10-22|behind=0|ahead=54|OK
fix/estates-secrets-relocate-20261022|2026-10-22|behind=0|ahead=51|DIVERGED(local=3e95768c70a67377f3b47932cf309a3f0821d28e remote=6554b73cd90585439ccb157f6d17c175f557126b)
fix/event-ledger-single-source|2026-10-25|behind=0|ahead=67|OK
fix/gate-battery-20260928|2026-09-28|behind=43|ahead=0|LOCAL-ONLY
fix/gate-secrets-scan-head-history|2026-09-02|behind=109|ahead=2|OK
fix/git-hygiene-repo-truncation-floor|2026-07-25|behind=744|ahead=2|OK
fix/gitleaks-fingerprints-20260928|2026-09-28|behind=41|ahead=0|LOCAL-ONLY
fix/grok-sensitive-artifact-stop-loop|2026-09-02|behind=100|ahead=1|DIVERGED(local=d750e82511e6e2ebadebc2ad43b294dd36c9db84 remote=b2ffa6e031de5bb2a9faf9c1fbbef189285ba18b)
fix/harness-corpus-control-guard|2026-07-25|behind=722|ahead=1|OK
fix/hollow-output-gate-20261021|2026-10-21|behind=0|ahead=37|DIVERGED(local=1be0a4beaac39e552234589a0dfc6c2b578ed0b7 remote=0273da9210f7bbee6e40a5d2e71953cbae8d175a)
fix/hook-separator-scope-20260930|2026-09-30|behind=47|ahead=21|OK
fix/hooks-webfetch-sentinel-and-browser-compress|2026-07-24|behind=770|ahead=3|OK
fix/live-harness-drift-20261021|2026-10-22|behind=0|ahead=60|OK
fix/main-debt-gates-20261022|2026-10-22|behind=0|ahead=52|OK
fix/mcp-health-agentmail-fbmessenger|2026-07-25|behind=814|ahead=8|OK
fix/mcp-hub-multi-client-sticky-20260924|2026-10-13|behind=0|ahead=51|OK
fix/osv-ignore-brace-expansion|2026-07-25|behind=749|ahead=2|OK
fix/retire-wfmon-autolaunch|2026-10-24|behind=0|ahead=66|OK
fix/sentinel-status-field-not-payload|2026-07-25|behind=742|ahead=3|OK
fix/skill-frontmatter-and-grok-pulls|2026-07-24|behind=775|ahead=1|OK
fix/stubscan-wrapped-comment|2026-07-27|behind=709|ahead=1|OK
fix/triage-dispatch-manifest-presence|2026-07-25|behind=730|ahead=1|OK
fix/triage-dispatch-wiring|2026-07-25|behind=730|ahead=2|OK
fix/triage-golden-standalone|2026-07-25|behind=730|ahead=1|OK
fix/triage-memory-spool-replay|2026-07-25|behind=730|ahead=1|OK
fix/triage-per-edit-check-secrets|2026-07-25|behind=730|ahead=3|OK
fix/ui-audit-dead-button-noise-subtraction|2026-07-31|behind=814|ahead=9|OK
fix/use-vs-mention-result-scanner|2026-07-20|behind=814|ahead=2|OK
fold/vm-link-estatesync|2026-10-01|behind=3|ahead=0|LOCAL-ONLY
handoff/cloud-agent-2026-09-02|2026-09-02|behind=120|ahead=22|OK
harness/browser-attach-module|2026-10-21|behind=0|ahead=39|OK
harness/upgrade-2026-07-17|2026-07-18|behind=868|ahead=0|LOCAL-ONLY
lane-cigreen/dual-write-gates|2026-08-13|behind=396|ahead=1|OK
lane-cigreen/sast-install-split|2026-08-14|behind=351|ahead=2|DIVERGED(local=5176f2034307bd8118297e7a5e8ae6f04ad59e4b remote=963315e31c750b4db26cf97c06d8f661415c12d7)
lane2/mcp-control|2026-07-27|behind=703|ahead=8|OK
lane2/mcpctl|2026-07-26|behind=718|ahead=3|OK
main|2026-10-01|behind=0|ahead=0|DIVERGED(local=88584d2aa10939516648dacfbe560ed677fe9415 remote=7a1393ca4f6cf8cd635d19b20bb261f70f737cd7)
pr-325|2026-09-19|behind=100|ahead=273|OK
pr127|2026-07-20|behind=814|ahead=1|OK
reconcile/harness-drift-wave2|2026-07-20|behind=814|ahead=7|OK
remove-gitcrypt-filters|2026-09-22|behind=89|ahead=1|OK
remove-gitcrypt-filters-v2|2026-09-22|behind=89|ahead=1|OK
rescue/chore/statusline-gotchas-and-goal-short-20260724|2026-07-24|behind=763|ahead=4|LOCAL-ONLY
rescue/fix/ssh-platform-cleanup-20260720|2026-07-24|behind=763|ahead=1|OK
rescue/w2-c16-error-taxonomy|2026-07-24|behind=756|ahead=1|LOCAL-ONLY
salvage/C1-one-shared-completion-predicate-held-id|2026-07-19|behind=868|ahead=6|OK
salvage/codex-profiles-config-lint|2026-08-09|behind=649|ahead=0|LOCAL-ONLY
salvage/codex-scoping-layer|2026-07-19|behind=828|ahead=1|OK
sessions-vault|2026-10-18|behind=0|ahead=58|LOCAL-ONLY
sessions/vault-sync|2026-10-18|behind=0|ahead=24|OK
uber-sandbox-research-20260930|2026-10-01|behind=0|ahead=16|LOCAL-ONLY
vprobe/skillgate|2026-08-09|behind=656|ahead=1|OK
w2-c16-error-taxonomy|2026-07-24|behind=761|ahead=4|OK
wave/blocking-mode-consolidation|2026-10-18|behind=0|ahead=57|OK
wip/harness-workspace-supervisor-20260826|2026-08-26|behind=649|ahead=2|OK
wt/pr325-fix|2026-10-22|behind=0|ahead=373|LOCAL-ONLY

---
## REMOTE-ONLY BRANCHES — 189 refs on origin with no local branch (tip from live ls-remote)

archive/glm53-space-2026-09 | tip c4df87af060d59a099e43d06706c6c71e87a7238
chore/statusline-token-hud | tip 3e206e714cbd01f877de609a9157384baf7d6839
ci/execute-never-run-dualwrite-steps | tip f90b3e023f91c26c3a2f1de1ca328af72eb852d1
claude/fix-osv-scanner-deps-20260929 | tip f07d6a8d392ee9b8538f4c6c2ddc6881895642b0
claude/fix-quality-secrets-hygiene-20260929 | tip c0b3fe404a72cef0efe5ada927fe526ca644951b
claude/laughing-lovelace-n12r11 | tip 0098c3026ba8c9047d512aed6dc1ea69094752e9
claude/sleepy-pascal-pnlqwc | tip 071571bc31457c77034ae4006b4dc73778dd004d
copilot/find-databricks-env-names | tip 782f68ec0fb1b356c0c15401e61c70726c87cbdd
cursor/aud-0003-impl-0db0 | tip 32f9066199ed21d2651f1adf47d732f644cf762b
cursor/aud-0003-review-0db0 | tip cdca774ebdd0a0e42c7108085c0534372c0d4fb7
cursor/aud-0017-impl-0db0 | tip 8f7ffb1e78e88804d39d56a6cfcf47dbb4fc1dce
cursor/aud-0017-review-0db0 | tip 09448bd4c7de2d6cdd83ef5de47ef2f446ac654a
cursor/aud-0023-impl-0db0 | tip e18a3d0f8d5196a3c77a611b0ae821215e98a7ba
cursor/aud-0023-review-0db0 | tip 9904c0aa2a392ea32f809cde1008346b23f081e8
cursor/aud-0025-impl-0db0 | tip 87e0ba98df9cba927122ca67367f9391b9700173
cursor/aud-0025-review-0db0 | tip 078580697df20c7cf73dd34b0662253f255b3106
cursor/aud-0025-unpinned-census-50a3 | tip 08c8092d639211d87791d4e40e196006aa6db0a2
cursor/aud-0026-impl-0db0 | tip 617ddaf9eb4e81b923ed06c1be80dfc8dd1b06b0
cursor/aud-0026-review-0db0 | tip a79c709c46d55e13db1360a4d716c518a37c9a65
cursor/aud-0027-impl-0db0 | tip 1a5a07a1b0889716d13d3b2b03d0636a78b230f1
cursor/aud-0027-review-0db0 | tip ff47c3c21e2995e6a930cfb5f45595b27811c3f3
cursor/aud-0031-lib-consumers-0db0 | tip 6c219bc1dbf8c2b6298571086fb14bbb0d64c840
cursor/aud-0032-independent-rereview-ad1f | tip b1640ab1b10ead5b9b4de4b7b68c3b69b7cdaaee
cursor/aud-0032-rereview4-ancestor-0db0 | tip 20b6e5a4cec00eef4248e6477ef0ddcfaf4dbd94
cursor/aud-0032-rereview5-0db0 | tip 9381f2868250876d9e769ce5bb640aa650c0a730
cursor/aud-0032-rereview6-0db0 | tip 9eb4092c71027fd8dc76361238fccbd85d0e4daf
cursor/aud-0040-impl-0db0 | tip 9258310bbc7ba1c73fca4eee99339070dfd6e4a2
cursor/aud-0040-review-0db0 | tip ee13df117f65cf9c2ae9c490369a6b90997d8345
cursor/aud-0042-impl-0db0 | tip 327786f3068ce46e3124fbc24c7ad46a5ffe80dd
cursor/aud-0042-review-0db0 | tip 8f8a97ed14ca3d5cd37cf45eb2ce56df10904cd8
cursor/aud-0043-impl-0db0 | tip 80a08f8b5ac334baa2cb11f6b6975f9296877ff3
cursor/aud-0043-review-0db0 | tip 20c648af51df367b7962a667162b887a2b4b5e81
cursor/aud-0044-impl-0db0 | tip 9b40edd4c8a256c21fc2cf3c44d6b6d454db6c52
cursor/aud-0044-review-0db0 | tip d1b4c10208e94ea52792ba761f8a4e7ff01a910e
cursor/aud-0046-impl-0db0 | tip bf75c90b6ea8c77231e4a1156ab79ebda4a376e9
cursor/aud-0046-review-0db0-1670 | tip 17ca0b3d990a4b80237d103bf62319a172169110
cursor/aud-0047-path-filters-0db0 | tip 9cf6aded873e42574a1d170ee5a7d4f459b91be4
cursor/aud-0048-action-pins-0db0 | tip 5609abd8c353b48920e4a34450f575f0e6921948
cursor/aud-0049-review-0db0 | tip 42e247af6bccab9946946895d8dafe66e8801f4c
cursor/aud-0050-impl-0db0 | tip b8718f01ab1ee07fbb6edd7d2c5d12f4f13b1a1c
cursor/aud-0050-review-0db0 | tip 5fb59e7812ef845e53425fc792388b7542b1a29f
cursor/aud-0052-impl-0db0 | tip ce34020844ac8600653192a75951e7da52c01aed
cursor/aud-0052-review-0db0 | tip fcc922213c8ed7cf3e46cb60557316c80e7823cb
cursor/aud-0053-impl-0db0 | tip 387ab20bd079438310890098a8d05dfb91755e22
cursor/aud-0053-review-0db0 | tip b305339ec7604d8d0fe4ffeaefe94139f64da1ea
cursor/aud-0054-impl-0db0 | tip 19f042a8cc90f5a4ebf33edc936eaf7d72bb7e5e
cursor/aud-0054-review-0db0 | tip 78ee3ccd7672c6836492aea603659bc9384a1bc5
cursor/aud-0055-impl-0db0 | tip e04c2e6840587d248bfa9086d96ed1664bb21323
cursor/aud-0055-review-0db0 | tip 5f0593cba9ded19496e25e1000af3082fc959d90
cursor/aud-0056-impl-0db0 | tip ad003558b0f18a0bace299457bfd81af5be120fe
cursor/aud-0056-review-0db0 | tip fd80b4145772e461a987e96fa201b64c25dcd018
cursor/aud-0057-impl-0db0 | tip 115c7c337065ca2a7f7c3949a2787961247eeeab
cursor/aud-0057-review-0db0 | tip b4c8e0653c9293f2f132445af68bffbd78f4b337
cursor/aud-0059-impl-0db0 | tip 52af12f7505e5f933a07f30c9c88413d01fd2785
cursor/aud-0059-review-0db0 | tip 05465b27d6f597bdc314d607c860d7c87b30f343
cursor/aud-0060-impl-0db0 | tip c678aaa35f35748d3ae888768a993e5982748f61
cursor/aud-0060-review-0db0 | tip d855c16de924e7ecad49668dd4a931b15c799ba3
cursor/aud-0061-impl-0db0 | tip cf53dccb3e85b9329a6f4609d861b60bccc9503a
cursor/aud-0061-review-0db0 | tip 8355803fe99276a232c92dc2e83e0e3431bdf408
cursor/aud-0062-review-0db0 | tip a0b9b1519919e4f54096d8140e3d9dafb8655d08
cursor/aud-0064-remedi-0db0 | tip c16688da1a3c593dc0b9dfc938c1a15600d527bb
cursor/aud-0064-rereview-0db0 | tip 15eddd5b5ac8028fa3ec6122b23afe36b7e2e34f
cursor/aud-0064-review-0db0 | tip edafb98902c87a709ea9f17a297a0079ee2f56da
cursor/aud-0074-impl-0db0 | tip 596d66af53400b101c7193726875602c423ae03c
cursor/aud-0074-review-0db0 | tip f6f6e2d55830332bd75ae4f4ffc7eb3e392da9b9
cursor/aud-0080-review-0db0 | tip 92d93b6c5b8a964ac7aae1efedd9a13b9e5bcfd7
cursor/aud-0081-claude-review-0db0 | tip 3e384d1f425aca07d800a4bdc1cbc8e962fd731c
cursor/aud-0081-codex-review-0db0 | tip 03996b0da4259206a756f6a2443d8e67af6afa79
cursor/aud-0081-impl-0db0 | tip 8f5545043fa097c523c911266cd6cc843798a579
cursor/aud-0083-impl-0db0 | tip c72d82f152ee7faf23e1212b80a88c6bbef610c5
cursor/aud-0083-review-0db0 | tip 7eba520e0663b890b201255a6311a97c0b820eed
cursor/aud-0091-impl-0db0 | tip 0cc1beeaf900ce3a934f9fb6c2deade0720723d4
cursor/aud-0091-review-0db0 | tip dc218ef2766a255e14f1d48bdc033025170deb14
cursor/aud-0094-impl-0db0 | tip aa38775252d6e51df58eb86f3beb5903de76cdde
cursor/aud-0094-review-0db0 | tip dda74616f710cd9991cfe259ef1ac90dc72f0449
cursor/aud-0096-impl-0db0 | tip 5593b0d6b5228dff0b3e15f5d3828e79c8ab59f2
cursor/aud-0096-review-0db0 | tip d54c01cf0341f04a53ae5b0781230874b8cdcf94
cursor/aud0031-independent-review-3dad | tip eead798af918f34c6efa42d1fc184a4125162f77
cursor/aud0047-independent-review-0b16 | tip f25aa3a4ffef5362f93e11bf74c12d9c20dd0a1b
cursor/aud0048-independent-review-743c | tip 4f9247ec49705262e163faff1db792217c92594b
cursor/cc-0004-review-0db0 | tip 8f6f5d13cb2a1dc2fd457e77a2c540ef08cf62a4
cursor/cc-0006-impl-0db0 | tip e9494ad4114745000b773d8ef03cec623dceb064
cursor/cc-0006-review-0db0 | tip 35d0b5c73ca214e0bef7cf6a86daaf7c719c589e
cursor/cc-0008-independent-review-483b | tip 549f3b5f5e220b4acc76d5ed53b972053e15e7f2
cursor/cc-0012-independent-review-0db0 | tip 42988bc195faaef196d0b82e601059d0e8fdc619
cursor/cc-0014-independent-review-0db0 | tip 6890c30eb8ce92c03f8646a160f0c18e695193f7
cursor/cc-0016-impl-0db0 | tip 2177a20948229340235f7f74ec66f4ac05de3d78
cursor/cc-0016-review-0db0 | tip fca90e365c8d686f9dab6e389084f898b312f703
cursor/cc-0017-impl-0db0 | tip eb48fe78421bd70b87ac310a070793bc8132aaf2
cursor/cc-0017-schedule-review-0db0 | tip 6d187098f4d1c599498aba55b7883df97c73c2b2
cursor/cc-0017-schema-review-0db0 | tip 9b566e3e1c2bfbaf43902c2925055b0cb14213e0
cursor/cc-0018-adversarial-rereview-0db0 | tip fa415c7120b7cb7e3e50c521f0320cbe09063f97
cursor/cc-0018-adversarial-review-0db0 | tip 2d5e34fa22b107d55856f4bd93d5fa3a00473ead
cursor/cc-0018-impl-0db0 | tip 69f5f373e46cab1434ef0304f9b746a09907ef4d
cursor/cc-0019-impl-0db0 | tip cf387788f3236e704e6ce5459a8288380df4fea4
cursor/cc-0020-impl-0db0 | tip eb44536bed6ac95043bc52ca4ac4d32f8da507a2
cursor/cc-0020-review-0db0 | tip a6f51cf8f395dbcc324877cf50c7957b002318e8
cursor/cc-0021-impl-0db0 | tip 59bf8ee332d5c0778789d46f8f520a9b33f05e52
cursor/cc-0021-review-0db0 | tip 8aab31afdbf708212b495cc85ac57ad6325d1d07
cursor/cc-0022-impl-0db0 | tip 297a9b8cafc778e18e0acb03525fe9dbc6184023
cursor/cc-0022-review-0db0 | tip 56f8e6e2e3b8b1cee53e9aff7bd71ce439ab0c6d
cursor/cc-0023-impl-0db0 | tip 8db8e79d59a734f001cf6e996652086e45f93be6
cursor/cc-0023-review-0db0 | tip 3b110b2f05f1eb501ab05b9d8c8b985eb16a6853
cursor/cyber-suite-full-program | tip 4878e9dbff7a6c67d293cda12c51391214390e61
cursor/fix-312-lineage-path-0db0 | tip 714275ecff46f0ec2386c285f411313d981ccb45
cursor/fleet-autonomy-pointer-4739 | tip 2d6c1bcc806e6e368e1f847dd5fcaf7eda7d11bf
cursor/imp-0002-adversarial-review-0db0 | tip a2fe3eb5763f9bdcca55f7f6f63812023b497915
cursor/imp-0002-blocked-impl-0db0 | tip c3b82eb6c3aca55c5cc32b60350f29f333ca0121
cursor/imp-0003-adversarial-review-0db0 | tip 47c78f193c74bdf594661b7b5ce425c34938edc6
cursor/imp-0003-blocked-impl-0db0 | tip c562782b2ddc6d72f227306372945906e3e961e5
cursor/imp-0004-adversarial-review-0db0 | tip ad089dee10c543c0a94a9e1df79d8ec7856da774
cursor/imp-0004-blocked-impl-0db0 | tip 3c6300dc596533ce2360076b409261bd7033bc3f
cursor/imp-0004-evasion-r2-0db0 | tip 7f95771ddb0284613fea66f3d3bf58bc6d023f0d
cursor/imp-0004-evasion-r3-0db0 | tip 22bbc6259a8d3b61c9f662becf57fbc42701210d
cursor/imp-0005-adversarial-review-0db0 | tip 0317450db6e310153a10593c534ac580bacd2f5e
cursor/imp-0005-blocked-impl-0db0 | tip 2c2cbebabf2449e03d7845956207529086621ebf
cursor/imp-0006-adversarial-review-0db0 | tip c29b81dfcb8a93e0dd4ea4f2182a3df1a115c5e0
cursor/imp-0006-blocked-impl-0db0 | tip 06226ef5a9eba1680801cd4cf7084fb8e2fc69e0
cursor/imp-0007-blocked-impl-0db0 | tip cc19566df762acff658b2ac2aa275a5806af5aae
cursor/imp-0007-frozen-key-review-0db0 | tip 619a854f94164a45d4defd47a91e6a3bc1c539f1
cursor/imp-0009-blocked-impl-0db0 | tip 97e8b64a9e829026bc775d5c894c1c95076e7831
cursor/imp-0009-duplicate-preserve-review-0db0 | tip 468d65f8d8ecf15d648899b4f002e297cf76f6d1
cursor/imp-0010-blocked-impl-0db0 | tip 2aa9bd0e98ed64cac33b1c3cc08a9ab2daabe900
cursor/imp-0010-consumes-generators-review-0db0 | tip a5681c5b3a26bb76c62ac4bf7041a73533f18b2e
cursor/imp-0017-adversarial-review-0db0 | tip 7c614b7bbdf6dc9c1cefa3de49c3af95fbaebfac
cursor/imp-0017-blocked-impl-0db0 | tip 92569e7f877194a8622d01f207051eae8d1a4ea2
cursor/imp-0022-blocked-impl-0db0 | tip 31b5ae15a7dc545a200b04adfddb002a2bf285f2
cursor/imp-0062-blocked-impl-0db0 | tip 1fcdb4fcf560fe12ffdf3ff3932341d0805d9ea4
cursor/imp-0062-vendored-rep-review-0db0 | tip c2fee3e15827edf41cd215d543b4b6abe3e6598c
cursor/imp-0436-adversarial-review-0db0 | tip 77a363bc0987ae3286e9b4772a940dce582210ad
cursor/imp-0436-impl-0db0 | tip a562373bfbc0d83625c38e42cc03cf88b90890a4
cursor/imp-0436-schema-review-0db0 | tip 608c594447958a2a2ee97626877e64766ad0ab7a
cursor/imp-0437-impl-0db0 | tip ae0c13f700c2ca2c00f21150eda209f0e2423b7d
cursor/imp-0437-review-0db0 | tip 8ded1f7e29deba5dd9e7937de2d454bd7b7c29b7
cursor/imp-0438-adversarial-review-0db0 | tip bcd25fd7930517a8910b4b1f2ee8ee5924866402
cursor/imp-0438-impl-0db0 | tip 7dbd68c4a6e27a9abbb2a104e6e2dcb70ea57a2d
cursor/imp-0439-independent-review-0db0 | tip 286ae4708811d46feca00b93dcc97af6202dd7ce
cursor/imp-0456-impl-0db0 | tip 7b7c469a1398c258bc1c8df600ff64e337df79de
cursor/imp-0456-independent-review-0db0 | tip 6b932ef690b3504cc405564e202210d80e356401
cursor/maintainer-session-2026-09-06-0db0 | tip c7c186b778f2dbc094f08dca8327b97490d5e648
cursor/search-stack-reunion-self-hosted-9cde | tip 46f6dd2ee86986d24ad299e8788a1cee6e800151
cursor/system-resource-hygiene-4a5e | tip 80861fafe8d192721686588c146b2500a81507ad
cursor/tst-0328-independent-review-0db0 | tip a9eacfe15dfcfcdfe5de96f3687ce535e2edccfe
cursor/tst-0329-adversarial-rereview-0db0 | tip 352b1fd6f3504c9eac89b912d486b3bfd922caf9
cursor/tst-0329-adversarial-review-0db0 | tip 0b617ebb5e5ca1f47982138cb703e6eca2ed9589
cursor/tst-0329-blocked-impl-0db0 | tip d7766c5400ec4ff019f2b8aefed89bcba2399427
cursor/tst-0331-adversarial-review-0db0 | tip b8a548cbe24434e4e1fbee04611567c51b0cbbfd
cursor/tst-0331-blocked-impl-0db0 | tip fa123c84376ad19234c190ea48cc940cd127e5ff
cursor/tst-0341-adversarial-rereview-0db0 | tip 6f5f3e103c20c831d4f4d165c36d067d65a0514d
cursor/tst-0341-adversarial-review-0db0 | tip 81b9f99f8300d1e2dc63b4c3c7a211ce7f911e70
cursor/tst-0341-impl-0db0 | tip 8b6de658ca1b325c9178ffa2b4d9479c3aa9cdcf
cursor/tst-0348-adversarial-review-0db0 | tip 70e11271754394a9de90166572f7b160b02de7c7
cursor/tst-0348-blocked-impl-0db0 | tip a45d70e4694b97c590449dbdaa1b93edb1545a80
docs/mirror-runbook-warnings | tip 44ef09cd9e6f0e38036c19035ab902c9c320407b
fix/deny-credential-gaps | tip d3def686983907b2d2d2468323011f0c0e28bd47
fix/grok-sensitive-artifact-stop-loop-preserve-20260929 | tip d750e82511e6e2ebadebc2ad43b294dd36c9db84
gemhunt/hosted-models-00-consolidated | tip 76c56669a8d4b4f293b4111f42f339e83e3c5c2a
gemhunt/hosted-models-01-native-capability-audit | tip 2f57b44823ef7f2de1cc9cbaa6aefc6c38c33646
gemhunt/hosted-models-02-huggingface-inference-surfaces | tip 6d6dc816a2acd70eed985a0c5a18afa6cc8cc366
gemhunt/hosted-models-03-openrouter-sidecar | tip b492d8437533460e2e334c9159d2e93f5a227901
gemhunt/hosted-models-04-local-inference-ram-budget | tip 03b249d785e8181ce6d13e9a00915d2a13ebed00
gemhunt/hosted-models-05-competitive-teardown-provider-registries | tip c17629836102374c086e4a6969010d5c94c72a51
gemhunt/hosted-models-06-models-registry-ssot-design | tip d4ec5ea5a26f5542b3253a710779c9f1dda115c2
gemhunt/hosted-models-07-generic-inference-mcp-tool | tip 75f66af2edd534cf7cf053a5c3a05e2dfc3b7e12
gemhunt/hosted-models-08-eval-harness-and-autoresearch | tip 89f0799de5326183ec0216b9f2074b3204d76ae6
gemhunt/hosted-models-09-security-governance-hosted-models | tip daad24fc75eec01c4dbde6ae1564a110c3bffa68
gemhunt/hosted-models-10-cross-domain-borrows-wildcard | tip 7c8d48a5d74cf742811c966d733df07d371fa3a5
gemhunt/hosted-models-11-prune-and-consolidate | tip 69b2807db9e9fb04311fedfc54ed81da11f69e68
gemhunt/hosted-models-12-peers-and-parallelism | tip 5e1ba76d93b15a3ad51c120b5024b8f19dafc3d0
gemhunt/hosted-models-13-skills-mcps-in-the-wild-and-meta | tip b300489a43b998128526de9eb1a15307fb15f88a
grill/qwen38-heretic-space-2026-09-19 | tip 9e7211acf2eeeca566ee83fe1bc247b9f6503625
home/local-state-2026-09-25 | tip 05b282825e01378a7c18a9f369957af3d88b125f
imp0014-darwin-probe | tip 6d1938ccf5f324f0dce9b8e8e05599484035ba0d
import/agents-fullstate-2026-08-28 | tip c3cde97bd6d807800a1f6201c126f55915f6c247
live-capture/2026-09-02 | tip 95f2fd21087ce9dd7c124a24eda5688ba379bcb8
p2-loop-to-green | tip a49fdf879115e5e5dea1d7cf2db5413f2d7d6d65
p2/loop-to-green-2026-09-02 | tip 44c54b68fb429d4f60a6d38554257bf5009a09fa
remove-gitcrypt-v2 | tip 03b28e33d2d8e792803dd850683f041b3f503aca
rescue/chore/statusline-gotchas-and-goal-short-20260724-preserve-20260929 | tip ace747b14cef87254725955e78b9184e3207fa20
rescue/w2-c16-error-taxonomy-preserve-20260929 | tip 318565b1dc989db650d5783aabe8d3905145d6d5
skill/gcp-compute-foothold-20260929 | tip e41b033a283bbd87ae90fd6f1c1045439af115d9
test/deny-credential-denylist-coverage | tip 90b7b39cbb9e8a5fa5b2fcebf88c988ed28ad20c
vm/offload-w2025-2026-09-29-offensive-stack | tip f859761029e54f027c8c8d0d0a1f94ebdc3cf160
wave3/ci-trigger | tip 97ea5eab3094cd22c9c535a171fff8c32945d33d
wave3/command-center | tip 589d5422568450b5274f92ff0539155a512e6326
wave3/monitor | tip a8e8c2d062a0512253e4c63954380e7f97b2dfb3
wave3/program-b | tip e3245cea3a216f343095840b02a8f03382764811
wave3/skill-gate | tip 147a2813bbb06b2fe0bb228eaa7491237b3fa70e
wip/harness-additions-2026-08-28 | tip f9fa65821454735b73098148d79ba3735c224684
