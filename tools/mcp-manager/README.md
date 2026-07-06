# mcp-manager

Cross-plane MCP server manager — inventory CLI + PySide6 desktop GUI, with
named **presets** for one-action bulk enable/disable on the Claude plane.

Manages three configuration planes from a single interface:

- **Claude plane** — `~/.claude.json` (user scope + per-project `disabledMcpServers`)
- **Codex plane** — `~/.codex/config.toml` (`[mcp_servers.<name>].enabled`)
- **Funnel plane** — `~/.mcp-funnel-profiles.json` + `mcp-profile.ps1` profile switcher

> **Timing (read this):** MCP servers spawn once at session start. Every config
> change here **applies to the NEXT session — restart Claude Code to take
> effect.** Nothing in this tool toggles a *running* session live.

---

## Install

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```powershell
cd D:/tools/mcp-manager
uv sync
```

Or run without installing (uv handles the venv on first use):

```powershell
uv run app.py status
```

---

## CLI usage

```powershell
uv run app.py status        # unified MCP inventory across planes (+ duplicates)
uv run app.py duplicates    # just the cross-plane duplicate servers
uv run app.py consolidate   # user-skill consolidation analysis (no deletions)
uv run app.py json          # full machine-readable inventory as JSON
```

## Presets (Claude plane) — bulk enable/disable

A **preset** is a named list of servers to ENABLE. Presets are stored in
`~/.mcp-presets.json` (seeded on first use) and **compose** — list several and
their enable-sets union. `core` is always on; applying `core` alone is the RAM
kill-switch. The resolver inverts the enable-set against the live inventory:

```text
disabled = all_known_servers - (core  ∪  selected_presets)
```

Only the **current project's** `disabledMcpServers` is written (safe mtime-merge
+ timestamped backup). Servers outside the inventory (your hand-curated
`claude.ai *` / `plugin:*` disables) are never touched.

```powershell
uv run app.py preset list                 # show core + every named preset
uv run app.py use re                       # enable RE bundle for THIS project
uv run app.py use re research              # compose two bundles
uv run app.py use core                     # kill-switch: only the 8 core servers
uv run app.py use re --dry-run             # resolve + preview, write nothing
uv run app.py preset save myset a b c      # save a new enable-list preset
uv run app.py preset delete myset
```

Seeded catalog: `core` (basic-memory, tavily, exa, context7, github_cli,
deepwiki, huggingface, figma) plus `re`, `chem`, `research`, `social`, `cloud`,
`media`, `docs`. Spec abbreviations are stored as the exact live server names
(e.g. `ida` → `ida-pro-mcp`) so resolution is exact.

### Paste-parse fallback

When `claude mcp list` isn't available (or you prefer it), paste the raw `/mcp`
panel and use it as the inventory + current state:

```powershell
uv run app.py parse-list dump.txt          # parse a pasted /mcp dump (stdin ok)
uv run app.py use re --from-paste dump.txt  # resolve against the pasted list
```

Lines like `apktool-mcp · ✔ connected · 16 tools`, `codecov · ✘ failed`, and
`hexstrike-ai · ◯ disabled` parse into `(name, state, tool_count)`; the header
(`74 servers`) and footer (`↑/↓ to navigate`) chrome is skipped.

### EXPERIMENTAL: `try-live` keystroke macro

Claude Code has **no** robust external live-toggle. `try-live` is a fragile,
opt-in escape hatch that computes an arrow-navigation plan from a pasted panel
order and (with `--apply`) blind-drives the `/mcp` TUI in a target window. It is
**not reliable** — there is no success signal; verify `/mcp` manually.

```powershell
uv run app.py try-live re --from-paste dump.txt --window "Terminal"           # dry-run
uv run app.py try-live re --from-paste dump.txt --window "Terminal" --apply    # send keys
```

## Desktop GUI

```powershell
uv run python -m ui.gui        # (or)  uv run python ui/gui.py
```

A native window with a live server table plus a **preset bar**: a preset
dropdown + **Apply Preset** (bulk enable/disable for this project), **Save
Selection** (turn selected rows into a preset), **Paste /mcp List** (use a
pasted dump as inventory), a **fuzzy filter** box, and an **experimental Try
Live** button. Every apply says *"applies next session — restart to take
effect."*

## TUI usage

```powershell
uv run --with textual ui/app.py
# or if deps are already installed:
uv run ui/app.py
```

Key bindings: `r` refresh · `Space` toggle row · `Ctrl+A` select all · `Esc` clear
selection · `e` enable selected · `d` disable selected · `a` authenticate help · `q` quit.

