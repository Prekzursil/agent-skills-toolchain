#!/usr/bin/env python3
"""Emit ADV-0050 license-rider audit artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

OUT = A.REPO / A.OUTPUT_REL


def main() -> int:
    doc = A.build_document()
    ok, why = A.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:ADV-0050-emit schema {why}")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0050-emit state={doc.get('state')} sentinel={doc.get('sentinel')}")
        return 1
    text = json.dumps(doc, indent=1, ensure_ascii=True, sort_keys=True)
    if A.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0050-emit completion sentinel absent")
        return 1
    if not doc.get("one_verdict_per_target"):
        print("FAILED:ADV-0050-emit one_verdict_per_target false")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    size = OUT.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ADV-0050-emit {size}B below floor")
        return 1
    n_ok = sum(1 for t in doc["tests"] if t.get("result") == "PASS")
    print(
        f"wrote {A.OUTPUT_REL} bytes={size} state={doc['state']} "
        f"targets={len(doc['targets'])} tests_pass={n_ok}/{len(doc['tests'])}"
    )
    print("SUCCESS:ADV-0050-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
