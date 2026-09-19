# dbx-ai MCP server

Vendored 2026-09-19 from `D:/opt/cyberstrike-mcp/dbx-ai-mcp-server.py`
(finish-scope lane A2, audit disposition local-impl-move).

- Single self-contained FastMCP server (~10.4KB, stdlib + `mcp` package only).
- Launched by the SSOT registry (`~/.agents/agents.json` row `dbx-ai`,
  python transport) as `C:\Python314\python.exe <this file>`; no venv needed.
- Consumed by: claude surface (sync-managed) + cyberstrike TUI config
  (hand-healed 2026-09-19; not sync-covered).
- Rollback anchor: the D:/opt original stays in place until a fresh-session
  live reconnect passes, then may be retired.
