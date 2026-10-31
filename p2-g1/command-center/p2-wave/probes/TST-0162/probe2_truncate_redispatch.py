#!/usr/bin/env python3
"""TST-0162 probe 2: truncate a claim; honest re-dispatch vs silent-skip mutant.

Independent signal (b) is a receipt-directory hash diff that does not
read the resume plan lists.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from claim_resume import run_mutation_truncate  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0162.json"
SENTINEL = "SUCCESS:TST-0162"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst-0162-p2-") as td:
        result = run_mutation_truncate(Path(td))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0162-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0162-probe2 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    honest = result.get("honest") or {}
    mutant = result.get("mutant_skip_corrupt") or {}
    if not result.get("pass"):
        print("FAILED:TST-0162-probe2 mutation truncate redispatch")
        return 1
    if not both.get("honest_truncate_redispatches"):
        print(
            "FAILED:TST-0162-probe2 honest planner did not redispatch truncated claim "
            f"{honest.get('plan_redispatch')}"
        )
        return 1
    if not both.get("mutant_silently_skips"):
        print(
            "FAILED:TST-0162-probe2 skip-corrupt mutant did not turn the control red "
            f"{mutant.get('plan_skip')}"
        )
        return 1
    signals = result.get("signals") or {}
    print(
        f"honest_redispatch={honest.get('plan_redispatch')} "
        f"mutant_skip={mutant.get('plan_skip')} "
        f"independent={(signals.get('b_independent_receipt_diff') or {}).get('honest')}"
    )
    print("SUCCESS:TST-0162-probe2 truncate redispatches; mutant silently skips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
