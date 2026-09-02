#!/usr/bin/env python3
"""Probe 1: three-route byte table, LF-norm control, known-CRLF blob, classic 3837/3737."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import OUT_REL, measure  # noqa: E402
from scenario import CONTROL, KNOWN_CRLF, REVIEWER, UNIT  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    live = measure()
    tests = live["tests_required"]
    control = live["three_route_table"][0]
    reviewer = live["three_route_table"][1]
    classic = live["classic_3837_3737_control"]
    broken = live["known_broken_crlf_blob"]

    if control["path"] != CONTROL or reviewer["path"] != REVIEWER:
        print("FAILED:CNF-0149-probe1 unexpected paths", control["path"], reviewer["path"])
        return 1
    if not control["cat_file_equals_show"] or not reviewer["cat_file_equals_show"]:
        print("FAILED:CNF-0149-probe1 cat-file != show")
        return 1
    if not tests["lf_normalisation_control"]:
        print("FAILED:CNF-0149-probe1 LF-normalisation control")
        return 1
    if not tests["archive_differs_from_blob_on_eol_crlf_file"]:
        print("FAILED:CNF-0149-probe1 archive equals blob; archive is not converting")
        print(json.dumps(control["routes"], indent=2))
        return 1
    if not control["eol_is_sole_variable"] or not reviewer["eol_is_sole_variable"]:
        print("FAILED:CNF-0149-probe1 routes differ by more than EOL")
        return 1
    if not tests["known_broken_crlf_detected_by_blob_route"]:
        print("FAILED:CNF-0149-probe1 CRLF blob not seen by cat-file", broken)
        return 1
    if broken["path"] != KNOWN_CRLF:
        print("FAILED:CNF-0149-probe1 known-broken path", broken["path"])
        return 1
    if not classic["reproduced"]:
        print("FAILED:CNF-0149-probe1 classic 3837/3737 not reproduced", classic)
        return 1
    if live["blob_source_policy"]["forbidden"] != "git archive | tar -x":
        print("FAILED:CNF-0149-probe1 missing archive forbid")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0149-probe1 receipt missing", ART)
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if f"SUCCESS:{UNIT}" not in json.dumps(doc):
        print("FAILED:CNF-0149-probe1 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0149-probe1 receipt self-declared", doc.get("state"))
        return 1
    live_arch = control["routes"]["git archive | tar -x"]
    rec_arch = doc["three_route_table"][0]["routes"]["git archive | tar -x"]
    if live_arch["bytes"] != rec_arch["bytes"] or live_arch["crlf"] != rec_arch["crlf"]:
        print("FAILED:CNF-0149-probe1 receipt stale vs live three-route")
        return 1

    print(json.dumps(
        {
            "probe": "probe1-three-route",
            "unit_id": UNIT,
            "archive_bytes": live_arch["bytes"],
            "archive_crlf": live_arch["crlf"],
            "cat_file_bytes": control["routes"]["git cat-file -p"]["bytes"],
            "cat_file_crlf": control["routes"]["git cat-file -p"]["crlf"],
            "classic_reproduced": classic["reproduced"],
            "known_crlf_detected": broken["detected"],
            "second_file": REVIEWER,
            "pass": True,
        },
        sort_keys=True,
    ))
    print(
        f"SUCCESS:{UNIT}-probe1 three-route archive≠blob, LF-norm identity, "
        f"classic {classic['archive_bytes']}/{classic['cat_file_bytes']}, "
        "known-CRLF blob detected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
