#!/usr/bin/env python3
"""IMP-0453 probe 2: cleanup mutation turns preservation red; complete is not INCOMPLETE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_partial_preserve import run_mutation_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0453.json"
SENTINEL = "SENTINEL:IMP-0453:PARTIALS-PRESERVED"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_mutation_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:IMP-0453-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0453-probe2 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    if not result.get("pass") or not both.get("mutant_cleanup_turns_preservation_red"):
        print("FAILED:IMP-0453-probe2 cleanup mutation / complete control")
        return 1
    if not both.get("complete_not_incomplete"):
        print("FAILED:IMP-0453-probe2 complete artifact classified INCOMPLETE")
        return 1
    print(
        f"honest_green={both.get('honest_preserve_green')} "
        f"mutant_red={both.get('mutant_cleanup_turns_preservation_red')} "
        f"complete_cls={result.get('complete_control', {}).get('classification')}"
    )
    print("SUCCESS:IMP-0453-probe2 cleanup mutation turns red; complete is not INCOMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
