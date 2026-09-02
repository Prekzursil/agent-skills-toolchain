#!/usr/bin/env python3
"""Named probe 2: UNTESTED is not AGREE; schema rejects garbage.

Mechanically different from probe 1 (classifier hole + schema, not
extraction/noexec). Re-derives the git-archive CONTRADICT from the
statement text without trusting probe 1's printout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    COMPLETION_SENTINEL,
    KNOWN_PRESENT_SNIPPET,
    OUT_REL,
    UNIT_ID,
    domain,
)
from statements import (  # noqa: E402
    classify_one,
    force_agree_without_test_id,
    validate_no_silent_agree,
)
import schema_local as S  # noqa: E402

ART = REPO / OUT_REL
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0020-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:SYN-0020-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:SYN-0020-probe2 self-declared", doc.get("state"))
        return 1
    if COMPLETION_SENTINEL not in text:
        print("FAILED:SYN-0020-probe2 sentinel absent")
        return 1

    for garbage in GARBAGE:
        if not S.iter_errors(garbage):
            print("FAILED:SYN-0020-probe2 schema accepted garbage")
            return 1
    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:SYN-0020-probe2 artifact schema-invalid", errs[0].message)
        return 1

    payload = domain(doc)
    rows = [
        s
        for s in (payload.get("behaviour_statements") or [])
        if isinstance(s, dict)
    ]
    silent = validate_no_silent_agree(rows)
    if silent:
        print("FAILED:SYN-0020-probe2 silent AGREE in artifact")
        print(json.dumps(silent[0], indent=2)[:1000])
        return 1

    untested = [
        s
        for s in rows
        if "signed wheel on Tuesdays" in str(s.get("text") or "")
    ]
    if not untested:
        print("FAILED:SYN-0020-probe2 planted untested statement missing")
        return 1
    if any(s.get("verdict") != "UNTESTED" for s in untested):
        print("FAILED:SYN-0020-probe2 planted statement not UNTESTED", untested)
        return 1
    if any(s.get("test_id") for s in untested):
        print("FAILED:SYN-0020-probe2 untested row carried a test id")
        return 1

    forced = force_agree_without_test_id(
        "The hello token command always prints SYN-0020-readme-ok."
    )
    if forced["verdict"] != "UNTESTED" or forced.get("test_id"):
        print("FAILED:SYN-0020-probe2 classifier allowed AGREE without test id")
        print(json.dumps(forced, indent=2))
        return 1

    derived = classify_one(
        "Verify formatting against the LF blob (git archive)."
    )
    if derived["verdict"] != "CONTRADICT":
        print("FAILED:SYN-0020-probe2 independent re-derive was not CONTRADICT")
        print(json.dumps(derived, indent=2))
        return 1
    if derived.get("test_id") != "known-present-git-archive-lf-blob":
        print("FAILED:SYN-0020-probe2 independent re-derive test_id drift")
        return 1
    if KNOWN_PRESENT_SNIPPET not in text:
        print("FAILED:SYN-0020-probe2 snippet absent from artifact")
        return 1

    art_ctrl = payload.get("untested_control") or {}
    if art_ctrl.get("pass") is not True:
        print("FAILED:SYN-0020-probe2 artifact untested_control.pass is not true")
        return 1
    if (payload.get("fingerprint") or {}).get("agree_without_test_id") != 0:
        print("FAILED:SYN-0020-probe2 fingerprint agree_without_test_id")
        return 1
    if (payload.get("known_present_control") or {}).get("fired") is not True:
        print("FAILED:SYN-0020-probe2 known_present_control.fired missing")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "conformance-report":
        print("FAILED:SYN-0020-probe2 report.kind is not conformance-report")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-untested-not-agree",
                "untested_planted": len(untested),
                "forced_verdict": forced["verdict"],
                "independent_contradict": derived["verdict"],
                "schema_garbage_rejected": 3,
                "silent_agree": 0,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0020-probe2 UNTESTED-not-AGREE and independent CONTRADICT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
