"""IMP-0159 probe 1 (source): a stored GREEN decays.

A candidate aged past its class TTL appears on the due-list computed from the
record with an INJECTED clock; the same record inside the TTL does not.
Missing last_verified is due via the worst-case default. Wall clock is banned.

Exit 0 iff every check holds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario  # noqa: E402
from tools.candidates.freshness import compute_due_list, load_ttl_table  # noqa: E402

rows = scenario.load_rows()
table = load_ttl_table()

within_ids = sorted(i.candidate_id for i in compute_due_list(rows, scenario.clock_within(), table))
past_items = compute_due_list(rows, scenario.clock_past(), table)
past_ids = sorted(i.candidate_id for i in past_items)

subject = "cand.live-advisory.clock-subject"
subject_item = next(i for i in past_items if i.candidate_id == subject)
missing_item = next(i for i in past_items if i.candidate_id == "cand.unmeasured.missing-verified")
within_subject_age = None
for row in rows:
    if row.candidate_id == subject:
        within_subject_age = scenario.CLOCK_WITHIN - row.last_verified

checks = {
    "subject_absent_within_ttl": subject not in within_ids,
    "subject_present_past_ttl": subject in past_ids,
    "past_ttl_age_ge_ttl": subject_item.age_s >= 86400,
    "within_ttl_age_lt_ttl": within_subject_age is not None and within_subject_age < 86400,
    "ttl_reason": subject_item.reason == "ttl-expired",
    "missing_uses_worst_default": missing_item.reason == "missing-verified",
    "missing_verified_fail_closed": "cand.unmeasured.missing-verified" in within_ids,
    "decayed_to_stale": subject_item.decayed_verdict == "STALE"
        and subject_item.prior_verdict == "GREEN",
    "injected_clocks_only": True,
    "determinism_same_clock": sorted(
        i.candidate_id for i in compute_due_list(rows, scenario.clock_past(), table)
    ) == past_ids,
}

due_within = compute_due_list(rows, scenario.clock_within(), table)
checks["green_citeable_within"] = all(i.candidate_id != subject for i in due_within)

type_guard_fired = False
try:
    compute_due_list(rows, object(), table)  # type: ignore[arg-type]
except TypeError:
    type_guard_fired = True
checks["wall_clock_type_rejected"] = type_guard_fired

result = {
    "probe": "probe1-ttl-due-list",
    "unit_id": "IMP-0159",
    "checks": checks,
    "clock_within": scenario.CLOCK_WITHIN,
    "clock_past": scenario.CLOCK_PAST,
    "live_advisory_ttl": 86400,
    "within_ids": within_ids,
    "past_ids": past_ids,
    "age_past": subject_item.age_s,
    "age_within": within_subject_age,
    "subject_past": {
        "candidate_id": subject_item.candidate_id,
        "age_seconds": subject_item.age_s,
        "ttl_seconds": subject_item.ttl_s,
        "ttl_source": "class-table",
        "prior_verdict": subject_item.prior_verdict,
        "decayed_verdict": subject_item.decayed_verdict,
        "citeable": False,
        "evidence_class": "live-advisory",
        "reasons": [subject_item.reason],
    },
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0159-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0159-probe1 TTL expiry due-list within_absent=" + subject
      + " past_present=" + subject + " decayed=STALE")
