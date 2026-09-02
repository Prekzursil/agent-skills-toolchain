#!/usr/bin/env python3
"""IMP-0273 probe 1: paired vs unpaired first-round spread on 10 matched questions.

Independent recount: parse POSITION lines from the emitted transcripts and
recompute mean pairwise |polarity| without calling polarity_spread().
A third signal: structured read of 3 transcripts confirming the refuter
opposed rather than agreed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_adversarial import (  # noqa: E402
    AGREE_DISTANCE,
    default_pool,
    default_questions,
    emit_first_round,
    euclidean,
    run_matched_experiment,
    select_adversarial,
    select_unpaired,
    structured_opposition_read,
)

POSITION_RE = re.compile(r"^POSITION\s+(\[[^\n]+\])\s*$", re.MULTILINE)


def local_parse_position(text: str) -> tuple[float, float, float]:
    m = POSITION_RE.search(text)
    if not m:
        raise ValueError("probe1 POSITION missing")
    vec = json.loads(m.group(1))
    return (float(vec[0]), float(vec[1]), float(vec[2]))


def local_polarity(text: str, axis: tuple[float, float, float]) -> float:
    pos = local_parse_position(text)
    return sum(a * b for a, b in zip(pos, axis))


def local_spread(texts: list[str], axis: tuple[float, float, float]) -> float:
    xs = [local_polarity(t, axis) for t in texts]
    n = len(xs)
    if n < 2:
        return 0.0
    acc = 0.0
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            acc += abs(xs[i] - xs[j])
            k += 1
    return acc / k


def main() -> int:
    pool = default_pool()
    questions = default_questions()
    if len(questions) != 10:
        print("FAILED:IMP-0273-probe1 expected 10 questions")
        return 1

    exp = run_matched_experiment(pool, questions, n_proposers=3)
    paired = select_adversarial(pool, n_proposers=3)
    unpaired = select_unpaired(pool, n_seats=len(paired.seats), mode="sequential")

    if paired.findings:
        print("FAILED:IMP-0273-probe1 default pool produced loud findings")
        print(json.dumps([f.as_dict() for f in paired.findings], indent=2))
        return 1
    if len(paired.pairs()) != 3:
        print("FAILED:IMP-0273-probe1 expected 3 proposer/refuter pairs")
        return 1
    refuter_ids = [
        s.participant.participant_id for s in paired.seats if s.role == "refuter"
    ]
    if "R-label-only" in refuter_ids:
        print("FAILED:IMP-0273-probe1 label-trap seated as refuter")
        return 1
    if not any(pid.startswith("R-neg-") or pid.startswith("C-neg-") for pid in refuter_ids):
        print("FAILED:IMP-0273-probe1 refuters are not the oppose cluster")
        return 1

    drift = False
    local_rows = []
    for q in questions:
        p_turns = emit_first_round(paired, q, agree_mode="none")
        u_turns = emit_first_round(unpaired, q, agree_mode="none")
        p_texts = [t.text for t in p_turns]
        u_texts = [t.text for t in u_turns]
        p_local = local_spread(p_texts, q.axis)
        u_local = local_spread(u_texts, q.axis)
        author = next(r for r in exp["rows"] if r["question_id"] == q.question_id)
        rec = {
            "question_id": q.question_id,
            "author_paired": author["paired_spread"],
            "author_unpaired": author["unpaired_spread"],
            "local_paired": p_local,
            "local_unpaired": u_local,
            "paired_gt_unpaired": p_local > u_local,
            "self_gt_self": p_local > p_local,
        }
        local_rows.append(rec)
        if abs(p_local - author["paired_spread"]) > 1e-9:
            print(f"FAILED:IMP-0273-probe1 recount drift paired {q.question_id}")
            drift = True
        if abs(u_local - author["unpaired_spread"]) > 1e-9:
            print(f"FAILED:IMP-0273-probe1 recount drift unpaired {q.question_id}")
            drift = True
        if not (p_local > u_local):
            print(f"FAILED:IMP-0273-probe1 paired not greater {q.question_id}")
            drift = True
        if rec["self_gt_self"]:
            print("FAILED:IMP-0273-probe1 comparison is tautologically true")
            drift = True

    reads = []
    for transcript in exp["transcripts"][:3]:
        if not transcript["pairs"]:
            print("FAILED:IMP-0273-probe1 empty pair transcripts")
            return 1
        pair = transcript["pairs"][0]
        read = structured_opposition_read(pair["proposer_text"], pair["refuter_text"])
        # Independent re-read: claims must differ and gap must clear the metric.
        p_pos = local_parse_position(pair["proposer_text"])
        r_pos = local_parse_position(pair["refuter_text"])
        gap = euclidean(p_pos, r_pos)
        ok = (
            read["opposed"]
            and "I refute" in pair["refuter_text"]
            and "I agree with the proposer" not in pair["refuter_text"]
            and gap >= AGREE_DISTANCE
        )
        reads.append(
            {
                "question_id": transcript["question_id"],
                "proposer_id": pair["proposer_id"],
                "refuter_id": pair["refuter_id"],
                "opposed": ok,
                "gap": gap,
                "proposer_claim": read["proposer_claim"],
                "refuter_counter": read["refuter_counter"],
            }
        )
        if not ok:
            print("FAILED:IMP-0273-probe1 transcript not opposed")
            print(json.dumps(reads[-1], indent=2))
            drift = True

    payload = {
        "id": "spread-comparison-10-matched",
        "n_questions": len(questions),
        "all_paired_greater": all(r["paired_gt_unpaired"] for r in local_rows),
        "label_trap_seated_as_refuter": False,
        "refuter_ids": refuter_ids,
        "paired_ids": [s.participant.participant_id for s in paired.seats],
        "unpaired_ids": [s.participant.participant_id for s in unpaired.seats],
        "rows": local_rows,
        "transcript_reads": reads,
        "all_three_opposed": all(r["opposed"] for r in reads) and len(reads) == 3,
        "pass": (
            not drift
            and len(local_rows) == 10
            and all(r["paired_gt_unpaired"] for r in local_rows)
            and all(r["opposed"] for r in reads)
            and len(reads) == 3
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0273-probe1 spread comparison")
        return 1
    print(
        "SUCCESS:IMP-0273-probe1 paired spread > unpaired on 10 questions; "
        "3 transcripts opposed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
