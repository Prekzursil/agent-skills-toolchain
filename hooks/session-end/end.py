#!/usr/bin/env python3
"""session-end/end.py — SessionEnd hook: terminal ledger checkpoint + unflushed-spool alert.

Fires when a Claude Code session closes for any reason (clear, resume, logout,
prompt_input_exit, bypass_permissions_disabled, other). CC ignores exit code
and stdout for SessionEnd — side-effects only.

Jobs:
  (a) Append a TERMINAL event-ledger entry (kind="note") recording session-end + reason.
      Reuses ledger.append() from event-ledger/ledger.py — same format as stop-hook.py.
  (b) Check memory-spool for unflushed entries via _common.list_spools(); if any exist,
      write a second ledger note so the next session's flush_check/SessionStart can surface
      them. Does NOT write to basic-memory — a hook cannot reliably call MCP tools.

SessionEnd payload (stdin JSON):
  session_id, cwd, reason, hook_event_name

Opt-out: SESSION_END=off  OR  create hooks/session-end/.disabled
Fail-open: any exception at any layer → exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent

# ── path bootstrap: make sibling hook modules importable ──────────────────────
_LEDGER_DIR = str(THIS.parent / "event-ledger")
_SPOOL_DIR = str(THIS.parent / "memory-spool")
for _p in (_LEDGER_DIR, _SPOOL_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Module-level import so tests can patch `end._ledger` cleanly.
try:
    import ledger as _ledger  # type: ignore[import]
except Exception:
    _ledger = None  # type: ignore[assignment]

DISABLED = THIS / ".disabled"


# ── helpers ───────────────────────────────────────────────────────────────────

def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("SESSION_END", "").lower() in ("off", "0", "false")


def _list_spools() -> list:
    """Return list of unflushed spool Paths from memory-spool/_common. Fail-open → []."""
    try:
        import _common as C  # type: ignore[import]  # noqa: PLC0415
        return C.list_spools()
    except Exception:
        return []


def _spool_title(p: "Path") -> str:
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
        return str(rec.get("title") or p.stem)[:60]
    except Exception:
        return str(p.name)[:60]


# ── core logic ────────────────────────────────────────────────────────────────

def run(data: dict) -> int:
    """Process a parsed SessionEnd payload. Always returns 0 — outer try/except is the safety net."""
    if _ledger is None:
        return 0

    session_id = str(data.get("session_id") or "")
    cwd = str(data.get("cwd") or os.getcwd())
    reason = str(data.get("reason") or "unknown")
    short_sid = session_id[:16]

    # (a) Terminal checkpoint: record the session end in the event ledger.
    try:
        _ledger.append(
            cwd,
            "note",
            text=f"SessionEnd: reason={reason} session={short_sid}",
            reason=reason,
            session=short_sid,
            hook="session-end",
        )
    except Exception:
        pass  # fail-open: ledger write must never crash the hook

    # (b) Unflushed-spool check: surface any memory writes that were never confirmed.
    try:
        spools = _list_spools()
        if spools:
            titles = [_spool_title(Path(p)) for p in spools[:5]]
            extra = "" if len(spools) <= 5 else f" (+{len(spools) - 5} more)"
            note_text = (
                f"SessionEnd: {len(spools)} memory-spool write(s) unconfirmed at exit — "
                f"{', '.join(titles)}{extra}. "
                f"Re-attempt write_note(s) next session or discard the spool."
            )
            _ledger.append(
                cwd,
                "note",
                text=note_text,
                hook="session-end",
                unflushed_count=len(spools),
                session=short_sid,
            )
    except Exception:
        pass  # fail-open: spool check must never crash the hook

    return 0


def main(data: dict | None = None) -> int:
    """Entry point. Accepts pre-parsed dict (tests) or reads stdin (production)."""
    try:
        if _disabled():
            return 0
        if data is None:
            try:
                raw = sys.stdin.read() or "{}"
            except Exception:
                raw = "{}"
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
        return run(data)
    except Exception:
        return 0  # fail-open: outer catch-all


if __name__ == "__main__":
    sys.exit(main())
