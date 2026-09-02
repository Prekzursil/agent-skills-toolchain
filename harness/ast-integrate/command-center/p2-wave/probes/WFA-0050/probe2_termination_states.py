#!/usr/bin/env python3
"""Probe 2: 20 synthetic states, grammar vs documented control-flow.

Mechanically different from probe 1: this probe never inspects construct
status or role maps. It evaluates stopping.py against documented.py.

Both-states: the good expression agrees on all 20; replacing OR with AND
disagrees on at least one AutoGen state (vacuity control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from battery import run_battery  # noqa: E402
from fixtures import SYNTHETIC_STATES  # noqa: E402

UNIT = "WFA-0050"
ART = REPO / "command-center/wfa/WFA-0050-adapter-crew-autogen.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0050" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    if len(SYNTHETIC_STATES) != 20:
        return fail(f"fixture n={len(SYNTHETIC_STATES)} want 20")

    live = run_battery()
    if live["n"] != 20:
        return fail(f"battery n={live['n']}")
    if live["disagree"]:
        return fail(f"grammar/documented disagree {live['disagree']}")
    if not live["stop_ids"] or not live["continue_ids"]:
        return fail("battery not mixed")
    if not live["planted_and_hits"]:
        return fail("planted AND mutation silent (vacuous detector)")

    rec = doc.get("termination_battery") or {}
    if rec.get("n") != 20:
        return fail("artifact battery n != 20")
    if rec.get("disagree"):
        return fail("artifact recorded disagreements")
    rec_ids = {r["id"] for r in rec.get("rows") or []}
    live_ids = {r["id"] for r in live["rows"]}
    if rec_ids != live_ids:
        return fail("artifact state ids != live fixtures")

    kinds = {s["kind"] for s in SYNTHETIC_STATES}
    if kinds != {"crew-sequential", "autogen-groupchat"}:
        return fail(f"kinds {kinds}")

    summary = {
        "n": live["n"],
        "stop": len(live["stop_ids"]),
        "continue": len(live["continue_ids"]),
        "disagree": live["disagree"],
        "planted_and_hits": live["planted_and_hits"],
        "both_states": {
            "good_silent": not live["disagree"],
            "plant_fires": bool(live["planted_and_hits"]),
        },
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:WFA-0050-probe2 20-state grammar vs documented "
        f"stop={summary['stop']} continue={summary['continue']} "
        f"plant_hits={len(live['planted_and_hits'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
