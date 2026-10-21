#!/usr/bin/env python3
"""CyberStrike orphan-call census (G-10/CS-2 measurement substrate for S5).

Counts tool-call parts stuck in a non-terminal state ("running", "pending",
"created") per session, read-only against the live sqlite database.

Why this exists
---------------
Interruption/process-death orphans tool calls: every stream attempt keys tool
parts by the PROVIDER-side toolCallId, so an interrupt+resume or a retry mints
NEW callIDs while the originals keep status "running" forever (audit CS-2:
12% of recent sessions, 67 stuck calls per BOLT parent). Nothing in the
installed v1.1.16 binary reconciles these at startup. This script is the
standing measurement that (a) sizes the class, (b) verifies the callID patch
(callid_patch.diff) actually drives it to zero, and (c) feeds the G-13 test
battery verdict records.

Usage
-----
  python scripts/orphan_census.py                     # last 50 sessions, human table
  python scripts/orphan_census.py --limit 200 --all-statuses
  python scripts/orphan_census.py --json out.json     # machine-readable receipt
  python scripts/orphan_census.py --self-test         # parser fixture, no db needed

Exit codes: 0 = census ran (no orphans), 2 = census ran (orphans found:
use for gating), 1 = error (db missing / unparseable).

TWO-SIGNAL GUARD (read before declaring orphans)
------------------------------------------------
A part stuck at "running" is ONE signal, not a verdict. Before acting on a
count (killing a process, patching, reporting "N zombie calls"):
  1. Corroborate session liveness with a MECHANICALLY DIFFERENT probe —
     session.time_updated recency AND the cyberstrike process table (a session
     updated seconds ago may simply be mid-run; rows below live-window-min
     are flagged needs_corroboration=true and must NOT be counted as orphans).
  2. Re-run this census after the session has provably gone idle; only a
     count that persists across two runs spaced by the live window is an
     orphan. Re-running the same query immediately is NOT a second signal.
  3. json parse failures are counted and surfaced (parse_failures) — a spike
     there means schema drift, not zero orphans (adverse-inference rule).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

DEFAULT_DB = os.environ.get(
    "CYBERSTRIKE_DB", "C:/Users/Prekzursil/.local/share/cyberstrike/cyberstrike.db"
)
DEFAULT_STATUSES = ("running", "pending", "created")
LIVE_WINDOW_DEFAULT_MIN = 30


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(ms / 1000).isoformat(
            sep=" ", timespec="seconds"
        )
    except Exception:
        return str(ms)


def status_of(data: dict):
    st = data.get("state")
    if isinstance(st, dict):
        return st.get("status")
    return st


def census(db_path: str, limit: int, statuses, live_window_min: int) -> dict:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM session")
        total_sessions = cur.fetchone()[0]
        cur.execute(
            "SELECT id, title, time_updated FROM session ORDER BY time_updated DESC LIMIT ?",
            (limit,),
        )
        sessions = cur.fetchall()

        # SQL prefilter (proven on this db by audit step2/step4): only fetch
        # part rows whose serialized state mentions a candidate status. False
        # positives (the substring inside text/output payloads) are removed by
        # the JSON pass below; false negatives are impossible for the default
        # statuses because json.dumps always emits "status":"<value>".
        pats = [f'%"status":"{s}"%' for s in statuses]
        where = " OR ".join("data LIKE ?" for _ in pats)

        per_session = []
        orphan_sessions = 0
        stuck_total = 0
        parse_failures = 0
        now_ms = datetime.datetime.now().timestamp() * 1000
        for s in sessions:
            cur.execute(
                f"SELECT id, time_created, data FROM part WHERE session_id=? AND ({where}) ORDER BY time_created",
                (s["id"], *pats),
            )
            call_state = {}
            call_tool = {}
            call_time = {}
            n_tools = 0
            for r in cur.fetchall():
                try:
                    d = json.loads(r["data"])
                except Exception:
                    parse_failures += 1
                    continue
                if d.get("type") != "tool":
                    continue
                n_tools += 1
                cid = d.get("callID") or d.get("toolCallID") or r["id"]
                st = status_of(d)
                # keep the LATEST status seen for this callID; only non-None
                if st is not None:
                    call_state[cid] = st
                    call_tool[cid] = d.get("tool")
                    call_time[cid] = r["time_created"]
            stuck = {
                c: (call_tool[c], call_state[c], call_time[c])
                for c in call_state
                if call_state[c] in statuses
            }
            age_min = max(0, (now_ms - (s["time_updated"] or 0)) / 60000)
            entry = {
                "id": s["id"],
                "title": (s["title"] or "")[:70],
                "updated": ts(s["time_updated"]),
                "age_min": round(age_min, 1),
                "n_tool_parts": n_tools,
                "stuck": len(stuck),
                "stuck_by_status": {},
                "stuck_by_tool": {},
                "oldest_stuck_created": None,
                # two-signal guard: recent sessions may be LIVE, not orphaned
                "needs_corroboration": age_min < live_window_min,
            }
            oldest_raw = None
            for c, (tool, st, t) in stuck.items():
                entry["stuck_by_status"][st] = entry["stuck_by_status"].get(st, 0) + 1
                entry["stuck_by_tool"][tool or "unknown"] = (
                    entry["stuck_by_tool"].get(tool or "unknown", 0) + 1
                )
                if oldest_raw is None or t < oldest_raw:
                    oldest_raw = t
            if oldest_raw is not None:
                entry["oldest_stuck_created"] = ts(oldest_raw)
            if stuck:
                orphan_sessions += 1
                stuck_total += len(stuck)
            per_session.append(entry)

        return {
            "db": db_path,
            "scanned": len(per_session),
            "total_sessions_in_db": total_sessions,
            "orphan_sessions": orphan_sessions,
            "stuck_calls_total": stuck_total,
            "parse_failures": parse_failures,
            "statuses": list(statuses),
            "live_window_min": live_window_min,
            "two_signal_guard": (
                "counts are ONE signal; corroborate with session-liveness + a "
                "second census run after the live window before acting. Entries "
                "with needs_corroboration=true were updated inside the live "
                "window and may be genuinely running."
            ),
            "census": per_session,
        }
    finally:
        con.close()


FIXTURE_SESSIONS = [
    # (part rows as raw data strings, expected stuck count)
    (
        [
            '{"type":"tool","tool":"bash","callID":"c1","state":{"status":"completed"}}',
            '{"type":"tool","tool":"task","callID":"c2","state":{"status":"running"}}',
            '{"type":"text","text":"running substring decoy \\"status\\":\\"running\\""}',
        ],
        1,
    ),
    (
        [
            '{"type":"tool","tool":"write","callID":"c3","state":{"status":"error","error":"x"}}',
            '{"type":"tool","tool":"grep","callID":"c4","state":{"status":"pending"}}',
            '{"type":"tool","tool":"grep","callID":"c4","state":{"status":"completed"}}',
        ],
        0,
    ),
]


def self_test() -> int:
    """Both-states detector control: the parser must fire on the known-broken
    shape AND stay silent on the completed shape; the text-decoy must not
    count; a later terminal status for the same callID must win."""
    ok = True
    for rows, expected in FIXTURE_SESSIONS:
        call_state = {}
        n_tools = 0
        for raw in rows:
            d = json.loads(raw)
            if d.get("type") != "tool":
                continue
            n_tools += 1
            cid = d.get("callID") or "id"
            st = status_of(d)
            if st is not None:
                call_state[cid] = st
        stuck = sum(1 for v in call_state.values() if v in DEFAULT_STATUSES)
        verdict = "PASS" if stuck == expected else "FAIL"
        if stuck != expected:
            ok = False
        print(f"self-test fixture expected={expected} got={stuck} [{verdict}]")
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"sqlite path (default env CYBERSTRIKE_DB or {DEFAULT_DB})",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=50,
        help="recent sessions to scan (default 50, 0 = all)",
    )
    ap.add_argument(
        "--statuses",
        default=",".join(DEFAULT_STATUSES),
        help="comma list of non-terminal statuses",
    )
    ap.add_argument(
        "--live-window-min",
        type=int,
        default=LIVE_WINDOW_DEFAULT_MIN,
        help="recency window flagged needs_corroboration",
    )
    ap.add_argument(
        "--json", dest="json_out", help="write full census JSON to this path"
    )
    ap.add_argument(
        "--orphans-only",
        action="store_true",
        help="print only sessions with stuck calls",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="run the parser fixture and exit (no db)",
    )
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    statuses = tuple(s.strip() for s in args.statuses.split(",") if s.strip())
    if not statuses:
        print("FAILED:no statuses given", file=sys.stderr)
        return 1
    if not os.path.exists(args.db):
        print(f"FAILED:db not found: {args.db}", file=sys.stderr)
        return 1

    limit = args.limit if args.limit > 0 else 10**9
    result = census(args.db, limit, statuses, args.live_window_min)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"json receipt: {args.json_out}")

    rows = result["census"]
    if args.orphans_only:
        rows = [r for r in rows if r["stuck"] > 0]
    print(
        f"scanned={result['scanned']} orphan_sessions={result['orphan_sessions']} stuck_calls={result['stuck_calls_total']} parse_failures={result['parse_failures']}"
    )
    for r in rows:
        if (
            r["stuck"] == 0
            and args.orphans_only is False
            and result["orphan_sessions"] > 0
        ):
            continue  # compact table: show orphans plus a counter
        if r["stuck"] == 0:
            continue
        flag = " [LIVE?]" if r["needs_corroboration"] else ""
        print(
            f"  {r['id']} updated={r['updated']} stuck={r['stuck']} by_status={r['stuck_by_status']} by_tool={r['stuck_by_tool']}{flag}"
        )
    if result["parse_failures"] > 0:
        print(
            f"WARNING: {result['parse_failures']} part rows failed json parse — schema drift check needed"
        )
    return 2 if result["orphan_sessions"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
