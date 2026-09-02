#!/usr/bin/env python3
"""Probe 1: both-states planted lossy collapse vs union-preserving collapse.

The gate must fire on the planted capability-loss merge and stay silent on
the same pair with the four attribute unions kept. Negative control is
printed verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import policy as P  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0095-duplicate-collapse-policy.json"
SCHEMA = HERE / "audit-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0095-probe1 {msg}")
    return 1


def main() -> int:
    fx = P.fixtures()
    lossy = P.run_fixture(fx["planted-lossy-mechanism"])
    good = P.run_fixture(fx["union-preserving"])

    print(
        f"lossy accepted={lossy['accepted']} codes={lossy['codes']} "
        f"missing={lossy['missing']}"
    )
    print(
        f"good accepted={good['accepted']} codes={good['codes']} "
        f"governing={good['governing_licence']} restore_ok={good['restore_ok']}"
    )

    if lossy["accepted"]:
        return fail("planted lossy collapse was accepted")
    if lossy["codes"] != [P.CAPABILITY_LOSS]:
        return fail(f"lossy codes {lossy['codes']}")
    if "embedding-cosine-rewrite" not in (lossy["missing"].get(P.MECHANISMS) or []):
        return fail("lossy missing set does not name embedding-cosine-rewrite")
    if not good["accepted"] or good["codes"]:
        return fail(f"union-preserving not accepted codes={good['codes']}")
    if good["governing_licence"] != "AGPL-3.0-only":
        return fail(f"governing licence {good['governing_licence']}")
    if not good["edges"] or good["edges"][0].get("edge_type") != "duplicate-of":
        return fail("union-preserving did not write duplicate-of")
    if good["restore_ok"] is not True:
        return fail("restore from duplicate-of did not reconstruct the pair")
    if lossy["codes"] == good["codes"]:
        return fail("lossy and preserving not distinguishable")

    print("NEGATIVE_CONTROL_VERBATIM=" + P.NEGATIVE_CONTROL_VERBATIM)

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail(f"artifact missing {OUT}")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"artifact self-declared {doc.get('state')}")
    if P.SENTINEL not in text:
        return fail("sentinel absent from artifact")

    try:
        import jsonschema
    except ImportError:
        return fail("jsonschema not installed")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated"}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
    if garbage_rejected != 3:
        return fail(f"schema vacuous garbage_rejected={garbage_rejected}")

    recorded = {
        row["fixture_id"]: row
        for row in (doc.get("evaluations") or [])
        if isinstance(row, dict)
    }
    rec_lossy = recorded.get("planted-lossy-mechanism") or {}
    rec_good = recorded.get("union-preserving") or {}
    if rec_lossy.get("accepted") is not False:
        return fail("artifact did not record lossy rejection")
    if rec_lossy.get("codes") != [P.CAPABILITY_LOSS]:
        return fail(f"artifact lossy codes {rec_lossy.get('codes')}")
    if rec_good.get("accepted") is not True:
        return fail("artifact did not record union-preserving accept")
    if not (doc.get("controls") or {}).get("lossy_rejected"):
        return fail("artifact controls.lossy_rejected is not true")
    if not (doc.get("controls") or {}).get("union_preserving_accepted"):
        return fail("artifact controls.union_preserving_accepted is not true")
    if not (doc.get("controls") or {}).get("policy_has_rejected"):
        return fail("artifact claims a policy that never rejected")

    print(
        f"fired_on_bad={not lossy['accepted']} silent_on_good={good['accepted'] is True}"
    )
    print("SUCCESS:WFA-0095-probe1 planted-lossy rejected; union-preserving accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
