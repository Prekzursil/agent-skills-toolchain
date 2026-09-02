#!/usr/bin/env python3
"""Probe 2: UNVERIFIED with no settling probe must fail validation (both-states).

Good state: the same record with a settling_probe object validates.
Bad state: delete settling_probe -> one or more schema errors.
Mechanically different from probe 1 (collapse/ranking) : field-deletion mutation.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claims as C  # noqa: E402
import validator as V  # noqa: E402


def main() -> int:
    schema = V.load_schema()
    records, source = C.load_encoded()
    if not records:
        print("FAILED:ARC-0085-probe2 no claims to mutate")
        return 1

    good = copy.deepcopy(records[0])
    good["claim_id"] = "CLAIM-UNVERIFIED-WITH-PROBE"
    good["verification_status"] = "UNVERIFIED"
    good["confidence_band"] = "roughly-even"
    if not good.get("settling_probe"):
        print("FAILED:ARC-0085-probe2 fixture missing settling_probe to copy")
        return 1

    good_errs = V.schema_errors(good, schema)
    if good_errs:
        print(f"FAILED:ARC-0085-probe2 good UNVERIFIED rejected: {good_errs}")
        return 1

    bad = copy.deepcopy(good)
    bad.pop("settling_probe", None)
    bad_errs = V.schema_errors(bad, schema)
    if not bad_errs:
        print("FAILED:ARC-0085-probe2 UNVERIFIED without settling_probe was accepted")
        return 1
    joined = " ".join(bad_errs).lower()
    if "settling_probe" not in joined:
        print(f"FAILED:ARC-0085-probe2 errors do not name settling_probe: {bad_errs}")
        return 1

    # Control: CONFIRMED without settling_probe must also fail (field is required).
    confirmed_bad = copy.deepcopy(records[0])
    confirmed_bad.pop("settling_probe", None)
    confirmed_errs = V.schema_errors(confirmed_bad, schema)
    if not confirmed_errs:
        print("FAILED:ARC-0085-probe2 CONFIRMED without settling_probe was accepted")
        return 1

    print(
        json.dumps(
            {
                "source": source,
                "good_unverified_accepted": True,
                "bad_unverified_rejected": True,
                "bad_error_count": len(bad_errs),
                "bad_errors": bad_errs[:4],
                "confirmed_without_probe_rejected": True,
                "silent_on_good": True,
                "fired_on_bad": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"good_ok=True bad_errs={len(bad_errs)} confirmed_also_required=True "
        f"source={source}"
    )
    print("SUCCESS:ARC-0085-probe2 settling-probe requirement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
