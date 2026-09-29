# PR conflict surface, measured — 2026-09-29

Scope: all 28 open PRs on `Prekzursil/agent-skills-toolchain`, plus the remote-branch
prune executed the same day. Method and instrument bugs are recorded because one of them
produced a confidently wrong first answer.

## Method

`git merge-tree --write-tree <base> <head>` per PR. It computes the merge in the object
database and never touches the worktree or index, so it is safe to run while other work is
in flight. Verified after every run: `git status --porcelain` tracked-dirty count unchanged.

Conflict surface is counted in **conflicted files**, not lines, per
`rules/common/stale-megapr-reconcile.md`: added files never conflict, so a +1,571-file PR
can have a 2-file surface.

## Instrument bug found and fixed (v1 was wrong)

v1 measured every PR against `origin/main`. That is the wrong base: this repo has **11
stacked PRs** whose `baseRefName` is another feature branch. `#333` targets
`cursor/p2-loop-to-green-0db0`, and `main` is **67 commits** beyond that base — so v1
reported `#333` CLEAN while GitHub correctly reported `CONFLICTING`.

v1 "disagreed" with GitHub on 5 PRs. After fixing the base, agreement is **28/28**. The
disagreement was entirely my bug. Recorded because a wrong-base merge check is
indistinguishable from a real clean verdict unless the base is asserted.

## Result

| | count |
|---|---|
| open PRs | 28 |
| targeting `main` | 17 |
| stacked on another feature branch | 11 |
| merge with ZERO conflicted files | 17 |
| conflicted | 11 |
| agreement with GitHub `mergeable` | 28/28 |

### Shared conflict files — fix once, unblocks several

| file | PRs |
|---|---|
| `.agents/agents.json` | #318, #314, #310 |
| `.agents/tests/test_mcp_control_plane_live.py` | #318, #314, #310 |
| `osv-scanner.toml` | #362, #325 |
| `tools/mcp/hacktricks-mcp-server/package-lock.json` | #362, #325 |

Three reconcile clusters, not eleven independent jobs:

- **Cluster A** — `#310 #314 #318`, identical 2-file surface (`agents.json` +
  `test_mcp_control_plane_live.py`). Per `fan-out-contract.md` C3, check whether the
  overlapping content is byte-identical; if one PR contains another's work, the second
  merge is a no-op and they stack.
- **Cluster B** — `#362 #325`, `osv-scanner.toml` + the hacktricks lockfile. Both are
  ~1,500-file PRs whose real surface is 2 and 5 files.
- **Cluster C** — the stacked p2-wave PRs `#326 #327 #330 #332 #333`, each conflicting on
  its own `command-center/p2-wave/probes/IMP-*/` artifacts plus
  `command-center/receipts/IMP-*.json` and `_pack_receipt.py`. These are generated
  artifacts; resolve by regenerating on the merged base, not by hand-picking lines.

## Why nothing was merged

`main` is **not** protected by classic branch protection (`/protection` → 404), but an
active ruleset named **`main quality gate`** (target `branch`, enforcement `active`) is
what produces `mergeStateStatus: BLOCKED`.

Whether each PR satisfies that gate is **UNVERIFIED and unverifiable with the current
credential**: `gh pr checks` and `GET /commits/<sha>/check-runs` both return
`403 Resource not accessible by personal access token`. The detector was controlled — the
403 reproduces on a known-present commit, so this is a token-permission limit, not an
absence of checks.

Merging 17 PRs while blind to their gate status would be a budget-aborted gate treated as
green, which the verification doctrine forbids. Conflict-freedom is measured; merge
readiness is not. The fix is an owner action (grant the fine-grained PAT `Checks: read`);
agents do not touch credentials (AGENTS §9).

## Branch prune, same day

23 remote branches deleted under four guards: G1 merged into `origin/main`, G2
`rev-list --count origin/main..<b>` == 0 re-verified independently, G3 cross-checked
against 28 open PR head refs (deleting such a branch closes its PR), G4 name sanity.
Dry run: 23 SAFE / 0 held back.

**The prune's own success metric was broken.** It reported
`remote refs before: 231 -> after: 262 (delta 31, expected -23)`. A count rising after
deletions is self-contradicting, so it was the instrument: `git fetch --prune` *discovered*
remote branches never previously fetched into `refs/remotes/origin`, inflating the count
while the deletions succeeded. Verified against server truth instead —
`git ls-remote --heads origin`: 6/6 spot-checked branches absent, `main` control still
resolves, 261 heads remain. Count local tracking refs to measure a local prune; count
`ls-remote` to measure a remote one.

## Residuals

- `L-52` the PAT cannot read check runs, so PR merge-readiness stays unverifiable.
- `T-10` the three reconcile clusters above.
