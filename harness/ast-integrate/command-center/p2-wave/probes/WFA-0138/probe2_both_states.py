#!/usr/bin/env python3
"""Probe 2: both-states drop-one-source then restore.

Drop one source from a fusion body and require the round trip to fail with
that exact source named. Restore it and require the trip to pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import lineage as L  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0138-fusion-lineage-record-and-the-decomposition-round-tr.json"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0138-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0138-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0138" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0138-probe2 sentinel absent")
        return 1

    loaded = C.load_corpus(REPO)
    subject = C.first_fully_resolved(loaded["merge_units"])
    live = L.both_states_drop_restore(subject)
    recorded = doc.get("both_states") or {}

    print(
        f"drop source={live['dropped_source']} "
        f"missing={live['drop_missing']} extra={live['drop_extra']} "
        f"names_exact={live['drop_names_exact_source']} "
        f"drop_ok={live['drop_round_trip_ok']}"
    )
    print(
        f"restore recovered={live['restore_recovered']} "
        f"ok={live['restore_round_trip_ok']}"
    )

    if live["drop_round_trip_ok"]:
        print("FAILED:WFA-0138-probe2 drop still round-tripped")
        return 1
    if not live["drop_names_exact_source"]:
        print(
            f"FAILED:WFA-0138-probe2 drop did not name {live['dropped_source']} "
            f"in missing={live['drop_missing']}"
        )
        return 1
    if live["drop_extra"]:
        print(f"FAILED:WFA-0138-probe2 drop extra={live['drop_extra']}")
        return 1
    if live["dropped_source"] not in live["drop_missing"]:
        print("FAILED:WFA-0138-probe2 dropped source absent from missing")
        return 1
    if not live["restore_round_trip_ok"]:
        print("FAILED:WFA-0138-probe2 restore did not pass")
        return 1

    if recorded.get("dropped_source") != live["dropped_source"]:
        print("FAILED:WFA-0138-probe2 artifact dropped_source drift")
        return 1
    if recorded.get("drop_missing") != live["drop_missing"]:
        print("FAILED:WFA-0138-probe2 artifact drop_missing drift")
        return 1
    if not recorded.get("restore_round_trip_ok"):
        print("FAILED:WFA-0138-probe2 artifact restore not ok")
        return 1

    print(
        "NEGATIVE-CONTROL: dropping "
        f"{live['dropped_source']} from fusion {live['merge_unit_id']} "
        f"makes decompose miss exactly that id (missing={live['drop_missing']}); "
        "restoring the component makes declared==recovered."
    )
    out = {
        "probe": "probe2-both-states",
        "unit_id": "WFA-0138",
        "dropped_source": live["dropped_source"],
        "drop_missing": live["drop_missing"],
        "restore_ok": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0138-probe2 drop-one-source named; restore passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
