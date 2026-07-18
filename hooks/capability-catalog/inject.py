#!/usr/bin/env python3
"""CAPABILITY-CATALOG injection — SessionStart auto-tool-selection primer.

Injects a compact, curated "server/skill -> what + WHEN to use" catalog (from
catalog.json) as additionalContext so the agent reaches for the right MCP/skill
instead of a makeshift script — closing the "powerful tools sit unused unless
explicitly invoked" gap, especially the under-used DEPTH (Serena LSP, tooluniverse
find_tools, chrome-devtools perf, rdkit/schrodinger, secsearch/lolbin/cve, RE MCPs).

Inject-only; never blocks; FAIL-OPEN (any error -> exit 0, emit nothing). Skips the
'compact' source (the compact-restore hook already re-primes context — no need to
re-dump the catalog there) and dedups to once per session. Opt-out: CAPABILITY_CATALOG=off
or a .disabled file.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
CATALOG = THIS / "catalog.json"
DISABLED = THIS / ".disabled"
SEEN_DIR = Path(tempfile.gettempdir()) / "capability-catalog"


def _first_session(sid: str) -> bool:
    """True the first time we inject for this session; record it (dedup)."""
    try:
        SEEN_DIR.mkdir(parents=True, exist_ok=True)
        f = SEEN_DIR / f"{sid}.seen"
        if f.exists():
            return False
        f.write_text("1", encoding="utf-8")
        return True
    except Exception:
        return True  # fail-open: better one extra inject than a crash


def build_message() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8", errors="replace"))
    lines = [data.get("header", "[capabilities]")]
    for grp in data.get("groups", []):
        g = grp.get("g", "")
        for item in grp.get("items", []):
            lines.append(f"- {g}: {item}" if g else f"- {item}")
    footer = data.get("footer")
    if footer:
        lines.append(footer)
    return "\n".join(lines)


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("CAPABILITY_CATALOG", "").lower() in ("off", "0", "false"):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            data = {}
        # Skip compaction restores (context is re-primed elsewhere; avoid re-dumping).
        if str(data.get("source") or "").lower() == "compact":
            return 0
        sid = str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")
        if not _first_session(sid):
            return 0
        msg = build_message()
        # Append the CURRENT project's card (per-project intelligence) after the global
        # catalog, riding this same SessionStart carrier. Best-effort + fail-open: a card
        # problem must never drop the global catalog.
        try:
            if str(THIS) not in sys.path:
                sys.path.insert(0, str(THIS))
            import project_card  # sibling module
            block = project_card.build_block(data.get("cwd") or os.getcwd())
            if block:
                msg = msg + "\n\n" + block
        except Exception:
            pass
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": msg}}))
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
