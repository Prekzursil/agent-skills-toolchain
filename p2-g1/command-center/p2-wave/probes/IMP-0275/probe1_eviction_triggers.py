"""IMP-0275 probe 1: eviction triggers and quorum recomputation.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0275/probe1_eviction_triggers.py
Exit 0 iff the live tools/council/participants/replace module: inactivity and
repeated-failure triggers fire only when due; eviction recomputes quorum over
the remaining seated ids; a second eviction VOIDS the council (below
quorum_min); a replacement restores quorum without inheriting state; and the
tests suite (10 tests) passes as an independent signal.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from replace import compute_quorum, evict, find_eviction_candidates, make_run, record_failure  # noqa: E402

checks = {}

inactivity_run = make_run(dave_last_activity_at=140)
due = find_eviction_candidates(inactivity_run)
checks["inactivity_due"] = [c["id"] for c in due] == ["dave"] and due[0]["reasons"] == ["inactivity"]

failure_run = make_run(dave_last_activity_at=200, carol_failures=3)
due2 = find_eviction_candidates(failure_run)
checks["repeated_failure_due"] = [c["id"] for c in due2] == ["carol"]

no_trigger = find_eviction_candidates(make_run(dave_last_activity_at=200))
checks["no_false_positive_when_fresh"] = no_trigger == []

after1 = evict(inactivity_run, "dave")
q1 = compute_quorum(after1)
checks["quorum_after_inactivity_eviction"] = q1["seated_count"] == 3 and q1["ok"] is True

after2 = evict(after1, "carol")
checks["quorum_void_after_two_evictions"] = compute_quorum(after2)["void"] is True

after3 = evict(after2, "carol", replacement={"id": "erin", "role": "critic"})
q3 = compute_quorum(after3)
checks["replacement_restored_quorum"] = q3["seated_count"] == 3 and q3["ok"] is True and "erin" in q3["seated_ids"]
checks["replacement_no_inheritance"] = all(
    c["author_id"] != "erin" for c in after3["contributions"]
)

fresh = make_run(dave_last_activity_at=200)
refreshed = record_failure(fresh, "dave", 210)
dave = next(p for p in refreshed["participants"] if p["id"] == "dave")
checks["failure_is_activity"] = find_eviction_candidates(refreshed) == []

suite = subprocess.run(
    [sys.executable, "-B", str(W / "tools" / "council" / "participants" / "tests" / "test_replace.py")],
    capture_output=True, text=True, cwd=str(W),
)
checks["test_suite_10_pass"] = suite.returncode == 0 and "ran=10" in suite.stdout

ok = all(checks.values())
out = {"probe": "probe1-eviction-triggers-quorum", "unit_id": "IMP-0275",
       "inactivity_due": checks["inactivity_due"],
       "repeated_failure_due": checks["repeated_failure_due"],
       "quorum_after_inactivity_eviction": q1["seated_count"],
       "quorum_void_after_two_evictions": checks["quorum_void_after_two_evictions"],
       "replacement_restored_quorum": checks["replacement_restored_quorum"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-eviction-triggers.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0275-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0275-probe1 triggers due-only; quorum recomputed, voided at two evictions, restored by replacement")
