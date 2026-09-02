#!/usr/bin/env python3
"""Probe 1: scripted lone dissenter must appear in every downstream artifact.

Walks transcript -> argument ledger -> decision record -> synthesis ->
executive summary and records the UTF-8 byte offset and heading of the
dissent token and claim in each. Also requires the majority token to
survive, so a broken renderer cannot pass by dropping everything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from tools.council import simulate as S  # noqa: E402
from tools.council import synthesis as Y  # noqa: E402

FIXTURE = HERE / "fixtures" / "lone-dissenter.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0267-probe1 {msg}")
    return 1


def main() -> int:
    spec = S.load_spec(FIXTURE)
    run_a = S.run(spec)
    run_b = S.run(spec)
    if S.canonical_bytes(run_a) != S.canonical_bytes(run_b):
        return _fail("same-spec runs are not byte-identical")
    if run_a.get("dissent_first_round") != 4:
        return _fail(f"dissent first appeared in round {run_a.get('dissent_first_round')}")
    if run_a.get("dissenters") != ["skeptic"]:
        return _fail(f"expected lone skeptic, got {run_a.get('dissenters')}")
    mr = run_a.get("minority_report") or {}
    if mr.get("token") != S.DISSENT_TOKEN or S.DISSENT_CLAIM not in str(mr.get("claim") or ""):
        return _fail("minority_report missing token or claim")

    chain = Y.run_chain(run_a, propagate=True, max_body_chars=None)
    dissent = Y.trace_survival(chain["rendered"], token=S.DISSENT_TOKEN, claim=S.DISSENT_CLAIM)
    majority = Y.trace_survival(
        chain["rendered"], token=S.MAJORITY_TOKEN, claim=S.MAJORITY_CLAIM
    )
    if not dissent["ok"]:
        return _fail(f"dissent dropped at {dissent['first_missing']}")
    if not majority["ok"]:
        return _fail(f"majority dropped at {majority['first_missing']} (trace broken)")

    first = dissent["stages"][0]
    if first["stage"] != "transcript" or not first["present"]:
        return _fail("dissent absent from transcript")
    if first["token"]["heading"] != Y.MINORITY_HEADING:
        return _fail(f"transcript heading {first['token']['heading']!r}")

    out = {
        "claim_survived": True,
        "dissent_first_round": 4,
        "dissenters": run_a["dissenters"],
        "first_appearance": {
            "artifact": "transcript",
            "claim_byte_offset": first["claim"]["byte_offset"],
            "heading": first["heading"],
            "round": 4,
            "token_byte_offset": first["token"]["byte_offset"],
        },
        "first_missing": None,
        "majority_survived": True,
        "pass": True,
        "probe": "probe1-lone-dissenter-trace",
        "spec_id": spec.get("id"),
        "stages": [
            {
                "artifact": row["stage"],
                "claim_byte_offset": row["claim"]["byte_offset"],
                "heading": row["heading"],
                "present": row["present"],
                "token_byte_offset": row["token"]["byte_offset"],
            }
            for row in dissent["stages"]
        ],
        "transcript_sha256": S.digest_doc(run_a),
        "two_run_identical": True,
        "unit_id": "TST-0267",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:TST-0267-probe1 lone dissenter present in all downstream artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
