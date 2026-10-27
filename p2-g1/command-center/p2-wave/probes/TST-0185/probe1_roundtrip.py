#!/usr/bin/env python3
"""TST-0185 probe1 -- property test: generated ids spanning 2^40..2^63 and decimals
with 20 significant digits survive the exact parse/emit path with no loss.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import int_roundtrip as IR  # noqa: E402

UNIT = "TST-0185"


def main() -> int:
    rng = random.Random(185185)
    id_failures = []
    dec_failures = []
    n_ids, n_decs = 1000, 500
    for _ in range(n_ids):
        v = rng.randint(2 ** 40, 2 ** 63)
        text = IR.emit_exact({"id": v})
        back = IR.parse_exact(text)["id"]
        if not (isinstance(back, int) and back == v):
            id_failures.append(v)
    for _ in range(n_decs):
        digits = "".join(rng.choice("0123456789") for _ in range(20))
        d = Decimal(digits[0] + "." + digits[1:] + "e" + str(rng.randint(-8, 8)))
        text = IR.emit_exact({"price": d})
        back = IR.parse_exact(text)["price"]
        if not (isinstance(back, Decimal) and back == d):
            dec_failures.append(str(d))

    payload = {
        "probe": "probe1-roundtrip",
        "unit_id": UNIT,
        "pass": not id_failures and not dec_failures,
        "ids_checked": n_ids,
        "id_failures": len(id_failures),
        "decimals_checked": n_decs,
        "decimal_failures": len(dec_failures),
        "span": {"ids": "2^40..2^63", "decimals": "20 significant digits, exponent -8..8"},
        "exact_lane": "json parse_int=int + parse_float=Decimal; Decimal emitted as exact digits",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 ids=%d/1000 exact decimals=%d/500 exact"
              % (UNIT, n_ids - len(id_failures), n_decs - len(dec_failures)))
        return 0
    print("FAILED:%s-probe1 id_fail=%d dec_fail=%d" % (UNIT, len(id_failures), len(dec_failures)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
