#!/usr/bin/env python3
"""Reconstruct pendingReview ordering -> wave-4 review shard 12 units."""
import json

S10 = ['IMP-0305', 'IMP-0306', 'IMP-0311', 'IMP-0323', 'IMP-0324', 'IMP-0329',
       'IMP-0330', 'IMP-0332', 'IMP-0333', 'IMP-0338', 'IMP-0350', 'IMP-0355']

res = json.load(open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_agent_results.json", encoding="utf-8"))

pending = list(S10)
seen = set(pending)
wave_cum = {}
for wave in (1, 2, 3, 4):
    for si in range(24):
        label = f"build:w{wave}s{si}"
        if label not in res:
            continue
        for uid, state in res[label]["units"]:
            if state == "built-awaiting-review" and uid not in seen:
                pending.append(uid)
                seen.add(uid)
    wave_cum[wave] = len(pending)
    print(f"after wave {wave}: cumulative pendingReview = {len(pending)}")

shards4 = [pending[i:i+12] for i in range(0, len(pending), 12)]
print(f"wave-4 review shards: {len(shards4)}")
mine = shards4[12]
json.dump({"pendingReview": pending, "shards4": shards4, "mine": mine, "wave_cum": wave_cum},
          open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_shard12_w4_units.json", "w", encoding="utf-8"), indent=1)
print("shard12:", mine)
for i in (10, 11, 12, 13, 14):
    if i < len(shards4):
        print(f"s{i} ({len(shards4[i])}): {','.join(shards4[i])}")
