#!/usr/bin/env python3
"""Probe 1: registry + trademark-database search of each proposed listing name.

Mechanically: live HTTP to npm / PyPI / crates.io plus USPTO TMsearch and
WIPO Brand Database, joined to the local mark table (Nice 9/42).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from detector import CONTROL_CLEAN, CONTROL_INFRINGING, classify_name, control_pair  # noqa: E402
from inventory import names_to_search  # noqa: E402
from registries import search_name, search_trademark_databases, utc_now  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0052-probe1 {msg}")
    return 1


def main() -> int:
    search_date = utc_now()
    names = names_to_search()
    if "agent-skills-toolchain" not in names:
        return fail("inventory missing primary listing name")
    rows = []
    for name in names + [CONTROL_INFRINGING, CONTROL_CLEAN]:
        live = search_name(name)
        tm = search_trademark_databases(name)
        identity = classify_name(name)
        flagged = bool(live["exact_collisions"] or identity["flagged"])
        rows.append(
            {
                "name": name,
                "search_date": search_date,
                "identity": identity,
                "exact_collisions": live["exact_collisions"],
                "trademark_databases": tm,
                "trademark_classes_from_marks": [
                    {"mark_id": m["id"], "nice_classes": m["nice_classes"], "owner": m["owner"]}
                    for m in identity["marks"]
                ],
                "flagged": flagged,
                "registry_raw": {
                    "npm_status": live["npm"].get("status"),
                    "pypi_status": live["pypi"].get("status"),
                    "crates_status": live["crates"].get("status"),
                    "npm_sha256": live["npm"].get("sha256"),
                    "pypi_sha256": live["pypi"].get("sha256"),
                    "crates_sha256": live["crates"].get("sha256"),
                },
            }
        )

    controls = control_pair()
    inf = next(r for r in rows if r["name"] == CONTROL_INFRINGING)
    clean = next(r for r in rows if r["name"] == CONTROL_CLEAN)
    if not inf["flagged"]:
        return fail("infringing control name was not flagged")
    if clean["flagged"]:
        return fail("clean control name was flagged")
    if not controls["calibrated"]:
        return fail("identity classifier is not calibrated")

    # Primary listing uses Agent Skills as 'X Toolchain'.
    primary = next(r for r in rows if r["name"] == "agent-skills-toolchain")
    if not primary["identity"]["flagged"]:
        return fail("primary listing name evaded the Agent Skills Toolchain rule")

    out = {
        "pass": True,
        "probe": "probe1-registry-trademark-search",
        "unit_id": "ADV-0052",
        "search_date": search_date,
        "names_searched": names,
        "rows": rows,
        "control": {
            "infringing": CONTROL_INFRINGING,
            "clean": CONTROL_CLEAN,
            "infringing_flagged": inf["flagged"],
            "clean_flagged": clean["flagged"],
            "infringing_collisions": inf["exact_collisions"],
            "clean_collisions": clean["exact_collisions"],
            "search_date": search_date,
        },
        "classifier_calibration": controls["calibrated"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"search_date={search_date} names={len(names)} "
        f"infringing_flagged={inf['flagged']} clean_flagged={clean['flagged']} "
        f"primary_flagged={primary['flagged']}"
    )
    print("SUCCESS:ADV-0052-probe1 registry and trademark search")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
