#!/usr/bin/env python3
"""Probe 1: known-compatible pair co-executes cleanly; known-conflicting pair collides."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confirm as C  # noqa: E402
from session import co_execute_both_orders  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"


def main() -> int:
    bps = C.load_blueprints()
    cmap = C.load_map()
    bundle = C.run_all()
    nc = bundle["negative_control"]
    pos = bundle["positive_control"]
    live_pos = co_execute_both_orders(bps["BP-D01"], bps["BP-D02"])

    errors: list[str] = []
    if nc["verdict"] != "CLEAN":
        errors.append(f"compatible pair collided: {nc}")
    if pos["verdict"] != "CONFIRMED":
        errors.append(f"CF-01 not CONFIRMED: {pos}")
    if "session/ledger.json" not in live_pos["shared_files"]:
        errors.append("known-conflicting pair did not share session/ledger.json")
    if live_pos["shared_files"] == nc["live"]["shared_files"]:
        errors.append("harness did not distinguish compatible vs conflicting")

    doc = {
        "probe": "probe1-both-states",
        "unit_id": "WFA-0150",
        "compatible": nc,
        "conflicting": {
            "id": pos["id"],
            "verdict": pos["verdict"],
            "target": pos["target"],
            "shared_files": live_pos["shared_files"],
        },
        "distinguishes": pos["verdict"] == "CONFIRMED" and nc["verdict"] == "CLEAN",
        "map_rows": len(cmap["rows"]),
        "pass": not errors,
        "errors": errors,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"compatible={nc['verdict']} conflicting={pos['verdict']} "
        f"shared={live_pos['shared_files']} distinguishes={doc['distinguishes']}"
    )
    if errors:
        print("FAILED:WFA-0150-probe1 " + "; ".join(errors))
        return 1
    print(
        "SUCCESS:WFA-0150-probe1 known-compatible CLEAN; known-conflicting "
        "SHARED_FILE session/ledger.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
