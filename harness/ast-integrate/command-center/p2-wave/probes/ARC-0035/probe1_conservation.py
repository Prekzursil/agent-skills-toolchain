#!/usr/bin/env python3
"""Probe 1: record-count conservation (Python json.loads per line).

input_events == output_records + classified_drops.
Disagreement with the artifact's recorded counts is FAIL, not a picked winner.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fold as F  # noqa: E402
import harvest as H  # noqa: E402

ART = REPO / "command-center/phase3/A5/MIGRATION.json"
SOURCE = HERE / "fixtures" / "source-events.jsonl"
LEDGER = HERE / "fixtures" / "ledger.jsonl"
DROPS = HERE / "fixtures" / "drops.jsonl"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0035-probe1 migration artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0035" not in text:
        print("FAILED:ARC-0035-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0035-probe1 self-declared {doc.get('state')}")
        return 1
    if not SOURCE.is_file():
        info = H.harvest(SOURCE)
        print(f"harvested present={info['present_on_worktree']} lines={info['line_count']}")
    rel = SOURCE.relative_to(REPO).as_posix()
    result = F.fold_file(SOURCE, LEDGER, DROPS, rel)
    if not result.get("ok"):
        print("FAILED:ARC-0035-probe1 fold refused", result.get("reason"))
        return 1
    if not result.get("conservation_holds"):
        print(
            "FAILED:ARC-0035-probe1 conservation "
            f"{result['input_events']} != {result['output_records']}+{result['classified_drops']}"
        )
        return 1
    if result["classified_drops"] < 1:
        print("FAILED:ARC-0035-probe1 no classified drops; conservation would be tautological")
        return 1
    if result["output_records"] < 5:
        print(f"FAILED:ARC-0035-probe1 too few folded records {result['output_records']}")
        return 1
    recorded = (doc.get("tests") or {}).get("record_count_conservation") or {}
    live = (
        result["input_events"],
        result["output_records"],
        result["classified_drops"],
    )
    art_counts = (
        recorded.get("input_events"),
        recorded.get("output_records"),
        recorded.get("classified_drops"),
    )
    if live != art_counts:
        print("FAILED:ARC-0035-probe1 artifact counts disagree with live fold")
        print(f" live={live} artifact={art_counts}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-conservation-json-loads",
                "input_events": result["input_events"],
                "output_records": result["output_records"],
                "classified_drops": result["classified_drops"],
                "conservation_holds": True,
                "signal": "python-json.loads-per-line",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0035-probe1 record-count conservation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
