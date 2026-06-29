#!/usr/bin/env python3
r"""memory-spool/flush_check.py — confirm spooled basic-memory writes actually landed.

Two modes (wired as two slots, one script — mirrors mcp-liveness/liveness.py):

  posttool      PostToolUse, matcher mcp__basic-memory__write_note|edit_note
                Sees the tool_response. If the write SUCCEEDED, clear that spool entry
                (it is safely persisted). If it FAILED/empty, KEEP the spool and inject a
                LOUD alert that memory was NOT saved.

  sessionstart  SessionStart
                Report any unflushed spool entries — writes that were spooled but never
                confirmed saved (the session died between the Pre spool and the Post
                confirm, e.g. during a memory-store outage). "N memory writes were never
                confirmed saved - re-attempt?" Surfaces each entry once, then prunes
                stale ones (TTL).

FAIL-OPEN: any error -> exit 0. Opt-out: MEMORY_SPOOL=off or a .disabled file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("MEMORY_SPOOL", "").lower() in ("off", "0", "false")


def run_posttool(data: dict) -> int:
    tool = str(data.get("tool_name") or "")
    if tool not in C.SPOOLED_TOOLS:
        return 0
    ti = data.get("tool_input") or {}
    key = C.payload_key(tool, ti)
    matches = C.find_spools(key)
    # Secondary correlation by tool_use_id, in case the Post tool_input drifted.
    uid = str(data.get("tool_use_id") or "")
    for p in C.find_spools_by_uid(uid):
        if p not in matches:
            matches.append(p)
    if not matches:
        return 0  # nothing spooled (spool.py disabled or payload changed) -> nothing to do
    tr = data.get("tool_response")
    if tr is None:
        tr = data.get("tool_output")
    ok = C.response_ok(tr)
    if ok:
        # Confirmed saved -> clear the spool entry (or entries on identical retries).
        for p in matches:
            try:
                p.unlink()
            except OSError:
                pass
        return 0
    # FAILED / empty -> keep the spool, mark failed, alert loudly.
    title = C.title_of(tool, ti)
    kept = matches[-1]
    try:
        rec = C.load_json(kept)
        rec["status"] = "failed"
        rec["failed_ts"] = C.now()
        kept.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    short = tool.split("__")[-1]
    C.emit("PostToolUse",
           f"[memory-spool] basic-memory {short} did NOT confirm saving '{title}'. "
           f"Memory is NOT persisted. The payload is spooled at {kept} - re-attempt the "
           f"write (check mcp-liveness: the store may be down) before relying on recall.")
    return 0


def run_sessionstart(data: dict) -> int:
    spools = C.list_spools()
    if not spools:
        return 0
    rep = C.load_reported()
    ttl = C.SPOOL_TTL_DAYS * 86400.0
    unflushed = []
    for p in spools:
        rec = C.load_json(p)
        ts = 0.0
        try:
            ts = float(rec.get("ts") or 0)
        except (TypeError, ValueError):
            ts = 0.0
        # Garbage-collect ancient entries so the spool can't grow without bound.
        if ts and (C.now() - ts) > ttl:
            try:
                p.unlink()
            except OSError:
                pass
            continue
        if p.name in rep:
            continue  # already surfaced once
        unflushed.append((p, rec))
    if not unflushed:
        return 0
    titles = ", ".join(f"'{r.get('title') or p.stem}'" for p, r in unflushed[:5])
    extra = "" if len(unflushed) <= 5 else f" (+{len(unflushed) - 5} more)"
    ts_now = C.now()
    for p, _ in unflushed:
        rep[p.name] = ts_now
    C.save_reported(rep)
    C.emit("SessionStart",
           f"[memory-spool] {len(unflushed)} memory write(s) were spooled but never "
           f"confirmed saved: {titles}{extra}. These were lost mid-write (likely a "
           f"basic-memory outage) - re-attempt the write_note(s) or discard the spool "
           f"({C.SPOOL_DIR}).")
    return 0


def main(argv) -> int:
    try:
        if _disabled():
            return 0
        mode = (argv[0] if argv else "sessionstart").lower()
        data = C.read_stdin()
        if mode == "posttool":
            return run_posttool(data)
        return run_sessionstart(data)
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
