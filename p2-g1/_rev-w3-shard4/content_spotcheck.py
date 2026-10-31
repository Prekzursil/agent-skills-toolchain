#!/usr/bin/env python3
"""Adversarial content spot-check for the 12 shard-4 w3 artifacts.
Reads each artifact, prints the load-bearing fields a reviewer must eyeball:
self state, verdicts per target, controls, honest NOT-CHECKED disclosure.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}

for uid in MY:
    e = byid[uid]
    art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
    print("=" * 90)
    print(uid, "|", e["title"])
    print("  state:", art.get("state"), "| status:", art.get("status"),
          "| verdict:", art.get("verdict"), "| reviewer_verdict:", art.get("reviewer_verdict"))
    # verdict-bearing collections
    for key in ("verdicts", "targets", "findings", "rows"):
        v = art.get(key)
        if isinstance(v, list) and v:
            sample = v[0]
            if isinstance(sample, dict):
                vk = [k for k in sample.keys() if "verdict" in k.lower() or "status" in k.lower()]
                counts = {}
                for row in v:
                    for k in vk:
                        val = row.get(k)
                        if isinstance(val, str):
                            counts[val] = counts.get(val, 0) + 1
                if counts:
                    print(f"  {key}: {len(v)} rows, verdict-ish counts: {counts}")
    # controls / negative tests
    for key in ("control", "controls", "negative_controls", "clean_control", "control_ok"):
        v = art.get(key)
        if v is not None and key != "control_ok":
            print(f"  {key}: {json.dumps(v)[:220]}")
        elif key == "control_ok":
            print(f"  control_ok: {v}")
    # honest gaps
    blob = json.dumps(art)
    nc = blob.count("NOT-CHECKED")
    print(f"  NOT-CHECKED mentions: {nc}")
    q = art.get("question") or art.get("question_or_target") or art.get("headline")
    if q:
        print("  question/headline:", str(q)[:220])
    a = art.get("answer")
    if a:
        print("  answer:", str(a)[:320])
