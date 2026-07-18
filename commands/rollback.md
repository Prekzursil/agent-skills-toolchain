# Rollback

Restore files from an **edit-checkpoint** taken automatically before edits this
session. The `edit-checkpoints` PreToolUse hook snapshots the pre-edit state once
per turn (git repos: a `git stash create` object tagged under
`refs/claude-checkpoints/`; non-git paths: a file copy) so a botched edit run is
recoverable even though Claude Code has no native edit-undo.

## Usage

```text
/rollback            # list this session's checkpoints (most recent first)
/rollback <turn>     # show how to restore the checkpoint for that turn
```

## Behavior

When invoked, read the checkpoint index and present options. Do NOT auto-revert —
show the user the checkpoints and the exact restore command, then act on their choice.

1. **Find the index** for the current session:
   - `~/.claude/checkpoints/<session_id>/index.ndjson` (one JSON record per line).
   - Each record has: `ts`, `turn`, `type` (`git-stash` | `git-head-clean` | `copy`),
     and either `repo` + `restore` (a sha) or `copy_path` + `original`.

2. **List** the records newest-first (turn, time, type, file(s)/repo touched).

3. **Restore** per type:
   - `git-stash` — the `restore` sha is a stash-create snapshot of the whole dirty
     tree at that turn. Inspect, then apply:
     ```bash
     git -C <repo> stash show -p <restore_sha>      # preview the snapshot
     git -C <repo> stash apply <restore_sha>        # restore working-tree state
     # or restore ONE file from the snapshot:
     git -C <repo> checkout <restore_sha> -- <path>
     ```
     The snapshot is also tagged `refs/claude-checkpoints/<turn>` (GC-safe).
   - `git-head-clean` — the tree was clean at that turn; revert edits with
     `git -C <repo> checkout -- <path>` (or `git -C <repo> restore <path>`).
   - `copy` — a non-git file copy; restore with
     `cp "<copy_path>" "<original>"`.

4. **Confirm** the restored content with the user before continuing.

## Notes

- Checkpoints are per-session and retained under `~/.claude/checkpoints/`.
- The hook captures the **pre-edit** state, so applying a checkpoint undoes the
  edits made during/after that turn.
- Opt-out of checkpointing: set `EDIT_CHECKPOINTS=off` or create
  `~/.claude/hooks/edit-checkpoints/.disabled`.
