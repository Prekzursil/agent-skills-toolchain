#!/usr/bin/env python3
"""Named probe 2: a no-evidence stage in the input fails the build.

Both-states:
  * complete evidence emits a fusion (silent on good)
  * dropping the rank/beta evidence row refuses with NO_EVIDENCE (fires on bad)
  * empty run id refuses with EMPTY_RUN_ID
  * reputation-only row refuses with REPUTATION_NOT_EVIDENCE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.best_of_breed import (  # noqa: E402
    EMPTY_RUN_ID,
    NO_EVIDENCE,
    REPUTATION_NOT_EVIDENCE,
    build_best_of_breed,
)
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0185-probe2 {msg}")
    return 1


def main() -> int:
    srcs = F.sources()

    good = build_best_of_breed(srcs, F.evidence_complete())
    if not good.get("ok"):
        return fail(f"good state refused: {good}")
    silent_on_good = True

    missing = build_best_of_breed(srcs, F.evidence_missing_rank_beta())
    if missing.get("ok"):
        return fail("missing rank/beta evidence was accepted")
    if missing.get("error") != NO_EVIDENCE:
        return fail(f"missing-row error {missing.get('error')} want {NO_EVIDENCE}")
    if missing.get("slot_id") != "rank" or missing.get("source_id") != "wf.source.beta-ranker":
        return fail(f"missing-row attributed wrong {missing}")
    fired_on_missing = True

    empty = build_best_of_breed(srcs, F.evidence_empty_run_id())
    if empty.get("ok"):
        return fail("empty run id was accepted")
    if empty.get("error") != EMPTY_RUN_ID:
        return fail(f"empty-run-id error {empty.get('error')} want {EMPTY_RUN_ID}")
    fired_on_empty = True

    reputation = build_best_of_breed(srcs, F.evidence_reputation_only())
    if reputation.get("ok"):
        return fail("reputation-only row was accepted")
    if reputation.get("error") != REPUTATION_NOT_EVIDENCE:
        return fail(
            f"reputation error {reputation.get('error')} want {REPUTATION_NOT_EVIDENCE}"
        )
    fired_on_reputation = True

    prefer = build_best_of_breed(
        srcs, F.evidence_complete(), prefer_source="wf.source.alpha-retriever"
    )
    if prefer.get("ok"):
        return fail("prefer_source was accepted as a selection basis")

    payload = {
        "probe": "probe2-no-evidence",
        "unit_id": "IMP-0185",
        "silent_on_good": silent_on_good,
        "fired_on_missing_row": fired_on_missing,
        "fired_on_empty_run_id": fired_on_empty,
        "fired_on_reputation": fired_on_reputation,
        "prefer_source_refused": not prefer.get("ok"),
        "missing_error": missing.get("error"),
        "empty_error": empty.get("error"),
        "reputation_error": reputation.get("error"),
        "both_states": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "fired_on_missing=True fired_on_empty_run_id=True "
        "fired_on_reputation=True silent_on_good=True"
    )
    print("SUCCESS:IMP-0185-probe2 no-evidence stage fails the build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
