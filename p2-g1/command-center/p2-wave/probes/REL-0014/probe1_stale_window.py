#!/usr/bin/env python3
# REL-0014 probe1: stale-window + snapshot freshness (resume 2026-10-25).
# T1 stale_stored_result: a 48h-old stored green MUST be refused with a
#   visible REFUSED line in the promotion log, then a forced rescan runs and
#   promotion completes only on its own exit.
# T4 distinct_snapshot_ids: two pulls of identical advisory content MUST get
#   distinct snapshot ids (a result is a query against a live database).
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0014_scanner", HERE / "scanner.py")
S = importlib.util.module_from_spec(spec)
sys.modules["rel0014_scanner"] = S
spec.loader.exec_module(S)
CLEAN = HERE / "fixtures" / "lockfile-clean.json"


def fail(msg):
    print("FAILED:REL-0014-probe1 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0014-p1-"))
    try:
        now = "2026-08-24T18:00:00Z"
        # rebuild stored from a real pull at the stale timestamp
        p0 = subprocess.run([sys.executable, "-B", str(HERE / "scanner.py"),
                             "--lockfile", str(CLEAN), "--db-pull", "2026-08-22T18:00:00Z",
                             "--report", str(tmp / "stored.json")],
                            capture_output=True, text=True)
        stored = json.loads((tmp / "stored.json").read_text(encoding="utf-8"))
        log = tmp / "promotion-log.json"
        g = subprocess.run([sys.executable, "-B", str(HERE / "gate.py"),
                            "--stored", str(tmp / "stored.json"), "--now", now,
                            "--window", "86400", "--lockfile", str(CLEAN),
                            "--log", str(log), "--rescan-pull", now],
                           capture_output=True, text=True, timeout=300)
        events = json.loads(log.read_text(encoding="utf-8"))
        refused = [e for e in events if e.get("event") == "REFUSED"]
        rescan = [e for e in events if e.get("event") == "forced-rescan"]
        verdict = [e for e in events if e.get("event") == "promotion-verdict"]
        print("promotion_events=" + json.dumps([e.get("event") for e in events]))
        if not refused or refused[0].get("classification") != "stale-green":
            return fail("stale-green-refusal-not-visible")
        if refused[0].get("age_seconds") != 172800:
            return fail("age-arithmetic:" + str(refused[0].get("age_seconds")))
        if not rescan or rescan[0].get("exit_code") != 0:
            return fail("forced-rescan-missing-or-failed")
        if not verdict or verdict[-1].get("allowed") is not True:
            return fail("promotion-not-completed-on-fresh-rescan")
        print("REFUSED_stale_green=visible age_seconds=172800 window=86400 rescan_exit=0")
        # T4: two pulls, same content, distinct snapshot ids
        s1 = S.pull_snapshot("2026-08-24T18:00:00Z")
        s2 = S.pull_snapshot("2026-08-24T19:00:00Z")
        print("snapshot_id_1=" + s1["snapshot_id"][:16] + "... snapshot_id_2=" + s2["snapshot_id"][:16] + "...")
        if s1["snapshot_id"] == s2["snapshot_id"]:
            return fail("snapshot-ids-not-distinct")
        if s1["content_sha256"] != s2["content_sha256"] or s1["advisory_count"] != 2:
            return fail("snapshot-content-shape-drift")
        rec = json.loads((REPO / "command-center/receipts/REL-0014.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if rec.get("scan", {}).get("window_length_seconds") != 86400:
            return fail("receipt-window-drift")
        if rec.get("advisory_database", {}).get("snapshot_id") != rec.get("scan", {}).get("snapshot_id"):
            return fail("receipt-snapshot-id-not-carried")
        refused_in_receipt = any(e.get("event") == "REFUSED" for e in rec.get("promotion_log") or [])
        if not refused_in_receipt:
            return fail("receipt-refusal-not-visible")
        print("SUCCESS:REL-0014-probe1 stale-window-and-snapshot-freshness")
        return 0
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
