#!/usr/bin/env python3
"""Probe 1: family coverage, executable schedules, both-states, negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import composition as C  # noqa: E402

NOTE = C.REPO / "command-center/design/council/CNL-0046-executable-runtime-semantics-for-the-7-meta-composition-pr.md"


def main() -> int:
    C.dump_fixtures()
    catalog = C.catalog_named_members()
    catalog_ids = [pid for pid, _ in catalog]
    print(f"catalog_n={len(catalog)} catalog_ids={catalog_ids}")
    if len(catalog) != C.EXPECTED_N or catalog_ids != list(C.NAMED_IDS):
        print("FAILED:CNL-0046-probe1 catalog named list mismatch")
        return 1

    fam = C.family_records()
    print(f"fixture_n={len(fam)} fixture_ids={[r['id'] for r in fam]}")
    if len(fam) != C.EXPECTED_N:
        print("FAILED:CNL-0046-probe1 fixture family count")
        return 1

    verdicts = [C.protocol_verdict(r) for r in fam]
    for v in verdicts:
        print(
            f"record {v['id']} verdict={v['verdict']} missing={v['missing_element']}"
        )
        if v["verdict"] != "EXECUTABLE":
            print("FAILED:CNL-0046-probe1 record not executable")
            return 1
    if len(verdicts) != C.EXPECTED_N:
        print("FAILED:CNL-0046-probe1 verdict count")
        return 1

    states = C.both_states()
    print(f"known_good_fires={states['known_good']['fires']} verbatim={states['known_good']['verbatim']}")
    print(
        "planted_bad_count_fires="
        f"{states['planted_bad_count']['fires']} verbatim={states['planted_bad_count']['verbatim']}"
    )
    print(
        "planted_bad_schedule_fires="
        f"{states['planted_bad_schedule']['fires']} verbatim={states['planted_bad_schedule']['verbatim']}"
    )
    print(
        "planted_bad_conflict_fires="
        f"{states['planted_bad_conflict']['fires']} verbatim={states['planted_bad_conflict']['verbatim']}"
    )
    if not states["silent_on_good"]:
        print("FAILED:CNL-0046-probe1 known-good was not silent")
        return 1
    if not (
        states["fires_on_bad_count"]
        and states["fires_on_bad_schedule"]
        and states["fires_on_bad_conflict"]
    ):
        print("FAILED:CNL-0046-probe1 planted-bad did not fire")
        return 1

    # Negative control: the reject-state is a 6-member family (P56 omitted).
    # The check must FIRE FAMILY_COUNT, not silently accept.
    neg = states["planted_bad_count"]
    codes = {f.get("code") for f in neg["findings"]}
    print(f"negative_control_codes={sorted(codes)}")
    if "FAMILY_COUNT" not in codes:
        print("FAILED:CNL-0046-probe1 negative control did not fire FAMILY_COUNT")
        return 1

    if not NOTE.is_file():
        print("FAILED:CNL-0046-probe1 design note missing")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    if note.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0046-probe1 self-declared {note.get('state')}")
        return 1
    if "SUCCESS:CNL-0046" not in NOTE.read_text(encoding="utf-8"):
        print("FAILED:CNL-0046-probe1 sentinel absent")
        return 1
    recs = note.get("records") or []
    if len(recs) != C.EXPECTED_N:
        print(f"FAILED:CNL-0046-probe1 note record count {len(recs)}")
        return 1
    note_ids = [r.get("id") for r in recs]
    if note_ids != list(C.NAMED_IDS):
        print(f"FAILED:CNL-0046-probe1 note ids {note_ids}")
        return 1
    for r in recs:
        if r.get("verdict") != "EXECUTABLE":
            print(f"FAILED:CNL-0046-probe1 note verdict {r.get('id')} {r.get('verdict')}")
            return 1
    bs = note.get("both_states") or {}
    if bs.get("silent_on_good") is not True or bs.get("fires_on_bad_count") is not True:
        print("FAILED:CNL-0046-probe1 note both_states incomplete")
        return 1
    print("SUCCESS:CNL-0046-probe1 family schedules both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
