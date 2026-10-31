#!/usr/bin/env python3
"""Probe 1: known-relevant retrieval, STALE classification, under-powered query."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / A.OUT_REL


def main() -> int:
    result = A.run_audit(REPO)
    if not result["all_pass"]:
        print("FAILED:BLD-0037-probe1 controls did not all PASS")
        for c in result["controls"]:
            print(f"  {c['id']} {c['result']}: {c['detail']}")
        return 1
    known = result["known_retrieved"]
    if not known:
        print("FAILED:BLD-0037-probe1 known-relevant note not retrieved")
        return 1
    if A.STALE_PIN in result["author_set"] and any(
        u["permalink"] == A.STALE_PIN for u in result["unconsulted"]
    ):
        print("FAILED:BLD-0037-probe1 stale note treated as current UNCONSULTED")
        return 1
    stale_rows = [
        f for f in result["findings"] if f["kind"] == "STALE" and f["permalink"] == A.STALE_PIN
    ]
    if not stale_rows:
        print("FAILED:BLD-0037-probe1 superseded note not classified STALE")
        return 1
    dummy = [
        r.permalink
        for r in result["records"]
        if r.permalink in A.KNOWN_RELEVANT and A.query_hits("zzzz-not-a-topic", r)
    ]
    if dummy:
        print(f"FAILED:BLD-0037-probe1 under-powered query still hit {dummy}")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0037-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0037" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0037-probe1 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0037-probe1 self-declared {doc.get('state')}")
        return 1
    art_known = next(
        (c for c in doc.get("controls") or [] if c.get("id") == "known-relevant-retrieved"),
        None,
    )
    if not art_known or art_known.get("result") != "PASS":
        print("FAILED:BLD-0037-probe1 artifact control known-relevant not PASS")
        return 1
    live_unconsulted = {u["permalink"] for u in result["unconsulted"]}
    art_unconsulted = {u["permalink"] for u in doc.get("unconsulted") or []}
    if live_unconsulted != art_unconsulted:
        print("FAILED:BLD-0037-probe1 artifact unconsulted set drifted from live audit")
        print(f"  live={sorted(live_unconsulted)}")
        print(f"  art={sorted(art_unconsulted)}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-recall-controls",
                "known_retrieved": known,
                "stale": A.STALE_PIN,
                "unconsulted": len(result["unconsulted"]),
                "underpowered_hits": dummy,
                "pass": True,
            }
        )
    )
    print(
        f"known={known} stale=STALE unconsulted={len(result['unconsulted'])} "
        "underpowered=0"
    )
    print("SUCCESS:BLD-0037-probe1 recall controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
