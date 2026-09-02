#!/usr/bin/env python3
"""Probe 1: pairing-schedule completeness and depth bound (both-states).

Independent of probe 2 (which scores Pearson r and planted coverage gaps).
Completeness is a set relation: every substantive position id appears in
at least one valid pairing. Depth is a numeric bound, not a flag.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.crossexam import (  # noqa: E402
    DEPTH_BOUND,
    Pairing,
    SELF_EXAM,
    audit_record,
    examination_quota,
    pairing_is_valid_exam,
    propose_followup,
    schedule_cross_examination,
)
from fixtures import EXPECTED_QUOTA, MAX_DEPTH, PARTICIPANTS, labelled_positions  # noqa: E402


def _valid_targets(positions, pairings) -> set[str]:
    by_id = {p.position_id: p for p in positions}
    out: set[str] = set()
    for pairing in pairings:
        pos = by_id.get(pairing.position_id)
        if pos is not None and pairing_is_valid_exam(pos, pairing):
            out.add(pairing.position_id)
    return out


def main() -> int:
    positions = labelled_positions()
    substantive = {p.position_id for p in positions if p.substantive}
    max_pop = max(p.popularity for p in positions if p.substantive)

    quota_rows = []
    quota_ok = True
    for pos in positions:
        if not pos.substantive:
            continue
        got = examination_quota(pos.popularity, max_pop, MAX_DEPTH)
        want = EXPECTED_QUOTA[pos.position_id]
        match = got == want
        quota_ok = quota_ok and match
        quota_rows.append(
            {
                "position_id": pos.position_id,
                "popularity": pos.popularity,
                "got": got,
                "want": want,
                "match": match,
            }
        )
    monotone = True
    subst = [p for p in positions if p.substantive]
    for a in subst:
        for b in subst:
            qa = examination_quota(a.popularity, max_pop, MAX_DEPTH)
            qb = examination_quota(b.popularity, max_pop, MAX_DEPTH)
            if a.popularity >= b.popularity and qa < qb:
                monotone = False

    sched = schedule_cross_examination(positions, PARTICIPANTS, max_depth=MAX_DEPTH)
    independent_complete = substantive <= _valid_targets(positions, sched.pairings)
    depths = [p.depth for p in sched.pairings]
    depth_ok = bool(depths) and max(depths) <= MAX_DEPTH and min(depths) >= 1
    self_exams = []
    by_id = {p.position_id: p for p in positions}
    for pairing in sched.pairings:
        pos = by_id[pairing.position_id]
        if pairing.examiner_id == pos.author_id:
            self_exams.append(pairing.pairing_id)

    proc_row = next(r for r in sched.coverage if r.position_id == "P-proc")
    proc_not_gap = proc_row.gap is False and proc_row.substantive is False

    counts = {r.position_id: r.examination_count for r in sched.coverage}
    quota_realized = all(
        counts[pid] == want for pid, want in EXPECTED_QUOTA.items()
    )

    shallow = schedule_cross_examination(positions, PARTICIPANTS, max_depth=1)
    shallow_depths = [p.depth for p in shallow.pairings]
    shallow_ok = (
        shallow.complete
        and shallow_depths
        and max(shallow_depths) == 1
        and substantive <= _valid_targets(positions, shallow.pairings)
    )
    deep_has_followup = any(p.depth == 2 for p in sched.pairings)

    parent = next(p for p in sched.pairings if p.depth == MAX_DEPTH)
    used = {p.examiner_id for p in sched.pairings if p.position_id == parent.position_id}
    follow_examiner = next(
        pid
        for pid in PARTICIPANTS
        if pid not in used and pid != by_id[parent.position_id].author_id
    )
    bound = propose_followup(positions, sched, parent.pairing_id, follow_examiner)

    depth1 = next(p for p in sched.pairings if p.depth == 1)
    author = by_id[depth1.position_id].author_id
    self_try = propose_followup(positions, sched, depth1.pairing_id, author)

    planted_self = audit_record(
        positions,
        [
            Pairing(
                pairing_id="SELF",
                examiner_id="A",
                position_id="P-dom",
                depth=1,
                parent_pairing_id=None,
            )
        ],
        max_depth=MAX_DEPTH,
        participant_ids=PARTICIPANTS,
    )
    self_does_not_cover = any(
        r.position_id == "P-dom" and r.gap for r in planted_self.coverage
    )

    payload = {
        "probe": "probe1-schedule-completeness",
        "unit_id": "IMP-0363",
        "quota_rows": quota_rows,
        "quota_ok": quota_ok,
        "monotone_quota": monotone,
        "independent_complete": independent_complete,
        "scheduler_complete": sched.complete,
        "gaps": list(sched.gaps),
        "depth_ok": depth_ok,
        "max_observed_depth": max(depths) if depths else None,
        "self_exams": self_exams,
        "proc_not_gap": proc_not_gap,
        "quota_realized": quota_realized,
        "examination_counts": counts,
        "both_states_depth": {
            "max_depth_1_complete_and_flat": shallow_ok,
            "max_depth_2_has_followup": deep_has_followup,
        },
        "depth_bound": {
            "accepted": bound.accepted,
            "reason": bound.reason,
            "fires": bound.accepted is False and bound.reason == DEPTH_BOUND,
        },
        "self_exam_followup": {
            "accepted": self_try.accepted,
            "reason": self_try.reason,
            "fires": self_try.accepted is False and self_try.reason == SELF_EXAM,
        },
        "self_exam_does_not_fill_coverage": self_does_not_cover,
        "pairing_count": len(sched.pairings),
    }
    payload["pass"] = bool(
        quota_ok
        and monotone
        and independent_complete
        and sched.complete
        and not sched.gaps
        and depth_ok
        and not self_exams
        and proc_not_gap
        and quota_realized
        and shallow_ok
        and deep_has_followup
        and payload["depth_bound"]["fires"]
        and payload["self_exam_followup"]["fires"]
        and self_does_not_cover
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0363-probe1 pairing schedule completeness")
        return 1
    print("SUCCESS:IMP-0363-probe1 pairing schedule completeness and depth bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
