---
title: PrimariRo finish workflow wf_549c7956-0a3
type: note
permalink: main/projects/primariro/primari-ro-finish-workflow-wf-549c7956-0a3
tags:
- primariro
- workflow
- ultracode
- session-state
---

# PrimariRo finish workflow — wf_549c7956-0a3

Session state as of 2026-08-01 ~00:40 local. Repo `C:\Users\Prekzursil\Documents\GitHub\PrimariRo-atlas-build`, branch `atlas/scope1-integration`, PR #6 → main.

## Commits landed this session

- `737aef1` fix(app): combobox keyboard-active option scroll-into-view. Both-states verified (pre-fix FAILS, fixed PASSES).
- `9580679` test(private-leak): stop the shell-fallback guards passing vacuously on Windows. Both-states verified. Also added `scratchpad/` to `.gitignore`.

## Two durable technical findings (generalise beyond this repo)

**1. Relocating an MSYS binary onto a stripped PATH makes it exit 127.**
Tools in `C:\Program Files\Git\usr\bin` load `msys-2.0.dll` from their own directory. A symlink
OR a plain `.exe` copy into another dir → 127 for git, tr, grep, rm, sed, cat (all measured; all 0
on the inherited PATH). The fix that works: a `#!/bin/sh\nexec "$REAL_X" "$@"` shim — no DLL of its
own. Any test that builds a minimal-PATH bindir on Windows must use shims, not symlinks.

**2. A gate whose own NAME contains the asserted keyword can never fail that assertion.**
`test_shell_fallback_blocks_a_diacritic_private_path_without_python` asserted `"private" in output`.
Every failure the hook emits starts `FAILED:private-leak-precommit`, so the assertion held even when
the hook died at `not-a-git-repo` and never reached the guard under test. It passed while proving
nothing. Assert the VERDICT ("staged private-tier path", "blocked"), and add an explicit bail-out
guard that fails if the output carries a known early-exit marker.

## Measured CI-faithful baseline at 9580679

- app: svelte-check 0 · vitest 139/139 · build 0 · verify:build 0 · playwright 30/30
- python (CI's actual command `pytest -q -m "not live" pipeline` + coverage from
  `.coverage-thresholds.json` = 55.98): exit 0, **974 passed / 1 skipped / 2 deselected**,
  coverage **67.80%**.
- NOTE: a bare repo-root `pytest -q` is NOT the CI gate and collects `scratchpad/`. Use the
  scoped command. `pipeline/pyproject.toml` holds the pytest config (`testpaths`, `pythonpath`).

## The workflow

Script `scratchpad/wf-finish.mjs`, run id `wf_549c7956-0a3`, ~130 agents.
Phases: Ground (contract pack) → 4 read-only lanes ∥ pipeline(31 units × triage→implement→2×verify→repair).

Safety model: **disjoint per-file ownership** — 31 units, one file each, so no worktrees and no merge.
Agents are FORBIDDEN from running any build/test (`app/build` and `.svelte-kit` are shared across
concurrent agents → EBUSY + false results). The orchestrator runs gates centrally via
`scratchpad/gates.sh`.

Inputs generated: `scratchpad/ui-audit-units.json`, `scratchpad/units/*.md` (31 briefs +
`cross-cutting.md`), `scratchpad/CONTRACT-PACK.md` (42 KB, independently verified: 16 rootVars +
5 selectors pinned, matches `app/tests/e2e/visual-tokens.baseline.json`).

## Known-stale audit findings (do NOT re-fix)

The 284-finding audit predates `df67cc9`. Already fixed there: `summarizeCounties` O(n·m) bucketing,
search-haystack `WeakMap` memoisation. And `737aef1` fixed the combobox scroll. Triage stage exists
specifically to catch these.

## Deliberately deferred

`data.ts:605-607` module-level `await fetchClientSnapshot()` gates ALL hydration (a confirmed
BLOCKER). Unpicking it converts synchronous exports to stores across every route + 139 tests —
cannot be done concurrently with 30 agents editing those routes. Needs its own serialized wave.

## Owner-gated blocker

Deploy cannot happen until GitHub Actions runs again. Runs Jul 26→29 all died in 3–16s with
`steps=0`. Calibrated 75–90% that this is an Actions availability/billing block, NOT code —
explicitly NOT confirmed, because the annotation is 403-walled to both `gh` and the GitHub MCP
(no fine-grained PAT can carry `checks:read`). A workflow lane is re-deriving this independently.

## Relations

- relates_to [[PrimariRo Code4Ro ingest]]
- relates_to [[Workflow zombie slot starvation]]
