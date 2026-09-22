# Biomni local patches — live-tree state snapshot (2026-09-22)

These files are COPIES of the live WSL `~/Biomni` tree, not a fork. The live tree is
authoritative; this directory preserves the local deltas against upstream
snap-stanford/Biomni for re-application after an upstream pull. Re-apply by copying
back and checking the markers below.

| File | Delta vs upstream | Marker |
|---|---|---|
| `a1.py.key-mask.patch.py` | api_key masked in the DEFAULT-CONFIG dump (`a1.py` ~line 135: `value = "*" * 8 + value[-4:]`); upstream prints raw | key-mask |
| `biomni_mcp_server.py` | (1) HOME-independent anchors (`_BIOMNI_DIR` via `__file__`, `_HOME_ROOT` hardcoded); (2) `biomni_task` reads `go()`'s tuple return `(history, solution_str)` — `main_history_copy` is None on fresh instances; (3) lazy `agent()` calls `add_mcp(mcp_inject.yaml)` fail-open | go-fix + inject |
| `biomni_mcp_stdio.py` | stdio wrapper: loads `.env` explicitly (sandbox nulls dotfiles), `show_banner=False` (FastMCP banner crashes in bwrap) | envfix |
| `mcp_inject.yaml` | estate MCP injection config — dict-format `mcp_servers:` (NOT list), `command: [uvx, pkg==ver]` as list | inject-config |

Environment pins: gradio<6, langgraph 1.2.x (per biomni-local skill), nest_asyncio
installed (add_mcp hard dependency). `bm-model` verb at `~/.local/bin/bm-model`
flips BIOMNI_LLM in `.env` + CS `local-mcp.json` env in lockstep.
