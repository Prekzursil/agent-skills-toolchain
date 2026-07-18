# Worktree isolation for `Agent(isolation:"worktree")`

Makes Claude Code's **native git-worktree agent isolation** work in this workspace, where
the default auto-detection fails.

## The problem it solves
`Agent(isolation:"worktree")` runs `git worktree add` from the tool process CWD. In this
setup that CWD is `~/.agents/harness` (the shared harness), **not a git repo** — and the
session isn't rooted in any single repo (`CLAUDE_PROJECT_DIR` resolves to the user's *home*,
also not a repo, because agents work across many repos). So the harness aborts with:

```
Cannot create agent worktree: not in a git repository and no WorktreeCreate hooks are configured.
```

Claude Code's sanctioned fix is to register **`WorktreeCreate` / `WorktreeRemove` hooks** that
create/remove the worktree with custom logic. That's what this capability ships.

## Hook contract (verified against code.claude.com/docs/en/hooks.md)
- **WorktreeCreate** — stdin JSON `{ cwd, worktree_config: { base_directory, worktree_name, source_ref } }`;
  must print the created worktree's absolute path to **stdout** on exit 0 (non-zero aborts).
- **WorktreeRemove** — stdin JSON `{ cwd, worktree_path }`; non-blocking (always exit 0).
- The hooks also get `$env:CLAUDE_PROJECT_DIR` (here: the user's home, not a repo).

## How this implementation works
Because the harness passes **no git repo**, the create hook resolves the target repo from, in
order: a **target-repo hint file** → `worktree_config.base_directory` → `$env:CLAUDE_PROJECT_DIR`
→ `cwd`, taking the first that is actually a git repo.

- **Hint file:** `~/.claude/hooks/worktree-target.txt` containing the absolute path of the repo
  you want worktrees of. **Set this before dispatching worktree agents** for a given local repo.
- Worktrees are created **outside** the repo at `~/.claude/agent-worktrees/<name>` with
  `--detach` (so they never collide with a branch already checked out in the main worktree).
  The agent makes its own branch inside.
- Remove finds the main repo via `git -C <wt> rev-parse --git-common-dir` (a worktree's `.git`
  is a *file* pointing back to the main repo), then `worktree remove --force` + `prune`.

## When to use worktree vs clone-to-temp (the picking heuristic)
- **Native worktree** (this) — parallel agents on **one local repo**: set the hint file, pass
  `isolation:"worktree"`. Fast, shares `.git` objects, no full clone.
- **Clone-to-temp** — agents on **remote / multiple different** repos, or ad-hoc work where no
  single local repo applies: have each agent `git clone <url> $TEMP\<unique>` and work there.
  Equivalent isolation, heavier setup. This is the reliable default when the target repo isn't
  local or when several agents target different repos concurrently.

## Verified behaviour
Manual create/remove against a real repo: worktree count 2→3→2, valid detached-HEAD checkout.
Live `Agent(isolation:"worktree")` smoke test: agent ran in
`~/.claude/agent-worktrees/agent-<id>` (detached HEAD), isolated from `main`.

## Known caveat
`WorktreeRemove` did **not** auto-fire at agent-exit in testing (the leftover worktree persisted;
it likely runs at a later lifecycle point / session end). Until confirmed, prune periodically:
`git -C <repo> worktree prune` and clean `~/.claude/agent-worktrees/`. `install.ps1` is idempotent.

## Install
```powershell
scripts\worktree-isolation\install.ps1            # copies scripts to ~/.claude/hooks, prints the settings snippet
scripts\worktree-isolation\install.ps1 -PatchSettings   # also merges the hooks into ~/.claude/settings.json (backs it up first)
```
Then set a target and use it:
```powershell
Set-Content ~/.claude/hooks/worktree-target.txt "C:\path\to\your\repo" -NoNewline
# Agent(isolation:"worktree")  ->  runs in ~/.claude/agent-worktrees/<name>
```
