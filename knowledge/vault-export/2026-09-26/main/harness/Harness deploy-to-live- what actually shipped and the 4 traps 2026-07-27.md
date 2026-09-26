---
title: 'Harness deploy-to-live: what actually shipped and the 4 traps 2026-07-27'
type: reference
permalink: main/harness/harness-deploy-to-live-what-actually-shipped-and-the-4-traps-2026-07-27
tags:
- harness
- deployment
- drift
- hooks
- secret-gate
- traps
- windows
---

# Harness deploy-to-live: what shipped, and the 4 traps (2026-07-27)

Brought the live `~/.claude` harness up to `origin/main`. Hook suite went **36 failed -> 3 failed**
(694 passing, 2 xfailed). Live dispatcher smoke-tested clean afterwards: `dispatch.py stop` rc=0
in 383 ms, no traceback.

## What shipped

| change | effect |
|---|---|
| `per-edit-check/check.py` (**PR #211**) | the write-path **secret gate now exists live**. Was 9,546 B with ZERO `_scan_secrets`; now 15,378 B. Blocks rc=2, docs samples exempt, `PER_EDIT_SECRETS=off` works, and the reason never echoes the credential — all four verified. |
| `tool-result-sentinel/sentinel.py` (#198) | HTTP 200 was read as `exit code 200`, inverting every successful fetch. 6/6 both-states. |
| `stub-ledger/stubscan.py` (**PR #230**) | wrapped-comment false positive. |
| `_dispatch/manifest.json` (#210) | adds the `dark-surface` Stop check — the ONLY manifest delta. |
| `_dispatch/test_manifest_presence.py`, `memory-spool/test_replay.py`, `test_wiring.py` | Wave-3 fixes (#210/#212/#214). |
| 16 new files | incl. `cmd-rewrite/msys_pathconv.py`, `_shared/hookrun.py`, `failure_taxonomy.py`, `harness-bench/gate.py`. |
| `_shared/use_vs_mention.py` +56 lines | closed a skew I had created by deploying its dependents first. |

## THE 4 TRAPS (all self-inflicted; each cost a wrong claim)

1. **Compare CODE lines, not bytes.** `sessionstart-replay.py` looked undeployed at 4230 vs 4326
   bytes; by code lines it was IDENTICAL — comments only. I called it stale and was wrong.
2. **Never deploy a test without its subject.** Hit THREE times: `test_secrets.py` without
   `check.py`, `test_eval.py` without `eval.py`, `test_manifest_presence.py` without
   `manifest.json`. Each produced phantom failures that looked like regressions.
3. **A deploy tree is a RUNTIME target, not a repo mirror.** `_shared/test_manifest_provenance.py`
   asserts `.provenance/` and `.github/workflows/quality.yml` — repo structure that cannot exist
   in `~/.claude`, so it can never pass there. Removed.
4. **Audit non-`.py` files too.** My first audit covered only `.py` (193 files) and missed
   `manifest.json`, `hooks.json`, corpora, router indexes — 6 differ, 1 missing. `manifest.json`
   is what drives live dispatch.

Plus a 5th, repeated all night: **`/tmp` from Git Bash is NOT `/tmp` from Windows Python**
(resolves to `C:\tmp`). It produced a false "repo manifest has 0 checks" reading that would have
looked like deploying it would wipe all 22 dispatched hooks. It would not have — the manifest
delta is exactly one addition.

## Classification that made it safe

By CODE lines, per file: `IDENTICAL` / `LIVE-STALE` (repo strict superset -> deploy) /
`LIVE-AHEAD` (never overwrite) / `DIVERGED` (merge by hand) / `MISSING` (additive).
Result: 158 / 8 / **0** / 11 / 16. The old "7 LIVE-AHEAD, never overwrite" note is now STALE —
there are currently zero.

## Still open

- **3 real live-config findings** from `test_wiring.py` (NOT stale tests): duplicate PreToolUse
  dispatch entries in `settings.json`, a script wired both in the manifest AND standalone, and an
  unadopted conformance gate.
- `semantic-router/eval.py` is genuinely LIVE-AHEAD (10 unique code lines) — needs a real merge.
- `surface_reconciler.py` missing from `~/.agents/harness`.
- `hooks/hooks.json` missing live; 6 non-py files differ.

## The basic-memory question, answered

Deploying did NOT change it, because nothing was broken. `precompact-basicmemory/capture.ps1` is
live and PreCompact is armed; `memory-spool` (spool/replay/flush_check/_common) all import fine.
**No hook prompts a proactive semantic write** — PreCompact only snapshots at compaction. That is a
missing FEATURE, not a regression. See
[[always-write-durable-memory-to-basic-memory-not-the-ledger-or-auto-memory]].

Related: [[live-harness-drift-vs-main-mcp-scope-conflict-resolution-2026-07-27]] ·
[[claude-desktop-repair-the-code-tab-config-truth-2026-07-27]]
