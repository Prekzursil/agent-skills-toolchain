#!/usr/bin/env python3
"""Probe 2: inexpressible rule is UNKNOWN-NEEDS-PROBE by id; never approximated.

Both-states:
  GOOD  expressible twin compiles to EVALUABLE
  BAD   cand-inexpressible-feels-done is UNKNOWN-NEEDS-PROBE, asserted by id
Mutation: the known-broken approximator that snaps prose to completeness_score
must NOT be the production extractor (detector would go silent if it were).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from candidates import (  # noqa: E402
    EXPRESSIBLE_TWIN_ID,
    INEXPRESSIBLE_ID,
    candidate_set,
)
from extract import (  # noqa: E402
    CLASS_EVALUABLE,
    CLASS_NONE,
    CLASS_UNKNOWN,
    approximate_prose_to_completeness,
    extract_all,
    extract_stop_rule,
)

ART = Path(__file__).resolve().parents[3] / "command-center/receipts/IMP-0166.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0166-probe2 {msg}")
    return 1


def main() -> int:
    rows = extract_all(candidate_set())
    by_id = {r["id"]: r for r in rows}
    print(
        json.dumps(
            {
                "probe": "probe2-inexpressible",
                "classifications": {
                    r["id"]: r["classification"] for r in rows
                },
            },
            indent=2,
        )
    )

    bad = by_id.get(INEXPRESSIBLE_ID)
    if bad is None:
        return _fail(f"missing id {INEXPRESSIBLE_ID}")
    if bad["classification"] != CLASS_UNKNOWN:
        return _fail(
            f"{INEXPRESSIBLE_ID} classification={bad['classification']} "
            "want=UNKNOWN-NEEDS-PROBE"
        )
    if bad.get("tree") is not None:
        return _fail(f"{INEXPRESSIBLE_ID} carried an approximated tree")

    good = by_id.get(EXPRESSIBLE_TWIN_ID)
    if good is None:
        return _fail(f"missing id {EXPRESSIBLE_TWIN_ID}")
    if good["classification"] != CLASS_EVALUABLE:
        return _fail(
            f"{EXPRESSIBLE_TWIN_ID} classification={good['classification']} "
            "want=EVALUABLE"
        )
    tree = good.get("tree") or {}
    if tree.get("kind") != "ALL":
        return _fail(f"expressible twin tree kind={tree.get('kind')}")

    none = by_id.get("cand-none")
    if none is None or none["classification"] != CLASS_NONE:
        return _fail("empty stop rule must be NONE, not a blank EVALUABLE")

    juice = by_id.get("cand-inexpressible-juice")
    if juice is None or juice["classification"] != CLASS_UNKNOWN:
        return _fail("second inexpressible not flagged")

    # Mutation control: the approximator WOULD compile the planted prose.
    planted = next(c for c in candidate_set() if c["id"] == INEXPRESSIBLE_ID)
    fake_tree = approximate_prose_to_completeness(str(planted["stop"]))
    if fake_tree.get("kind") != "CMP" or fake_tree.get("metric") != "completeness_score":
        return _fail("broken approximator did not snap; mutation is inert")
    prod = extract_stop_rule(planted)
    if prod.get("tree") == fake_tree or prod["classification"] == CLASS_EVALUABLE:
        return _fail("production extractor used the approximator")

    spec_ok = [
        r
        for r in rows
        if r["id"].startswith("cand-spec-109") and r["classification"] == CLASS_EVALUABLE
    ]
    if len(spec_ok) != 6:
        return _fail(f"spec candidates evaluable={len(spec_ok)} want=6")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        asserted = doc.get("inexpressible_asserted_by_id") or []
        if INEXPRESSIBLE_ID not in asserted:
            return _fail("receipt did not assert inexpressible id")
        if doc.get("approximated") is True:
            return _fail("receipt claims approximation")

    print(
        f"bad_id={INEXPRESSIBLE_ID} classification=UNKNOWN-NEEDS-PROBE "
        f"good_id={EXPRESSIBLE_TWIN_ID} classification=EVALUABLE "
        "approximator_diverged=yes"
    )
    print("SUCCESS:IMP-0166-probe2 inexpressible flagged, never approximated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
