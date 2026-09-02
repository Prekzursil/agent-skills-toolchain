#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0009-frame-completeness.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comparator as C  # noqa: E402

OUT = C.REPO / C.OUTPUT_REL


def main() -> int:
    doc = C.build_artifact()
    ok, why = C.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:CNF-0009-emit schema {why}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0009-emit state={doc.get('state')}")
        return 1
    blob = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True)
    if C.COMPLETION_SENTINEL not in blob:
        print("FAILED:CNF-0009-emit completion_sentinel absent")
        return 1
    plant = (C.domain_from_doc(doc).get("planted_id_control") or {})
    if not plant.get("nonzero_difference") or not plant.get("same_run_as_clean"):
        print("FAILED:CNF-0009-emit planted control did not fire in the same run")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {C.OUTPUT_REL} bytes={OUT.stat().st_size} state={doc['state']}")
    print("SUCCESS:CNF-0009-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
