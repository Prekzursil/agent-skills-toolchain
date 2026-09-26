---
name: HexStrike AI install layout
description: Custom local layout of the hexstrike-ai MCP server install — non-obvious
  launcher, local server.py optimization, log rotation, and werkzeug silencing must
  be preserved across upgrades
type: project
originSessionId: 174a3e5e-8ec8-4b41-8953-de3f1a677d12
permalink: main/claude-memory/root/hexstrike-ai-install
---

HexStrike AI is installed at `C:\Users\Prekzursil\.local\opt\hexstrike-ai` (forked from `0x4m4/hexstrike-ai`, branch `master`). Three pieces are local-only and must be preserved when pulling upstream:

1. **`hexstrike_mcp_launcher.py`** — custom launcher (untracked in git). Auto-spawns `hexstrike_server.py` with `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` if port 8888 is closed, polls `/health` every 1 s for up to 180 s, then `os.execve`'s itself into `hexstrike_mcp.py --server http://127.0.0.1:8888`. Registered at `~/.claude.json` line 662 as the MCP `command` for `hexstrike-ai`.

2. **Local `/health` optimization in `hexstrike_server.py`** — defers tool detection unless `?full=1` is passed, and replaces subprocess `which X` with `shutil.which(X)`. The probe path is O(1) instead of running 60+ subprocess calls per ping.

3. **werkzeug silencing + log rotation in `hexstrike_server.py`** (added 2026-05-04):
   - `from logging.handlers import RotatingFileHandler` at the top imports
   - `RotatingFileHandler('hexstrike.log', maxBytes=10*1024*1024, backupCount=3, encoding='utf-8')` replaces the unbounded `FileHandler`
   - `logging.getLogger('werkzeug').setLevel(logging.ERROR)` after `basicConfig`

4. **Windowless spawning in `hexstrike_mcp_launcher.py`** (added 2026-05-05):
   - `spawn_server` uses `pythonw.exe` (GUI subsystem) instead of `python.exe` (CUI). Prevents Windows from allocating a console window per spawn. Falls back to `python.exe` if `pythonw.exe` is missing.
   - Adds `subprocess.CREATE_NO_WINDOW` to creationflags as belt-and-suspenders for any future fallback path.
   - `healthy()` switched from `urllib.request.urlopen` to `requests.get` (CWE-939: urllib's file:// scheme support flagged by semgrep). Scheme is also asserted as `http://` before the call. `requests` is already in the venv via `requirements.txt`.

**Why:** Without (3), the Flask dev server's per-request access log writes every `/health` probe (~1 Hz from MCP reconnects) to `hexstrike.log`, which grew to 243 MB + a parallel 148 MB in `logs/server.stdout.log` (~391 MB total) before being noticed. Without (1) and (2), the launcher pattern wouldn't work at all — they're the boundary between Claude Code's MCP transport and the long-running Flask server.

**How to apply:** When `git pull`ing upstream `0x4m4/hexstrike-ai`, stash `hexstrike_server.py` first and pop after — the launcher and venv are untracked so they survive automatically. Verify the three patch markers with `grep -n "RotatingFileHandler\|werkzeug.*setLevel\|tool_scan_deferred" hexstrike_server.py` — should return ≥4 hits. Upstream is currently a slow-moving repo (last code change pre-dates 2026-04-27), so most pulls will be README-only.

**Cleanup pattern when servers go orphaned:** `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*hexstrike-ai*' }` finds them. The launcher's detached flag means `Stop-Process` on the parent won't reap the child — kill the child (the python311 worker) too.