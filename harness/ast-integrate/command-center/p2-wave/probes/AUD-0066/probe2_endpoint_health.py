#!/usr/bin/env python3
"""Probe 2: endpoint health + wrong-port control (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

RAW = HERE / "probe2-endpoint-health.raw.txt"
JSON_OUT = HERE / "probe2-endpoint-health.json"
CTRL_RAW = HERE / "control-wrong-port.raw.txt"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    health = E.probe_health()
    text = E.text_p2(health)
    RAW.write_text(text + "\n", encoding="utf-8")
    CTRL_RAW.write_text(
        json.dumps(
            {
                "wrong_port": health["wrong_port"],
                "wrong_port_failed": health["wrong_port_failed"],
                "scratch_good": health["scratch_good"],
                "scratch_good_passed": health["scratch_good_passed"],
                "control_pass": health["control_pass"],
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    E.dump(JSON_OUT, {"probe": "probe2-endpoint-health", "health": health})
    print(text)

    if not health["wrong_port_failed"]:
        print("FAILED:AUD-0066-probe2 wrong-port control did not fail")
        return 1
    if not health["scratch_good_passed"]:
        print("FAILED:AUD-0066-probe2 scratch good-state listener did not succeed")
        return 1
    if not health["control_pass"]:
        print("FAILED:AUD-0066-probe2 both-states control did not pass")
        return 1

    try:
        art_text, doc = E.load_artifact()
    except FileNotFoundError:
        print("FAILED:AUD-0066-probe2 artifact missing")
        return 1
    if E.SENTINEL not in art_text:
        print("FAILED:AUD-0066-probe2 catalog sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        print(f"FAILED:AUD-0066-probe2 self-declared {st}")
        return 1
    ah = doc.get("health") or {}
    if int(ah.get("n_live_up", -1)) != int(health["n_live_up"]):
        print(
            "FAILED:AUD-0066-probe2 n_live_up drift "
            f"artifact={ah.get('n_live_up')} live={health['n_live_up']}"
        )
        return 1
    if int(ah.get("n_live_down", -1)) != int(health["n_live_down"]):
        print(
            "FAILED:AUD-0066-probe2 n_live_down drift "
            f"artifact={ah.get('n_live_down')} live={health['n_live_down']}"
        )
        return 1
    if ah.get("wrong_port_failed") is not True:
        print("FAILED:AUD-0066-probe2 artifact missing wrong-port failure")
        return 1
    if ah.get("scratch_good_passed") is not True:
        print("FAILED:AUD-0066-probe2 artifact missing scratch good-state pass")
        return 1
    if ah.get("control_pass") is not True:
        print("FAILED:AUD-0066-probe2 artifact control_pass is not true")
        return 1
    tests = doc.get("tests") or []
    ctrl_ok = any(
        isinstance(t, dict)
        and t.get("id") == "wrong-port-control"
        and str(t.get("result") or "").upper() == "PASS"
        for t in tests
    )
    if not ctrl_ok:
        print("FAILED:AUD-0066-probe2 artifact missing passing wrong-port-control test")
        return 1
    print("SUCCESS:AUD-0066-probe2 endpoint health + wrong-port control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
