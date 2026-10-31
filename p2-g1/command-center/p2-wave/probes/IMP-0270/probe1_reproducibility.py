"""IMP-0270 probe 1: a run reproduces seat-for-seat from the recorded seed.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0270/probe1_reproducibility.py
Exit 0 iff the live tools/council/participants/select_random samplers: two
runs with the same recorded seed produce identical ordered rosters (uniform
and stratified), reproduce() replays a recorded run from the seed alone, a
different seed produces a different roster, and an unseeded run RECORDS its
fresh-entropy seed in the artifact (seed_source=fresh-entropy).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_random import reproduce, roster_matches, select_stratified, select_uniform  # noqa: E402

SEED = 20260824
pool = [
    {"id": f"{vendor}-{i:02d}", "vendor": vendor}
    for vendor in ("anthropic", "google", "openai")
    for i in range(8)
]
quotas = {"anthropic": 2, "google": 2, "openai": 2}

u1 = select_uniform(pool, 6, seed=SEED)
u2 = select_uniform(pool, 6, seed=SEED)
u_other = select_uniform(pool, 6, seed=SEED + 1)
s1 = select_stratified(pool, quotas, seed=SEED)
s2 = select_stratified(pool, quotas, seed=SEED)
s_replay = reproduce(s1, pool)
u_replay = reproduce(u1, pool)
s_other = select_stratified(pool, quotas, seed=SEED + 1)
fresh = select_uniform(pool, 6, seed=None)

checks = {
    "uniform_same_seed_identical": roster_matches(u1, u2),
    "uniform_seed_recorded_caller": u1["seed"] == SEED and u1["seed_source"] == "caller",
    "uniform_other_seed_differs": not roster_matches(u1, u_other),
    "stratified_same_seed_identical": roster_matches(s1, s2),
    "stratified_replay_from_seed": roster_matches(s1, s_replay),
    "uniform_replay_from_seed": roster_matches(u1, u_replay),
    "stratified_other_seed_differs": not roster_matches(s1, s_other),
    "stratified_census_matches_quotas": s1["stratum_census"] == quotas,
    "fresh_entropy_recorded": fresh["seed_source"] == "fresh-entropy" and isinstance(fresh["seed"], int),
    "fresh_replay_match": roster_matches(fresh, reproduce(fresh, pool)),
}
ok = all(checks.values())
out = {"probe": "probe1-reproducibility", "unit_id": "IMP-0270",
       "seed": SEED,
       "uniform_roster_ids": u1["roster_ids"],
       "stratified_roster_ids": s1["roster_ids"],
       "fresh_entropy_recorded_seed": fresh["seed"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-reproducibility.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0270-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0270-probe1 same recorded seed reproduces both samplers seat-for-seat; unseeded records entropy")
