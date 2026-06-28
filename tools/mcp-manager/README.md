# mcp-manager

Cross-plane MCP server manager — read-only inventory CLI + Textual TUI.

Manages three configuration planes from a single interface:

- **Claude plane** — `~/.claude.json` (user scope + per-project `disabledMcpServers`)
- **Codex plane** — `~/.codex/config.toml` (`[mcp_servers.<name>].enabled`)
- **Funnel plane** — `~/.mcp-funnel-profiles.json` + `mcp-profile.ps1` profile switcher

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
- **Persistent TUI state / saved loadouts beyond the defaults file**: the TUI
  reads the single `~/.claude/.mcp-disabled-defaults.json` file; multi-named
  loadout storage is not implemented.
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
uv run pytest -q          # run all 137 tests
uv run pytest --cov=core  # coverage report
```

Tests are fully offline (no real config files accessed; all adapters accept
injected paths/output strings).
