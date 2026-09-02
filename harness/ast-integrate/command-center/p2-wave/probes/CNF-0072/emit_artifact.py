#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0072-option-id-namespaces.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

OUT = E.REPO / E.OUTPUT_REL


def main() -> int:
    doc = E.audit(E.REPO)
    ok, why = E.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:CNF-0072-emit schema {why}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0072-emit state={doc.get('state')}")
        return 1
    if E.SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0072-emit sentinel absent")
        return 1
    if E.no_guess_violation(E.report_of(doc)["references"]):
        print("FAILED:CNF-0072-emit guessed rows")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {E.OUTPUT_REL} bytes={OUT.stat().st_size} state={doc['state']}")
    print("SUCCESS:CNF-0072-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
