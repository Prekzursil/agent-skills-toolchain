---
name: claude-swap-install
description: claude-swap multi-account switcher installed for Claude Code; safe-usage
  rules + Windows UTF-8 gotcha
metadata:
  node_type: memory
  type: reference
  originSessionId: 0d02c989-c946-4f88-98b0-1c889787bc73
permalink: main/claude-memory/root/claude-swap-install
---

claude-swap (`realiti4/claude-swap`, by Onur Cetinkol, MIT, on PyPI) installed 2026-06-05 via `uv tool install claude-swap` → `cswap` v0.11.0 (execs `claude-swap`/`cswap` at `~/.local/bin`). Switches between multiple Claude Code OAuth accounts without re-login. Security-verified CLEAN from source: only network endpoints are Claude's OAuth token refresh (`platform.claude.com/v1/oauth/token`, real CC client id) + PyPI update check; sole dep `keyring`; no telemetry/exfil; PyPI↔repo provenance matches. NOT authored by umesh-malik.com (that's just a blog guide).

**Accounts registered:** slot 1 = mariusvisalon70@gmail.com, slot 2 = prekzursil1993@gmail.com.

**⭐ Safety distinction (traced in switcher.py):** `cswap --add-account` is READ-ONLY on live creds — reads `~/.claude/.credentials.json`, copies to cswap's encrypted `.enc` backup; NO token refresh/rotation, NO live-file write → safe to run with sessions open. `cswap --switch`/`--switch-to` REWRITE the live `~/.claude/.credentials.json` → swap the active account for ALL running Claude sessions at once → run deliberately. `cswap --list` makes an authenticated usage API call (not local). This is a multi-account switcher, NOT a fix for the concurrent-session 401 refresh-race (see [[claude-code-401-auth-notes]]); `--switch` can worsen concurrency.

**Windows console gotcha:** `--status`/`--list`/`--tui` crash with `UnicodeEncodeError: 'charmap'` (cp1252) on box-drawing chars. FIXED permanently via User env `PYTHONIOENCODING=utf-8` (deliberately chose the narrow var over `PYTHONUTF8=1`, which would change `open()`/filesystem encoding and risk the heavy local Python tooling).

Backups: `~/.claude-swap-backup/` (per-account creds = encrypted `.enc`; `configs\*.json`; `--export` = plaintext JSON). Uninstall: `cswap --purge` then `uv tool uninstall claude-swap`. ToS gray area only if rotating accounts to dodge usage limits. Full doc: `source/reports/CLAUDE-SWAP-INSTALL-AND-SECURITY-2026-06-05.md`. Related cleanup: [[disk-cleanup-c-drive]].