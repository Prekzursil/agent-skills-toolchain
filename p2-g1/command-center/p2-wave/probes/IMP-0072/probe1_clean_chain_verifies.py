#!/usr/bin/env python3
"""IMP-0072 probe1 (source): a genuine append-only log verifies clean end to end."""
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_chain import EventLog, build_demo_log, verify_log  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0072-p1-"))
    try:
        log = work / "events.jsonl"
        rows = build_demo_log(log)
        res = verify_log(log)
        ev = EventLog(log)
        extra = ev.append("moderate", "moderator:zoe", "demo-pkg", "1.0.1", "2026-08-24T18:00:00Z", {"flag": "post"})
        res2 = verify_log(log)
        checks = {
            "demo_log_ok": res.ok is True and res.record_count == 5,
            "actions_covered": {r["action"] for r in rows} == {"publish", "yank", "deprecate", "revoke", "moderate"},
            "append_chains": res2.ok is True and res2.record_count == 6,
            "new_hash_differs": extra["record_hash"] != rows[-1]["record_hash"],
        }
        print(checks)
        if not all(checks.values()):
            print("FAILED:IMP-0072-probe1 clean chain did not verify")
            return 1
        print("SUCCESS:IMP-0072-probe1 genuine log verifies; append chains from the tail")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
