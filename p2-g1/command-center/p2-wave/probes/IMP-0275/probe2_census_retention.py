"""IMP-0275 probe 2: eviction retains prior contributions (census control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0275/probe2_census_retention.py
Exit 0 iff the live replace module: the contribution census before and after
eviction retains every prior vote and idea keyed by the evicted author_id
(no orphans, no remap); the recorded tally equals an independent
recomputation under the documented R-EVICT-RETAIN rule (closed rounds keep
the evicted member's votes, the open round excludes them); dropping the
evicted member's ideas FAILS census_retention_check (negative control); and
re-attributing a contribution to another author is DETECTED as a remap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from replace import census_retention_check, compute_tally, contribution_census, evict, make_run  # noqa: E402

run = make_run(dave_last_activity_at=140)
before = contribution_census(run)
after_run = evict(run, "dave")
after = contribution_census(after_run)

census_retained = after["by_author"].get("dave") == before["by_author"]["dave"]
tally = compute_tally(after_run)
tally_matches = (
    tally["rule_id"] == "R-EVICT-RETAIN"
    and tally["closed_rounds"]["1"]["counts"] == {"yes": 4}
    and tally["closed_rounds"]["1"]["includes_evicted"] == ["dave"]
    and tally["open_round"]["counts"] == {"yes": 3}
    and [c["author_id"] for c in tally["open_round"]["excluded_evicted"]] == ["dave"]
    and tally == after_run["tally"]
)

pruned = {"by_author": {k: [i for i in v if not (k == "dave" and i == "i-r1-dave")] for k, v in after["by_author"].items()}}
neg = census_retention_check(before, pruned)

remapped = {"by_author": {k: list(v) for k, v in after["by_author"].items()}}
victim = remapped["by_author"]["dave"][-1]
remapped["by_author"]["dave"] = remapped["by_author"]["dave"][:-1]
remapped["by_author"]["alice"].append(victim)
remap_res = census_retention_check(before, remapped)

checks = {
    "census_retained": census_retained,
    "orphan_ids_none": after["orphan_ids"] == [],
    "tally_matches_rule": tally_matches,
    "negative_control_fired": neg["ok"] is False and bool(neg["missing"]),
    "remap_detected": remap_res["ok"] is False and bool(remap_res["remapped"]),
    "evicted_prior_rounds_in_ledger": all(
        c["author_id"] == "dave" for c in after_run["contributions"] if c["author_id"] == "dave"
    ) and len(after["by_author"]["dave"]) == 3,
}
ok = all(checks.values())
out = {"probe": "probe2-census-retention", "unit_id": "IMP-0275",
       "census_retained": census_retained,
       "tally_matches": tally_matches,
       "negative_control_fired": checks["negative_control_fired"],
       "remap_detected": checks["remap_detected"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-census-retention.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0275-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0275-probe2 census retained across eviction; tally rule holds; drop/remap both detected")
