---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/config/hooks/cmd-rewrite/readme
---

# cmd-rewrite hooks

Two companion hooks that rewrite Bash tool input/output deterministically at
the tool boundary. Both are **fail-open**: any error produces no output (exit 0)
so the original command / response passes through unchanged.

---

## Hook A — `inject-nopager.py` (PreToolUse)

**Problem:** On Windows / Git-Bash, git subcommands like `log`, `diff`, `show`,
`branch`, `tag`, `stash list`, `shortlog`, `blame`, and `reflog` open a pager
(`less` / `more`) by default. When Claude Code's Bash tool runs these, the pager
hangs waiting for terminal input that never arrives.

**Solution:** Insert `--no-pager` immediately after `git` before the command
executes.

```
git log --oneline -5        →  git --no-pager log --oneline -5
git diff HEAD~1             →  git --no-pager diff HEAD~1
git branch -a               →  git --no-pager branch -a
```

**Semantics-preserving guarantee:**
`git --no-pager <subcmd>` is 100% equivalent to `GIT_PAGER=cat git <subcmd>`.
No flags that change output format are ever added (`--porcelain`, `--quiet`,
etc.).

**Pager-prone subcommands rewritten:**
`log`, `diff`, `show`, `branch`, `tag`, `stash`, `shortlog`, `blame`,
`reflog`, `diff-tree`, `diff-index`, `diff-files`, `format-patch`, `whatchanged`

**Not rewritten (passthrough):**
- Commands already containing `--no-pager`
- Compound commands containing subshell expansions `$(...)` or backticks `` ` ``
  (skipped entirely to avoid misparse)
- Any parsing error for a segment (that segment is left unchanged)
- Non-git commands

### CRITICAL: One-rewriter-per-tool caveat

Claude Code runs all matching PreToolUse hooks in parallel and the **last
`updatedInput` writer wins** (the ordering is non-deterministic when multiple
hooks emit `updatedInput`).

**You MUST NOT register a second `updatedInput`-emitting PreToolUse hook that
also targets the `Bash` tool.** If you need another Bash input rewriter, either:

- Add it to this script, or
- Give one hook a narrower matcher so they don't both target the same tool,
  (but this is only safe if at most one of them actually emits `updatedInput`
  for any given command).

---

## Hook B — `compress-output.py` (PostToolUse)

**Problem:** Some Bash commands produce enormous output that floods Claude's
context window:
- `git status` in a large repo lists hundreds of untracked files.
- Build/CI/test output may contain megabytes of ANSI-coloured noise.

**Solution:** After the Bash tool executes, compress output that matches a
known-noisy pattern AND exceeds a size threshold (default 4000 chars).

**What is compressed:**

1. **`git status` with large output** → summarised:
   - Branch and tracking lines kept verbatim
   - Staged / Modified / Untracked counts shown
   - First 10 paths per category shown; rest summarised as `[N more not shown]`

2. **Long output containing ANSI escape sequences** → ANSI codes stripped.
   Content is unchanged; only colour/cursor codes are removed.

**What is NOT compressed:**
- Output shorter than the size threshold (4000 chars by default)
- Commands that don't match the known-noisy patterns
- Anything where a parsing/detection step fails (fail-open → passthrough)

**Configuration:**

| Env var | Default | Meaning |
|---------|---------|---------|
| `COMPRESS_SIZE_THRESHOLD` | `4000` | Min output length (chars) to trigger compression |

### Honest caveats

- This hook fires **after** the tool runs. It is a context-budget optimiser,
  NOT a gate — it cannot prevent the command from executing.
- It does **NOT redact secrets**: the original output is captured in the
  transcript / OTel trace before this hook fires. Do not rely on this hook for
  security or compliance.

---

## settings.json registration

Add these blocks to your `~/.claude/settings.json` under the `"hooks"` key.
Do **not** add `inject-nopager.py` to a matcher group that already has another
hook emitting `updatedInput` for Bash (see caveat above).

### Hook A — PreToolUse (Bash matcher)

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python C:/Users/Prekzursil/.claude/hooks/cmd-rewrite/inject-nopager.py",
          "timeout": 5,
          "statusMessage": "Injecting --no-pager into git commands"
        }
      ]
    }
  ]
}
```

### Hook B — PostToolUse (Bash matcher)

```json
{
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python C:/Users/Prekzursil/.claude/hooks/cmd-rewrite/compress-output.py",
          "timeout": 10,
          "statusMessage": "Compressing noisy Bash output"
        }
      ]
    }
  ]
}
```

Both blocks merge into the existing `"hooks"` object — the existing
`PreToolUse` and `PostToolUse` arrays accept multiple matcher entries.

---

## File layout

```
hooks/cmd-rewrite/
  inject-nopager.py   — Hook A: PreToolUse, git --no-pager injection
  compress-output.py  — Hook B: PostToolUse, output compression
  README.md           — this file
  test_hooks.py       — automated self-tests (run: python test_hooks.py)
```