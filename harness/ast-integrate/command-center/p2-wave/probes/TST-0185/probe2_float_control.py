#!/usr/bin/env python3
"""Named probe 2: float-based parser fails above 2^53; lossless path does not.

Independent of probe 1's property generator. Rebuilds the IEEE-754 hole on
2^53+1 and on a 20-digit decimal. 2^53 itself is the both-states control
(float still exact).
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from tools.plugin.json_codec import (  # noqa: E402
    as_decimal,
    emit,
    extract_number_tokens,
    parse,
)

ART = REPO / "command-center/receipts/TST-0185.json"
TWO_53 = 2**53
LOST_ID = TWO_53 + 1
EXACT_ID = TWO_53
DECIMAL_TOKEN = "1.2345678901234567890"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0185-probe2 {msg}")
    return 1


def lossless_int(n: int) -> bool:
    token = str(n)
    text = '{"package_id": ' + token + "}"
    parsed = parse(text)
    emitted = emit(parsed)
    tokens = extract_number_tokens(emitted)
    if tokens != [token]:
        return False
    got = parsed["package_id"]
    return as_decimal(got) == Decimal(token) and int(got) == n


def lossless_decimal(token: str) -> bool:
    text = '{"quality_score": ' + token + "}"
    parsed = parse(text)
    emitted = emit(parsed)
    if extract_number_tokens(emitted) != [token]:
        return False
    return as_decimal(parsed["quality_score"]) == Decimal(token)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0185" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    if int(float(EXACT_ID)) != EXACT_ID:
        return fail("float(2^53) was not exact; both-states control collapsed")
    if int(float(LOST_ID)) == LOST_ID:
        return fail("float(2^53+1) unexpectedly exact; negative control silent")

    via_json = json.loads(str(LOST_ID), parse_int=float, parse_float=float)
    if via_json == LOST_ID:
        return fail("json parse_int=float did not lose 2^53+1")
    via_json_exact = json.loads(str(EXACT_ID), parse_int=float, parse_float=float)
    if int(via_json_exact) != EXACT_ID:
        return fail("json parse_int=float lost 2^53 (both-states)")

    if not lossless_int(EXACT_ID) or not lossless_int(LOST_ID):
        return fail("lossless codec failed on 2^53 or 2^53+1")

    stdlib_dec = json.loads('{"quality_score": ' + DECIMAL_TOKEN + "}")
    if not isinstance(stdlib_dec["quality_score"], float):
        return fail("stdlib json.loads did not use float for the decimal")
    if Decimal(str(stdlib_dec["quality_score"])) == Decimal(DECIMAL_TOKEN):
        return fail("stdlib float decimal unexpectedly matched 20-digit Decimal")
    if not lossless_decimal(DECIMAL_TOKEN):
        return fail("lossless codec lost the 20-digit decimal")

    rec = (doc.get("tests") or {}).get("float_negative_control") or {}
    if rec.get("pass") is not True:
        return fail("receipt float_negative_control.pass is not true")
    lost = rec.get("lost_id", rec.get("lost_id"))
    if lost != LOST_ID:
        return fail("receipt lost_id is not 2^53+1")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict is not PASS")

    out = {
        "probe": "probe2-float-negative-control",
        "unit_id": "TST-0185",
        "pass": True,
        "float_preserves_2_53": True,
        "float_preserves_2_53_plus_1": False,
        "json_parse_int_float_lost": via_json,
        "lossless_preserves_2_53_plus_1": True,
        "stdlib_decimal_is_float": True,
        "lossless_preserves_20_digit_decimal": True,
        "lost_id": LOST_ID,
        "exact_id": EXACT_ID,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"float(2^53) exact=True float(2^53+1) exact=False "
        f"json_float_lost={via_json} lossless_ok=True"
    )
    print("SUCCESS:TST-0185-probe2 float parser fails above 2^53")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
