#!/usr/bin/env python3
"""Probe 2: backfill census treats missing pre-fix FAIL runs as DEBT, not pass.

Already-CLOSED defects without a recorded pre-fix FAIL are named. A
both-PASS oracle cannot close. Census verdict is DEBT while debt_n > 0.
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
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    proof = run_proof()
    errors: list[str] = []
    cen = proof["census"]

    if cen.get("treat_debt_as") != "DEBT":
        errors.append("treat-debt-as-not-DEBT")
    if cen.get("pass_if_debt") is not False:
        errors.append("pass-if-debt-not-false")
    debt_n = int(cen.get("debt_missing_prefix_fail") or 0)
    if debt_n < 2:
        errors.append(f"debt-too-small:{debt_n}")
    if cen.get("verdict") != "DEBT":
        errors.append(f"census-verdict:{cen.get('verdict')}")
    if cen.get("verdict") == "PASS":
        errors.append("census-called-pass-with-debt")

    debt_ids = set(cen.get("debt_ids") or [])
    for expected in ("B11-I2-SCHEMA-ABSENT", "B10-PAPER-CLOSED"):
        if expected not in debt_ids:
            errors.append(f"debt-id-missing:{expected}")
    if "B11-I1-WORKER-ISOLATION" in debt_ids:
        errors.append("honest-historical-counted-as-debt")
    if "B10-R1-EXISTENCE-ONLY" in debt_ids:
        errors.append("live-both-states-counted-as-debt")
    if "B10-R1-EXISTENCE-ONLY" not in set(cen.get("honest_ids") or []):
        errors.append("live-close-not-honest")

    silent = proof["silent_oracle"]
    if silent.get("allow"):
        errors.append("silent-oracle-allowed")
    if "oracle-silent-in-both-states" not in (silent.get("reasons") or []):
        errors.append(f"silent-reason:{silent.get('reason')}")
    if proof["noop_pre_outcome"] != "PASS" or proof["noop_post_outcome"] != "PASS":
        errors.append("noop-not-both-pass")
    if proof["b10r2_status"] != "OPEN":
        errors.append(f"silent-closed-b10r2:{proof['b10r2_status']}")

    cited = proof["cited_closed"]
    live = [row for row in cited if row["defect_id"] == "B10-R1-EXISTENCE-ONLY"]
    if not live or not live[0]["both_recorded"]:
        errors.append("live-close-missing-two-run-ids")
    hist = [row for row in cited if row["defect_id"] == "B11-I1-WORKER-ISOLATION"]
    if not hist or not hist[0]["both_recorded"]:
        errors.append("hist-honest-missing-two-run-ids")

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
            backfill = doc.get("backfill_census") or {}
            if backfill.get("verdict") == "PASS":
                errors.append("receipt-census-pass-with-debt")

    payload = {
        "probe": "probe2-census-debt",
        "unit_id": UNIT_ID,
        "debt_n": debt_n,
        "debt_ids": sorted(debt_ids),
        "honest_ids": cen.get("honest_ids"),
        "verdict": cen.get("verdict"),
        "silent_blocked": not silent.get("allow"),
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        return fail(",".join(errors))
    print(
        f"SUCCESS:{UNIT_ID}-probe2 census debt_n={debt_n} treated as DEBT not pass; "
        "silent both-PASS oracle cannot close"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
