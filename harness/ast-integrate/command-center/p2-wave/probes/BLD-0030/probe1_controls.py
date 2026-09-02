#!/usr/bin/env python3
"""Probe 1: catalog controls for BLD-0030 (inline / buried-short / no-tags)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

UNIT = "BLD-0030"


def main() -> int:
    ctrls = A.run_catalog_controls()
    required = {"C1-INLINE", "C2-BURIED-SHORT", "C3-NO-TAGS"}
    failed = [c for c in ctrls if c["id"] in required and not c["pass"]]
    extra_failed = [c for c in ctrls if c["id"] not in required and not c["pass"]]
    print(json.dumps({"unit_id": UNIT, "controls": ctrls}, indent=2))
    if failed:
        print(
            "FAILED:"
            + UNIT
            + "-probe1 catalog controls "
            + ",".join(c["id"] for c in failed)
        )
        return 1
    if extra_failed:
        print(
            "FAILED:"
            + UNIT
            + "-probe1 extra controls "
            + ",".join(c["id"] for c in extra_failed)
        )
        return 1
    inline = next(c for c in ctrls if c["id"] == "C1-INLINE")
    none = next(c for c in ctrls if c["id"] == "C3-NO-TAGS")
    if inline.get("document_class") == none.get("got"):
        print("FAILED:" + UNIT + "-probe1 NO-TAGS collapsed into ALL-INLINE")
        return 1
    print(
        "inline="
        + str(inline["got"])
        + " buried="
        + str(next(c for c in ctrls if c["id"] == "C2-BURIED-SHORT")["got"])
        + " no_tags="
        + str(none["got"])
        + " mention="
        + str(next(c for c in ctrls if c["id"] == "C4-MENTION")["got"])
    )
    print("SUCCESS:" + UNIT + "-probe1 catalog controls inline/buried/no-tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
