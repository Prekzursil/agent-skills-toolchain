#!/usr/bin/env python3
"""IMP-0362 probe2: assertion is not fetch (independent reviewer).

Runs the receipt's three named negative controls and the good-state twin:
  - assert-prepared-without-tool-calls  (carol: prepared=true, empty log)
  - asserted-read-status-is-not-a-fetch (status=asserted does not corroborate)
  - url-without-webfetch                (URL anchor, no WebFetch -> FIRE)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.prep import (  # noqa: E402
    FIRED_ASSERTED_STATUS,
    FIRED_ASSERT_WITHOUT_TOOL_CALLS,
    FIRED_URL_WITHOUT_WEBFETCH,
    PrepGate,
    UnpreparedError,
)

RECEIPT = REPO / "command-center/receipts/IMP-0362.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0362-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    declared = {n.get("id") for n in doc.get("negative_controls") or []}
    for want in ("assert-prepared-without-tool-calls",
                 "asserted-read-status-is-not-a-fetch",
                 "url-without-webfetch"):
        if want not in declared:
            return fail(f"receipt-negctl-missing:{want}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # Control 1: carol asserts prepared, empty tool-call log -> MUST FIRE.
        seat = root / "carol"
        seat.mkdir()
        (seat / "brief.md").write_text("quorum floor five seats.\n", encoding="utf-8")
        (seat / "notes.md").write_text("notes on the quorum floor\n", encoding="utf-8")
        (seat / "prep.json").write_text(json.dumps({
            "seat": "carol", "notes": "notes.md", "sources": ["brief.md"],
            "asserted_prepared": True,
        }), encoding="utf-8")
        (seat / "tool_log.json").write_text(json.dumps({"tool_calls": []}),
                                            encoding="utf-8")
        try:
            PrepGate(root).require_prepared("carol")
            return fail("carol-asserted-allowed")
        except UnpreparedError as exc:
            if FIRED_ASSERT_WITHOUT_TOOL_CALLS not in exc.reasons:
                return fail(f"carol-wrong-fire:{exc.reasons}")

        # Control 2: status=asserted Read does not corroborate.
        seat = root / "dan"
        seat.mkdir()
        (seat / "brief.md").write_text("reviewer count is two.\n", encoding="utf-8")
        (seat / "notes.md").write_text("notes on reviewer count\n", encoding="utf-8")
        (seat / "prep.json").write_text(json.dumps({
            "seat": "dan", "notes": "notes.md", "sources": ["brief.md"],
        }), encoding="utf-8")
        (seat / "tool_log.json").write_text(json.dumps({"tool_calls": [
            {"tool": "Read", "target": "brief.md", "status": "asserted"},
        ]}), encoding="utf-8")
        try:
            PrepGate(root).require_prepared("dan")
            return fail("dan-asserted-read-allowed")
        except UnpreparedError as exc:
            if FIRED_ASSERTED_STATUS not in exc.reasons:
                return fail(f"dan-wrong-fire:{exc.reasons}")

        # Control 3: URL anchor with no WebFetch -> FIRE.
        seat = root / "erin"
        seat.mkdir()
        (seat / "notes.md").write_text("notes about the spec\n", encoding="utf-8")
        (seat / "prep.json").write_text(json.dumps({
            "seat": "erin", "notes": "notes.md",
            "sources": ["https://example.org/spec.md"],
        }), encoding="utf-8")
        (seat / "tool_log.json").write_text(json.dumps({"tool_calls": []}),
                                            encoding="utf-8")
        try:
            PrepGate(root).require_prepared("erin")
            return fail("erin-url-no-fetch-allowed")
        except UnpreparedError as exc:
            if FIRED_URL_WITHOUT_WEBFETCH not in exc.reasons:
                return fail(f"erin-wrong-fire:{exc.reasons}")

        # Good-state twin of control 3: WITH WebFetch the seat speaks.
        seat = root / "frank"
        seat.mkdir()
        (seat / "notes.md").write_text("notes about the spec\n", encoding="utf-8")
        (seat / "prep.json").write_text(json.dumps({
            "seat": "frank", "notes": "notes.md",
            "sources": ["https://example.org/spec.md"],
        }), encoding="utf-8")
        (seat / "tool_log.json").write_text(json.dumps({"tool_calls": [
            {"tool": "WebFetch", "target": "https://example.org/spec.md",
             "status": "ok"},
        ]}), encoding="utf-8")
        verdict = PrepGate(root).require_prepared("frank")
        if verdict.get("allowed_to_speak") is not True:
            return fail("frank-webfetch-seat-refused")

    print(json.dumps({
        "probe": "probe2-assert-without-fetch", "unit_id": "IMP-0362",
        "pass": True,
        "controls_fired": ["assert-prepared-without-tool-calls",
                           "asserted-read-status-is-not-a-fetch",
                           "url-without-webfetch"],
        "good_state": "frank speaks with WebFetch",
    }, sort_keys=True))
    print("SUCCESS:IMP-0362-probe2 assertion detectors fire; WebFetch twin speaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
