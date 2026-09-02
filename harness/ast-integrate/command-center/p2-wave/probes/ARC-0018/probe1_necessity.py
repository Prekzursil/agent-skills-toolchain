#!/usr/bin/env python3
"""Probe 1: necessity test for every dead-weight classification.

Live walker (not the COST.json labels): for each named marketplace item,
remove it and record which of install/update/rollback/uninstall fail.
Dead-weight stands only when that list is empty. The four ops are then
walked through the lifecycle-core subset and must all succeed.

Negative control: removing lockfile_pin must break rollback, or the walker
cannot discriminate absence and dead-weight labels would be vacuous.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lifecycle import LIFECYCLE_CORE, NAMED_MARKETPLACE, broken_ops_if_absent, walk_four  # noqa: E402
from score import classify, compute  # noqa: E402

ART = REPO / "command-center/phase3/A3/COST.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0018-probe1 {msg}")
    return 1


def main() -> int:
    live = compute()
    named = {r["id"]: r for r in live["named"]}
    if set(named) != set(NAMED_MARKETPLACE):
        return fail(f"named mismatch {sorted(named)}")

    dead = []
    for item in NAMED_MARKETPLACE:
        broken = broken_ops_if_absent(item)
        klass = classify(item, broken)
        rec = named[item]
        if rec["broken_ops_if_absent"] != broken:
            return fail(f"{item} stored broken {rec['broken_ops_if_absent']} live {broken}")
        if rec["classification"] != klass:
            return fail(f"{item} stored {rec['classification']} live {klass}")
        if klass == "dead-weight":
            if broken:
                return fail(f"{item} classified dead-weight but breaks {broken}")
            dead.append(item)
            print(f"necessity {item} dead-weight operation=none")
        elif klass == "deferrable":
            if broken:
                return fail(f"{item} classified deferrable but breaks {broken}")
            print(f"necessity {item} deferrable operation=none")
        else:
            if not broken:
                return fail(f"{item} classified required but no op breaks")
            print(f"necessity {item} required operation={broken[0]}")

    pin_broken = broken_ops_if_absent("lockfile_pin")
    if "rollback" not in pin_broken:
        return fail(f"negative control lockfile_pin did not break rollback: {pin_broken}")
    print(f"negative_control lockfile_pin breaks={pin_broken}")

    walk = walk_four(set(LIFECYCLE_CORE))
    blocked = [r["op"] for r in walk if not r["ok"]]
    if blocked:
        return fail(f"minimal subset blocked {blocked}")
    if not walk[-1].get("owner_data_preserved"):
        return fail("uninstall dropped owner data")
    print(
        "walk_minimal "
        + ",".join(f"{r['op']}={'ok' if r['ok'] else r['reason']}" for r in walk)
    )

    if not ART.is_file():
        return fail("COST.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0018" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    hl = doc.get("headline") or {}
    live_n = live["headline"]["dead_weight_count"]
    art_n = hl.get("dead_weight_count")
    if art_n != live_n:
        return fail(f"headline dead_weight_count artifact={art_n} live={live_n}")
    if live_n != len(dead):
        return fail(f"live headline {live_n} != necessity dead {len(dead)}")
    by_id = {r["id"]: r for r in doc.get("machinery") or [] if r.get("group") == "marketplace"}
    for item, rec in named.items():
        row = by_id.get(item)
        if not row:
            return fail(f"COST.json missing machinery {item}")
        if row.get("classification") != rec["classification"]:
            return fail(f"{item} COST classification {row.get('classification')}")
        if row.get("classification") == "dead-weight" and row.get("necessity_operation"):
            return fail(f"{item} dead-weight still names an operation")

    payload = {
        "pass": True,
        "probe": "probe1-necessity",
        "unit_id": "ARC-0018",
        "dead_weight_count": live_n,
        "dead_weight_ids": dead,
        "minimal_blocked": blocked,
        "lockfile_pin_breaks": pin_broken,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:ARC-0018-probe1 necessity test and minimal-subset walk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
