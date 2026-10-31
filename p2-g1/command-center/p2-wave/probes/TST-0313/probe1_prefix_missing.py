#!/usr/bin/env python3
"""Probe 1: closure is blocked when the pre-fix FAIL run is missing.

Both-states is enforced by the closure tool. reviewer_ok does not close.
A single passing run is inadmissible. The two-commit runner executes against
snapshots (polarity inverts when snapshots are swapped).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from contract import OUTPUT_REL, SENTINEL, UNIT_ID  # noqa: E402
from scenario import run_proof  # noqa: E402

RECEIPT = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    proof = run_proof()
    errors: list[str] = []

    if proof["existence_pre_outcome"] != "FAIL":
        errors.append(f"pre-not-fail:{proof['existence_pre_outcome']}")
    if proof["existence_post_outcome"] != "PASS":
        errors.append(f"post-not-pass:{proof['existence_post_outcome']}")
    if not proof["existence_pre_executed"] or not proof["existence_post_executed"]:
        errors.append("pair-not-executed")

    close_ok = proof["close_ok"]
    if not close_ok.get("allow"):
        errors.append(f"honest-pair-blocked:{close_ok.get('reason')}")
    if proof["b10r1_status"] != "CLOSED":
        errors.append(f"b10r1-not-closed:{proof['b10r1_status']}")

    missing = proof["missing_prefix"]
    if missing.get("allow"):
        errors.append("missing-prefix-allowed")
    if missing.get("reason") != "pre-fix-run-missing":
        errors.append(f"missing-reason:{missing.get('reason')}")

    reviewer = proof["reviewer_bypass"]
    if reviewer.get("allow"):
        errors.append("reviewer-ok-bypassed-gate")
    if not reviewer.get("reviewer_ok_ignored"):
        errors.append("reviewer-ok-not-ignored")
    if "reviewer-discipline-insufficient" not in (reviewer.get("reasons") or []):
        errors.append("reviewer-discipline-tag-absent")
    if proof["b10r3_status"] != "OPEN":
        errors.append(f"b10r3-moved:{proof['b10r3_status']}")

    if proof["stub_allows_missing_prefix"] is not True:
        errors.append("stub-did-not-allow")
    if proof["stub_allows_missing_prefix"] == reviewer.get("allow"):
        errors.append("tool-equals-reviewer-stub")

    single = proof["single_passing"]
    if single.get("allow"):
        errors.append("single-passing-allowed")
    if "single-passing-run-inadmissible" not in (single.get("reasons") or []):
        errors.append(f"single-reason:{single.get('reason')}")

    unexec = proof["unexecuted_claim"]
    if unexec.get("allow"):
        errors.append("unexecuted-claim-allowed")
    if "pre-fix-run-not-executed" not in (unexec.get("reasons") or []):
        errors.append(f"unexecuted-reason:{unexec.get('reason')}")

    if proof["swapped_pre_outcome"] != "PASS":
        errors.append(f"swap-pre:{proof['swapped_pre_outcome']}")
    if proof["swapped_post_outcome"] != "FAIL":
        errors.append(f"swap-post:{proof['swapped_post_outcome']}")
    swapped = proof["swapped_close"]
    if swapped.get("allow"):
        errors.append("swapped-pair-allowed")
    if "pre-fix-not-fail" not in (swapped.get("reasons") or []):
        errors.append(f"swap-reason:{swapped.get('reason')}")

    if proof["git_checkout_used"]:
        errors.append("git-checkout-used")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"receipt-unparseable:{exc}")
        else:
            if SENTINEL not in text:
                errors.append("sentinel-absent")
            if str(doc.get("state") or "").upper() != "SUCCESS":
                errors.append(f"receipt-state:{doc.get('state')}")

    payload = {
        "probe": "probe1-prefix-missing",
        "unit_id": UNIT_ID,
        "close_ok_allow": close_ok.get("allow"),
        "missing_prefix_reason": missing.get("reason"),
        "reviewer_ok_ignored": reviewer.get("reviewer_ok_ignored"),
        "stub_would_close": proof["stub_allows_missing_prefix"],
        "single_inadmissible": not single.get("allow"),
        "swap_inverts": (
            proof["swapped_pre_outcome"] == "PASS"
            and proof["swapped_post_outcome"] == "FAIL"
        ),
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        return fail(",".join(errors))
    print(
        f"SUCCESS:{UNIT_ID}-probe1 closure blocked without pre-fix FAIL; "
        "reviewer_ok ignored; both-states pair closes; snapshot polarity inverts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
