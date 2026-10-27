"""IMP-0273 probe 1: adversarial pairing raises first-round position spread.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0273/probe1_spread_experiment.py
Exit 0 iff, on the live tools/council/participants/select_adversarial module:
over the 10 matched questions the paired (proposer+refuter) council's
first-round polarity spread beats the same-size sequential unpaired council
on every question; the genuinely opposed refuters are the ones seated
(R-neg-1, R-neg-2, C-neg-4); the label-trap participant whose POSITION agrees
with the proposers is never seated as a refuter despite the label; and a
structured read of the first three pair transcripts confirms the refuters
actually opposed (I refute + distinct COUNTER, gap >= AGREE_DISTANCE).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_adversarial import (  # noqa: E402
    default_pool,
    default_questions,
    run_matched_experiment,
    select_adversarial,
    structured_opposition_read,
)

pool = default_pool()
questions = default_questions()
exp = run_matched_experiment(pool, questions, n_proposers=3)

rows = exp["rows"]
all_paired_greater = all(r["paired_gt_unpaired"] for r in rows)

sel = select_adversarial(pool, n_proposers=3)
refuter_ids = [s.participant.participant_id for s in sel.seats if s.role == "refuter"]
label_trap_seated_as_refuter = "R-label-only" in refuter_ids

reads = []
for tr in exp["transcripts"][:3]:
    for pair in tr["pairs"]:
        reads.append(structured_opposition_read(pair["proposer_text"], pair["refuter_text"]))
        break
all_three_opposed = len(reads) >= 3 and all(r["opposed"] for r in reads[:3])

checks = {
    "n_questions_10": len(rows) == 10,
    "all_paired_greater": all_paired_greater,
    "refuters_are_opposed_cluster": sorted(refuter_ids) == ["C-neg-3", "R-neg-1", "R-neg-2"],
    "label_trap_not_seated_as_refuter": label_trap_seated_as_refuter is False,
    "structured_read_all_opposed": all_three_opposed,
    "gaps_above_agree_distance": all(r["gap"] >= 1.0 for r in reads[:3]),
}
ok = all(checks.values())
out = {"probe": "probe1-spread-experiment", "unit_id": "IMP-0273",
       "n_questions": len(rows),
       "paired_wins": sum(1 for r in rows if r["paired_gt_unpaired"]),
       "paired_ids": [s.participant.participant_id for s in sel.seats if s.role == "proposer"],
       "refuter_ids": refuter_ids,
       "read_gaps": [round(r["gap"], 4) for r in reads[:3]],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-spread.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0273-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0273-probe1 paired spread > unpaired on 10/10; refuters opposed; label trap not seated")
