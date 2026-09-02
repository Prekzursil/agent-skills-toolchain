#!/usr/bin/env python3
"""Probe 1: speaker control + Opus-not-Sonnet aside must be found."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0038.json"


def main() -> int:
    gold = E.load_gold()
    rows, _meta = E.build_rows()
    sp = E.speaker_control(rows, gold)
    print(json.dumps({k: sp[k] for k in sp if k != "opus_quotes"}, sort_keys=True))
    if sp["opus_quotes"]:
        print("opus_quote=" + sp["opus_quotes"][0][:160])
    if not sp["pass"]:
        print("FAILED:BLD-0038-probe1 speaker control")
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0038-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0038-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:BLD-0038" not in text:
        print("FAILED:BLD-0038-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "BLD-0038":
        print("FAILED:BLD-0038-probe1 unit_id")
        return 1
    leaked = []
    blob = "\n".join(r.get("owner_quote") or "" for r in (doc.get("rows") or []))
    for item in gold["agent_must_not_attribute"]:
        if item["snippet"] in blob:
            leaked.append(item["id"])
    if leaked:
        print("FAILED:BLD-0038-probe1 receipt leaked agent text", leaked)
        return 1
    print("SUCCESS:BLD-0038-probe1 speaker-control opus-not-sonnet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
