#!/usr/bin/env python3
"""Named probe 1: missing receipt is NOT-CHECKED, never assumed satisfied.

Also: a present supporting receipt can SATISFY (positive control), and a
present wrong-schema receipt must not count as SATISFIED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conditions import REL_0008  # noqa: E402
from evaluate import FALSE, NOT_CHECKED, SATISFIED, evaluate, map_lookup  # noqa: E402
from schema_local import release_payload  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0126-release-gate-recompute.json"
OK = (HERE / "fixtures" / "ok-receipt.json").read_bytes()
BAD = (HERE / "fixtures" / "wrong-schema.json").read_bytes()

CONTROL = {
    "id": "PG-CONTROL-SATISFIABLE",
    "spec_anchor": "fixture:control",
    "wording": "positive-control condition with a named fixture receipt",
    "wording_provenance": "probe fixture, not a live promotion condition",
    "receipt_paths": ["fixtures/ok-receipt.json"],
    "unsatisfiable_under": None,
    "unsatisfiable_wording": None,
}

MISSING = {
    "id": "PG-CONTROL-NO-RECEIPT",
    "spec_anchor": "fixture:missing",
    "wording": "condition whose named receipt does not exist",
    "wording_provenance": "probe fixture",
    "receipt_paths": ["fixtures/does-not-exist.json"],
    "unsatisfiable_under": None,
    "unsatisfiable_wording": None,
}

WRONG = {
    "id": "PG-CONTROL-WRONG-SCHEMA",
    "spec_anchor": "fixture:wrong-schema",
    "wording": "condition whose named receipt is present but wrong schema",
    "wording_provenance": "probe fixture",
    "receipt_paths": ["fixtures/wrong-schema.json"],
    "unsatisfiable_under": None,
    "unsatisfiable_wording": None,
}


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0126-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0126":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live_rows = release_payload(doc).get("conditions") or []
    if len(live_rows) < 9:
        return fail(f"live conditions {len(live_rows)}")
    assumed = []
    for row in live_rows:
        present = [r for r in (row.get("receipts_consulted") or []) if r.get("present")]
        st = row.get("computed_state")
        if not present and st == SATISFIED:
            assumed.append(row.get("id"))
        if st == SATISFIED and not present:
            assumed.append(row.get("id"))
    if assumed:
        return fail(f"live SATISFIED without receipts {assumed}")
    live_nc = [r["id"] for r in live_rows if r.get("computed_state") == NOT_CHECKED]
    if not live_nc:
        return fail("live artifact has no NOT-CHECKED row (missing-receipt test unshown)")

    lookup = map_lookup(
        {
            "fixtures/ok-receipt.json": OK,
            "fixtures/wrong-schema.json": BAD,
        }
    )
    report = evaluate("PR-ONLY", lookup, [CONTROL, MISSING, WRONG])
    by_id = {r["id"]: r for r in report["conditions"]}

    if by_id[MISSING["id"]]["computed_state"] != NOT_CHECKED:
        return fail(
            f"missing receipt computed {by_id[MISSING['id']]['computed_state']} want NOT-CHECKED"
        )
    if by_id[CONTROL["id"]]["computed_state"] != SATISFIED:
        return fail(
            f"positive control computed {by_id[CONTROL['id']]['computed_state']} want SATISFIED"
        )
    if by_id[WRONG["id"]]["computed_state"] == SATISFIED:
        return fail("wrong-schema receipt counted as SATISFIED")
    if by_id[WRONG["id"]]["computed_state"] != FALSE:
        return fail(
            f"wrong-schema computed {by_id[WRONG['id']]['computed_state']} want FALSE"
        )

    empty = evaluate("PR-ONLY", map_lookup({}), [MISSING])
    if empty["conditions"][0]["computed_state"] != NOT_CHECKED:
        return fail("empty corpus did not yield NOT-CHECKED")
    if empty["promotion_verdict"] != "NO-GO":
        return fail("empty corpus folded into GO")

    live_rel0008 = next(
        (r for r in live_rows if r.get("id") == "PG-11132-no-data-loss"), None
    )
    if live_rel0008 is None:
        return fail("live missing PG-11132-no-data-loss")
    consulted = {r["path"]: r["present"] for r in live_rel0008["receipts_consulted"]}
    if consulted.get(REL_0008) is True:
        return fail("REL-0008 unexpectedly present; probe assumption broken")
    if live_rel0008["computed_state"] != NOT_CHECKED:
        return fail(f"PG-11132 live state {live_rel0008['computed_state']}")

    payload = {
        "missing_is_not_checked": True,
        "positive_control_satisfied": True,
        "wrong_schema_not_satisfied": True,
        "empty_corpus_no_go": True,
        "live_not_checked": live_nc,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0126-probe1 missing-receipt NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
