#!/usr/bin/env python3
"""Probe 2: genuine REFUTED still records; re-queue BLOCKED is idempotent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import run_scenario  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0136-probe2 {msg}")
    return 1


def main() -> int:
    data = run_scenario()
    genuine = data["genuine"]
    if genuine.get("verdict") != "REFUTED":
        return fail(f"genuine verdict={genuine.get('verdict')} want=REFUTED")
    if genuine.get("fault_class") is not None:
        return fail("genuine REFUTED carried a fault_class")
    if genuine.get("named_prerequisite") is not None:
        return fail("genuine REFUTED carried named_prerequisite")
    if not genuine.get("source_probe") or not genuine.get("verifier_probe"):
        return fail("genuine REFUTED missing probes")
    if genuine["source_probe"] == genuine["verifier_probe"]:
        return fail("genuine REFUTED same-probe-rerun")
    if not data.get("launder_raised"):
        return fail("retry of REFUTED did not raise VerdictLaunderingError")
    if not data.get("unsourced_confirmed_rejected"):
        return fail("unsourced CONFIRMED was representable")

    idemp = data["idemp"]
    if idemp["first_id"] != idemp["second_id"]:
        return fail("requeue changed record_id")
    if idemp["count_before"] != idemp["count_after"]:
        return fail(
            f"requeue duplicated records {idemp['count_before']}->{idemp['count_after']}"
        )

    two = data["two_strikes"]
    if not two.get("same_id"):
        return fail("two-strikes created a new record_id")
    if not two.get("parked"):
        return fail("two-strikes did not park")
    if two.get("retry_len", 0) < 2:
        return fail(f"two-strikes retries={two.get('retry_len')}")

    if data.get("infra_refuted_ids"):
        return fail(
            "reviewer grep: REFUTED with infra evidence "
            + ",".join(data["infra_refuted_ids"])
        )

    summary = {
        "genuine_verdict": genuine["verdict"],
        "launder_raised": data["launder_raised"],
        "idemp_same_id": idemp["first_id"] == idemp["second_id"],
        "idemp_count_stable": idemp["count_before"] == idemp["count_after"],
        "two_strikes_parked": two["parked"],
        "infra_refuted_ids": data["infra_refuted_ids"],
        "unsourced_confirmed_rejected": data["unsourced_confirmed_rejected"],
        "pass": True,
        "probe": "probe2-refute-and-idempotence",
        "unit_id": "CNF-0136",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "genuine=REFUTED launder_blocked=True "
        "idemp_stable=True two_strikes_parked=True "
        "reviewer_infra_refuted=0"
    )
    print("SUCCESS:CNF-0136-probe2 genuine REFUTED and idempotent requeue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
