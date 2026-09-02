#!/usr/bin/env python3
"""Probe 1: per merge_unit round trip; print set difference on every failure.

Two signals: blob-parse source ids vs fingerprint-walk source ids. Disagreement
is FAIL, not a picked winner. Pass rate is not a substitute for per-unit diffs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import lineage as L  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0138-fusion-lineage-record-and-the-decomposition-round-tr.json"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0138-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0138-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0138" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0138-probe1 sentinel absent")
        return 1
    if doc.get("kind") != "lineage-record" or doc.get("unit_id") != "WFA-0138":
        print("FAILED:WFA-0138-probe1 kind/unit_id")
        return 1

    loaded = C.load_corpus(REPO)
    units = loaded["merge_units"]
    if len(units) != 30:
        print(f"FAILED:WFA-0138-probe1 count={len(units)} want=30")
        return 1

    recorded = {r["merge_unit_id"]: r for r in (doc.get("records") or [])}
    live_ok = 0
    live_unresolved_fail = 0
    for unit in units:
        trip = L.round_trip(unit)
        uid = trip["merge_unit_id"]
        print(
            f"unit={uid} ok={trip['round_trip_ok']} "
            f"missing={trip['missing']} extra={trip['extra']} "
            f"unresolved={trip['unresolved_recorded']} "
            f"fail_because_unresolved={trip['fail_because_unresolved']} "
            f"signals={trip['signals']}"
        )
        if trip.get("signal_disagreement"):
            print(f"FAILED:WFA-0138-probe1 signal-disagreement {uid}")
            print(json.dumps(trip["signal_disagreement"], indent=2)[:2000])
            return 1
        rec = recorded.get(uid)
        if not rec:
            print(f"FAILED:WFA-0138-probe1 artifact missing record {uid}")
            return 1
        if rec.get("recovered_sources") != trip["recovered"]:
            print(f"FAILED:WFA-0138-probe1 recovered drift {uid}")
            return 1
        if rec.get("missing") != trip["missing"] or rec.get("extra") != trip["extra"]:
            print(f"FAILED:WFA-0138-probe1 set-diff drift {uid}")
            return 1
        if bool(rec.get("round_trip_ok")) != trip["round_trip_ok"]:
            print(f"FAILED:WFA-0138-probe1 ok drift {uid}")
            return 1
        if trip["round_trip_ok"]:
            if trip["unresolved_recorded"]:
                print(f"FAILED:WFA-0138-probe1 unresolved unit passed {uid}")
                return 1
            live_ok += 1
            continue
        print(f"SET-DIFF {uid} declared-recovered missing={trip['missing']} extra={trip['extra']}")
        if not trip["fail_because_unresolved"]:
            print(f"FAILED:WFA-0138-probe1 fail not explained by unresolved {uid}")
            return 1
        live_unresolved_fail += 1

    if live_ok + live_unresolved_fail != 30:
        print("FAILED:WFA-0138-probe1 classification incomplete")
        return 1
    if int((doc.get("counts") or {}).get("round_trip_ok") or -1) != live_ok:
        print("FAILED:WFA-0138-probe1 counts.round_trip_ok drift")
        return 1
    if int((doc.get("counts") or {}).get("fail_because_unresolved") or -1) != live_unresolved_fail:
        print("FAILED:WFA-0138-probe1 counts.fail_because_unresolved drift")
        return 1
    if bool(doc.get("maps", {}).get("present")) != bool(loaded["maps_present"]):
        print("FAILED:WFA-0138-probe1 maps.present drift")
        return 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "WFA-0138",
        "merge_units": 30,
        "round_trip_ok": live_ok,
        "fail_because_unresolved": live_unresolved_fail,
        "maps_present": loaded["maps_present"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:WFA-0138-probe1 per-unit round-trip "
        f"ok={live_ok} fail_unresolved={live_unresolved_fail}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
