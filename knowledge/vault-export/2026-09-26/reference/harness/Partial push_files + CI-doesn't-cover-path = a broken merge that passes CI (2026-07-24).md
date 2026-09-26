---
title: Partial push_files + CI-doesn't-cover-path = a broken merge that passes CI
  (2026-07-24)
type: reference
permalink: main/reference/harness/partial-push-files-ci-doesnt-cover-path-a-broken-merge-that-passes-ci-2026-07-24
tags:
- github
- push_files
- ci
- merge
- gotcha
- verification
- '2026-07-24'
---

## Observations
- [gotcha] A push_files landing can drop files silently, and a green CI does NOT prove the file set is complete when CI doesn't cover that path. #partial-push — Measured 2026-07-24: the `land-gems` subagent pushed TG-1 (detector-self-test) to its branch via push_files then DIED; only 9 of 12 files landed — the 3 MISSING were the critical ones (`detector_self_test.py` core module, `tests/test_detector_self_test.py` main test, `README.md`). I created PR #182 from that branch, its CI went ALL GREEN, and I merged (c9b56da) → TG-1 on main is BROKEN (core module absent). CI passed because `gate-tests-coverage (python packages)` is scoped to the CHARTER packages, NOT `tools/` — so a new opt-in tool dir under `tools/` is NOT exercised by CI, and a missing module there fails nothing.
- [decision] Before merging a PR that adds files CI does NOT gate (opt-in tools, docs, new dirs outside the coverage scope), VERIFY the pushed FILE SET matches the source — count + names — not just that CI is green. #verify-file-set — Cheap check: `git ls-tree -r --name-only <ref> <dir>` (or get_file_contents on the dir) vs the source worktree's `git diff --name-only origin/main..HEAD`. A push_files result reporting success is NOT proof all files landed (esp. if the pusher died mid-work). Byte-SHA-verify EACH file (get_file_contents sha == local rev-parse) — a per-file loop, not a spot-check.
- [gotcha] `git cat-file -e <ref>:<path>` is the RIGHT existence check (errors on missing); `git ls-tree -d ... && echo EXISTS` is WRONG (ls-tree exits 0 on a missing path). Both used this session; the cat-file one caught the incomplete TG-1. #existence-check

## Relations
- relates_to [[Workflow isolation:worktree mis-targets the repo (2026-07-24)]]
- relates_to [[Use the github MCP for all GitHub ops, not gh-CLI / github_cli (2026-07-24)]]