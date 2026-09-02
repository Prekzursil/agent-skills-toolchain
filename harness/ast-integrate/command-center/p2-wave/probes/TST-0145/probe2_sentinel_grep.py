#!/usr/bin/env python3
"""Probe 2 (signal b): independent grep of fixture bytes.

Does not import evaluate_c05_artifact for the verdict. Reads artifact
bytes and JSON role keys directly. Confirms missing has no own token,
wrong-id bytes carry SUCCESS:TST-9999 in the role field, and quoted
mention has the token only outside role keys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import condition5 as C  # noqa: E402

ART = REPO / "command-center/receipts/TST-0145.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0145-probe2 {msg}")
    return 1


def main() -> int:
    fixtures = C.write_fixtures()
    scans = {case_id: C.grep_signals(fx["text"]) for case_id, fx in fixtures.items()}
    payload = {
        "probe": "probe2-sentinel-grep",
        "scans": scans,
        "unit_id": C.UNIT,
    }
    print(json.dumps(payload, sort_keys=True))

    correct = scans["correct"]
    missing = scans["missing"]
    wrong = scans["wrong_id"]
    quoted = scans["quoted_mention"]

    if not correct["own_token_in_bytes"] or not correct["own_in_role"]:
        return fail("correct fixture grep missed SUCCESS:TST-0145 in role")
    if missing["own_token_in_bytes"] or missing["foreign_token_in_bytes"]:
        return fail("missing fixture still contains a SUCCESS:UID token")
    if missing["own_in_role"] or missing["foreign_in_role"]:
        return fail("missing fixture role carried a sentinel")
    if not wrong["foreign_token_in_bytes"] or not wrong["foreign_in_role"]:
        return fail("wrong-id grep did not find SUCCESS:TST-9999 in role")
    if wrong["own_in_role"] or wrong["own_token_in_bytes"]:
        return fail("wrong-id fixture unexpectedly carries SUCCESS:TST-0145")
    if not quoted["own_token_in_bytes"]:
        return fail("quoted mention fixture lost the token; control is vacuous")
    if quoted["own_in_role"]:
        return fail("quoted mention placed SUCCESS:TST-0145 in a role field")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0145" not in text:
            return fail("receipt sentinel absent")
        sentinel_field = str(doc.get("sentinel") or "")
        if not sentinel_field.startswith("SUCCESS:TST-0145"):
            return fail("receipt sentinel role missing SUCCESS:TST-0145")
        evidence = doc.get("evidence") or []
        anchors = {e.get("anchor") for e in evidence if isinstance(e, dict)}
        if "grep:runtime/missing" not in anchors:
            return fail("receipt missing grep evidence for missing case")
        if "grep:runtime/wrong_id" not in anchors:
            return fail("receipt missing grep evidence for wrong-id case")

    print(
        "grep: missing token-absent; wrong-id SUCCESS:TST-9999 in role; "
        "quoted token-in-bytes but not in role; correct role match"
    )
    print("SUCCESS:TST-0145-probe2 independent grep mismatch-named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
