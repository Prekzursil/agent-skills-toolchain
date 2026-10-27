"""IMP-0279 probe 1: eight copies of one configuration are ONE voice.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0279/probe1_effective_voice.py
Exit 0 iff the live tools/council/integrity/dupes.audit_roster reports
effective_independence_count == 1 for eight seats that share vendor, model,
system prompt, tools (up to tool-ORDER permutation) and context while having
distinct seat_id/name/role labels (identity fields are excluded from the
fingerprint), flags exactly one duplicate cluster of size 8, and the
independent output-similarity read (mean pairwise token Jaccard 1.0 on
identical first-round texts) corroborates the config-level verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "integrity"))
from dupes import audit_roster  # noqa: E402

TOOLS = ["search", "grep", "shell"]
clones = []
for i in range(8):
    rotated = TOOLS[i % 3:] + TOOLS[: i % 3]  # tool-order permutation, same set
    clones.append({
        "seat_id": f"seat-{i}",
        "name": f"Panelist {chr(65 + i)}",
        "role": ["chair", "panelist", "critic", "scribe"][i % 4],
        "vendor": "single-vendor",
        "model": "single-model-7b",
        "system_prompt": "You are an independent council expert.",
        "tools": rotated,
        "context": "partition-A",
    })
outputs = ["I support option one because the evidence is strongest."] * 8

report = audit_roster(clones, outputs)

checks = {
    "effective_independence_count_1": report["effective_independence_count"] == 1,
    "seat_count_8": report["seat_count"] == 8,
    "one_flagged_cluster_of_8": report["duplicate_cluster_count"] == 1
    and report["flagged"][0]["size"] == 8,
    "identity_fields_excluded": sorted(report["identity_fields_excluded"]) == ["label", "name", "seat_id"],
    "tool_order_permutation_still_clone": report["effective_independence_count"] == 1,
    "mean_jaccard_1": report["similarity"]["mean_pairwise_jaccard"] == 1.0,
    "corroborated": report["corroboration"]["verdict"] == "CORROBORATED"
    and report["corroboration"]["agrees"] is True,
}
ok = all(checks.values())
out = {"probe": "probe1-effective-voice", "unit_id": "IMP-0279",
       "seat_count": report["seat_count"],
       "effective_independence_count": report["effective_independence_count"],
       "duplicate_cluster_count": report["duplicate_cluster_count"],
       "flagged_sizes": [f["size"] for f in report["flagged"]],
       "similarity": report["similarity"],
       "corroboration": report["corroboration"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-effective-voice.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0279-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0279-probe1 8 clones of one config audit to effective independence 1, CORROBORATED")
