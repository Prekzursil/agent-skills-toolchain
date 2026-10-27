"""IMP-0274 probe 1: elastic scale-up trigger conditions.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0274/probe1_scale_up.py
Exit 0 iff the live tools/council/participants/elastic.scale_decision:
recruits within min/max when required coverage or mid-run expertise is
missing; holds when no gap; at max capacity reports the gap instead of
recruiting (unfilled); and never exceeds max_seats.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from elastic import scale_decision  # noqa: E402


def base_run(seat_tags, required, topics, seats=3, max_seats=6):
    return {
        "seats": [
            {"seat_id": f"s{i + 1}", "role": "panelist", "expertise": [t], "original": True}
            for i, t in enumerate(seat_tags)
        ],
        "required_coverage": required,
        "mid_run_topics": topics,
        "candidates": [
            {"seat_id": "r-security", "role": "panelist", "expertise": ["security"]},
            {"seat_id": "r-crypto", "role": "panelist", "expertise": ["cryptography"]},
        ],
        "max_seats": max_seats,
        "min_seats": 3,
    }


rows = []

d1 = scale_decision(base_run(["privacy", "policy", "law"], ["security"], []))
rows.append({"id": "coverage-gap-recruits", "pass": (
    d1.action == "recruit" and d1.recruit_count == 1
    and d1.missing_tags == ["security"] and d1.reason == "coverage_or_expertise_gap"
)})

d2 = scale_decision(base_run(["privacy", "security"], ["security"], []))
rows.append({"id": "no-gap-holds", "pass": (
    d2.action == "hold" and d2.recruit_count == 0 and d2.reason == "no_gap"
)})

d3 = scale_decision(base_run(["privacy", "policy", "law", "ops", "art", "bio"], ["security"], [], seats=6))
rows.append({"id": "at-max-reports-gap", "pass": (
    d3.action == "hold" and d3.reason == "at_max_with_gap"
    and d3.missing_tags == ["security"] and d3.current_seats == d3.max_seats == 6
)})

d4 = scale_decision(base_run(["privacy", "policy", "law"], [], ["cryptography"]))
rows.append({"id": "expertise-gap-recruits", "pass": (
    d4.action == "recruit" and d4.missing_tags == ["cryptography"]
)})

d5 = scale_decision(base_run(["privacy", "policy"], ["security", "cryptography"], [], seats=3, max_seats=4))
rows.append({"id": "recruit_never_exceeds_max", "pass": (
    d5.action == "recruit"
    and d5.recruit_count == min(len(d5.missing_tags), d5.max_seats - d5.current_seats)
    and d5.current_seats + d5.recruit_count <= d5.max_seats
)})

checks = {"all_trigger_cases_pass": all(r["pass"] for r in rows), "cases_are_5": len(rows) == 5}
ok = all(checks.values())
out = {"probe": "probe1-scale-up", "unit_id": "IMP-0274",
       "rows": rows, "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-scale-up.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0274-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0274-probe1 scale-up triggers fire on coverage/expertise gaps; max respected")
