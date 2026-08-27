---
name: skill-tree-reconcile
description: Use when asked to sync skills, reconcile skill trees, deploy skills to live, choose which tree wins, compare live vs vault vs repo, run sync-from-live, or repair drift - classifies differences and applies a human-reviewed direction.
---

# Skill Tree Reconcile

Use this procedure for "sync my skills", "reconcile the skill trees", "deploy skills to live", "which tree wins", "live vs vault vs repo", "sync-from-live", or "my skills drifted".

## Establish the model

Read `writing-skills` for the full four-tree model. In brief, REPO `.agents/skills` is the source of truth; `scripts/sync-from-live.ps1` writes VAULT `~/.agents/skills` to REPO; `scripts/sync-skills.ps1` writes repo `skills/` to VAULT; and `scripts/deploy-skills-daily.py` writes REPO to Claude LIVE `~/.claude/skills.daily`. The Codex hop is `python scripts/deploy-skills-codex.py`, which delivers only `ci/codex-skill-allowlist.txt` names from REPO to `~/.codex/skills`.

## Reject bulk direction

There is no safe bulk direction. Of 99 substantive LIVE-vs-VAULT text pairs, 95 DIVERGED, 4 were LIVE-supersets, and 0 were VAULT-supersets. Scope this honestly: 41 of the 95 have at most three unique lines per side. DIVERGED means "not a clean superset", not 95 files of two-sided authored work. The heavyweight set is about 20 files with more than 10 unique lines on both sides.

Do not use timestamps. Of 337 LIVE `SKILL.md` files, 136 share one bulk-copy mtime. "Repo commit newer" holds for 86 of 95 differing files, including all eight corrupted files. `gem-hunt` and `re-ensure` are LIVE-supersets even though mtime says VAULT is newer.

## Classify, then reconcile

| class | direction | note |
|---|---|---|
| the 8 vendor-corrupted skills | **LIVE -> REPO/VAULT, ignore dates** | information-destroying substitution is one-way |
| skills where LIVE has a negative-case clause VAULT lacks (34) | **LIVE -> REPO/VAULT** | this is the active anti-overlap work |
| 4 strict LIVE supersets + ~75 orphaned live-only files | **LIVE -> REPO** | |
| CRLF-only differences (34 of 135) | either; **exclude from effort** | 25% of the surface, zero content risk |
| ~20 heavyweight DIVERGED files | **no automatic direction; per-file union merge only** | both sides hold unique lines |
| VAULT as a whole | **rebuild from REPO after the above; never a merge source** | VAULT carries the most corruption (18) and the fewest disambiguation clauses |

This is a human-driven per-class procedure. Measured: `scripts/sync-from-live.ps1` lines 128-138 expose no per-path include/exclude or direction selector and intentionally implement only live-to-repo. Review each class, edit REPO, preserve dual-write requirements, validate, then use the appropriate delivery hop.

Always exclude `crypto-ctf` explicitly: LIVE contains 12,816 files while git tracks 2; the extras are neither ignored nor staged. Letting it ride along buries the real fixes.

For CRLF questions, inspect the stored blob with `git ls-files -s`, `git cat-file -p`, or `git show <rev>:<path>`. On this workstation only `git archive` is the CRLF trap (it returns worktree bytes). `git show <rev>:<path>` and `git cat-file -p` both return the LF blob. Measured: three tracked files with 127/32/72 worktree CRLF pairs (`.agents/skills/010-editor/SKILL.md`, `.agents/skills/README.md`, `.agents/skills/acceptance-review/README.md`) returned 0 CRLF from both blob routes; `git archive` matched the worktree CRLF count on each.

All fleet measurements above come from `command-center/SKILL-FLEET-SOTA-PLAN.md:361-405` and were measured for that plan. Almost certain (90-99%): the direction rules reflect those recorded probes; re-measure before a future destructive reconciliation.

## What this skill does NOT do

It does not choose a winner from dates, bulk-sync diverged files, merge heavyweight files automatically, prune any live tree, deploy non-allowlisted Codex skills, or make direct edits in `~/.claude`, `~/.agents`, or `~/.codex`.
