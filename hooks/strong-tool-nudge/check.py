#!/usr/bin/env python
"""PreToolUse(Bash|Write|Edit|MultiEdit) — strong-tool nudge.

Catches the agent HAND-ROLLING a capability a registered MCP already provides (pip install rdkit,
requests.get scraping, pdfplumber, git-grep symbol-walk, pandas CSV munging) at the EXACT moment of the
action — the window the UserPromptSubmit router structurally misses. Reads the SHARED capabilities.py
hand-roll signatures (one source of truth with the router). Inject-only (additionalContext); NEVER blocks;
fail-open; loop-marker-gated so it fires ONCE per signature per session (no nagging).

Opt-out: STRONG_TOOL_NUDGE=off, or hooks/strong-tool-nudge/.disabled
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.home() / ".claude" / "hooks" / "skill-router"))
try:
    import capabilities as _caps
except Exception:
    _caps = None


def _first_seen(sid, sig):
    """Return True the FIRST time this (session, signature) is seen; record it. Once-per-session gate."""
    try:
        d = Path(tempfile.gettempdir()) / "strong-tool-nudge"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{sid}.seen"
        seen = set(f.read_text(encoding="utf-8").split("\n")) if f.exists() else set()
        if sig in seen:
            return False
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(sig + "\n")
        return True
    except Exception:
        return True  # fail-open: better to nudge once than crash


def main():
    try:
        if (THIS / ".disabled").exists() or os.environ.get("STRONG_TOOL_NUDGE", "").lower() in ("off", "0", "false"):
            return 0
        if _caps is None:
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        ti = data.get("tool_input") or {}
        text = str(ti.get("command") or ti.get("content") or ti.get("new_string") or "")
        if len(text) < 6:
            return 0
        hits = _caps.match(text, hand_roll_only=True)
        if not hits:
            return 0
        sid = str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")
        fresh = [lbl for lbl, _h in hits if _first_seen(sid, hashlib.md5(lbl.encode()).hexdigest()[:10])]
        if not fresh:
            return 0
        msg = ("[strong-tool] You're about to hand-roll a capability a registered MCP already provides — "
               "prefer: " + " ; ".join(fresh[:2]))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}))
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
