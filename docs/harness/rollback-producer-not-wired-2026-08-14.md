---
title: rollback-producer-not-wired-2026-08-14
type: note
permalink: dqverify-repo-20261013/docs/harness/rollback-producer-not-wired-2026-08-14
---

# `/rollback` cannot work on this box — its producer is deployed but not wired

`commands/rollback.md` promises to list edit-checkpoints for the session. On this machine it
would always find nothing, and the reason is one line in a stale file.

This closes a long-standing open loop recorded as *"`commands/rollback.md` reads a checkpoint
index that no wired hook writes"* — the "consumer with no producer" defect the hook audit
opened with. It is **not** that the producer is missing. It is that the live dispatcher has
never been told about it.

## Measured

| | repo `hooks/_dispatch/manifest.json` | live `~/.claude/hooks/_dispatch/manifest.json` |
|---|---|---|
| SessionStart | 6 | 6 |
| Stop | 9 | 9 |
| PostToolUse | 5 | 5 |
| **PreToolUse** | **7** | **5** |
| file mtime | 2026-08-14 06:06 | **2026-08-12 11:08 (2.0 days stale)** |

The two PreToolUse entries present in git and absent live:

* **`edit-checkpoints`** — the `/rollback` producer
* **`mcp-liveness/pretool`**

Zero entries are live-only. `python command-center/probe_hook_manifest_drift.py` agrees
independently: `in git, NOT deployed: 2` · `deployed, NOT in git: 0` · `same hook, behaviour
differs: 1` (Stop `git-hygiene`, timeout live=90 vs repo=30), with its detector control
reporting `25 live checks across 4 events` rather than a silent zero.

**The hook code IS deployed** — `~/.claude/hooks/edit-checkpoints/` exists. Only the manifest
entry is missing, so the dispatcher never calls it. The hook is dormant, not absent, which is
why every "is the hook installed?" check would answer yes.

## The chain

1. `commands/rollback.md:4` — *"The `edit-checkpoints` PreToolUse hook snapshots the pre-edit
   state once ... `refs/claude-checkpoints/`; non-git paths: a file copy"*
2. `commands/rollback.md:18` — *"read the checkpoint index and present options"*
3. `hooks/edit-checkpoints/checkpoint.py:102,112` — writes the state file and appends the index
4. the live manifest does not list `edit-checkpoints`, so step 3 never runs
5. `/rollback` reads an index nothing writes

## Correcting the synthesis lane's B4 sample

`command-center/GRIND-STATUS.md` B4 reports "21 HAZARDs" and samples them as *"`PreToolUse`
repo has 12 entries, live has 13 (live-only `workflow-monitor-autolaunch/check.py`)"* and
*"`UserPromptSubmit` repo has `open-loops/trigger_match.py`, live has `semantic-router/route.py`"*.

**REFUTED on both counts, measured:** PreToolUse is **7 repo / 5 live**, not 12/13; the
difference runs the *other* way (git has more, not live); `workflow-monitor-autolaunch` appears
in **neither** manifest; and there is **no `UserPromptSubmit` event at all** in either file —
both carry exactly four events (SessionStart, Stop, PostToolUse, PreToolUse). The lane itself
graded that row `uncertain (20-55%)` and said it had not triaged the findings, so this is the
triage it asked for rather than a contradiction of a confident claim.

Method note, because the first attempt got it wrong: reading the roster with `c.get("module")`
returns `None` for every entry — the key is **`name`** (`args, emits, matcher, name, script,
timeout`). A substring search over those `None`s finds nothing and looks exactly like "no
drift". The counts are what exposed it, and the corrected reader confirmed it.

## What to do, and what NOT to do

**Recommended (owner):** deploy the repo manifest over the live one. The repo is SSOT per
`rules/common/harness-vcs-hygiene.md`, the hook code is already present live, and the change
arms two hooks plus a `git-hygiene` timeout of 30 s instead of 90 s.

**Not done autonomously.** Arming a `PreToolUse` hook changes behaviour on every edit, on a box
with concurrent sessions running, and it could not be CI-verified (Actions has been unable to
start a job since 04:33:59Z).

> ⚠ **Do NOT run `scripts/sync-from-live.ps1` to fix this.** It carries **live → repo**. Run
> now, it would copy the 2-day-stale live manifest *into* the repository and **delete
> `edit-checkpoints` and `mcp-liveness/pretool` from SSOT**, converting a deploy gap into
> permanent data loss. The needed direction is repo → live.