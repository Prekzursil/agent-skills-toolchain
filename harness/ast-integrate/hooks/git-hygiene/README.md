# git-hygiene — no local work is left abandoned or unpushed

A **Stop** hook (`check.py`) plus an on-demand survey (`scripts/repo-sweep.ps1`) that answer
the owner's ask directly: *"always make sure no local gits are left abandoned and that harness
improvements aren't left stale or abandoned and are always committed and pushed to the toolchain
repo."*

The repo previously shipped only **repo → live** sync scripts, so live-authored harness work
could never reach version control — 462 files / 2.73 MB were architecturally orphaned until
`scripts/sync-from-live.ps1` closed that half. This hook makes the *remaining* gap visible: work
that sync **would** carry but that hasn't been committed, and repos that hold uncommitted or
unpushed work.

## Why the classifier — not the scan — is the whole job

Measured on this box 2026-07-18: **329 git repositories, 175 dirty, 111 with no upstream.** Almost
none of it is yours to act on:

| population | count | verdict |
|---|---|---|
| third-party clones under `~/.claude/plugins/**` | 258 | VENDORED — dirt is the expected steady state |
| detached scratch worktrees `~/.claude/agent-worktrees/*` | 20 | EPHEMERAL — auto-reclaimed, all 0 dirty |
| no-remote `temp_subdir_*.clone` husks in the plugin cache | 8 | VENDORED — position beats provenance |
| dirty third-party repos (insta-mcp, hexstrike-ai, mcp_agent_mail, …) | ~37 | VENDORED — foreign origin |

A hook that reports those emits ~175 lines of noise and **gets disabled within a day, which is
strictly worse than no hook.** So the code spends its complexity on telling YOURS from VENDORED.

### Ownership classes (order is load-bearing: position beats provenance)
- **YOURS** — origin owner matches (`Prekzursil`). Reported when it holds real risk.
- **NO-REMOTE** — a real repo with no remote at all. Highest severity: it exists only on this
  disk. 4 measured (fb-messenger-mcp, openmm-md-mcp, schrodinger-mcp, tiktok-mcp).
- **VENDORED** — someone else's clone (foreign origin, **or** nested inside another repo, **or**
  in a plugin/dependency cache). Never reported. Dirt here is normal.
- **EPHEMERAL** — agent scratch worktree. Never reported.

A clone nested inside your repo, or in the plugin cache, is VENDORED **regardless of its origin** —
the 8 husks have no remote, so grading them on provenance first would file them under NO-REMOTE
and let them dominate the report.

## The two external signals (neither authored in-context)
1. **`git status --porcelain=v2 --branch`** per discovered repo — branch, upstream, ahead/behind,
   dirty count, and unborn/detached state, in one call the model cannot fake.
2. **Live-tree vs repo size comparison** across the exact `sync-from-live.ps1` map
   (`~/.claude/{rules,agents,commands,hooks}`, `~/.agents/skills`, and the named loose files) —
   what sync would carry that the repo lacks. It points at `sync-from-live.ps1 -Drift` for the
   authoritative diff.

## Behavior
- **INJECTS** `hookSpecificOutput.additionalContext`; **never blocks** (AGENTS.md §6). There is
  no code path that returns exit 2 — blocking a Stop on uncommitted work would be maddening.
- Silent when nothing you own is at risk. Bounded to ≤16 lines; says how many rows it suppressed.
- **Fail-open**: any exception, malformed stdin, or missing git → silent exit 0.
- **Budgeted** (`GIT_HYGIENE_BUDGET`, default 8s; measured 3.7s warm / 5.6s cold). If the budget
  expires the drift count is labelled a FLOOR — a partial count is never reported as complete.
- Per-repo git reads run 8-wide (threads); the first serial version took 63s and was unusable.

### Environment
| var | effect |
|---|---|
| `GIT_HYGIENE=off` or `hooks/git-hygiene/.disabled` | disable entirely |
| `GIT_HYGIENE_OWNER` | github owner treated as YOURS (default `Prekzursil`) |
| `GIT_HYGIENE_ROOTS` | `os.pathsep`-separated scan roots; **set-but-empty = scan nothing** (used by the tests) |
| `GIT_HYGIENE_SYNC=off` | skip the live-tree drift half |
| `GIT_HYGIENE_REPO` | toolchain repo root for the drift comparison |
| `GIT_HYGIENE_BUDGET` | wall-clock seconds the whole check may spend |

## repo-sweep.ps1 — the on-demand full picture
```
pwsh -File scripts/repo-sweep.ps1          # actionable rows only, summarised by class
pwsh -File scripts/repo-sweep.ps1 -All     # include VENDORED + EPHEMERAL
pwsh -File scripts/repo-sweep.ps1 -Json    # full survey as JSON, for scripting
```
**Strictly read-only** — runs only `status`, `config`, `rev-parse`, `branch`; it never pushes,
commits, stages, resets, checks out, or deletes, and writes no file. Two independent tests enforce
that: a behavioural one that hashes the whole tree + every HEAD before and after, and a
mention-aware static one that rejects any mutating verb in command position (the recommendation
strings legitimately contain the text `git push`). Per-repo reads run via
`ForEach-Object -Parallel -ThrottleLimit 8` — 133s serial → ~7s.

## Registration (settings.json — a human runs this; deploy is out of scope)
This hook runs **in-process** via `_dispatch/dispatch.py` + `_dispatch/manifest.json`, like the
other Stop scanners. Add to the `Stop` event's `checks` array in `manifest.json`:
```json
{ "name": "git-hygiene", "script": "git-hygiene/check.py",
  "args": [], "emits": true, "isolate": null, "side_effect": "none",
  "slow": true, "timeout": 20 }
```
`slow: true` matches `wire-check` (the existing slow Stop check); the 20s timeout covers the 8s
budget plus git spawn overhead. It emits the standard `hookSpecificOutput.additionalContext`
envelope the dispatcher aggregates.

## Files
```
hooks/git-hygiene/
  check.py                 — the hook (survey / classify / scan_sync_drift / build_message)
  test_git_hygiene.py      — 31 tests: classification, measured-noise populations, genuine
                             finds, KNOWN-POSITIVE controls, sync-drift, hook contract, message
  README.md                — this document
scripts/
  repo-sweep.ps1           — the on-demand read-only survey
  test_repo_sweep.py       — 15 tests (pytest-driven, drives the real .ps1 through pwsh):
                             classification, read-only proof, mention-aware verb guard, UX
```
