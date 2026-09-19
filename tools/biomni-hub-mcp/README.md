# biomni-hub MCP server

Vendored 2026-09-19 from `C:/Users/Prekzursil/.local/opt/biomni-hub` (finish-scope
lane A3, audit disposition local-impl-move). The source dir had NO git origin —
this repo copy is now the source of record (upstream Prekzursil/biomni-hub does
not exist on GitHub; the `bm_*` McpHub lane is NOT a replacement: ~4k source
lines with an offline test suite).

- `hub/`: FastMCP server (server.py, schema.py, offline tests).
- `databricks/`: Track B deploy assets (bootstrap, provision).
- Build: `cd hub && C:/Python314/python.exe -m venv .venv && .venv/Scripts/python.exe -m pip install -e ".[dev]"`
- Old copy at `~/.local/opt/biomni-hub` retained as rollback until the vendored
  copy runs green in a real zcode session, then may be retired.
