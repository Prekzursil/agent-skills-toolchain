#!/usr/bin/env python3
"""SessionStart hook: keep every project .mcp.json synced to the canonical ~/.mcp.json.

The canonical source of truth is ~/.mcp.json (also committed to the toolchain as
tools/mcp/canonical-mcp-servers.json). This hook mirrors its `mcpServers` into every
KNOWN project .mcp.json on session start, so a fix to the canonical propagates
everywhere and per-project files can never drift back to stale npx-stub commands.

Interim measure until the user-scope promote removes per-project files entirely.
Only writes on drift, backs up once per drift, and is fail-open (any error -> exit 0).
Rule: edit the CANONICAL (~/.mcp.json) only; this hook overwrites project copies.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

HOME = os.path.expanduser("~").replace("\\", "/")
CANON = HOME + "/.mcp.json"
# Scoped roots where the user's project .mcp.json live (fast globs, not a full-disk scan).
GLOBS = [
    "D:/Research/.mcp.json",
    "D:/Research/projects/*/.mcp.json",
    HOME + "/Documents/GitHub/*/.mcp.json",
]
# battlecats-toolkit = ralph's intentional project scope (--setting-sources project,local); never touch.
EXCLUDE = ("node_modules", "/.git/", "_config-backups", ".retired", ".bak",
           ".tmp", "battlecats-toolkit")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def main() -> int:
    canon = _load(CANON)
    canon_servers = (canon or {}).get("mcpServers")
    if not canon_servers:
        return 0
    synced = []
    for pat in GLOBS:
        for f in glob.glob(pat):
            f = f.replace("\\", "/")
            if f == CANON or any(x in f for x in EXCLUDE):
                continue
            d = _load(f)
            if d is None or d.get("mcpServers") == canon_servers:
                continue  # unreadable or already in sync
            if len(d.get("mcpServers", {})) < 10:
                continue  # minimal project-specific config (e.g. bilbo agent_handler) -> leave it
            try:
                bak = f + ".bak-canonsync-" + time.strftime("%Y%m%d-%H%M%S")
                if not os.path.exists(bak):
                    import shutil
                    shutil.copy2(f, bak)
                d["mcpServers"] = canon_servers
                tmp = f + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(d, fh, indent=2)
                os.replace(tmp, f)
                synced.append(os.path.basename(os.path.dirname(f)) or f)
            except Exception:
                continue
    if synced:
        print("[mcp-canonical-sync] synced %d project .mcp.json to canonical: %s"
              % (len(synced), ", ".join(synced)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # fail-open: never block session start
        print("[mcp-canonical-sync] warn: %s" % e, file=sys.stderr)
        sys.exit(0)
