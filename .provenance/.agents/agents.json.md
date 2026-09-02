# Provenance for `.agents/agents.json`

The registry is a closed schema: keys carry behaviour, never rationale. The
"why" for entries that need one lives here (AGENTS.md, Coding Style).

## `mcp.servers.basic-memory.x_cursor.stdio_bridge` (added 2026-09-02)

- **What:** Cursor runs `C:\Python314\python.exe
  C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --stdio` as a
  per-window stdio shim in front of the shared daemon. `merge_generated_cursor_mcp.py`
  appends `--url <mcp.servers.basic-memory.url>` when rendering, so the URL stays
  single-sourced; Claude and Codex renderers ignore the key and keep the direct URL.
- **Why:** the daemon restarts near-daily under RAM pressure (watchdog); Cursor's
  Streamable-HTTP client then sits on `-32600 Session not found` or a stale
  `ECONNREFUSED` while the port is healthy (`.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`).
  The client bug is modelcontextprotocol/typescript-sdk#1708 (404 on a stale
  session is not handled; fixes #1718 / #2150 unmerged at the time of writing).
  The shim re-initializes and replays, serves cached discovery while the port is
  dead, and heals on the next call.
- **Why not the alternatives:** decision record and the reverse-proxy proposal in
  `docs/plans/2026-09-02-basic-memory-transport-decision.md`. Basic Memory's CLI
  exposes no stateless mode; a proxy that owns `:8765` needs the owner's approval.
- **Invariants the tests pin:** only `basic-memory` carries `x_cursor`
  (`test_live_registry_declares_the_cursor_bridge_for_basic_memory_only`); the
  shim's argv matches none of the daemon's `processMatch` tokens, so the fleet
  supervisor never counts shims as duplicate daemons
  (`test_bridge_argv_never_matches_the_daemon_process_identity`); `--check`
  treats both the bare URL and the pre-registry hand edit (no `--url`) as drift.
- **Rollback:** delete the `x_cursor` object and run `merge_generated_cursor_mcp.py
  --write`; Cursor is back on the direct URL. No daemon, port or secret is touched.
