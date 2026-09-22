#!/usr/bin/env python3
"""manifest_poll.py — poll-based session manifest writer (PRIMARY after event-hook PARKED).

The fork's 1.1.16 binary does not dispatch plugin event hooks to file://-loaded
plugins (session.* keys absent from typings AND the generic `event` hook silent —
verified live 2026-09-22, logs 171843 + prior). This writer polls the session
store (sqlite, mode=ro) and appends shard lines in the exact shape
scripts/manifest_merge.py consumes.

Usage:
  python scripts/manifest_poll.py --once        # one pass (scheduled task calls this)
  python scripts/manifest_poll.py --interval 300 # daemon-ish loop
Shards:  <data>/manifest/sessions/<sessionID>.ndjson  (append-only)
State:   <data>/manifest/_poll_state.json             (last-seen time_updated per id)
Exit: 0 = pass complete (rows written or not); 2 = store unreadable.
"""
import argparse
import datetime
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.environ.get("CYBERSTRIKE_DATA") or os.path.join(
    os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".",
    ".local", "share", "cyberstrike")
DB = os.path.join(DATA_DIR, "cyberstrike.db")
MANIFEST_DIR = os.path.join(DATA_DIR, "manifest", "sessions")
STATE = os.path.join(DATA_DIR, "manifest", "_poll_state.json")


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def sanitize(sid):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in sid)


def pass_once():
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    state = {}
    if os.path.exists(STATE):
        try:
            state = json.load(open(STATE, encoding="utf-8"))
        except Exception:
            state = {}
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    except Exception as e:
        print(f"FAILED:store-open {e}")
        return 2
    written = 0
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(session)")}
        need = {"id", "time_created", "time_updated"} <= cols
        if not need:
            print(f"FAILED:schema cols={sorted(cols)[:10]}")
            return 2
        title_col = "title" if "title" in cols else "NULL as title"
        directory_col = "directory" if "directory" in cols else "NULL as directory"
        q = (f"SELECT id, time_created, time_updated, {title_col}, {directory_col} "
             "FROM session ORDER BY time_updated")
        for sid, tc, tu, title, directory in con.execute(q):
            key = sid if isinstance(sid, str) else str(sid)
            tu_s = tu if isinstance(tu, str) else str(tu or "")
            if state.get(key) == tu_s:
                continue
            row = {
                "event": "session.updated" if key in state else "session.created",
                "ts": now_iso(),
                "sessionID": key,
                "title": title,
                "directory": directory,
                "time_created": tc if isinstance(tc, str) else str(tc or ""),
                "time_updated": tu_s,
                "source": "manifest_poll",
            }
            with open(os.path.join(MANIFEST_DIR, sanitize(key) + ".ndjson"), "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            state[key] = tu_s
            written += 1
    finally:
        con.close()
    tmp = STATE + ".tmp"
    json.dump(state, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, STATE)
    print(f"SUCCESS:manifest-poll written={written} tracked={len(state)}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    a = ap.parse_args()
    if a.interval and not a.once:
        import time
        while True:
            pass_once()
            time.sleep(a.interval)
    return pass_once()


if __name__ == "__main__":
    sys.exit(main())
