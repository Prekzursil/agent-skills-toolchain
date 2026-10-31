"""IMP-0274 probe 2: recruited seats get the information partition, not the
consensus (both-states independence control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0274/probe2_independence.py
Exit 0 iff, on the live elastic module: an honest recruit shares question,
shared_evidence and catch_up_facts with the original seat and holds NO
consensus keys (context_diff.partition_match true, leak false) and its first
output is NOT the consensus (independence_check SILENT); a recruit fed the
consensus transcript leaks it (context_diff.bad shows the forbidden keys,
partition_match false), drafts the consensus verbatim (token Jaccard 1.0),
and independence_check FIRES with output-echoes-consensus +
forbidden-consensus-key.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from elastic import (  # noqa: E402
    context_diff,
    draft_first_position,
    feed_consensus_transcript,
    first_original_context,
    independence_check,
    recruit,
)

CONSENSUS = "Ship the workaround that skips the bounds check and mark the ticket closed."
run = {
    "question": "Do we ship the bounds-check fix this release?",
    "shared_evidence": ["EV-1 crash report", "EV-2 upstream patch"],
    "catch_up_facts": ["the fix missed code-freeze", "two regressions were filed"],
    "running_consensus": CONSENSUS,
    "transcript": [{"seat_id": "s1", "position": CONSENSUS}],
    "seats": [
        {"seat_id": "s1", "role": "chair", "expertise": ["release"], "original": True},
        {"seat_id": "s2", "role": "panelist", "expertise": ["qa"], "original": True},
        {"seat_id": "s3", "role": "panelist", "expertise": ["ops"], "original": True},
    ],
    "required_coverage": ["security"],
    "mid_run_topics": [],
    "candidates": [{"seat_id": "r-security", "role": "refuter", "expertise": ["security"]}],
    "max_seats": 6,
    "min_seats": 3,
}

orig_seat_id, orig_ctx = first_original_context(run)
honest = recruit(run, leak_consensus=False)
bad = recruit(run, leak_consensus=True)

rec_honest = honest.recruited[0]
rec_bad = bad.recruited[0]

diff_good = context_diff(orig_ctx, rec_honest["context"],
                         original_seat_id=orig_seat_id, recruit_seat_id=rec_honest["seat_id"])
diff_bad = context_diff(orig_ctx, rec_bad["context"],
                        original_seat_id=orig_seat_id, recruit_seat_id=rec_bad["seat_id"])

bad_ctx = feed_consensus_transcript(dict(orig_ctx), CONSENSUS)
bad_output = draft_first_position(bad_ctx)

def jaccard(a, b):
    ta, tb = set(a.lower().split()), set(b.lower().split())
    return len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0

chk_silent = independence_check(rec_honest["context"], rec_honest["first_output"], CONSENSUS)
chk_fire = independence_check(bad_ctx, bad_output, CONSENSUS)

checks = {
    "honest_partition_shared": all([
        diff_good.question_equal, diff_good.shared_evidence_equal, diff_good.partition_match,
    ]),
    "honest_no_consensus_keys": diff_good.consensus_leaked_to_recruit is False
    and diff_good.forbidden_on_recruit == [],
    "honest_check_silent": chk_silent.fired is False,
    "bad_partition_mismatch": diff_bad.partition_match is False
    and diff_bad.consensus_leaked_to_recruit is True,
    "bad_forbidden_keys_present": sorted(diff_bad.forbidden_on_recruit) == ["running_consensus", "transcript"],
    "bad_output_echoes_consensus": jaccard(bad_output, CONSENSUS) == 1.0,
    "bad_check_fires": chk_fire.fired is True
    and "output-echoes-consensus" in chk_fire.reasons
    and "forbidden-consensus-key" in chk_fire.reasons,
    "recruit_has_no_extra_keys_beyond_original": set(rec_honest["context"]) <= {
        "question", "shared_evidence", "catch_up_facts"},
}
ok = all(checks.values())
out = {"probe": "probe2-independence-and-context-diff", "unit_id": "IMP-0274",
       "context_diff_good": diff_good.to_dict(),
       "context_diff_bad": diff_bad.to_dict(),
       "bad_first_output": bad_output,
       "jaccard_bad_output_vs_consensus": jaccard(bad_output, CONSENSUS),
       "silent_check": chk_silent.to_dict(),
       "fire_check": chk_fire.to_dict(),
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-independence.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0274-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0274-probe2 honest recruit holds the partition (silent); fed-consensus recruit FIRES")
