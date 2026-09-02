#!/usr/bin/env python3
"""Probe 1: every candidate records daemon liability and death behaviour."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
from rails import capture_map, live_sha  # noqa: E402

OUT = REPO / "command-center/research/RES-0046.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0046-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    table = doc.get("candidate_table") or []
    if len(table) < 4:
        return fail(f"candidate_table too small n={len(table)}")
    if C.DAEMON_COL not in (doc.get("daemon_liability_column") or ""):
        return fail("daemon_liability_column not declared")
    missing_col = [r.get("id") for r in table if C.DAEMON_COL not in r]
    if missing_col:
        return fail(f"daemon_liability column absent on {missing_col}")
    death = [
        r.get("id")
        for r in table
        if not str(r.get("when_daemon_dies") or "").strip()
        or len(str(r.get("when_daemon_dies"))) < 24
    ]
    if death:
        return fail(f"when_daemon_dies missing/short on {death}")
    daemons = [r for r in table if r.get("requires_persistent_daemon") is True]
    if len(daemons) < 3:
        return fail("expected at least three daemon-backed candidates")
    baseline = [r for r in table if r.get("id") == C.BASELINE_ID]
    if len(baseline) != 1:
        return fail("baseline row missing")
    if baseline[0].get("requires_persistent_daemon") is not False:
        return fail("baseline must not require a persistent daemon")
    caps = capture_map()
    missing = C.verify_needles(caps)
    if missing:
        return fail(f"needles {missing[:6]}")
    for claim in doc.get("claims") or []:
        rails = claim.get("rails") or []
        if not C.two_rail_ok(claim):
            return fail(f"claim {claim.get('id')} not two-rail")
        for rail in rails:
            digest, _, _ = live_sha(rail["path"])
            if digest != rail.get("sha256"):
                return fail(f"sha mismatch {rail.get('id')}")
            if int(rail.get("http_status") or 0) != 200:
                return fail(f"http {rail.get('id')}")
            if not rail.get("permalink") or not rail.get("fetch_timestamp"):
                return fail(f"incomplete rail {rail.get('id')}")
    report = {
        "pass": True,
        "probe": "probe1-daemon-liability",
        "unit_id": "RES-0046",
        "n_candidates": len(table),
        "daemon_backed": [r["id"] for r in daemons],
        "baseline": C.BASELINE_ID,
        "column": C.DAEMON_COL,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"n_candidates={len(table)} daemon_backed={len(daemons)} "
        f"column={C.DAEMON_COL}"
    )
    print("SUCCESS:RES-0046-probe1 daemon-liability column and death behaviour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
