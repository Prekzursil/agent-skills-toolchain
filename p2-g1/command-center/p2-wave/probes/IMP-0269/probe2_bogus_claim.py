"""IMP-0269 probe 2: a merely-asserted expertise claim cannot be seated.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0269/probe2_bogus_claim.py
Exit 0 iff the live select_expertise() seats only claimants whose
demonstrated-competence probe passes (each seat carries probe results), the
assertion-only claimant is UNSEATED as hallucinated-expertise, the wrong-answer
and unanswerable-overclaim claimants are unseated too, and the unchecked
baseline WOULD have seated the assertion-only claimant (probe is load-bearing).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_expertise import (  # noqa: E402
    select_claimed_tags_unchecked,
    select_expertise,
)

FX = Path(__file__).resolve().parent / "fixtures"
doc = json.loads((FX / "candidates.json").read_text(encoding="utf-8"))
bank = json.loads((FX / "competence-bank.json").read_text(encoding="utf-8"))["bank"]
task = doc["task_tags"]
candidates = doc["candidates"]

sel = select_expertise(task, candidates, bank, baseline=0.5)
seated_ids = [s.participant_id for s in sel.seated]
unseated = {u.participant_id: u.reason for u in sel.unseated_claimants}
unchecked_ids = select_claimed_tags_unchecked(task, candidates)

checks = {
    "seated_experts": seated_ids == ["alice-crypto", "blake-tax"],
    "each_seat_has_probe_result": all(s.probe_results for s in sel.seated),
    "mallory_unseated": "mallory-asserted-crypto" not in seated_ids,
    "mallory_reason_hallucinated": unseated.get("mallory-asserted-crypto") == "hallucinated-expertise",
    "ned_unseated": "ned-wrong-crypto" not in seated_ids,
    "olga_unseated_overclaim": unseated.get("olga-overclaim-ua") == "unanswerable-overclaim",
    "no_overlap_skipped": sel.skipped_no_overlap == ["petra-botany"],
    "unchecked_would_seat_mallory": "mallory-asserted-crypto" in unchecked_ids,
    "probe_is_load_bearing": (
        "mallory-asserted-crypto" in unchecked_ids
        and "mallory-asserted-crypto" not in seated_ids
    ),
}
ok = all(checks.values())
out = {"probe": "probe2-bogus-claim-rejected", "unit_id": "IMP-0269",
       "seated_ids": seated_ids,
       "unseated_ids": sorted(unseated),
       "unseated_reasons": unseated,
       "unchecked_ids": unchecked_ids,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-bogus-claim.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0269-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0269-probe2 bogus expertise claims rejected; every seat carries a probe result")
