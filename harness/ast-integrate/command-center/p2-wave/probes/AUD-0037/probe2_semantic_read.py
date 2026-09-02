#!/usr/bin/env python3
"""Probe 2: semantic SUPPORTS / MENTIONS-ONLY / CONTRADICTS of cited spans.

Independent of probe 1. Re-reads span bytes; does not treat mechanical
resolution as support. The catalog control is a line that contains only the
subject word and must be MENTIONS-ONLY.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.artifact_path()
SENTINEL = E.catalog_sentinel()
RAW = HERE / "probe2-semantic-read.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0037-probe2 {msg}")
    return 1


def main() -> int:
    live = E.probe2_payload()
    RAW.write_text(json.dumps(live, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(live, sort_keys=True))
    if not live.get("pass"):
        return fail("semantic controls did not pass")
    if not live.get("mentions_only_not_treated_as_resolved_support"):
        return fail("subject-only line was classified as support, not MENTIONS-ONLY")
    ctrl = {c["control"]: c for c in live.get("controls") or []}
    if ctrl.get("mentions-only", {}).get("got_semantic") != "MENTIONS-ONLY":
        return fail(
            f"mentions-only control got {ctrl.get('mentions-only', {}).get('got_semantic')}"
        )
    if ctrl.get("mentions-only", {}).get("got_mechanical") is not True:
        return fail("mentions-only control must still be mechanically resolved")
    if ctrl.get("supports", {}).get("got_semantic") != "SUPPORTS":
        return fail(f"supports control got {ctrl.get('supports', {}).get('got_semantic')}")
    if ctrl.get("contradicts", {}).get("got_semantic") != "CONTRADICTS":
        return fail(
            f"contradicts control got {ctrl.get('contradicts', {}).get('got_semantic')}"
        )
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "AUD-0037":
        return fail(f"unit_id {doc.get('unit_id')}")
    recorded = ((doc.get("report") or {}).get("live_tally") or {})
    live_t = live["live_tally"]
    if recorded.get("semantic_counts") != live_t.get("semantic_counts"):
        return fail(
            f"artifact semantic_counts {recorded.get('semantic_counts')} "
            f"!= live {live_t.get('semantic_counts')}"
        )
    rec_hv = recorded.get("n_high_value_mentions_only")
    if rec_hv is None or int(rec_hv) != int(live_t["n_high_value_mentions_only"]):
        return fail("artifact high-value count mismatch")
    print(
        "SUCCESS:AUD-0037-probe2 semantic read; "
        f"counts={live_t['semantic_counts']} "
        f"high_value={live_t['n_high_value_mentions_only']} "
        "mentions-only-control=MENTIONS-ONLY"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
