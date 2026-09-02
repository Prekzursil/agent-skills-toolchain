#!/usr/bin/env python3
"""Probe 2: detector control — delete one documented flag, the differ must name it.

Two mechanically independent surfaces:
  * toy fixture (owned parser + owned docs)
  * live seed.py inventory with `--overlay` stripped in memory (live file untouched)

The good state must stay silent. A differ that is empty in both states is dead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import parity as P  # noqa: E402

UNIT = "TST-0251"
ART = REPO / "command-center/receipts/TST-0251.json"
SENTINEL = "SUCCESS:TST-0251"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt-unparseable:{exc}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    det = doc.get("detector_control") or {}
    if det.get("fired_on_removed_flag") is not True:
        return "receipt-detector-did-not-fire"
    if det.get("silent_on_unmodified_docs") is not True:
        return "receipt-detector-not-silent-on-good"
    return None


def main() -> int:
    toy = P.detector_control_toy()
    live = P.detector_control_live(REPO)
    print(
        json.dumps(
            {
                "probe": "probe2-detector-control",
                "unit_id": UNIT,
                "toy": toy,
                "live": {
                    "target_cli": live["target_cli"],
                    "removed_flag": live["removed_flag"],
                    "live_empty": live["live_empty"],
                    "detector_named_removed_flag": live["detector_named_removed_flag"],
                    "mutant_parser_not_docs": live["mutant_parser_not_docs"],
                    "live_docs_untouched": live["live_docs_untouched"],
                },
            },
            sort_keys=True,
        )
    )
    if not toy["good_empty"]:
        return fail(f"toy-good-not-empty parser_not_docs={toy['good_parser_not_docs']} docs_not_parser={toy['good_docs_not_parser']}")
    if not toy["detector_named_removed_flag"]:
        return fail(f"toy-detector-silent mutant={toy['bad_parser_not_docs']}")
    if not live["live_empty"]:
        return fail("live-good-not-empty")
    if not live["detector_named_removed_flag"]:
        return fail(f"live-detector-silent mutant={live['mutant_parser_not_docs']}")
    if not live["live_docs_untouched"]:
        return fail("live-docs-mutated")
    if live["removed_flag"] not in live["mutant_parser_not_docs"]:
        return fail("removed-flag-not-in-parser_not_docs")
    err = check_receipt()
    if err:
        return fail(err)
    print("SUCCESS:TST-0251-probe2 detector named the removed flag; good state silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
