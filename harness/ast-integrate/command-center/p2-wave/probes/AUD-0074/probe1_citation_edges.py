#!/usr/bin/env python3
"""Probe 1: citation-derived edges between artifacts.

Recomputes edges from corpus file bodies. Does not read the correction
register and does not apply timestamps as a staleness verdict — that is
probe 2. Disagreement with the artifact's recorded cite-edge set is a failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import engine as E  # noqa: E402

ART = REPO / "command-center/audit/AUD-0074-source-lineage-graph.json"
SENTINEL = "SUCCESS:AUD-0074"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0074-probe1 {msg}")
    return 1


def edge_key(e: dict) -> tuple[str, str, str]:
    return (str(e.get("from")), str(e.get("to")), str(e.get("cited_version") or ""))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")
    if doc.get("unit_id") != "AUD-0074":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    pack = C.load()
    live = E.extract_citation_edges(pack["records"])
    recorded = [
        e
        for e in (doc.get("edges") or [])
        if isinstance(e, dict) and e.get("kind") == "cites"
    ]
    live_keys = {edge_key(e) for e in live}
    rec_keys = {edge_key(e) for e in recorded}
    print(
        json.dumps(
            {
                "probe": "probe1-citation-edges",
                "unit_id": "AUD-0074",
                "live_edges": len(live),
                "recorded_edges": len(recorded),
                "origin": pack["origin"],
                "equal": live_keys == rec_keys,
            },
            sort_keys=True,
        )
    )
    if len(live) < 8:
        return fail(f"too few citation edges live={len(live)}")
    if live_keys != rec_keys:
        missing = sorted(live_keys - rec_keys)[:8]
        extra = sorted(rec_keys - live_keys)[:8]
        return fail(f"edge set mismatch missing={missing} extra={extra}")
    # Probe 1 must not be a disguised timestamp check: it does not load corrections.
    print("probe1_did_not_consult_corrections=True")
    print("SUCCESS:AUD-0074-probe1 citation-derived edges match live extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
