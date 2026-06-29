#!/usr/bin/env python3
r"""PERSIST-NUDGE (Stop hook) — close the "did real work, saved nothing" gap.

The recurring loss: a session does substantial DURABLE work (many edits, a commit,
a decision) but never writes it to basic-memory, so the next compaction/session
starts cold. This hook nudges — ONCE PER SESSION, only when the signal is strong —
to capture the durable decision/state via basic-memory `write_note` (or note.py).

Fires only when ALL hold:
  * this session has real durable work:  >= EDIT_THRESHOLD file edits, OR >= 1 git commit;
  * NOTHING was persisted this session (no basic-memory write_note/edit_note, no note.py);
  * we have not already nudged this session (once-per-session marker).

That conjunction makes it high-signal and non-naggy. Inject-only; FAIL-OPEN.
Opt-out: PERSIST_NUDGE=off or a .disabled file.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path


# --------------------------------------------------------------------------- calibrated-silence
# Fail-open shim: the persistence nudge is SDT-gated by should_interject(). ANY error
# (gate missing, corrupt ledger, bad input) returns ALLOW — suppression is the dangerous failure.
def _cs_allow(itype, ctx):
    try:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).resolve().parent.parent / "calibrated-silence"))
        import calibrated_silence as _c
        return _c.should_interject(itype, ctx)[0]
    except Exception:
        return True


def _cs_record(itype, ck, sid):
    try:
        import calibrated_silence as _c
        _c.record_interjection(itype, ck, sid)
    except Exception:
        pass


THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
SEEN_DIR = Path(tempfile.gettempdir()) / "persist-nudge"
EDIT_THRESHOLD = int(os.environ.get("PERSIST_NUDGE_EDITS", "6"))

_GIT_COMMIT = re.compile(r"\bgit\b[^\n]*\bcommit\b", re.IGNORECASE)
_PERSIST_BASH = re.compile(r"note\.py|write_note|basic[-_]memory[^\n]*(write|note)", re.IGNORECASE)
_BM_WRITE_TOOL = re.compile(r"mcp__basic-memory__(write_note|edit_note|create)", re.IGNORECASE)


def _iter_events(transcript_path: str):
    p = Path(transcript_path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _tool_uses(ev: dict):
    msg = ev.get("message") or {}
    content = msg.get("content")
    if content is None:
        content = ev.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            yield str(b.get("name") or ""), json.dumps(b.get("input") or {})


def tally(transcript_path: str) -> dict:
    edits = commits = 0
    persisted = False
    for ev in _iter_events(transcript_path):
        for name, inp in _tool_uses(ev):
            if name in ("Edit", "Write", "MultiEdit"):
                edits += 1
            elif name in ("Bash", "PowerShell"):
                if _GIT_COMMIT.search(inp):
                    commits += 1
                if _PERSIST_BASH.search(inp):
                    persisted = True
            if _BM_WRITE_TOOL.search(name):
                persisted = True
    return {"edits": edits, "commits": commits, "persisted": persisted}


def _first_session(sid: str) -> bool:
    try:
        SEEN_DIR.mkdir(parents=True, exist_ok=True)
        f = SEEN_DIR / f"{sid}.done"
        if f.exists():
            return False
        f.write_text("1", encoding="utf-8")
        return True
    except Exception:
        return True  # fail-open


def should_fire(t: dict) -> bool:
    if t["persisted"]:
        return False
    return t["edits"] >= EDIT_THRESHOLD or t["commits"] >= 1


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("PERSIST_NUDGE", "").lower() in ("off", "0", "false"):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("stop_hook_active"):
            return 0
        tp = str(data.get("transcript_path") or "")
        if not tp:
            return 0
        t = tally(tp)
        if not should_fire(t):
            return 0
        sid = str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")
        # CALIBRATED SILENCE: gate BEFORE burning the once-per-session marker, so a turn we
        # suppress now can still nudge on a later turn; fail-open allows on any gate error.
        if not _cs_allow("nudge", {"session_id": sid}):
            return 0
        if not _first_session(sid):
            return 0
        did = []
        if t["commits"]:
            did.append(f"{t['commits']} commit(s)")
        if t["edits"]:
            did.append(f"{t['edits']} edit(s)")
        msg = (
            f"[persist-nudge] This session did durable work ({', '.join(did)}) but "
            f"nothing was saved to memory. Before context is lost, write the durable "
            f"decision/state with basic-memory write_note (or note.py for the event "
            f"ledger) so it survives the next compaction/session. (One-time nudge.)"
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop", "additionalContext": msg}}))
        _cs_record("nudge", "persist:durable-work", sid)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
