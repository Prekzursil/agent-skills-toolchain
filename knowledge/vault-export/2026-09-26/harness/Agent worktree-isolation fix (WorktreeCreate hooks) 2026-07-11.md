---
title: Agent worktree-isolation fix (WorktreeCreate hooks) 2026-07-11
type: note
permalink: main/harness/agent-worktree-isolation-fix-worktree-create-hooks-2026-07-11
tags:
- harness
- worktree
- agent-isolation
- claude-code
- hooks
- reference
---

# Agent worktree-isolation fix (WorktreeCreate hooks) 2026-07-11

⭐ Made Claude Code's native `Agent(isolation:"worktree")` work in this workspace. Vendored to `agent-skills-toolchain` PR #69 (`scripts/worktree-isolation/`).

## Root cause (why native worktree failed)
`Agent(isolation:"worktree")` runs `git worktree add` from the **tool process CWD**, which here is `C:\Users\Prekzursil\.agents\harness` — **NOT a git repo**. And the session isn't rooted in one repo: the WorktreeCreate hook input's `cwd` = `~/.agents/harness` and `$env:CLAUDE_PROJECT_DIR` = the user's **home** (`C:/Users/Prekzursil`) — neither a git repo (agents here work across many repos). So the harness aborts: *"not in a git repository and no WorktreeCreate hooks are configured."* The env-note's "primary working directory" (a repo) is NOT what reaches the hook.

## The fix — WorktreeCreate/WorktreeRemove hooks (the sanctioned path)
Registered in `~/.claude/settings.json` `hooks` (single `command` STRING, matching the existing dispatcher hooks — NOT command+args). Hook contract (verified vs code.claude.com/docs/en/hooks.md):
- **WorktreeCreate**: stdin `{cwd, worktree_config:{base_directory, worktree_name, source_ref}}` → print the worktree abs path to **stdout** on exit 0 (non-zero aborts).
- **WorktreeRemove**: stdin `{cwd, worktree_path}` → non-blocking (always exit 0).

`create-worktree.ps1` resolves the target repo from, in order: a **hint file** `~/.claude/hooks/worktree-target.txt` → `base_directory` → `CLAUDE_PROJECT_DIR` → `cwd` (first that's a git repo). Creates a `--detach` worktree OUTSIDE the repo at `~/.claude/agent-worktrees/<name>` (detach avoids "branch already checked out" collisions). Remove finds the main repo via `git -C <wt> rev-parse --git-common-dir` (a worktree's `.git` is a FILE pointing to the main repo, so you can't walk up for a `.git` dir).

## Gotchas learned
- **EAP=Stop throws on git's normal stderr** ("Preparing worktree (detached HEAD ...)") even when git SUCCEEDS → use `$ErrorActionPreference="Continue"` + judge success by `$LASTEXITCODE`, capturing `2>&1` into a var.
- **The session isn't repo-rooted**, so the hook can't auto-detect the repo → the **target-hint file** is required (set it before dispatching worktree agents for a local repo).
- **WorktreeRemove did NOT auto-fire at agent-exit** in testing (leftover worktree persisted) — likely runs at a later lifecycle point/session end; prune periodically.

## Picking heuristic (worktree vs clone-to-temp)
- **Native worktree**: parallel agents on ONE local repo (set the hint file; `isolation:"worktree"`). Fast, shares `.git`, no full clone.
- **Clone-to-temp**: agents on REMOTE/different repos (the fleet), or several agents targeting different repos concurrently (the hint file is global → race). Each agent `git clone <url> $TEMP\<unique>`. Equivalent isolation, heavier. The reliable default. (Proven this session — the 3 Reframe Wave-0 agents used it.)

Extends [[project_harness_session_scoping_fix_2026-07-11]] and [[Harness credential-read guard default-off toggle 2026-07-11]].
