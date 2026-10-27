#!/usr/bin/env python3
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull" / "remeasure"
BOX_IP = {
    "gra11-a": "176.31.201.117",
    "gra11-c": "176.31.201.215",
    "waw1-b": "51.75.63.116",
    "waw1-c": "54.38.138.226",
    "de1-a": "51.75.93.252",
    "de1-c": "162.19.209.251",
    "gra9-b": "37.59.27.161",
    "gra9-c": "141.94.186.60",
    "rbx-a": "164.132.87.22",
    "rbx-c": "152.228.192.99",
    "par-a": "57.130.47.223",
    "par-c": "57.130.46.182",
    "uk1-a": "54.37.3.247",
    "uk1-c": "54.37.7.164",
    "sbg5-a": "57.128.35.67",
    "sbg5-c": "57.128.111.33",
    "gra7-a": "51.91.140.54",
    "gra7-c": "51.210.248.225",
}
ok = fail = n = 0
fails = []
for f in sorted(DIR.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    n += int(d.get("n") or 0)
    ok += int(d.get("ok") or 0)
    fail += int(d.get("fail") or 0)
    box = f.stem
    for r in d.get("results") or []:
        if r.get("ok"):
            continue
        fails.append(
            {
                "box": box,
                "ip": BOX_IP[box],
                "id": r.get("id"),
                "line": r.get("line"),
                "rc": r.get("rc"),
            }
        )
out = {
    "n": n,
    "ok": ok,
    "fail": fail,
    "pass_pct": round(100.0 * ok / n, 2) if n else 0,
    "fails": fails,
}
dest = DIR.parent / "g1-remeasure-summary.json"
dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(f"n={n} ok={ok} fail={fail} pass={out['pass_pct']}% wrote {dest}")
for row in fails:
    print(f"{row['box']:10s} {row['id']:10s} {row['line']}")
