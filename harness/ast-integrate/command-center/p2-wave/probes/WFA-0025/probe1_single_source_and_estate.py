#!/usr/bin/env python3
"""Probe 1: SINGLE-SOURCE + settling experiment, and estate candidate links.

Re-scans the filesystem (not the catalog) and re-classifies the frozen corpus.
Both-states: dropping SINGLE-SOURCE settling, or dropping an implemented
protocol's candidate id, must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0025-sweep-academic-protocols.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0025-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "WFA-0025":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0025" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = C.build_classified(REPO)
    if not live["all_pass"]:
        return fail("live classification did not pass")

    art_rows = {r["protocol_id"]: r for r in (doc.get("protocols") or [])}
    live_rows = {r["protocol_id"]: r for r in live["protocols"]}
    if set(art_rows) != set(live_rows):
        return fail(
            f"protocol-id-set mismatch art={sorted(art_rows)} live={sorted(live_rows)}"
        )

    for pid, live_row in live_rows.items():
        art = art_rows[pid]
        if live_row["replication_class"] != art.get("replication_class"):
            return fail(f"{pid} replication_class mismatch")
        if live_row["replication_class"] in {"SINGLE-SOURCE", "UNQUANTIFIED"}:
            if not art.get("settling_experiment"):
                return fail(f"{pid} missing settling_experiment")
            if art.get("settling_experiment") != live_row.get("settling_experiment"):
                return fail(f"{pid} settling_experiment drift")
        if live_row["estate"]["status"] == "IMPLEMENTED":
            cand = (art.get("estate") or {}).get("implementing_candidate_id")
            if not cand:
                return fail(f"{pid} implemented but candidate id missing")
            if cand != live_row["estate"]["implementing_candidate_id"]:
                return fail(f"{pid} candidate id drift")

    for item in doc.get("implemented_on_estate") or []:
        if not item.get("implementing_candidate_id"):
            return fail(
                f"implemented_on_estate {item.get('protocol_id')} missing candidate"
            )

    controls = C.detector_controls(live)
    if not controls["mutant_drop_settling_fires"]:
        return fail("settling mutant silent")
    if not controls["mutant_drop_candidate_fires"]:
        return fail("candidate mutant silent")
    if not controls["good_state_silent"]:
        return fail("good state not silent")

    payload = {
        "probe": "probe1-single-source-and-estate",
        "unit_id": "WFA-0025",
        "pass": True,
        "protocol_count": len(live_rows),
        "single_source": [
            pid
            for pid, r in live_rows.items()
            if r["replication_class"] == "SINGLE-SOURCE"
        ],
        "implemented": [
            {
                "protocol_id": pid,
                "candidate_id": r["estate"]["implementing_candidate_id"],
            }
            for pid, r in live_rows.items()
            if r["estate"]["status"] == "IMPLEMENTED"
        ],
        "mutant_drop_settling_fires": True,
        "mutant_drop_candidate_fires": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"single_source={payload['single_source']} "
        f"implemented={payload['implemented']}"
    )
    print("SUCCESS:WFA-0025-probe1 single-source settling and estate candidate link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
