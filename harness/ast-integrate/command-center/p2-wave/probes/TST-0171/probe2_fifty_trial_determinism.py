#!/usr/bin/env python3
"""TST-0171 probe 2: 50 SIGKILL trials share one outcome; independent reader agrees.

A planted coin-flip (alternate register/discard) must turn the determinism
assertion red.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_orphan_resume import run_determinism_suite  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0171.json"
SENTINEL = "SUCCESS:TST-0171"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_determinism_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0171-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0171-probe2 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    honest = result.get("honest") or {}
    if not result.get("pass"):
        print("FAILED:TST-0171-probe2 fifty-trial determinism")
        return 1
    if not both.get("honest_50_share_one"):
        print(f"FAILED:TST-0171-probe2 mixed honest outcomes {honest.get('outcomes')}")
        return 1
    if not both.get("coinflip_mutant_mixed"):
        print("FAILED:TST-0171-probe2 coin-flip mutant did not turn red")
        return 1
    if not both.get("independent_reader_agrees"):
        print("FAILED:TST-0171-probe2 independent reader disagrees with resume()")
        return 1
    print(
        f"trials={result.get('trials')} outcomes={honest.get('outcomes')} "
        f"mutant={result.get('mutant_alternate', {}).get('outcomes')}"
    )
    print("SUCCESS:TST-0171-probe2 50/50 trials share REGISTERED; mutant mixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
