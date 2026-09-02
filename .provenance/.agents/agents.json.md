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

## Live-lineage entries folded back 2026-09-02 (from `live-capture/2026-09-02`, `726687ec`)

The live registry (`C:\Users\Prekzursil\.agents\agents.json`, the SSOT named in
`CLAUDE.md`) had moved ahead of this mirror since the 2026-08-28 fold. Reunited here as
live + the `x_cursor` block above; the three-way merge had no conflicting hunk
(`reconcile-flags/mcp-cursor-merge-lineage-2026-09-02.md`, section "Result").

- **`context7`, `firecrawl` -> hosted HTTP (`remote-required`).** Owner decision
  2026-08-28: the vendors' remote MCPs (`https://mcp.context7.com/mcp`,
  `https://mcp.firecrawl.dev/v2/mcp`, bearer from `${CONTEXT7_API_KEY}` /
  `${FIRECRAWL_API_KEY}`) replace the per-session `npx` process trees. Pinned by
  `mcp_control_plane.REMOTE_REQUIRED_SERVERS` (http transport + `remote-required` tag
  required; http may not declare `command`/`args`; credential-bearing http must be
  https) and by `tests/test_cursor_remote_transport_policy.py`.
- **`inference-hub`** (`owner-requested`, `approved`, `hosted-inference`, `shared`): the
  registry-driven successor of `glm53-space` (hosted-models hunt, D1 = hard delete,
  2026-09-02). One resident process on `127.0.0.1:8901` (`tools/mcp/inference-hub/`)
  with an MCP face and an OpenAI `/v1` face, reading `.agents/models.json`; the registry
  entry is the thin stdio shim `.agents/scripts/inference_hub_stdio.py`, which lazy-starts
  the hub on first use and bridges with the same session healing as the basic-memory
  shim, and the hub idle-exits after 10 min (0 RAM when unused). It took glm53-space's
  Cursor safe-default slot (`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`) and is not one of
  the core six. Declares only the inference-scoped token NAME
  `HUGGINGFACE_TOKEN_INFERENCE` (D7); the Hub MCP keeps `HUGGINGFACE_TOKEN`. Targets
  `claude` + `codex`; Cursor mounts it through the Claude projection.
  The `glm53-space` row was REMOVED here rather than tombstoned (owner decision D1 = B):
  its code was never on a remote ref, so the archive branch
  `archive/glm53-space-2026-09` carries the last registry state and the owner adds the
  box copy (`OWNER-CLICKS.md`); the capability survives as model `glm-5.3` on endpoint
  `hf-router` in `.agents/models.json` (L7), and the name is in
  `merge_generated_cursor_mcp.CURSOR_RETIRED_SERVERS` so a stale live definition is
  dropped by every merge.
- **`linkedin`** (`default-off`, `unapproved`, `own-feed-write`): self-serve LinkedIn MCP
  restored from the recovered private-repo source; owner OIDC identity plus own-feed
  post create/delete only. Rendered for Claude and Cursor, never default-attached in
  Cursor (explicit `--attach-all-safe` only); runtime approval is per session.
- **`huggingface`** description only (Hub control plane vs inference runtimes).
