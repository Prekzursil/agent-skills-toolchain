#!/usr/bin/env python3
"""Named probe 2: adding 50 capabilities must not proportionally grow injection.

Both-states control from the catalog. Flood (inject every body, no ceiling)
is the detector's red state: it must grow with N and exceed the ceiling so
the top-k budgeter is not a one-sided always-green.
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

from router.inject import CEILING_TOKENS, POLICY_FLOOD, inject  # noqa: E402
from router.tokens import count_tokens  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0240-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable {exc}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0240" not in text:
        return fail("sentinel absent")

    ctl = C.add50_control()
    if not ctl["topk_under_ceiling"]:
        return fail(f"topk crossed ceiling {ctl}")
    if not ctl["topk_not_proportional"]:
        return fail(
            f"adding 50 grew top-k proportionally "
            f"ratio={ctl['topk_ratio']:.3f} "
            f"proportional={ctl['proportional_ratio']:.3f}"
        )
    if not ctl["flood_exceeds_ceiling"]:
        return fail(f"flood mutant stayed under ceiling {ctl}")
    if not ctl["flood_is_proportional"]:
        return fail(
            f"flood mutant did not grow with N ratio={ctl['flood_ratio']:.3f}"
        )
    if ctl["topk_tokens_n_plus_50"] >= ctl["flood_tokens_n_plus_50"]:
        return fail("topk cost was not below flood cost")
    if ctl["topk_selected_n"] != ctl["topk_selected_n_plus_50"]:
        return fail(
            f"adding 50 changed the selected set "
            f"{ctl['topk_selected_n']} -> {ctl['topk_selected_n_plus_50']}"
        )

    flood = inject(
        C.QUERY, C.build_catalog(C.ADD50_PLUS), policy=POLICY_FLOOD
    )
    flood_recount = count_tokens(flood.block)
    if flood_recount != flood.tokens:
        return fail("flood tokens not measured on the emitted block")
    if flood_recount <= CEILING_TOKENS:
        return fail(f"flood recount {flood_recount} <= ceiling")
    if "skill.filler.0000" not in flood.selected:
        return fail("flood did not include distractors")

    receipt_ctl = (doc.get("benchmark") or {}).get("add50") or {}
    if receipt_ctl.get("topk_tokens_n_plus_50") not in (None, ctl["topk_tokens_n_plus_50"]):
        return fail("receipt add50 topk tokens drifted from live re-measure")

    payload = {
        "probe": "probe2-add50-and-flood",
        "unit_id": "TST-0240",
        "pass": True,
        "control": ctl,
        "flood_n60_tokens": flood.tokens,
        "flood_n60_chars_div_4": flood.chars_div_4,
        "spec_anchor": (
            "_USER-PROMPTS.md:10963 selects relevant capabilities "
            "without flooding context"
        ),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        f"topk {ctl['topk_tokens_n']}->{ctl['topk_tokens_n_plus_50']} "
        f"ratio={ctl['topk_ratio']:.3f} flood {ctl['flood_tokens_n']}->"
        f"{ctl['flood_tokens_n_plus_50']} ratio={ctl['flood_ratio']:.3f}"
    )
    print("SUCCESS:TST-0240-probe2 add-50 does not proportionally grow injection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
