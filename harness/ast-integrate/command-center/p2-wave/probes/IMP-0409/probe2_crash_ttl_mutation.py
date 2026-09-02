#!/usr/bin/env python3
"""Probe 2: crash+TTL steal, and mutation that drops exclusive rename."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import work_claim as wc  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0409-p2-") as td:
        root = Path(td)
        crash = wc.run_crash_ttl(root / "crash", ttl_seconds=0.6)
        mutation = wc.run_mutation_control(root / "mut", n=50)
    passed = bool(crash.get("pass")) and bool(mutation.get("pass"))
    payload = {
        "probe": "probe2-crash-ttl-and-rename-mutation",
        "unit_id": "IMP-0409",
        "crash_ttl_pass": crash.get("pass"),
        "crash_ttl": {
            "claim_present_after_kill": crash.get("claim_present_after_kill"),
            "challenger_before_ttl_status": (crash.get("challenger_before_ttl") or {}).get(
                "status"
            ),
            "challenger_before_ttl_reason": (crash.get("challenger_before_ttl") or {}).get(
                "reason_code"
            ),
            "challenger_after_ttl_status": (crash.get("challenger_after_ttl") or {}).get(
                "status"
            ),
            "challenger_after_ttl_session": (
                (crash.get("challenger_after_ttl") or {}).get("claim") or {}
            ).get("session_id"),
        },
        "mutation_honest_granted": (mutation.get("honest") or {}).get("granted"),
        "mutation_honest_denied": (mutation.get("honest") or {}).get("denied"),
        "mutation_mutant_granted": (mutation.get("mutant_atomic_rename_removed") or {}).get(
            "granted"
        ),
        "mutation_mutant_denied": (mutation.get("mutant_atomic_rename_removed") or {}).get(
            "denied"
        ),
        "mutation_turns_red": mutation.get("mutant_turns_concurrency_red"),
        "pass": passed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not crash.get("pass"):
        print("FAILED:IMP-0409-probe2 crash/TTL did not release the unit")
        print(json.dumps({k: crash.get(k) for k in crash if k != "holder_grant"}, default=str)[:2000])
        return 1
    if not mutation.get("honest_ok"):
        print("FAILED:IMP-0409-probe2 honest atomic path was not granted=1")
        return 1
    if not mutation.get("mutant_turns_concurrency_red"):
        print(
            "FAILED:IMP-0409-probe2 removing atomic rename did not turn concurrency red "
            f"(mutant granted={payload['mutation_mutant_granted']})"
        )
        return 1
    print(
        "SUCCESS:IMP-0409-probe2 crash_ttl=PASS "
        f"mutant_granted={payload['mutation_mutant_granted']} (red vs honest 1)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
