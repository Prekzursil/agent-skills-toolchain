#!/usr/bin/env python3
"""Named probe 2: oracle sanity both-states + vacuous-oracle strip.

Mechanically different from probe 1: re-evaluates known-good / known-bad on
every on-disk case. Does not score jsonschema or split set-intersection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "bench"))
sys.path.insert(0, str(HERE))

from corpus import vacuous_control_case  # noqa: E402
from oracle import evaluate, load_cases, sanity  # noqa: E402

UNIT = "TST-0295"
ART = REPO / "command-center" / "receipts" / "TST-0295.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0295" not in json.dumps(doc):
        return fail("sentinel absent")

    cases = load_cases()
    if not cases:
        return fail("no cases")
    failed = []
    vacuous = []
    for case in cases:
        row = sanity(case)
        if not row["ok"]:
            failed.append(row)
        if row["vacuous"]:
            vacuous.append(case.get("id"))
        if evaluate(case, case.get("known_bad_solution") or {}):
            failed.append({"id": case.get("id"), "known_bad_accepted": True})
    if failed:
        return fail("oracle sanity", failed[:8])
    if vacuous:
        return fail("vacuous oracle retained", vacuous)

    planted = vacuous_control_case()
    planted_row = sanity(planted)
    if planted_row["ok"] or not planted_row["vacuous"]:
        return fail("vacuous control silent", planted_row)
    live_ids = {c["id"] for c in cases}
    if planted["id"] in live_ids:
        return fail("vacuous id present in corpus")

    rec = doc.get("vacuous_oracle_control") or {}
    if rec.get("present_in_corpus") is not False:
        return fail("receipt vacuous present_in_corpus")
    if planted["id"] not in (rec.get("rejected_ids") or []):
        return fail("receipt missing rejected vacuous id", rec)

    det = sum(1 for c in cases if (c.get("oracle") or {}).get("oracle_type") == "deterministic")
    judged = sum(1 for c in cases if (c.get("oracle") or {}).get("oracle_type") == "judged")
    rec_ot = doc.get("oracle_types") or {}
    if rec_ot.get("deterministic") != det or rec_ot.get("judged") != judged:
        return fail("oracle type count drift", {"live": {"deterministic": det, "judged": judged}, "recorded": rec_ot})
    if judged < 1:
        return fail("no judged oracles tagged")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict", reviewer)
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")

    payload = {
        "pass": True,
        "probe": "probe2-oracle-sanity",
        "unit_id": UNIT,
        "n_cases": len(cases),
        "all_known_good_pass": True,
        "all_known_bad_fail": True,
        "vacuous_rejected": True,
        "deterministic": det,
        "judged": judged,
        "reviewer_reexecuted_both_states": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"oracle_ok={len(cases)} vacuous_rejected=True det={det} judged={judged} "
        "reviewer_both_states=True"
    )
    print("SUCCESS:TST-0295-probe2 oracle-sanity vacuous-strip reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
