#!/usr/bin/env python3
"""Probe 1: stopping rule is evaluated and recorded; no third-order pass."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "SYN-0039.json"
SENTINEL = (
    "SUCCESS:SYN-0039 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the stopping rule fired "
    "with a recorded measurement and no deeper pass was launched. Any other "
    "terminal state is FAILED:SYN-0039 <classification> with the diagnostic "
    "tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0039-probe1 {msg}")
    return 1


def main() -> int:
    result = E.review(include_fixtures=True, depth=2)
    rule = result["stopping_rule"]
    reviews = result["meta_findings"]
    recomputed = E.information_gain(reviews)
    gain = float(recomputed["information_gain"])
    if rule.get("evaluated") is not True:
        return fail("stopping rule was assumed, not evaluated")
    if abs(float(rule["information_gain"]) - gain) > 1e-12:
        return fail(
            f"recorded IG {rule['information_gain']} != recomputed {gain}"
        )
    if rule.get("fired") is not True:
        return fail("stopping rule did not fire")
    if rule.get("deeper_pass_launched") is not False:
        return fail("deeper pass was launched")
    if rule.get("trigger") not in {"information_gain", "depth"}:
        return fail(f"trigger={rule.get('trigger')}")

    ig_repeat = E.information_gain(reviews, E.failing_axes(reviews))
    if abs(float(ig_repeat["information_gain"]) - 0.0) > 1e-12:
        return fail("re-applying the same tests on the same subjects was not zero-gain")

    low = E.should_launch_deeper(1, 0.01)
    if low["launch"] or low["trigger"] != "information_gain":
        return fail(f"low-IG depth-1 should stop on information_gain, got {low}")
    cap = E.should_launch_deeper(2, 1.0)
    if cap["launch"] or cap["trigger"] != "depth":
        return fail(f"depth-2 high-IG should stop on depth, got {cap}")
    cont = E.should_launch_deeper(1, 0.5)
    if not cont["launch"] or cont["fired"]:
        return fail(f"depth-1 high-IG should continue, got {cont}")

    refusal = E.refuse_deeper_pass(2, gain)
    if refusal.get("launched") is not False:
        return fail("refuse_deeper_pass launched a pass")

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("catalog sentinel absent from artifact")
    art_rule = E.payload_from_artifact(doc)["stopping_rule"]
    if art_rule.get("evaluated") is not True:
        return fail("artifact stopping_rule.evaluated is not true")
    if abs(float(art_rule.get("information_gain")) - gain) > 1e-12:
        return fail("artifact IG does not match live recompute")
    if art_rule.get("fired") is not True:
        return fail("artifact stopping_rule.fired is not true")
    if art_rule.get("deeper_pass_launched") is not False:
        return fail("artifact launched a deeper pass")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")

    print(f"ig={gain} trigger={rule['trigger']} depth={rule['depth']}")
    print(f"ig_if_reapplied={ig_repeat['information_gain']}")
    print(f"deeper_launched={rule['deeper_pass_launched']}")
    print("SUCCESS:SYN-0039-probe1 stopping rule evaluated, recorded, no third-order pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
