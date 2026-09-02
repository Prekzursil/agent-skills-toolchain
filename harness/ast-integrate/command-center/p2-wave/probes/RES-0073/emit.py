#!/usr/bin/env python3
"""Emit command-center/research/RES-0073.json from the frozen captures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

REPO = C.REPO
OUT = REPO / C.OUT_REL


def main() -> int:
    doc = C.build_document()
    bad = C.surviving_need_two_kinds(doc["claims"])
    if bad:
        print(f"FAILED:RES-0073 emit two-rail kinds missing {bad}")
        return 1
    avr = doc["authoring_versus_reviewing"]
    if not avr.get("answer_differs"):
        print("FAILED:RES-0073 emit answer_differs is not true")
        return 1
    if avr["authoring"]["n_claims"] < 1 or avr["reviewing"]["n_claims"] < 1:
        print("FAILED:RES-0073 emit empty authoring/reviewing split")
        return 1
    sample = doc["sample"]
    if int(sample["n_tools"]) != 5:
        print(f"FAILED:RES-0073 emit n_tools={sample['n_tools']}")
        return 1
    if not str(sample.get("selection_bias") or "").strip():
        print("FAILED:RES-0073 emit selection_bias empty")
        return 1
    if C.SENTINEL not in json.dumps(doc):
        print("FAILED:RES-0073 emit sentinel absent")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"WROTE {C.OUT_REL} bytes={len(text.encode('utf-8'))}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
