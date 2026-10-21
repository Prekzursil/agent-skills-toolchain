#!/usr/bin/env python3
"""Post-merge guard: fail if parked heavy stdio reappear in Claude mcpServers.

Run after merge_generated_claude_mcp.py --write.
Exit 1 if any server tagged parked-stdio-use-mcphub (or known heavy list)
is present as a direct stdio entry in ~/.claude.json mcpServers.
"""

from __future__ import annotations

import json
import pathlib

AGENTS = pathlib.Path(r"C:\Users\Prekzursil\.agents\agents.json")
CLAUDE = pathlib.Path(r"C:\Users\Prekzursil\.claude.json")
TAG = "parked-stdio-use-mcphub"


def main() -> int:
    agents = json.loads(AGENTS.read_text(encoding="utf-8"))
    parked = {
        name
        for name, s in agents.get("mcp", {}).get("servers", {}).items()
        if TAG in (s.get("tags") or [])
        or (
            s.get("enabled") is False
            and "parked" in str(s.get("description", "")).lower()
        )
    }
    live = json.loads(CLAUDE.read_text(encoding="utf-8"))
    mcp = live.get("mcpServers") or {}
    bad = sorted(n for n in parked if n in mcp)
    # Also flag if mcphub missing while parked exist
    if (
        parked
        and "mcphub" not in mcp
        and not any(
            isinstance(v, dict) and "24680" in str(v.get("url", ""))
            for v in mcp.values()
        )
    ):
        print(f"WARN:guard-mcphub-missing parked={len(parked)}")
    if bad:
        print(f"FAIL:parked-stdio-reintroduced count={len(bad)} names={bad[:20]}")
        return 1
    print(f"SUCCESS:parked-stdio-guard ok parked={len(parked)} live_mcp={len(mcp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
