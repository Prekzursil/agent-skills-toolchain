#!/usr/bin/env python3
"""Probe 1: static IR census (signal A) both-states.

A planted two-scheduler fusion and a two-store fusion must fire. A
singular fusion and a benign parallel helper must be silent. Signal A
does not read runtime_script, so a fusion that declares one scheduler
and spawns two is silent on A (probe 2 catches it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0109-fusion-control-plane-detector.json"
FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    two = D.static_census(load("two-scheduler.json"))
    singular = D.static_census(load("singular.json"))
    helper = D.static_census(load("helper-parallel.json"))
    stores = D.static_census(load("two-state-stores.json"))
    ghost = D.static_census(load("declare-one-spawn-two.json"))
    two_cap = D.capability_superset_ok(load("two-scheduler.json"))

    print(f"two-scheduler A fires={two['fires']} named={two['named_planes']}")
    print(
        f"singular A silent={singular['silent']} n_sched={singular['n_schedulers']}"
    )
    print(
        f"helper-parallel A silent={helper['silent']} "
        f"n_sched={helper['n_schedulers']} n_store={helper['n_state_stores']}"
    )
    print(
        f"two-state-stores A fires={stores['fires']} "
        f"consistent={stores['stores_consistent']} stores={stores['state_stores']}"
    )
    print(
        f"declare-one-spawn-two A silent={ghost['silent']} "
        f"(static cannot see spawned second scheduler)"
    )
    print(f"capability-superset on two-scheduler ok={two_cap['ok']} missing={two_cap['missing']}")

    checks = [
        (
            two["fires"]
            and "sched-primary" in two["schedulers"]
            and "sched-imported" in two["schedulers"]
            and two["n_schedulers"] == 2
            and two["n_execution_order_owners"] == 2,
            "two-scheduler not caught by static census",
        ),
        (singular["silent"] and singular["n_schedulers"] == 1, "singular not silent"),
        (
            helper["silent"]
            and helper["n_schedulers"] == 1
            and helper["n_state_stores"] == 1
            and helper["n_execution_order_owners"] == 1,
            "helper misclassified as control plane",
        ),
        (
            stores["fires"]
            and stores["n_state_stores"] == 2
            and stores["stores_consistent"] is True
            and "store-alpha" in stores["state_stores"]
            and "store-beta" in stores["state_stores"],
            "two consistent stores not failed",
        ),
        (
            ghost["silent"] and ghost["n_schedulers"] == 1,
            "static leaked runtime spawn (signals not independent)",
        ),
        (
            two_cap["ok"] is True,
            "capability check must pass on two-scheduler (blindness)",
        ),
    ]
    for ok, why in checks:
        if not ok:
            print(f"FAILED:WFA-0109-probe1 {why}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0109-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0109-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0109" not in text:
        print("FAILED:WFA-0109-probe1 sentinel absent")
        return 1
    cases = {c.get("fusion_id"): c for c in (doc.get("cases") or []) if isinstance(c, dict)}
    planted = cases.get("fx-two-scheduler") or {}
    if not planted.get("signal_a_fires"):
        print("FAILED:WFA-0109-probe1 artifact did not record two-scheduler A fire")
        return 1
    good = cases.get("fx-singular") or {}
    if good.get("signal_a_fires"):
        print("FAILED:WFA-0109-probe1 artifact recorded singular as fire")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-static-both-states",
                "two_scheduler": two,
                "singular": {"silent": singular["silent"]},
                "helper": {"silent": helper["silent"]},
                "two_stores": {
                    "fires": stores["fires"],
                    "consistent": stores["stores_consistent"],
                },
                "ghost_declared_one": {"silent": ghost["silent"]},
                "capability_blind": two_cap,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0109-probe1 static both-states helper-vs-plane two-stores")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
