#!/usr/bin/env python3
"""Probe 1: TTL expiry moves a candidate onto the due-list (injected clock).

Both-states on the SAME record: inside the class TTL the candidate is absent
from the due-list and its GREEN remains citeable; one second past the TTL it
appears on the due-list and GREEN decays to STALE. Wall clock is banned for
the duration of the measurement.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from candidates.freshness import (  # noqa: E402
    compute_due_list,
    due_item_as_dict,
)

WALL_CLOCK_TOKENS = (
    "time.time(",
    "time.time_ns(",
    "datetime.now(",
    "datetime.utcnow(",
    "date.today(",
)


def _ban_wall_clock() -> None:
    src = (REPO / "tools" / "candidates" / "freshness.py").read_text(encoding="utf-8")
    leaked = [tok for tok in WALL_CLOCK_TOKENS if tok in src]
    if leaked:
        raise AssertionError(f"scheduler source consults wall clock: {leaked}")

    def boom(*_a, **_k):
        raise AssertionError("wall clock consulted during TTL due-list computation")

    time.time = boom  # type: ignore[assignment]


def main() -> int:
    _ban_wall_clock()
    rows = S.load_candidates()
    table = S.ttl_policy()
    live_ttl = table.classes["live-advisory"]
    subject = S.by_id(rows)[S.TTL_SUBJECT]
    if subject.last_verified != S.T0:
        print("FAILED:IMP-0159-probe1 fixture last_verified is not T0")
        return 1
    if live_ttl != 86400:
        print(f"FAILED:IMP-0159-probe1 unexpected live-advisory TTL {live_ttl}")
        return 1

    clock_type_enforced = False
    try:
        compute_due_list(rows, S.CLOCK_WITHIN.now_unix, table)  # type: ignore[arg-type]
    except TypeError:
        clock_type_enforced = True

    within = compute_due_list(rows, S.CLOCK_WITHIN, table)
    past = compute_due_list(rows, S.CLOCK_PAST, table)
    past_again = compute_due_list(rows, S.CLOCK_PAST, table)

    within_ids = [item.candidate_id for item in within]
    past_ids = [item.candidate_id for item in past]
    past_ids_2 = [item.candidate_id for item in past_again]
    subject_within = next((i for i in within if i.candidate_id == S.TTL_SUBJECT), None)
    subject_past = next((i for i in past if i.candidate_id == S.TTL_SUBJECT), None)
    missing_within = next((i for i in within if i.candidate_id == S.MISSING_ID), None)

    age_within = S.CLOCK_WITHIN.now() - S.T0
    age_past = S.CLOCK_PAST.now() - S.T0
    checks = {
        "within_ttl_age_lt_ttl": age_within < live_ttl,
        "past_ttl_age_ge_ttl": age_past >= live_ttl,
        "subject_absent_within_ttl": subject_within is None,
        "subject_present_past_ttl": subject_past is not None,
        "decayed_to_stale": bool(
            subject_past
            and subject_past.prior_verdict == "GREEN"
            and subject_past.decayed_verdict == "STALE"
            and subject_past.citeable is False
        ),
        "ttl_reason": bool(subject_past and "ttl-expired" in subject_past.reasons),
        "missing_verified_fail_closed": missing_within is not None
        and "missing-last-verified" in missing_within.reasons,
        "missing_uses_worst_default": bool(
            missing_within and missing_within.ttl_source == "worst-case-default"
        ),
        "source_repo_not_due_at_past_clock": S.ARCHIVED_ID not in past_ids
        and S.MAINTAINED_ID not in past_ids,
        "determinism_same_clock": past_ids == past_ids_2
        and [due_item_as_dict(i) for i in past]
        == [due_item_as_dict(i) for i in past_again],
        "injected_clocks_only": clock_type_enforced,
    }
    payload = {
        "probe": "probe1-ttl-due-list",
        "unit_id": "IMP-0159",
        "clock_within": S.CLOCK_WITHIN.now_unix,
        "clock_past": S.CLOCK_PAST.now_unix,
        "live_advisory_ttl": live_ttl,
        "age_within": age_within,
        "age_past": age_past,
        "within_ids": within_ids,
        "past_ids": past_ids,
        "subject_past": due_item_as_dict(subject_past) if subject_past else None,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(payload, sort_keys=True))
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print(f"FAILED:IMP-0159-probe1 {failed}")
        return 1
    print(
        "SUCCESS:IMP-0159-probe1 TTL expiry due-list "
        f"within_absent={S.TTL_SUBJECT} past_present={S.TTL_SUBJECT} decayed=STALE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
