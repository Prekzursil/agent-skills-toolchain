#!/usr/bin/env python3
"""Probe 2: two-rail evidence and the NOASSERTION trap control.

Every salvage-register claim must carry two rails with permalink,
fetch timestamp, HTTP status, and sha256. A one-rail claim is E3 and
must not be cited as measured fact. The planted NOASSERTION label on
an MIT LICENSE file must fire the disagreement detector (negative
control: FIRES on the plant, reports the honest live count otherwise).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import salvage as S  # noqa: E402

ART = REPO / S.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
NEED = ("permalink", "fetch_timestamp", "http_status", "sha256")


def fail(msg: str) -> int:
    print(f"FAILED:RES-0109-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {type(exc).__name__}")
    if S.SENTINEL not in text:
        return fail("completion sentinel absent")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")

    live = S.build_register()
    control = S.planted_noassertion_control(live)
    art_control = doc.get("noassertion_trap_control") or {}
    if not control.get("pass"):
        return fail("live NOASSERTION control did not fire")
    if not art_control.get("pass") or not art_control.get("detector_fires"):
        return fail("artifact NOASSERTION control missing or silent")

    one_rail = [
        S.rail(
            kind="structured_api",
            permalink="https://example.invalid/one-rail",
            fetch_timestamp="2026-08-24T00:00:00Z",
            http_status=200,
            sha256="0" * 64,
            bytes_n=1,
            quote="single rail",
            path=None,
        )
    ]
    if S.grade_claim(one_rail) != "E3":
        return fail("one-rail fixture did not grade E3")

    checked = 0
    e3_cited = []
    for row in doc.get("salvage_register") or []:
        for cl in row.get("claims") or []:
            rails = cl.get("rails") or []
            if len(rails) < 2:
                return fail(f"{cl.get('id')} has {len(rails)} rails")
            for i, rail in enumerate(rails):
                for k in NEED:
                    if rail.get(k) in (None, ""):
                        return fail(f"{cl.get('id')} rail[{i}] missing {k}")
                cap = rail.get("capture_path")
                if cap:
                    raw = S.file_bytes(cap)
                    if not raw:
                        return fail(f"{cl.get('id')} capture missing {cap}")
                    live_sha = S.sha256_bytes(raw)
                    if rail.get("sha256") != live_sha:
                        return fail(f"{cl.get('id')} sha256 drift {cap}")
            grade = cl.get("grade")
            live_grade = S.grade_claim(rails)
            if grade != live_grade:
                return fail(f"{cl.get('id')} grade {grade} != live {live_grade}")
            if grade == "E3" and cl.get("cite_as_measured_fact"):
                e3_cited.append(cl.get("id"))
            checked += 1

    if e3_cited:
        return fail("E3 claims cited as measured fact: " + ",".join(e3_cited))
    if checked < 6:
        return fail(f"too few claims checked: {checked}")

    extract = [
        r
        for r in (doc.get("salvage_register") or [])
        if r.get("disposition") == "EXTRACT"
    ]
    if not extract:
        return fail("no EXTRACT row")
    for r in extract:
        for cl in r.get("claims") or []:
            if str(cl.get("id") or "").endswith("-license") and cl.get("grade") == "E3":
                return fail(f"{r.get('row_id')} EXTRACT license claim is E3")

    payload = {
        "probe": "probe2-two-rails",
        "unit_id": "RES-0109",
        "claims_checked": checked,
        "one_rail_grades_e3": True,
        "noassertion_control_fires": True,
        "e3_cited_as_fact": e3_cited,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "NEGATIVE CONTROL: relabelling an MIT LICENSE file as NOASSERTION "
        "must count as a label-versus-file disagreement. On that planted "
        f"state it FIRES (donor={control.get('donor_row')}). On the live "
        "register it reports the honest live count. A one-rail claim grades E3 "
        "and cannot be cited as measured fact."
    )
    print(
        f"claims_checked={checked} extract={','.join(r['row_id'] for r in extract)}"
    )
    print("SUCCESS:RES-0109-probe2 two-rail evidence and NOASSERTION control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
