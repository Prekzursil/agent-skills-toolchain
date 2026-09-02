#!/usr/bin/env python3
"""Probe 2: detector control for use-versus-mention.

Known-broken fixture: substring_classify treats any found span as USE.
The role classifier must still return MENTION for the quoted-example control
and for the defect-description trap. A wrapper-disabled mutant must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from auditor import (  # noqa: E402
    DEFECT_TRAP_ID,
    MENTION_CONTROL_ID,
    artifact_payload,
    audit_all,
)
from role import classify_role, read_lf, substring_classify  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0071-transcript-claims.json"


def main() -> int:
    rows = audit_all()
    by_id = {r["id"]: r for r in rows}
    mention = by_id[MENTION_CONTROL_ID]
    trap = by_id[DEFECT_TRAP_ID]

    # Known-broken: substring presence => USE (fires on the quoted example).
    broken_mention = substring_classify(
        read_lf(REPO / mention["source"]["locator"]),
        mention["source"]["quoted_span"],
    )
    broken_trap = substring_classify(
        read_lf(REPO / trap["source"]["locator"]),
        trap["source"]["quoted_span"],
    )
    fired = broken_mention == "USE" and broken_trap == "USE"
    print(
        json.dumps(
            {
                "probe": "probe2-mention-control",
                "broken_mention": broken_mention,
                "broken_trap": broken_trap,
                "role_mention": mention["role"],
                "role_trap": trap["role"],
                "mutant_mention": mention["wrapper_ignored_mutant_role"],
                "detector_control_fired": fired,
            },
            sort_keys=True,
        )
    )
    if not fired:
        print("FAILED:CNF-0071-probe2 known-broken substring matcher did not fire USE")
        return 1
    if mention["role"] != "MENTION":
        print(f"FAILED:CNF-0071-probe2 mention-only classified {mention['role']}")
        return 1
    if trap["role"] != "MENTION":
        print(f"FAILED:CNF-0071-probe2 defect-trap classified {trap['role']}")
        return 1
    if mention["wrapper_ignored_mutant_role"] != "USE":
        print("FAILED:CNF-0071-probe2 wrapper-ignored mutant did not go red")
        return 1
    if trap["wrapper_ignored_mutant_role"] != "USE":
        print("FAILED:CNF-0071-probe2 defect-trap mutant did not go red")
        return 1

    # Both-states on the live files: good (role) vs bad (ignore wrappers).
    text_m = read_lf(REPO / mention["source"]["locator"])
    s, e = mention["char_start"], mention["char_end"]
    good = classify_role(text_m, s, e)
    bad = classify_role(text_m, s, e, ignore_wrappers=True)
    if good == bad:
        print("FAILED:CNF-0071-probe2 both-states silent: good==bad")
        return 1
    if good != "MENTION" or bad != "USE":
        print(f"FAILED:CNF-0071-probe2 both-states good={good} bad={bad}")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0071-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = artifact_payload(doc)
    moc = body.get("mention_only_control") or {}
    if moc.get("classified_as") != "MENTION" or moc.get("pass") is not True:
        print("FAILED:CNF-0071-probe2 artifact mention_only_control failed")
        return 1
    trap_art = body.get("defect_description_trap") or {}
    if trap_art.get("role") != "MENTION" or trap_art.get("pass") is not True:
        print("FAILED:CNF-0071-probe2 artifact defect trap failed")
        return 1
    rev = doc.get("reviewer") or {}
    fired = rev.get("detector_control_fired")
    if fired is not True:
        fired = body.get("detector_control_fired")
    if fired is not True:
        notes = str(rev.get("notes") or "")
        fired = "detector_control_fired=true" in notes
    if fired is not True:
        print("FAILED:CNF-0071-probe2 reviewer did not record detector control")
        return 1
    print("SUCCESS:CNF-0071-probe2 detector control fired on known-broken fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
