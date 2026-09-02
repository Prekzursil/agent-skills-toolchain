#!/usr/bin/env python3
"""Probe 1: four catalog controls, including use-vs-mention."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0004-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0004" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    parsed = E.scan(include_live=False, method="parse")
    tests = E.evaluate_controls(parsed["control"])
    for t in tests:
        print(f"{t['id']} {t['result']} {t['detail']}")
        if t["result"] != "PASS":
            return fail(t["id"])

    receipt_tests = {t["id"]: t["result"] for t in doc.get("tests") or []}
    for t in tests:
        if receipt_tests.get(t["id"]) != "PASS":
            return fail(f"receipt test {t['id']} not PASS")

    mention = parsed["control"]["mention_ids"]
    docs = parsed["control"]["doc_ids"]
    if E.MENTION_PLANTED & docs:
        return fail("mention-only identifiers counted as live docs")
    if not E.MENTION_PLANTED <= mention:
        return fail("mention-only planted ids not suppressed")

    print(
        "SUCCESS:BLD-0004-probe1 use-vs-mention planted-undocumented "
        "documented-but-absent negative-paired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
