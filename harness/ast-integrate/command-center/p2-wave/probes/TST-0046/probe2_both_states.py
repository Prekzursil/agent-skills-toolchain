#!/usr/bin/env python3
"""Probe 2: both-states control — suite fails always-accept and always-reject mutants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import both_states, rules_covered  # noqa: E402

ART = REPO / "command-center/receipts/TST-0046.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0046-probe2 {msg}")
    return 1


def main() -> int:
    control = both_states()
    covered = rules_covered()
    print(
        json.dumps(
            {
                "real_pass": control["real_pass"],
                "always_accept_pass": control["always_accept_pass"],
                "always_reject_pass": control["always_reject_pass"],
                "always_accept_failed": control["always_accept_failed"],
                "always_reject_failed": control["always_reject_failed"],
                "planted_rejected": control["planted_rejected"],
                "genuine_accepted": control["genuine_accepted"],
                "rules": covered,
                "pass": control["pass"],
            },
            sort_keys=True,
        )
    )
    if not control["pass"]:
        return fail("both-states control did not discriminate")
    if control["always_accept_failed"] < 1 or control["always_reject_failed"] < 1:
        return fail("mutants did not fail the suite")
    if len(covered) < 8:
        return fail(f"too few rules covered: {covered}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    recorded = doc.get("both_states") or {}
    if recorded.get("always_accept_pass") is not False:
        return fail("artifact did not record always-accept failure")
    if recorded.get("always_reject_pass") is not False:
        return fail("artifact did not record always-reject failure")
    print("SUCCESS:TST-0046-probe2 both-states mutants fail; live gate discriminates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
