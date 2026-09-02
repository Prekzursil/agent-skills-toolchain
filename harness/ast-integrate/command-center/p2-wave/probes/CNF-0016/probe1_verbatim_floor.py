#!/usr/bin/env python3
"""Probe 1: re-run every P0 recipe verbatim; no blank rows; floor is a PASS."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as C  # noqa: E402
import corpus as K  # noqa: E402
import recipe as R  # noqa: E402

UID = "CNF-0016"


def main() -> int:
    try:
        doc = C.load_artifact()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:CNF-0016-probe1 artifact {type(exc).__name__}: {exc}")
        return 1

    if doc.get("unit_id") != UID:
        print("FAILED:CNF-0016-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in C.validator().schema["properties"]["state"]["enum"] and str(
        doc.get("state")
    ).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0016-probe1 self-declared", doc.get("state"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0016" not in blob:
        print("FAILED:CNF-0016-probe1 sentinel absent")
        return 1

    briefs = [K.strip_brief(d) for d in K.p0_records()]
    live = {row["id"]: row for row in R.measure_all(briefs)}
    art = {row["id"]: row for row in (doc.get("defects") or [])}

    if set(live) != set(art):
        print("FAILED:CNF-0016-probe1 id set mismatch", sorted(live), sorted(art))
        return 1

    ok_blank, why_blank = C.no_blank_rows(list(live.values()))
    print(why_blank)
    if not ok_blank:
        print("FAILED:CNF-0016-probe1", why_blank)
        return 1

    verbatim_pass = 0
    for ident, row in live.items():
        other = art[ident]
        if row["verdict"] != other.get("verdict"):
            print(f"FAILED:CNF-0016-probe1 {ident} live={row['verdict']} art={other.get('verdict')}")
            return 1
        if row["verdict"] == "PASS":
            if row.get("verbatim") is not True:
                print(f"FAILED:CNF-0016-probe1 {ident} not verbatim")
                return 1
            if row.get("improvised") is True:
                print(f"FAILED:CNF-0016-probe1 {ident} improvised")
                return 1
            if not row.get("commands"):
                print(f"FAILED:CNF-0016-probe1 {ident} PASS without commands")
                return 1
            verbatim_pass += 1
        else:
            if not str(row.get("missing_step") or "").strip():
                print(f"FAILED:CNF-0016-probe1 {ident} unnamed missing step")
                return 1
            if str(row.get("missing_step")) != str(other.get("missing_step")):
                print(
                    f"FAILED:CNF-0016-probe1 {ident} missing_step drift "
                    f"live={row.get('missing_step')!r} art={other.get('missing_step')!r}"
                )
                return 1

    if verbatim_pass < 1:
        print("FAILED:CNF-0016-probe1 no verbatim PASS; floor not established")
        return 1

    ok_suf, why_suf = C.sufficiency_matches(doc)
    print(why_suf)
    if not ok_suf:
        print("FAILED:CNF-0016-probe1", why_suf)
        return 1
    live_suf = C.sufficiency_from_rows(list(live.values()))
    if live_suf["pass_count"] != doc["sufficiency"]["pass_count"]:
        print("FAILED:CNF-0016-probe1 live pass_count drifted")
        return 1

    print(
        f"verbatim_pass={verbatim_pass} attempted={len(live)} "
        f"rate={live_suf['pass_count']}/{live_suf['attempted']}"
    )
    print("SUCCESS:CNF-0016-probe1 verbatim-floor no-blank-rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
