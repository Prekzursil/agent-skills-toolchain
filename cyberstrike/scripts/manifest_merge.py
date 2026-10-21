#!/usr/bin/env python3
"""Merge session-manifest shards + two-signal death check (G-8=B companion).

Shards:  <data>/manifest/sessions/<sessionID>.ndjson  (append-only, plugin-written)
Flat:    <data>/manifest/sessions.ndjson               (one row per session, last-wins)

TWO-SIGNAL DEATH CHECK (the rule, per single-signal-verification):
  A session may be declared dead ONLY when BOTH hold:
    S1  heartbeat stale: newest shard line ts older than --stale-min minutes
    S2  independent corroboration: (a) cyberstrike.db reports no activity for the
        session (read-only sqlite probe of the session row's updated_at), OR
        (b) no live TUI process tree can still be holding it (owner/TUI-side check).
  This script computes S1 always and S2a when the db is readable. S2b is documented
  for the operator/supervisor: never declare death from mtime alone. A shard whose
  last event is `idle` is NOT dead by itself — idle is a heartbeat, not a corpse.

Usage:
  python scripts/manifest_merge.py                 # merge + write flat manifest
  python scripts/manifest_merge.py --json          # print JSON, still merges
  python scripts/manifest_merge.py --status <id>   # death-check one session
Exit codes: 0 ok; 1 = FAILED (no shards found / bad session id).
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

DATA = Path.home() / ".local" / "share" / "cyberstrike"
SHARD_DIR = DATA / "manifest" / "sessions"
FLAT = DATA / "manifest" / "sessions.ndjson"
DB = DATA / "cyberstrike.db"
STALE_MIN_DEFAULT = 30


def read_shard(p: Path):
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"event": "corrupt-line", "ts": None, "sessionID": p.stem})
    return rows


def merge(stale_min: int):
    if not SHARD_DIR.is_dir() or not any(SHARD_DIR.glob("*.ndjson")):
        print("FAILED:manifest-merge no shards found under", SHARD_DIR)
        return 1, {}
    now = time.time()
    out = {}
    for shard in sorted(SHARD_DIR.glob("*.ndjson")):
        rows = read_shard(shard)
        if not rows:
            continue
        first = next((r for r in rows if r.get("ts")), None)
        last_ts = None
        for r in rows:
            if r.get("ts"):
                last_ts = r["ts"]
        last = rows[-1]
        meta = next((r for r in rows if r.get("title") or r.get("directory")), {})
        age_min = None
        if last and last.get("ts"):
            try:
                from datetime import datetime

                age_min = (now - datetime.fromisoformat(last["ts"]).timestamp()) / 60
            except ValueError:
                pass
        out[shard.stem] = {
            "sessionID": shard.stem,
            "title": meta.get("title"),
            "directory": meta.get("directory"),
            "parentID": meta.get("parentID"),
            "first_seen": first.get("ts") if first else None,
            "last_seen": last_ts,
            "last_event": last.get("event"),
            "events": len(rows),
            "heartbeat_age_min": round(age_min, 1) if age_min is not None else None,
            "s1_heartbeat_stale": age_min is not None and age_min > stale_min,
        }
    FLAT.parent.mkdir(parents=True, exist_ok=True)
    tmp = FLAT.with_suffix(".ndjson.tmp")
    tmp.write_text(
        "".join(
            json.dumps(v, ensure_ascii=False) + "\n"
            for v in sorted(out.values(), key=lambda v: v["last_seen"] or "")
        ),
        encoding="utf-8",
    )
    tmp.replace(FLAT)
    return 0, out


def db_signal(session_id: str):
    """S2a: read-only db probe. Returns None (unreadable) rather than guessing."""
    if not DB.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)
        try:
            row = con.execute(
                "SELECT updated_at FROM session WHERE id = ?", (session_id,)
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return "absent-from-db"
        return f"db-updated-at={row[0]}"
    except sqlite3.Error:
        return None  # table/schema unknown on this fork version — do NOT guess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--status", metavar="SESSION_ID")
    ap.add_argument("--stale-min", type=int, default=STALE_MIN_DEFAULT)
    args = ap.parse_args()
    rc, merged = merge(args.stale_min)
    if rc:
        return rc
    if args.status:
        row = merged.get(args.status)
        if not row:
            print(f"FAILED:manifest-status unknown session {args.status}")
            return 1
        s2a = db_signal(args.status)
        # Dead := S1 AND an INDEPENDENT death signal. s2a=="absent-from-db" is one.
        # A present-but-old db row needs the caller to compare its timestamp (S2b
        # or human); a present db row alone is NOT a death signal — under-claim.
        dead = bool(row["s1_heartbeat_stale"] and s2a == "absent-from-db")
        print(
            json.dumps(
                {
                    **row,
                    "s2a_db_signal": s2a,
                    "s2b_process_check": "operator/TUI-side (not computable here)",
                    "dead_two_signal": dead,
                    "verdict_note": "dead requires S1 AND (S2a or S2b); idle is a heartbeat, not a corpse",
                },
                indent=1,
                ensure_ascii=False,
            )
        )
        return 0
    print(f"SUCCESS:manifest-merge sessions={len(merged)} -> {FLAT}")
    if args.json:
        print(json.dumps(merged, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
