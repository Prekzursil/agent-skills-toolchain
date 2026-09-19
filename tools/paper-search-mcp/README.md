# paper-search-mcp (repo wrapper — build/rebuild documentation)

Repo-side documentation wrapper for the `paper-search` MCP server. Upstream:
https://github.com/openags/paper-search-mcp (PyPI package `paper-search-mcp`, MIT).
This directory deliberately vendors NO source and NO venv. The live executable stays
over on D::

    D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe

The registry SSOT entry (`paper-search` in `C:/Users/Prekzursil/.agents/agents.json`)
already points at that absolute path and is NOT changed by this wrapper.

## What is installed (verified 2026-09-19)

| fact | value |
|---|---|
| PyPI package | `paper-search-mcp` (dist: `paper_search_mcp-0.1.4.dist-info`) |
| Version | 0.1.4 — pin rebuilds to this until deliberately bumped |
| Python | 3.14.6 from `C:\Python314\python.exe` |
| venv path | `D:\ReverseTools\mcp\paper-search-mcp\venv` (created via `python -m venv`) |
| console scripts | `paper-search-mcp.exe` = server (`paper_search_mcp.server:main`); `paper-search.exe` = CLI (`paper_search_mcp.cli:main`) |
| key deps | fastmcp 3.4.2 (+ fastmcp_slim 3.4.2), httpx 0.28.1, lxml 6.1.1, feedparser 6.0.12, beautifulsoup4 4.15.0 |

## Build (first install) — must run ON the D: path, any cwd

    C:\Python314\python.exe -m venv D:\ReverseTools\mcp\paper-search-mcp\venv
    D:\ReverseTools\mcp\paper-search-mcp\venv\Scripts\python.exe -m pip install --upgrade pip
    D:\ReverseTools\mcp\paper-search-mcp\venv\Scripts\python.exe -m pip install paper-search-mcp==0.1.4

## Rebuild

Rename the old venv aside FIRST (estate rule: never delete outright), then re-run the
Build block. `build.ps1 -Apply -Rebuild` in this directory does exactly this. Trash the
`venv.old-*` directory only after the new venv is verified working.
