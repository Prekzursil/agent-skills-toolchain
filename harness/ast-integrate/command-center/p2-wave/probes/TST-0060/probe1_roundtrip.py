#!/usr/bin/env python3
"""Probe 1: each named transport is exercised against the adversarial payload.

Write tool, quoted heredoc, and quoted -c inline must byte-match. here-string
must run (bash here-strings append a newline; that mismatch is recorded, not
hidden). Receipt must already exist with SUCCESS:TST-0060.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import NAMED_TRANSPORTS, named_roundtrip  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0060.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0060-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if doc.get("unit_id") != "TST-0060":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:TST-0060" not in text:
        return fail("sentinel absent")

    live = named_roundtrip()
    print(json.dumps({k: v for k, v in live.items() if k != "cells"}, sort_keys=True))
    for cell in live["cells"]:
        print(
            f"transport={cell['transport']} equal={cell['equal']} "
            f"kind={cell['mismatch_kind']} intend={cell['intended_bytes']} "
            f"landed={cell['landed_bytes']}"
        )

    if not live["transports_present"]:
        return fail(f"missing transports {live['missing']}")
    if not live["write_tool_equal"]:
        return fail("write_tool did not round-trip the adversarial payload")
    if not live["heredoc_equal"]:
        return fail("quoted heredoc did not round-trip the adversarial payload")
    if not live["c_inline_equal"]:
        return fail("quoted -c inline did not round-trip the adversarial payload")
    if live.get("here_string_kind") is None:
        return fail("here_string was not measured")

    recorded = {
        c.get("transport"): c
        for c in ((doc.get("matrix") or {}).get("adversarial_cells") or [])
        if isinstance(c, dict)
    }
    for tr in NAMED_TRANSPORTS:
        if tr not in recorded:
            return fail(f"receipt missing adversarial cell for {tr}")
        live_cell = next(c for c in live["cells"] if c["transport"] == tr)
        if bool(recorded[tr].get("equal")) != bool(live_cell["equal"]):
            return fail(
                f"receipt/live equality drift on {tr}: "
                f"receipt={recorded[tr].get('equal')} live={live_cell['equal']}"
            )

    tests = doc.get("tests") or []
    t1 = next((t for t in tests if t.get("id") == "test_each_transport_round_trips_the_adversarial_payload"), None)
    if not t1 or t1.get("verdict") != "PASS":
        return fail("receipt did not record the round-trip test as PASS")

    print(
        "write_ok=True heredoc_ok=True c_inline_ok=True "
        f"here_string_equal={live['here_string_equal']} "
        f"here_string_kind={live['here_string_kind']}"
    )
    print("SUCCESS:TST-0060-probe1 each named transport round-tripped or was measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
