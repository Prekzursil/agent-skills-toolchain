#!/usr/bin/env python3
"""IMP-0183 probe 1: core+delta reproduces every source (n/n fingerprint equality)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "workflow_foundry" / "tests"))

from test_common_core import run_recompose_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0183.json"


def main() -> int:
    result = run_recompose_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0183-probe1 self-declared {st}")
            return 1
        if "SUCCESS:IMP-0183" not in text:
            print("FAILED:IMP-0183-probe1 sentinel-absent")
            return 1
    if not result.get("pass"):
        print("FAILED:IMP-0183-probe1 core+delta reproduction")
        return 1
    if int(result.get("matched") or 0) != int(result.get("n") or -1):
        print("FAILED:IMP-0183-probe1 matched != n")
        return 1
    print(
        f"matched={result['matched']}/{result['n']} "
        f"core_size={result['core_size']} spine={result['core_kinds']}"
    )
    print("SUCCESS:IMP-0183-probe1 core+delta reproduces every source exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
