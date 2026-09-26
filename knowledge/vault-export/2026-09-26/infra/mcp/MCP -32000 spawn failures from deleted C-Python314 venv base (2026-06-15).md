---
title: MCP -32000 spawn failures from deleted C:\Python314 venv base (2026-06-15)
type: report
permalink: main/infra/mcp/mcp-32000-spawn-failures-from-deleted-c-python314-venv-base-2026-06-15
tags:
- mcp
- venv
- python
- troubleshooting
- '-32000'
- claude-code
---

# MCP `-32000` reconnect failures — deleted venv base interpreter

## Root cause
Several local stdio MCP servers launch from a per-repo `.venv\Scripts\python.exe`. Those venvs were
created with base interpreter `C:\Python314`, which was later removed (Python 3.14 now lives at
`C:\Users\Prekzursil\AppData\Local\Python\pythoncore-3.14-64`). A venv whose base python is gone cannot
be spawned → Claude Code reports `Failed to reconnect to <server>: -32000`. NOT a code/config bug; the
`mcp` package + deps are still in the venv's site-packages.

## Fix (non-destructive, preserves site-packages incl. compiled wheels like rdkit)
`py -3.14 -m venv "<repo>\.venv" --upgrade`  — repoints the base to the working 3.14 and rewrites
pyvenv.cfg + Scripts\python.exe. ABI matches (both 3.14.3) so compiled wheels survive. Then reconnect.
(Use the matching `py -X.Y` for whatever `version` the venv's pyvenv.cfg declares.)

## Observations
- [fixed] schrodinger, rdkit, scholarly-access, fb-messenger — all had home=C:\Python314; repaired via --upgrade; verified (import + MCP initialize handshake). rdkit re-registered 74 tools; schrodinger serverInfo v1.27.2 #fixed
- [ok] Accurate venv scan: cheatengine (3.12 Python312), ghidra-mcp/ida-pro-mcp (3.14 pythoncore), hexstrike-ai (3.11 Python311), ocr/tiktok (3.12 uv) all have VALID bases — no dead-venv issue #ok
- [diagnosis] hexstrike-ai `-32000` was NOT a dead venv — its launcher (`hexstrike_mcp_launcher.py`) connects to a backend API at http://127.0.0.1:8888; it launches fine when that backend is up (health=healthy, v6.0.0). Cause was backend not running / startup-timeout race. Ensure the HexStrike backend server is running before reconnecting #diagnosis
- [note] postgres `-32001` is a different error class (connection refused — DB/server not running), not addressed #note
- [gotcha] Diagnostic scan: do NOT use `$home` as a PowerShell variable (reserved/read-only) — it silently breaks path checks #gotcha
