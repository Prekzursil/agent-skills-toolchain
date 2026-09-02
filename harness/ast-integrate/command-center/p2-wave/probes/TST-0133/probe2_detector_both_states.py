#!/usr/bin/env python3
"""Probe 2: detector control (planted URL fetch) + both-states pre/post lists."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0133-probe2 {msg}")
    return 1


def main() -> int:
    m = H.measure()
    try:
        H.require_contract(m)
    except SystemExit as exc:
        return fail(str(exc))
    pre_ids = [x["id"] for x in m["pre"]["undeclared"]]
    post_ids = [x["id"] for x in m["post"]["undeclared"]]
    print(f"planted={C.PLANTED_ID}")
    print(f"pre_ids={pre_ids}")
    print(f"post_ids={post_ids}")
    print(f"declarations_added={m['post']['network_declarations_added']}")
    if C.PLANTED_ID not in pre_ids:
        return fail("detector silent on planted URL-fetch test")
    if not pre_ids:
        return fail("both-states: pre-remediation list empty")
    if post_ids:
        return fail("both-states: post-remediation list not empty")
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    dc = doc.get("detector_control") or {}
    if dc.get("fired_on_planted_url_fetch") is not True:
        return fail("artifact detector_control.fired_on_planted_url_fetch is not true")
    if dc.get("trusted_zero_only_after_fire") is not True:
        return fail("artifact trusted_zero_only_after_fire is not true")
    if dc.get("planted_test_id") != C.PLANTED_ID:
        return fail("artifact planted_test_id mismatch")
    bs = doc.get("both_states_control") or {}
    if bs.get("pre_remediation_list_non_empty") is not True:
        return fail("artifact both-states pre flag false")
    if bs.get("post_remediation_list_empty") is not True:
        return fail("artifact both-states post flag false")
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")
    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print("SUCCESS:TST-0133-probe2 detector-control and both-states fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
