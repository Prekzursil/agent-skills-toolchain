#!/usr/bin/env python3
"""Named probe 1: re-fetch planted citations and locate quoted spans (independent of emit)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0062-citation-liveness.json"


def main() -> int:
    srv = E.start_fixture_server()
    try:
        rows = [E.audit_one(r, srv) for r in E.planted_inventory(srv.base)]
    finally:
        srv.close()

    live_ok = E.by_id(rows, "CITE-LIVE-OK")
    absent = E.by_id(rows, "CITE-200-ABSENT")
    contradict = E.by_id(rows, "CITE-CONTRADICT")
    untrusted = E.by_id(rows, "CITE-UNTRUSTED")
    dead = E.by_id(rows, "CITE-DEAD-LIVE")
    control = E.by_id(rows, "CONTROL-WRONG-QUOTE")

    if live_ok["http_status"] != 200 or not live_ok["quote_verbatim"]:
        print("FAILED:CNF-0062-probe1 live-ok", json.dumps(live_ok)[:600])
        return 1
    if live_ok["context_supports_claim"] is False:
        print("FAILED:CNF-0062-probe1 live-ok context wrongly contradicted")
        return 1
    if not (
        absent["http_status"] == 200
        and not absent["quote_present"]
        and absent["verdict"] == "FAILED"
        and absent["classification"] == "quote-not-found"
    ):
        print("FAILED:CNF-0062-probe1 200-absent", json.dumps(absent)[:600])
        return 1
    if contradict["classification"] != "context-contradicts-claim":
        print("FAILED:CNF-0062-probe1 contradict", json.dumps(contradict)[:600])
        return 1
    if not untrusted["quote_verbatim"] or untrusted["fetched_body_executed"]:
        print("FAILED:CNF-0062-probe1 untrusted", json.dumps(untrusted)[:600])
        return 1
    if dead["url_reachable"] or not dead["quote_present"] or not dead["archival"]["used"]:
        print("FAILED:CNF-0062-probe1 archival", json.dumps(dead)[:600])
        return 1
    if control["quote_present"] or control["verdict"] != "CONTROL-ABSENT":
        print("FAILED:CNF-0062-probe1 wrong-quote not absent", json.dumps(control)[:600])
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0062-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0062" or doc.get("state") in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0062-probe1 artifact state", doc.get("state"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0062 emitted only when" not in blob:
        print("FAILED:CNF-0062-probe1 sentinel absent")
        return 1
    det = SC.detector_of(doc)
    wrong_absent = bool(
        doc.get("wrong_quote_reported_absent")
        or SC.report_of(doc).get("wrong_quote_reported_absent")
        or det.get("wrong_quote_reported_absent")
        or (doc.get("extensions") or {}).get("wrong_quote_reported_absent")
    )
    if not wrong_absent:
        print("FAILED:CNF-0062-probe1 artifact did not record wrong-quote-absent")
        return 1

    errs = SC.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0062-probe1 schema", errs[0])
        return 1

    summary = {
        "probe": "probe1-liveness",
        "unit_id": "CNF-0062",
        "pass": True,
        "live_ok_verbatim": live_ok["quote_verbatim"],
        "absent_200_failed": absent["verdict"] == "FAILED",
        "wrong_quote_absent": not control["quote_present"],
        "archival_used": dead["archival"]["used"],
        "http_status": {r["id"]: r["http_status"] for r in rows},
        "verdicts": {r["id"]: r["verdict"] for r in rows},
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "live_ok_verbatim=True 200_absent_failed=True wrong_quote_absent=True "
        f"archival_used={dead['archival']['used']}"
    )
    print("SUCCESS:CNF-0062-probe1 citation liveness re-fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
