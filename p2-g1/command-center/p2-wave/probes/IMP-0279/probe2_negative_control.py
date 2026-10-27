"""IMP-0279 probe 2: genuinely diverse rosters pass; the detector is not
constant-firing (negative control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0279/probe2_negative_control.py
Exit 0 iff the live dupes.audit_roster: a fully diverse 8-seat roster
(distinct vendor/model/prompt/tools, dissimilar independent outputs) audits
to effective_independence_count == 8 with ZERO flagged clusters and is
CORROBORATED by the independent output-similarity read; and a mixed roster
(2 clones + 6 distinct) reports BOTH the one flagged cluster and the
distinct remainder (effective count 7), so the count tracks configuration,
not seat count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "integrity"))
from dupes import audit_roster  # noqa: E402

VENDORS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]
MODELS = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"]
TEXTS = [
    "Option one maximises long-run reliability for the fleet.",
    "The charter obliges us to weight cost above latency here.",
    "Security review must precede any rollout of this change.",
    "Users reported the current flow already meets the need.",
    "Rollback safety is the decisive factor in my assessment.",
    "Data residency rules constrain where this may run.",
    "Throughput evidence favours the second architecture.",
    "Maintenance burden tips my vote toward the simpler design.",
]
diverse = [
    {
        "seat_id": f"s{i}", "name": f"N{i}", "role": "panelist",
        "vendor": f"vendor-{VENDORS[i]}", "model": f"model-{MODELS[i]}",
        "system_prompt": f"Specialty {i}: {VENDORS[i]} view.",
        "tools": ["search"] if i % 2 else ["shell"],
        "context": f"partition-{i}",
    }
    for i in range(8)
]
rep_diverse = audit_roster(diverse, TEXTS)

mixed_seats = [dict(diverse[0], seat_id="clone-a", name="CA"), dict(diverse[0], seat_id="clone-b", name="CB")] + diverse[2:8]
mixed_texts = [TEXTS[0], TEXTS[0]] + TEXTS[2:8]
rep_mixed = audit_roster(mixed_seats, mixed_texts)

checks = {
    "diverse_count_8": rep_diverse["effective_independence_count"] == 8,
    "diverse_zero_flags": rep_diverse["duplicate_cluster_count"] == 0,
    "diverse_similarity_low": rep_diverse["similarity"]["mean_pairwise_jaccard"] < 0.35,
    "diverse_corroborated": rep_diverse["corroboration"]["verdict"] == "CORROBORATED",
    "not_constant_firing": rep_diverse["effective_independence_count"] > 1,
    "mixed_flags_one_cluster": rep_mixed["duplicate_cluster_count"] == 1
    and rep_mixed["flagged"][0]["size"] == 2,
    "mixed_effective_count_7": rep_mixed["effective_independence_count"] == 7,
    "mixed_corroborated": rep_mixed["corroboration"]["verdict"] == "CORROBORATED",
}
ok = all(checks.values())
out = {"probe": "probe2-negative-control", "unit_id": "IMP-0279",
       "diverse_effective_count": rep_diverse["effective_independence_count"],
       "diverse_flags": rep_diverse["duplicate_cluster_count"],
       "mixed_effective_count": rep_mixed["effective_independence_count"],
       "mixed_flag_sizes": [f["size"] for f in rep_mixed["flagged"]],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-negative-control.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0279-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0279-probe2 diverse roster counts 8 with no flags; mixed roster flags exactly the clone pair")
