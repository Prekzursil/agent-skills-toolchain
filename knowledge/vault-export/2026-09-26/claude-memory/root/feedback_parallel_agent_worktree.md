---
name: feedback-parallel-agent-worktree
description: Parallel file-disjoint subagents on a SHARED git checkout contaminate
  each other's commits via broad git-add; use Agent isolation:worktree or strict scoped
  adds
metadata:
  node_type: memory
  type: feedback
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/feedback-parallel-agent-worktree
---

When dispatching multiple subagents that edit DIFFERENT files of the same repo in parallel, they share ONE working tree + git index. A broad `git add -A`/`git add .` by any agent stages OTHER agents' in-flight (uncommitted) files into its own commit → cross-contamination (a panel commit containing launcher files), and concurrent `git reset`/re-commit churn rewrites HEAD under the others.

**Why:** observed live 2026-05-28 on the BC V1 squad — three agents (panel, launcher, auto_equip) each swept a sibling's unstaged files into a commit; all caught it via `git show --stat`/`git diff --cached --name-only` and recovered with `git reset --soft HEAD~1` + `git restore --staged <foreign>`, but it cost time and risked lost work. The final graph was clean only because the prompts mandated the verify-before-commit discipline.

**How to apply:**
- Preferred: dispatch parallel file-disjoint agents with `Agent(isolation: "worktree")` so each gets an isolated checkout + branch (no shared index); merge the returned branches at the end (clean since file-disjoint).
- If sharing one worktree: every agent prompt MUST say "stage ONLY your explicit owned paths; NEVER `git add -A`/`.`; run `git diff --cached --name-only` before every commit and `git restore --staged` anything foreign." This worked, but is fragile.
- A single file/registry edited by multiple agents (e.g. `feature_modules.py`) is a hotspot — give it ONE owner, or serialize.
- Generated artifacts: when agents regenerate from a template (e.g. `native_agent.py` → `*_agent.js`) + a gitignored frozen copy, tell them the frozen copy is gitignored (`cp`, never `git add`) — one agent stalled 10 min in a git-tracking rabbit hole over exactly this.

Related: [[feedback-peer-review]] (cross-model review before done), [[battlecats-v1-lean-bundle]] (the squad this came from).