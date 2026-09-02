#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0131-cross-artifact-contradictions.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = D.REPO / D.OUTPUT_REL


def main() -> int:
    doc = D.build_report(D.REPO)
    ok, why = D.validate_against_schema(doc)
    if not ok:
        print(f"FAILED:ADV-0131-emit schema {why}")
        return 1
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True)
    if D.SENTINEL not in text:
        print("FAILED:ADV-0131-emit sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0131-emit state={doc.get('state')} class={doc.get('classification')}")
        return 1
    if not doc.get("known_live_instance", {}).get("found"):
        print("FAILED:ADV-0131-emit known-live-absent")
        return 1
    if doc.get("false_positive_control", {}).get("reported"):
        print("FAILED:ADV-0131-emit false-positive-reported")
        return 1
    if "17-DECISION-LOG.md:175" not in text:
        print("FAILED:ADV-0131-emit canonical-anchor-absent")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {D.OUTPUT_REL} bytes={OUT.stat().st_size} state={doc['state']} pairs={doc['pair_count']}")
    print("SUCCESS:ADV-0131-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
