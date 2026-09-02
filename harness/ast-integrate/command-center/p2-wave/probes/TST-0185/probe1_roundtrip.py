#!/usr/bin/env python3
"""Named probe 1: 64-bit ids and 20-digit decimals round-trip without float.

Independent signals on every case:
  (a) emitted number token string-equals the source token
  (b) Decimal-typed comparison after re-parse
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0185.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0185-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0185" and doc.get("unit_id") != "TST-0185":
        return fail(f"unit_id {doc.get('unit_id')}")
    blob = json.dumps(doc)
    if "SUCCESS:TST-0185" not in blob:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.run_property_suite()
    if not live.get("pass"):
        return fail(
            "live property suite failed "
            f"id_fail={live.get('n_id_fail')} decimal_fail={live.get('n_decimal_fail')} "
            f"plugin={live.get('plugin_fixture')} market={live.get('marketplace_fixture')}"
        )
    n_ids = int(live.get("n_ids") or live.get("n_ids") or 0)
    n_decs = int(live.get("n_decimals") or live.get("n_decimals") or 0)
    n_above = int(live.get("n_ids_above_2_53") or live.get("n_ids_above_2_53") or 0)
    if n_ids < 128 or n_decs < 128:
        return fail(f"corpus too small ids={n_ids} decimals={n_decs}")
    if n_above < 1:
        return fail("no ids above 2^53")
    plugin = live.get("plugin_fixture") or live.get("plugin_fixture") or {}
    market = live.get("marketplace_fixture") or live.get("marketplace_fixture") or {}
    if not (plugin.get("token_equal") or plugin.get("token_equal")):
        return fail("plugin fixture round-trip lost precision")
    if not (plugin.get("decimal_equal") or plugin.get("decimal_equal")):
        return fail("plugin fixture decimal mismatch")
    if not (market.get("token_equal") or market.get("token_equal")):
        return fail("marketplace fixture round-trip lost precision")
    if not (market.get("decimal_equal") or market.get("decimal_equal")):
        return fail("marketplace fixture decimal mismatch")

    rec_tests = (doc.get("tests") or {}).get("property_round_trip") or {}
    if rec_tests.get("pass") is not True:
        return fail("receipt property_round_trip.pass is not true")
    rec_ids = int(rec_tests.get("n_ids") or rec_tests.get("n_ids") or 0)
    rec_decs = int(rec_tests.get("n_decimals") or rec_tests.get("n_decimals") or 0)
    if rec_ids != n_ids:
        return fail("receipt n_ids drifted from live")
    if rec_decs != n_decs:
        return fail("receipt n_decimals drifted from live")

    evidence = doc.get("evidence") or []
    kinds = {e.get("signal") for e in evidence if isinstance(e, dict)}
    if "token-string-equality" not in kinds or "decimal-typed-reparse" not in kinds:
        return fail("receipt missing the two independent evidence signals")

    plugin_tokens = plugin.get("source_tokens") or plugin.get("source_tokens")
    market_tokens = market.get("source_tokens") or market.get("source_tokens")
    out = {
        "probe": "probe1-precision-roundtrip",
        "unit_id": "TST-0185",
        "pass": True,
        "n_ids": n_ids,
        "n_ids_above_2_53": n_above,
        "n_decimals": n_decs,
        "plugin_tokens": plugin_tokens,
        "marketplace_tokens": market_tokens,
        "signal_a": live["signal_a"],
        "signal_b": live["signal_b"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"ids={n_ids} above_2^53={n_above} "
        f"decimals={n_decs} plugin_ok={plugin['pass']} "
        f"market_ok={market['pass']}"
    )
    print("SUCCESS:TST-0185-probe1 64-bit id and 20-digit decimal round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
