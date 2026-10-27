#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0005"
OUT = (REPO / "command-center/receipts/TST-0005.json").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
"""Both-states digest barrier: a real digest for a live artifact is ACCEPTED;
a well-formed digest for an ABSENT path is REJECTED with digest not parsed and
the absent path named."""
import hashlib
import sys

sys.path.insert(0, str(REPO / "tools" / "fan_in"))
import barrier

doc = load()
real_rel = "command-center/receipts/TST-0005.json"
live_sha = hashlib.sha256((REPO / real_rel).read_bytes()).hexdigest()
good = barrier.admit(REPO, [real_rel], f"phases complete. sha256: {live_sha}")
need(good["admitted"] is True and good["status"] == "ACCEPT"
     and good["digest_parsed"] is True, f"live artifact not admitted: {good['message']}")
fixture = (Path(__file__).resolve().parent / "fixtures" / "convincing-absent.digest.txt")
need(fixture.is_file(), "convincing-absent fixture missing")
digest_text = fixture.read_text(encoding="utf-8")
need(barrier.digest_well_formed(digest_text), "fixture digest not well-formed")
absent_rel = "command-center/receipts/TST-0005-ABSENT-ORACLE.json"
bad = barrier.admit(REPO, [absent_rel], digest_text)
need(bad["admitted"] is False and bad["status"] == "REJECT",
     "absent-artifact digest was admitted")
need(bad["digest_parsed"] is False, "digest was parsed despite absent artifact")
need(absent_rel in bad["message"], f"rejection does not name the absent path: {bad['message']}")
need(bad["reason_id"] == "absent-artifact", f"wrong reason_id: {bad['reason_id']}")
ok("both states: live ACCEPT, absent REJECT (digest never parsed, path named)")
