---
description: Alias for /claude-science - one-command control for the local Claude Science WSL2 workbench (127.0.0.1:8000). Shells to the cs dispatcher - open, status, fix, doctor, ensure, stop, backup, restore.
---

# cs — alias for `/claude-science`

The command was renamed to **`/claude-science`**. This short form is kept working
deliberately: the owner asked for a rename, not for `/cs` to break, and the `cs`
dispatcher, the `cs.cmd` shim and every `cs <verb>` in the docs still use the short name.

> There is no `alias:` frontmatter field in Claude Code — a forwarding file is the only
> mechanism. `name:` cannot do it either: in a personal or project command, `name` sets only
> the display label and the command still comes from the file name.

## Usage

```
/cs [open|status|fix|doctor|ensure|stop|backup|restore <ts|latest>]
```

$ARGUMENTS

## What to Do

Behave exactly as `/claude-science` does — **read `commands/claude-science.md` and follow it**.
The one-line summary, so this file is useful even on its own: shell to the dispatcher, passing
`$ARGUMENTS` through as the verb (defaulting to `status` when empty), then relay its output.

```
pwsh -NoProfile -File ~/.local/bin/cs.ps1 $ARGUMENTS
```

This must stay byte-for-byte the same target as `claude-science.md` — it is the **installed**
dispatcher, the same file the `cs` shim on `PATH` runs. It previously named a source checkout that
had drifted, so both slash commands silently ran the pre-fix tool; `cs doctor`'s **Slash-command
route** row now fails if either file routes anywhere but the running code.

Key facts that change a diagnosis (the full set is in `claude-science.md`):

- **HTTP 401 on `/` = alive** (auth gate). Slow/timeout = **WEDGED**, not down — `fix` recovers it.
- **`ensure`** emits `SUCCESS:cs-up` / `FAILED:cs-down`; only touch `:8000` on the success marker.
- **`NOT-CHECKED` is not `PASS`** — a doctor row that could not reach its input says so.
- A run tagged **`[INJECTED]`** or carrying a `Fault injection` row is a **simulation**, not a
  measurement of this box — never quote it as health evidence.

## Related

- Canonical: `commands/claude-science.md`
- Skill: `skills/claude-science-local/SKILL.md`
