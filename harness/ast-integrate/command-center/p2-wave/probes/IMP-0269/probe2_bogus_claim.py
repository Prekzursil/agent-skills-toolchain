#!/usr/bin/env python3
"""Named probe 2: bogus expertise claims must be rejected.

Both-states:
  good — alice-crypto and blake-tax are seated with an attached probe result.
  bad  — mallory (assertion-only), ned (below baseline), olga (unanswerable
         overclaim) are unseated claimants.

Negative control: select_claimed_tags_unchecked WOULD seat mallory, proving
the competence probe — not tag overlap — is what rejects hallucinated expertise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import load_selector, read_json  # noqa: E402

UNIT = "IMP-0269"
MUST_SEAT = ("alice-crypto", "blake-tax")
MUST_REJECT = (
    "mallory-asserted-crypto",
    "ned-wrong-crypto",
    "olga-overclaim-ua",
)


def main() -> int:
    sel = load_selector()
    bank_doc = read_json("competence-bank.json")
    cand_doc = read_json("candidates.json")
    task = cand_doc["task_tags"]
    candidates = cand_doc["candidates"]
    bank = bank_doc["items"]
    baseline = float(bank_doc.get("baseline") or 0.5)

    unchecked = sel.select_claimed_tags_unchecked(task, candidates)
    selection = sel.select_expertise(task, candidates, bank, baseline=baseline)
    seated_ids = [s.participant_id for s in selection.seated]
    unseated_ids = [u.participant_id for u in selection.unseated_claimants]
    unseated_by_id = {u.participant_id: u for u in selection.unseated_claimants}
    seated_by_id = {s.participant_id: s for s in selection.seated}

    mallory_in_unchecked = "mallory-asserted-crypto" in unchecked
    mallory_not_seated = "mallory-asserted-crypto" not in seated_ids
    probe_is_load_bearing = mallory_in_unchecked and mallory_not_seated

    seated_ok = all(pid in seated_ids for pid in MUST_SEAT)
    rejected_ok = all(pid in unseated_ids for pid in MUST_REJECT)
    frontend_skipped = "pat-frontend" in selection.skipped_no_overlap

    attached = True
    for pid in MUST_SEAT:
        seat = seated_by_id.get(pid)
        if seat is None or not seat.probe_results or not all(p.passed for p in seat.probe_results):
            attached = False

    mallory = unseated_by_id.get("mallory-asserted-crypto")
    mallory_reason_ok = bool(
        mallory and mallory.reason == "hallucinated-expertise" and mallory.probe_results
    )

    assertion_only = any(
        p.assertion_only for p in (mallory.probe_results if mallory else ())
    )

    ok = (
        probe_is_load_bearing
        and seated_ok
        and rejected_ok
        and attached
        and mallory_reason_ok
        and assertion_only
        and frontend_skipped
        and "pat-frontend" not in seated_ids
        and selection.seated[0].role == "domain_authority"
    )
    payload = {
        "probe": "probe2-bogus-claim-rejected",
        "unit_id": UNIT,
        "unchecked_would_seat_mallory": mallory_in_unchecked,
        "mallory_seated": not mallory_not_seated,
        "probe_is_load_bearing": probe_is_load_bearing,
        "seated_ids": seated_ids,
        "unseated_ids": unseated_ids,
        "unseated_reasons": {u.participant_id: u.reason for u in selection.unseated_claimants},
        "each_seat_has_probe_result": attached,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"seated={seated_ids} unseated={unseated_ids} "
        f"load_bearing={probe_is_load_bearing}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe2 bogus claim was not rejected")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 bogus expertise claim rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
