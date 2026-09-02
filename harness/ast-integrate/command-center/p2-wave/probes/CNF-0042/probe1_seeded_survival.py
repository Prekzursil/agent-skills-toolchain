#!/usr/bin/env python3
"""Named probe 1: every seeded user item survives set-difference rollback.

Field: pre/post sha256 of user-owned files, custom commands and settings,
including the status.md name collision. Different field from probe 2
(presence/absence of the N-only shipped path, plus wholesale destruction).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import live_both_engines  # noqa: E402
from scenario import COLLISION_USER_REL, USER_ITEMS  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0042-rollback-user-data.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0042-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0042":
        print("FAILED:CNF-0042-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0042-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0042" not in json.dumps(doc):
        print("FAILED:CNF-0042-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0042-p1-") as tmp:
        sd, _wh = live_both_engines(Path(tmp) / "work")

    preservation = sd["preservation"]
    collision = sd["collision"]
    if not preservation["passed"]:
        print("FAILED:CNF-0042-probe1 seeded items not byte-identical")
        print(json.dumps(preservation, indent=2)[:3000])
        return 1
    if len(preservation["items"]) != len(USER_ITEMS):
        print("FAILED:CNF-0042-probe1 item count drift")
        return 1
    if not collision["passed"] or not collision["user_survived_byte_identical"]:
        print("FAILED:CNF-0042-probe1 name-collision did not survive")
        print(json.dumps(collision, indent=2))
        return 1

    recorded = doc.get("seeded_user_items") or []
    if len(recorded) != len(USER_ITEMS):
        print(f"FAILED:CNF-0042-probe1 artifact item count {len(recorded)}")
        return 1
    if not all(row.get("byte_identical") for row in recorded):
        print("FAILED:CNF-0042-probe1 artifact lists a non-identical seeded item")
        return 1
    rec_collision = doc.get("collision_case") or {}
    if rec_collision.get("user_path") != COLLISION_USER_REL:
        print("FAILED:CNF-0042-probe1 artifact collision path drift")
        return 1
    if not rec_collision.get("user_survived_byte_identical"):
        print("FAILED:CNF-0042-probe1 artifact collision not survived")
        return 1

    out = {
        "probe": "probe1-seeded-survival",
        "unit_id": "CNF-0042",
        "seeded_items": len(preservation["items"]),
        "all_byte_identical": True,
        "collision_user_path": COLLISION_USER_REL,
        "collision_survived": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"seeded={len(preservation['items'])} identical=True "
        f"collision={COLLISION_USER_REL} survived=True"
    )
    print("SUCCESS:CNF-0042-probe1 seeded user items survived byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
