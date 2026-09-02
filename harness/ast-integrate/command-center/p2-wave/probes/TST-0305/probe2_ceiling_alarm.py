#!/usr/bin/env python3
"""Probe 2: ceiling alarm both-states (fires on fast, silent on slow)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    CATALOG_SENTINEL,
    OUT_REL,
    REPO,
    compact,
    inverted_ceiling_alarm,
    load_artifact,
    run_campaign,
)


def main() -> int:
    try:
        doc = load_artifact()
    except (OSError, json.JSONDecodeError, FileNotFoundError) as exc:
        print("FAILED:TST-0305-probe2 artifact", type(exc).__name__)
        return 1
    text = (REPO / OUT_REL).read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:TST-0305-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0305-probe2 self-declared", doc.get("state"))
        return 1

    live = run_campaign()
    print(json.dumps(compact(live), sort_keys=True, default=str))

    tiny = live["tiny"]
    real = live["real"]
    ceil = live["ceiling"]
    if not live.get("both_states"):
        print(
            "FAILED:TST-0305-probe2 both-states "
            f"fast_fired={ceil.get('fast_p50_fired')} "
            f"slow_fired={ceil.get('slow_p50_fired')}"
        )
        return 1
    if ceil.get("inverted_both_states"):
        print("FAILED:TST-0305-probe2 inverted detector also both-states (vacuous)")
        return 1
    if not tiny["ceiling_p50"]:
        print("FAILED:TST-0305-probe2 tiny p50 did not fire", tiny)
        return 1
    if real["ceiling_p50"]:
        print("FAILED:TST-0305-probe2 real p50 fired (want silent)", real)
        return 1

    inv_fast = inverted_ceiling_alarm(tiny["p50_oracle_ms"], tiny["p50_harness_ms"])
    inv_slow = inverted_ceiling_alarm(real["p50_oracle_ms"], real["p50_harness_ms"])
    if inv_fast is True and inv_slow is False:
        print("FAILED:TST-0305-probe2 inverted alarm matched production polarity")
        return 1
    if inv_fast is not False:
        print("FAILED:TST-0305-probe2 inverted fast should be silent", inv_fast)
        return 1
    if inv_slow is not True:
        print("FAILED:TST-0305-probe2 inverted slow should fire", inv_slow)
        return 1

    art_ceil = (doc.get("overhead") or {}).get("ceiling") or doc.get("ceiling") or {}
    if art_ceil.get("fast_p50_fired") is not True:
        print("FAILED:TST-0305-probe2 artifact fast_p50_fired", art_ceil)
        return 1
    if art_ceil.get("slow_p50_fired") is not False:
        print("FAILED:TST-0305-probe2 artifact slow_p50_fired", art_ceil)
        return 1
    if art_ceil.get("inverted_both_states") is True:
        print("FAILED:TST-0305-probe2 artifact inverted_both_states true")
        return 1

    print(
        f"fired_on_fast={tiny['ceiling_p50']} silent_on_slow={not real['ceiling_p50']} "
        f"inv_fast={inv_fast} inv_slow={inv_slow} "
        f"payload_s={live['payload_s']}"
    )
    print("SUCCESS:TST-0305-probe2 ceiling alarm both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
