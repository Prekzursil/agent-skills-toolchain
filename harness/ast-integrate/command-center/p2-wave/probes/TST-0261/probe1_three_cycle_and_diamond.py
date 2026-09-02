#!/usr/bin/env python3
"""Probe 1: planted 3-node citation cycle FIRES with the exact path.

Both-states: the same detector is SILENT on the planted diamond (a long
chain with a shared ancestor). A detector that flags the diamond is unusable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.evidence_graph import inspect  # noqa: E402
from council.tests.test_evidence_cycles import (  # noqa: E402
    test_diamond_is_silent,
    test_planted_three_node_cycle_fires,
)
from fixtures import (  # noqa: E402
    THREE_CYCLE_PATH,
    THREE_CYCLE_PRINTED,
    planted_diamond_long_chain,
    planted_three_node_cycle,
)

UNIT = "TST-0261"
ART = REPO / "command-center" / "receipts" / "TST-0261.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SUCCESS:TST-0261"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0261-probe1 {msg}")
    return 1


def independent_walk_three_cycle() -> list[str]:
    """Walk the planted edges without calling the detector."""
    adj = {
        e["from"]: e["to"]
        for e in planted_three_node_cycle()["support_edges"]
    }
    start = THREE_CYCLE_PATH[0]
    path = [start]
    cur = start
    for _ in range(3):
        cur = adj[cur]
        path.append(cur)
    return path


def both_states() -> dict:
    good = inspect(planted_diamond_long_chain())
    broken = inspect(planted_three_node_cycle())
    silent_on_good = good["status"] == "ACYCLIC" and not good["cycles"]
    fires_on_broken = broken["status"] == "CYCLIC" and bool(broken["cycles"])
    return {
        "detector_id": "TST-0261-cyclic-support",
        "good_output": {
            "fired": bool(good["cycles"]),
            "status": good["status"],
            "cycle_count": good["cycle_count"],
        },
        "broken_output": {
            "fired": bool(broken["cycles"]),
            "status": broken["status"],
            "path_printed": (broken["cycles"][0]["path_printed"] if broken["cycles"] else None),
        },
        "silent_on_good_state": silent_on_good,
        "fired_on_bad_state": fires_on_broken,
        "differs": silent_on_good and fires_on_broken,
        "verdict": "DIFFERS" if silent_on_good and fires_on_broken else "IDENTICAL",
    }


def check_receipt() -> dict:
    if not ART.is_file():
        return {"present": False, "ok": True, "skipped": True}
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return {"present": True, "ok": False, "reason": f"self-declared:{st}"}
    if SENTINEL not in text:
        return {"present": True, "ok": False, "reason": "sentinel-absent"}
    planted = doc.get("planted_three_node_cycle") or {}
    if planted.get("path") != THREE_CYCLE_PATH:
        return {
            "present": True,
            "ok": False,
            "reason": f"receipt path {planted.get('path')}",
        }
    if planted.get("path_printed") != THREE_CYCLE_PRINTED:
        return {
            "present": True,
            "ok": False,
            "reason": "receipt missing printed path",
        }
    if planted.get("fired") is not True:
        return {"present": True, "ok": False, "reason": "receipt did not fire on 3-cycle"}
    diamond = doc.get("planted_diamond") or {}
    if diamond.get("fired") is True or (diamond.get("cycles") or []):
        return {"present": True, "ok": False, "reason": "receipt flagged diamond"}
    if diamond.get("status") != "ACYCLIC":
        return {
            "present": True,
            "ok": False,
            "reason": f"receipt diamond status={diamond.get('status')}",
        }
    return {"present": True, "ok": True, "skipped": False, "state": st}


def main() -> int:
    walked = independent_walk_three_cycle()
    if walked != THREE_CYCLE_PATH:
        return fail(f"independent walk {walked}")

    try:
        cycle = test_planted_three_node_cycle_fires()
        diamond = test_diamond_is_silent()
    except AssertionError as exc:
        return fail(str(exc))

    states = both_states()
    if not states["differs"]:
        return fail(f"both-states {states}")

    receipt = check_receipt()
    if receipt.get("ok") is not True:
        return fail(f"receipt {receipt}")

    payload = {
        "probe": "probe1-three-cycle-and-diamond",
        "unit_id": UNIT,
        "independent_walk": walked,
        "test_planted_three_node_cycle_fires": cycle,
        "test_diamond_is_silent": diamond,
        "both_states": states,
        "receipt": receipt,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:TST-0261-probe1 3-node cycle fires "
        f"{THREE_CYCLE_PRINTED}; diamond silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
