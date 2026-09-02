#!/usr/bin/env python3
"""Named probe 1: measured token count of the actual injected block vs N.

Signal (a) from the catalog: count tokens of the live injected payload,
not an estimate. Reports the growth curve and asserts it stays under the
ceiling and is sub-linear in installed-capability count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0240.json"
sys.path.insert(0, str(HERE))

import catalog as C  # noqa: E402

from router.inject import inject  # noqa: E402
from router.tokens import count_tokens  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0240-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0240" not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != "TST-0240":
        return fail(f"unit_id {doc.get('unit_id')}")

    rows = C.growth_curve()
    verdict = C.curve_verdict(rows)
    if not verdict["all_under_ceiling"]:
        return fail(f"a curve point exceeded ceiling {verdict}")
    if not verdict["sublinear"]:
        return fail(f"growth not sub-linear slope={verdict['loglog_slope']}")
    if not verdict["measured_differs_from_chars_div_4"]:
        return fail("token count collapsed onto chars/4 estimate")
    if verdict["max_tokens"] < 8:
        return fail("injected block too small to be a real measurement")

    live = inject(C.QUERY, C.build_catalog(110))
    recount = count_tokens(live.block)
    if recount != live.tokens:
        return fail(f"result.tokens {live.tokens} != recount {recount}")
    if recount != count_tokens(live.block):
        return fail("tokenizer not stable on the same block")
    if live.policy != "topk":
        return fail(f"unexpected policy {live.policy}")
    planted = {spec[0] for spec in C.RELEVANT_SPECS}
    if set(live.selected) != planted:
        return fail(f"selected {live.selected} planted {sorted(planted)}")
    if "skill.filler.0000" in live.selected:
        return fail("distractor leaked into top-k injection")

    receipt_tokens = (
        (doc.get("benchmark") or {}).get("curve") or {}
    ).get("tokens")
    if receipt_tokens is not None and list(receipt_tokens) != verdict["tokens"]:
        return fail(
            f"receipt curve {receipt_tokens} != live {verdict['tokens']}"
        )

    payload = {
        "probe": "probe1-measured-token-curve",
        "unit_id": "TST-0240",
        "pass": True,
        "curve": verdict,
        "live_n110_tokens": live.tokens,
        "live_n110_chars_div_4": live.chars_div_4,
        "live_selected": live.selected,
        "tokenizer_pin": live.tokenizer.get("pin"),
        "measured_on": "actual injected block",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"tokens={verdict['tokens']} slope={verdict['loglog_slope']:.4f} "
        f"ceiling={verdict['ceiling']} under={verdict['all_under_ceiling']}"
    )
    print("SUCCESS:TST-0240-probe1 measured injected-block tokens stay under ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
