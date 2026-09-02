#!/usr/bin/env python3
"""Probe 2: reject a sub-check that cannot fail; independent recount.

Mechanically different from probe 1:
  * scores trust by re-deriving GOOD==SUCCESS and BROKEN==FAILED from the
    live pair dicts (does not call harness.assertions)
  * requires the always-SUCCESS double to be UNTRUSTWORTHY
  * requires a missing broken fixture to be UNTRUSTWORTHY
  * requires BLOCKED and unrun aggregates to refuse GREEN
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as HV  # noqa: E402
import health as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0075.json"


def recount_trust(row: dict) -> bool:
    good = (row.get("good") or {}).get("verdict")
    broken = (row.get("broken") or {}).get("verdict") if row.get("broken") else None
    return good == H.SUCCESS and broken == H.FAILED


def main() -> int:
    live = HV.evaluate_live()
    recounted = []
    for row in live["pairs"]:
        derived = recount_trust(row)
        recounted.append(
            {
                "id": row["id"],
                "derived_trusted": derived,
                "flag_trusted": bool(row.get("trusted")),
            }
        )
        if derived != bool(row.get("trusted")):
            print(
                f"FAILED:TST-0075-probe2 trust-flag drift {row['id']} "
                f"derived={derived} flag={row.get('trusted')}"
            )
            return 1
        if not derived:
            print(f"FAILED:TST-0075-probe2 {row['id']} does not discriminate")
            return 1

    inert = live["inert_always_ok"]
    if recount_trust(inert) or inert.get("trusted"):
        print("FAILED:TST-0075-probe2 always_ok was accepted")
        return 1
    if (inert.get("good") or {}).get("verdict") != H.SUCCESS:
        print("FAILED:TST-0075-probe2 always_ok was not SUCCESS on good")
        return 1
    if (inert.get("broken") or {}).get("verdict") != H.SUCCESS:
        print("FAILED:TST-0075-probe2 always_ok fired on broken (unexpected)")
        return 1

    fire = live["inert_always_failed"]
    if recount_trust(fire) or fire.get("trusted"):
        print("FAILED:TST-0075-probe2 always_failed was accepted")
        return 1

    missing = live["missing_broken_fixture"]
    if missing.get("trusted") or missing.get("reason") != "missing-broken-fixture":
        print(f"FAILED:TST-0075-probe2 missing fixture not rejected: {missing}")
        return 1

    if live["blocked_aggregate"] == H.GREEN:
        print("FAILED:TST-0075-probe2 BLOCKED probe still GREEN aggregate")
        return 1
    if live["unrun_aggregate"] == H.GREEN:
        print("FAILED:TST-0075-probe2 unrun sub-check still GREEN aggregate")
        return 1
    if (live.get("throwing") or {}).get("verdict") != H.FAILED:
        print(f"FAILED:TST-0075-probe2 throw swallowed: {live.get('throwing')}")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:TST-0075" not in ART.read_text(encoding="utf-8"):
            print("FAILED:TST-0075-probe2 sentinel absent")
            return 1
        recorded = doc.get("both_states") or []
        rec_ids = [r.get("subcheck") for r in recorded]
        live_ids = [r["id"] for r in live["pairs"]]
        if rec_ids != live_ids:
            print(f"FAILED:TST-0075-probe2 both_states id drift {rec_ids} vs {live_ids}")
            return 1
        for rec, row in zip(recorded, live["pairs"]):
            if rec.get("good_verdict") != row["good"]["verdict"]:
                print(f"FAILED:TST-0075-probe2 good verdict drift {rec}")
                return 1
            if rec.get("broken_verdict") != row["broken"]["verdict"]:
                print(f"FAILED:TST-0075-probe2 broken verdict drift {rec}")
                return 1
            if rec.get("trusted") is not True:
                print(f"FAILED:TST-0075-probe2 artifact pair not trusted {rec}")
                return 1
        inert_rec = doc.get("inert_rejected") or {}
        if inert_rec.get("rejected") is not True or inert_rec.get("trusted") is True:
            print(f"FAILED:TST-0075-probe2 artifact inert_rejected {inert_rec}")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:TST-0075-probe2 artifact self-declared {st}")
            return 1

    payload = {
        "probe": "probe2-inert-and-recount",
        "unit_id": "TST-0075",
        "recounted": recounted,
        "inert_rejected": True,
        "missing_fixture_rejected": True,
        "blocked_aggregate": live["blocked_aggregate"],
        "unrun_aggregate": live["unrun_aggregate"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"recount_trusted={len(recounted)}/{len(H.SUBCHECK_IDS)} "
        f"inert_rejected=True blocked={live['blocked_aggregate']} "
        f"unrun={live['unrun_aggregate']}"
    )
    print("SUCCESS:TST-0075-probe2 inert rejection and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
