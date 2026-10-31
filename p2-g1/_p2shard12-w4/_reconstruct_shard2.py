#!/usr/bin/env python3
"""pendingReview per wave = S10_UNITS + THIS wave's built-awaiting-review (no cross-wave accumulation)."""
import json

S10 = ['IMP-0305','IMP-0306','IMP-0311','IMP-0323','IMP-0324','IMP-0329',
       'IMP-0330','IMP-0332','IMP-0333','IMP-0338','IMP-0350','IMP-0355']
res = json.load(open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_agent_results.json", encoding="utf-8"))

for wave in (1, 2, 3, 4):
    pending = list(S10); seen = set(pending)
    for si in range(24):
        label = f"build:w{wave}s{si}"
        if label not in res:
            continue
        for uid, state in res[label]["units"]:
            if state == "built-awaiting-review" and uid not in seen:
                pending.append(uid); seen.add(uid)
    n = len(pending); nsh = (n + 11)//12
    print(f"wave {wave}: pendingReview={n} -> {nsh} shards")
    if wave == 4:
        shards = [pending[i:i+12] for i in range(0, n, 12)]
        mine = shards[12]
        json.dump({"pendingReview_w4": pending, "shards": shards, "mine": mine},
                  open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_shard12_w4_units.json","w",encoding="utf-8"), indent=1)
        print("shard12 =", mine)
        for i in range(10, min(15, len(shards))):
            print(f"s{i} ({len(shards[i])}): {','.join(shards[i])}")
