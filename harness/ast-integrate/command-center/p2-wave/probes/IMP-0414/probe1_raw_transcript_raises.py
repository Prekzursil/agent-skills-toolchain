#!/usr/bin/env python3
"""Named probe 1: passing a raw transcript must raise at the typed boundary.

Both-states in one process: the raw string is refused AND a typed handoff
built in the same run is accepted with goal re-anchored as section 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import handoff as H  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0414.json"
SENTINEL = "SENTINEL:IMP-0414:HANDOFF-TYPED-ONLY"
RAW = (
    "=== previous agent stdout ===\n"
    "Paste this blob as the next agent's prefix.\n"
    "untyped transcript body\n"
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0414-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact is not an object (raw prefix shape)")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != "IMP-0414":
        return fail(f"unit_id {doc.get('unit_id')}")

    raised_accept = False
    accept_trace = None
    try:
        H.accept_handoff(RAW)
    except H.HandoffBoundaryError as exc:
        raised_accept = True
        accept_trace = exc.trace
    if not raised_accept or not accept_trace or accept_trace.get("refused") is not True:
        return fail("raw transcript was not refused at accept_handoff")

    raised_prefix = False
    try:
        H.prefix_for_next_agent(RAW)
    except H.HandoffBoundaryError:
        raised_prefix = True
    if not raised_prefix:
        return fail("raw transcript became prefix_for_next_agent input")

    schema_errors = H.validate_document(RAW)
    if not schema_errors:
        return fail("schema accepted a raw string root")

    live = H.load_handoff(ART)
    prefix = H.prefix_for_next_agent(live)
    if not prefix or prefix[0].get("kind") != "goal" or prefix[0].get("ordinal") != 1:
        return fail("live artifact prefix is not goal-as-section-1")
    if any(isinstance(item, (str, bytes, bytearray)) for item in prefix):
        return fail("prefix contained a raw string member")

    art_trace = doc.get("rejected_raw_trace") or {}
    if art_trace.get("refused") is not True:
        return fail("artifact missing rejected_raw_trace")
    if art_trace.get("boundary") != "typed-handoff":
        return fail("rejected_raw_trace.boundary")

    payload = {
        "pass": True,
        "probe": "probe1-raw-transcript-raises",
        "unit_id": "IMP-0414",
        "raw_accept_raised": True,
        "raw_prefix_raised": True,
        "schema_rejects_string_root": True,
        "typed_accepted_same_run": True,
        "goal_section_1": True,
        "error_type": accept_trace.get("error_type"),
        "payload_type": accept_trace.get("payload_type"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "raw_raised=True prefix_raised=True schema_rejects_string=True "
        "typed_ok=True goal_section_1=True"
    )
    print("SUCCESS:IMP-0414-probe1 raw transcript raises at typed boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
