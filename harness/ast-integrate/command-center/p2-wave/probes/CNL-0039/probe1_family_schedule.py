#!/usr/bin/env python3
"""Probe 1: independent family recount + per-record schedule coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402

REPO = HERE.parents[3]
OUT_REL = (
    "command-center/design/council/"
    "CNL-0039-executable-runtime-semantics-for-the-7-adversarial-protoco.md"
)


def main() -> int:
    unit = F.catalog_unit()
    fixture = F.load_fixture()
    from_fix = F.ids_from_fixture(fixture)
    from_q = F.ids_from_catalog_question(unit)
    expected_n = F.expected_n_from_evidence(unit)
    slugs = F.slugs_from_catalog_question(unit)
    proto_n = len(fixture.get("protocols") or [])

    if proto_n != 58:
        print(f"FAILED:CNL-0039-probe1 fixture protocol count {proto_n} != 58")
        return 1
    if len(from_fix) != expected_n:
        print(
            f"FAILED:CNL-0039-probe1 fixture family count {len(from_fix)} "
            f"!= expected n={expected_n}"
        )
        return 1
    if from_fix != from_q:
        print(f"FAILED:CNL-0039-probe1 fixture ids {from_fix} != catalog {from_q}")
        return 1
    if from_fix != ["P07", "P08", "P09", "P10", "P11", "P12", "P13"]:
        print(f"FAILED:CNL-0039-probe1 unexpected id set {from_fix}")
        return 1

    note_path = REPO / OUT_REL
    if not note_path.is_file():
        print("FAILED:CNL-0039-probe1 design note absent")
        return 1
    note = json.loads(note_path.read_text(encoding="utf-8"))
    recs = note.get("records") or []
    note_ids = [str(r.get("id")) for r in recs if isinstance(r, dict)]
    if note_ids != from_fix:
        print(f"FAILED:CNL-0039-probe1 note ids {note_ids} != fixture {from_fix}")
        return 1
    if int(note.get("family_count") or -1) != expected_n:
        print("FAILED:CNL-0039-probe1 note family_count disagrees")
        return 1

    missing = []
    for row in F.adversarial_from_fixture(fixture):
        pid = str(row["id"])
        v = R.verdict_for(pid)
        if v["verdict"] != "EXECUTABLE":
            missing.append((pid, v))
            continue
        note_row = next(r for r in recs if r.get("id") == pid)
        if note_row.get("verdict") != "EXECUTABLE":
            print(f"FAILED:CNL-0039-probe1 {pid} note verdict {note_row.get('verdict')}")
            return 1
        if note_row.get("turn_schedule") != v["turn_schedule"]:
            print(f"FAILED:CNL-0039-probe1 {pid} schedule drift")
            return 1
        if note_row.get("slug") != slugs.get(pid) or note_row.get("slug") != row.get("slug"):
            print(f"FAILED:CNL-0039-probe1 {pid} slug mismatch")
            return 1
        if str(note_row.get("unfakeable_artifact", {}).get("kind")) != v["artifact_kind"]:
            print(f"FAILED:CNL-0039-probe1 {pid} artifact kind drift")
            return 1
    if missing:
        print(f"FAILED:CNL-0039-probe1 missing schedules {missing}")
        return 1

    lib = F.library_on_disk()
    lib_note = "absent"
    if lib is not None:
        lib_note = str(lib.relative_to(REPO)) if str(lib).startswith(str(REPO)) else str(lib)
        print(f"FAILED:CNL-0039-probe1 unexpected on-tree library {lib_note}")
        return 1

    print(
        f"fixture_n={len(from_fix)} catalog_n={len(from_q)} expected_n={expected_n} "
        f"protocols_in_fixture={proto_n} library={lib_note}"
    )
    print("ids=" + ",".join(from_fix))
    print("schedules=7/7 EXECUTABLE")
    print("SUCCESS:CNL-0039-probe1 independent family recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
