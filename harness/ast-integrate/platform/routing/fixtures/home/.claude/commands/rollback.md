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
