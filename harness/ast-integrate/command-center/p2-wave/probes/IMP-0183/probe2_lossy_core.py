#!/usr/bin/env python3
"""IMP-0183 probe 2: planted lossy core fails fingerprint equality (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "workflow_foundry" / "tests"))

from test_common_core import run_lossy_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0183.json"


def main() -> int:
    result = run_lossy_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0183-probe2 self-declared {st}")
            return 1
        if "SUCCESS:IMP-0183" not in text:
            print("FAILED:IMP-0183-probe2 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    if not result.get("pass") or not both.get("good_silent") or not both.get("bad_fires"):
        print("FAILED:IMP-0183-probe2 planted-lossy-core detector")
        return 1
    print(
        f"honest_silent={both['good_silent']} planted_fires={both['bad_fires']} "
        f"lost={result.get('lost_core_kinds')} "
        f"planted_matched={both.get('planted_matched')}/{both.get('planted_n')}"
    )
    print("SUCCESS:IMP-0183-probe2 planted lossy core fails reproduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