---

## The 3-plane model

```
┌─────────────────────────────────────────────────────────────────────┐
│  Plane       │  Config file                    │  Toggle mechanism  │
│─────────────────────────────────────────────────────────────────────│
│  claude      │  ~/.claude.json                 │  set-membership in │
│              │  projects[path].disabledMcpServers  (namespaced IDs) │
│─────────────────────────────────────────────────────────────────────│
│  codex       │  ~/.codex/config.toml           │  tomlkit flip of   │
│              │  [mcp_servers.<name>].enabled   │  .enabled bool     │
│─────────────────────────────────────────────────────────────────────│
│  funnel      │  ~/.mcp-funnel-profiles.json    │  mcp-profile.ps1   │
│              │  ~/.mcp-funnel.json (active)    │  <profile> script  │
└─────────────────────────────────────────────────────────────────────┘
```

A fourth read-only source (`~/.mcp.json`) is scanned by the inventory but is
not toggled — project-scope `.mcp.json` files are managed by Claude Code directly.

---

## Safe-write guarantees

**Claude plane (`~/.claude.json`):**

1. File is re-read and mtime recorded before mutation.
2. Targeted edit: only `projects[path].disabledMcpServers` is touched; every
   other key (including Claude Code's own keys such as `numStartups`,
   `mcpServers`, project configs, etc.) is preserved via `setdefault` reads.
3. Before writing, mtime is checked again; if the file changed (Claude Code
   rewrote it concurrently) the change is reloaded and re-applied once.
4. A timestamped backup is written to `~/.mcp-manager-backups/claude.json.<ts>.bak`
   before every write.
5. IDs are stored as **exact namespaced strings** (e.g.
   `plugin:semgrep:semgrep`, `claude.ai Tavily`) — never bare names or
   substrings.

**Codex plane (`~/.codex/config.toml`):**

- All edits use `tomlkit` (lossless TOML round-trip: comments, spacing, and
  quoting are preserved exactly).
- The result is validated with `tomllib` before writing; a malformed output is
  refused.
- A timestamped backup is written to the `.mcp-manager-backups/` directory
  before every write.

**Funnel plane:**

- mcp-manager does **not** write `~/.mcp-funnel.json` directly.
- Profile switches are delegated entirely to
  `C:/Users/Prekzursil/scripts/mcp-profile.ps1 <profile>`.
  The funnel file format is owned by that script; this tool only calls it.

---

## Auth / Authenticate — honest limits

The **Authenticate** action (`a` key or the toolbar button) shows instructions
only. mcp-manager:

- Does **not** open a browser or terminal.
- Does **not** store, read, or write any OAuth token, bearer token, or
  credential file.
- Does **not** complete any OAuth flow.

What it does: displays the correct command to run in Claude Code or a
terminal to trigger the host application's own auth flow. The status badge
updates on next Refresh once the host application has connected.

---

## Loadout / profile limits

Loadouts apply `~/.claude/.mcp-disabled-defaults.json` to the current project's
`disabledMcpServers` list. They:

- Only affect the **Claude plane** (no Codex toggle, no funnel switch).
- Do not remove servers from global `mcpServers`; they only add IDs to the
  per-project disabled list.
- Take effect for new Claude Code sessions; running sessions are not affected.

Funnel profile switches go through `mcp-profile.ps1` and affect the active
`~/.mcp-funnel.json`; no Claude or Codex state is touched.

---

## Deferred items

The following were explicitly scoped out and are not implemented:

- **Claude `claude mcp enable/disable` verb**: no such CLI verb exists. Toggle
  is implemented via the `disabledMcpServers` array.
- **Live mid-session toggle**: not architecturally possible from an external
  tool — config edits apply next session (see the timing note up top). The
  `try-live` macro is a fragile, honest best-effort escape hatch, not a
  reliable path.
- **Codex CLI auth** (`codex mcp login`): the tool shows the command but does
  not invoke it.
- **Antigravity / other AI planes**: not supported; only Claude, Codex, and the
  funnel are managed.
- **Skill deletion**: `consolidate` produces an analysis report only; no files
  are deleted.
- **Live session refresh**: toggling a server while Claude Code is running
  requires restarting Claude Code for the change to take effect.

---

## Development

```powershell
uv run pytest -q                    # run all 299 tests (offline)
uv run pytest --cov=core --cov=app  # coverage report (100% on core/ + app.py)
```

Tests are fully offline (no real config files accessed; all adapters accept
injected paths/output strings).
