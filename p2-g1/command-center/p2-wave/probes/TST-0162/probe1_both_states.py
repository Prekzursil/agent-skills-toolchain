#!/usr/bin/env python3
"""TST-0162 probe 1: intact claims skip; corrupted claims re-dispatch."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from claim_resume import run_both_states  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0162.json"
SENTINEL = "SUCCESS:TST-0162"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst-0162-p1-") as td:
        result = run_both_states(Path(td))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0162-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0162-probe1 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    if not result.get("pass"):
        print("FAILED:TST-0162-probe1 both-states skip/redispatch")
        return 1
    if not both.get("intact_claims_skip"):
        print("FAILED:TST-0162-probe1 intact terminals were not skipped")
        return 1
    if not both.get("corrupted_claims_redispatch"):
        print("FAILED:TST-0162-probe1 truncated claim was not redispatched")
        return 1
    intact = result.get("intact") or {}
    corrupt = result.get("corrupt") or {}
    print(
        "intact_skip="
        f"{(intact.get('plan') or {}).get('skip')} "
        "corrupt_redispatch="
        f"{(corrupt.get('plan') or {}).get('redispatch')} "
        f"independent_changed={corrupt.get('independent_receipt_changed')}"
    )
    print("SUCCESS:TST-0162-probe1 intact skip and corrupt redispatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
