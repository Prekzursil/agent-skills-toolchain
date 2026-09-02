#!/usr/bin/env python3
"""Poll G-1 fix loops; write ovh-monitor/g1-fix-latest.md; stdout ALL-DONE when every box finished."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

OUT = Path(__file__).resolve().parent.parent / "ovh-monitor"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
FLEET = [
    ("gra11-a", "176.31.201.117", 1),
    ("gra11-c", "176.31.201.215", 1),
    ("waw1-b", "51.75.63.116", 3),
    ("waw1-c", "54.38.138.226", 1),
    ("de1-a", "51.75.93.252", 1),
    ("de1-c", "162.19.209.251", 3),
    ("gra9-b", "37.59.27.161", 2),
    ("gra9-c", "141.94.186.60", 5),
    ("rbx-a", "164.132.87.22", 5),
    ("rbx-c", "152.228.192.99", 7),
    ("par-a", "57.130.47.223", 2),
    ("par-c", "57.130.46.182", 7),
    ("uk1-a", "54.37.3.247", 5),
    ("uk1-c", "54.37.7.164", 4),
    ("sbg5-a", "57.128.35.67", 2),
    ("sbg5-c", "57.128.111.33", 3),
    ("gra7-a", "51.91.140.54", 3),
    ("gra7-c", "51.210.248.225", 3),
]
CMD = r"""
import json
from pathlib import Path
st='RUN'
ok=n=None
fail=[]
last=''
if Path('/opt/p2/g1-fix.json').is_file():
    st='DONE'
    d=json.loads(Path('/opt/p2/g1-fix.json').read_text())
    ok=d.get('ok'); n=d.get('n'); fail=d.get('fail') or []
lp=Path('/opt/p2/g1-fix.log')
if lp.exists():
    lines=lp.read_text(errors='replace').splitlines()
    last=lines[-1] if lines else ''
print(json.dumps({'st':st,'ok':ok,'n':n,'fail':fail,'last':last[-180:]}))
"""


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe(name: str, ip: str, expect: int) -> dict:
    payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
    p = run(
        SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    rec = {"name": name, "ip": ip, "expect": expect, "reachable": p.returncode == 0}
    if p.returncode != 0:
        rec["st"] = "DOWN"
        rec["error"] = ((p.stderr or "") + (p.stdout or ""))[-200:]
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["st"] = "DOWN"
        rec["error"] = str(exc)
    return rec


def snapshot() -> dict:
    boxes = []
    with ThreadPoolExecutor(18) as pool:
        futs = {pool.submit(probe, *row): row[0] for row in FLEET}
        for f in as_completed(futs):
            boxes.append(f.result())
    boxes.sort(key=lambda b: b["name"])
    done = [b for b in boxes if b.get("st") == "DONE"]
    runn = [b for b in boxes if b.get("st") == "RUN"]
    down = [b for b in boxes if b.get("st") == "DOWN"]
    ok_sum = sum(int(b.get("ok") or 0) for b in done)
    n_sum = sum(int(b.get("n") or 0) for b in done)
    fail_ids = []
    for b in done:
        fail_ids.extend(b.get("fail") or [])
    expect_total = sum(r[2] for r in FLEET)
    return {
        "ts": utc(),
        "done_boxes": len(done),
        "run_boxes": len(runn),
        "down_boxes": len(down),
        "ok_sum": ok_sum,
        "n_sum": n_sum,
        "fail_ids": fail_ids,
        "expect_total": expect_total,
        "boxes": boxes,
    }


def render(snap: dict) -> str:
    lines = [
        f"# G-1 fix loop — {snap['ts']}",
        "",
        f"boxes DONE **{snap['done_boxes']}/18**  RUN {snap['run_boxes']}  DOWN {snap['down_boxes']}",
        f"finished units **{snap['ok_sum']}/{snap['n_sum']}** PASS (of {snap['expect_total']} expected FAILs)",
    ]
    if snap["fail_ids"]:
        lines.append("still FAIL after fix: " + ", ".join(snap["fail_ids"]))
    lines += ["", "| box | st | ok/n | last |", "|---|---|---|---|"]
    for b in snap["boxes"]:
        on = f"{b.get('ok')}/{b.get('n')}" if b.get("st") == "DONE" else "—"
        last = str(b.get("last") or b.get("error") or "")[:80].replace("|", "/")
        lines.append(f"| {b['name']} | {b.get('st')} | {on} | `{last}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    def tick(prev=None):
        snap = snapshot()
        (OUT / "g1-fix-latest.json").write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        md = render(snap)
        (OUT / "g1-fix-latest.md").write_text(md, encoding="utf-8")
        line = (
            f"TICK {snap['ts']} done_boxes={snap['done_boxes']}/18 "
            f"ok={snap['ok_sum']}/{snap['n_sum']} run={snap['run_boxes']} down={snap['down_boxes']}"
        )
        with (OUT / "g1-fix-watch.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if not args.quiet:
            print(line, flush=True)
            print(md, flush=True)
        if snap["down_boxes"]:
            print("ALERT DOWN " + ",".join(b["name"] for b in snap["boxes"] if b.get("st") == "DOWN"), flush=True)
        if snap["done_boxes"] == 18 and snap["down_boxes"] == 0:
            print(
                f"ALL-DONE ok={snap['ok_sum']}/{snap['n_sum']} still_fail={len(snap['fail_ids'])}",
                flush=True,
            )
            return snap, True
        return snap, False

    snap, finished = tick()
    if args.once or finished or args.watch <= 0:
        return 0
    while True:
        time.sleep(max(45, args.watch))
        snap, finished = tick(snap)
        if finished:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
