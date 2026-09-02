#!/usr/bin/env python3
"""Probe 1: known-present found AND known-absent empty.

A scout that answers both the same way measures nothing. Live must
discriminate; always-empty and always-same mutants must fail that test.
Recall is checked as found/planted with a named miss list, never a bare %.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recall as R  # noqa: E402
import scout as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0145-scout-anti-rebuild-recall-control-with-a-planted-kno.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0145-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0145" not in text:
        return fail("sentinel-absent")

    live = R.measure(mode="live")
    empty = R.measure(mode="always-empty")
    same = R.measure(mode="always-same")

    if live["planted"] < 4:
        return fail(f"too-few-plants planted={live['planted']}")
    if not live["pass"]:
        return fail(
            f"live-not-pass fraction={live['recall_fraction']} "
            f"misses={live['miss_list']} absent_nonempty={live['known_absent_nonempty']} "
            f"build={live['build_when_superior_present']}"
        )
    if live["recall_fraction"] != f"{live['found']}/{live['planted']}":
        return fail("fraction-not-found-over-planted")
    if "miss_list" not in live or live["miss_list"] is None:
        return fail("miss-list-absent")
    if live["miss_list"]:
        return fail(f"named-misses {live['miss_list']}")
    if not live["known_absent_all_empty"]:
        return fail("known-absent-not-empty")
    if empty["found"] != 0 or empty["pass"]:
        return fail("always-empty-mutant-did-not-fail-present")
    if same["known_absent_all_empty"] or same["pass"]:
        return fail("always-same-mutant-did-not-fail-absent")
    if live["discriminates_present_absent"] is not True:
        return fail("live-does-not-discriminate")
    if empty["discriminates_present_absent"] or same["discriminates_present_absent"]:
        return fail("mutant-still-discriminates")

    claimed = doc.get("recall") or {}
    if claimed.get("recall_fraction") != live["recall_fraction"]:
        return fail(
            f"artifact-fraction-mismatch claimed={claimed.get('recall_fraction')} "
            f"live={live['recall_fraction']}"
        )
    if claimed.get("found") != live["found"] or claimed.get("planted") != live["planted"]:
        return fail("artifact-found-planted-mismatch")
    if "miss_list" not in claimed:
        return fail("artifact-missing-miss-list")
    if claimed.get("miss_list") != []:
        return fail(f"artifact-miss-list-nonempty {claimed.get('miss_list')}")
    if claimed.get("known_absent_all_empty") is not True:
        return fail("artifact-absent-not-empty")

    wfs = S.load_workflows()
    ids = {w["id"] for w in wfs}
    for row in live["known_present"]:
        if row["workflow_id"] not in ids:
            return fail(f"plant-file-unreadable {row['workflow_id']}")
        if row["recommendation"] == "BUILD":
            return fail(f"build-on-present {row['plant_id']}")

    print(
        json.dumps(
            {
                "probe": "probe1-known-present-absent",
                "unit_id": "WFA-0145",
                "recall_fraction": live["recall_fraction"],
                "miss_list": live["miss_list"],
                "known_absent_all_empty": live["known_absent_all_empty"],
                "always_empty_found": empty["found"],
                "always_same_absent_empty": same["known_absent_all_empty"],
                "discriminates": live["discriminates_present_absent"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"recall {live['recall_fraction']} misses={len(live['miss_list'])} "
        f"absent_empty={live['known_absent_all_empty']} "
        f"mutants empty_found={empty['found']} same_absent_empty={same['known_absent_all_empty']}"
    )
    print("SUCCESS:WFA-0145-probe1 known-present found, known-absent empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
