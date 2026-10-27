#!/usr/bin/env python3
"""Pull remesure-281 fail_ids + leftover G-1 remaining from all 18 boxes."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
OUT = WAVE / "ovh-monitor" / "rm281-summary.json"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
FLEET = [
    ("gra11-a", "176.31.201.117"),
    ("gra11-c", "176.31.201.215"),
    ("waw1-b", "51.75.63.116"),
    ("waw1-c", "54.38.138.226"),
    ("de1-a", "51.75.93.252"),
    ("de1-c", "162.19.209.251"),
    ("gra9-b", "37.59.27.161"),
    ("gra9-c", "141.94.186.60"),
    ("rbx-a", "164.132.87.22"),
    ("rbx-c", "152.228.192.99"),
    ("par-a", "57.130.47.223"),
    ("par-c", "57.130.46.182"),
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
    ("sbg5-a", "57.128.35.67"),
    ("sbg5-c", "57.128.111.33"),
    ("gra7-a", "51.91.140.54"),
    ("gra7-c", "51.210.248.225"),
]
REMOTE = r"""
import json
from pathlib import Path

def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None
rm = load('/opt/p2/remeasure-281.json')
g1 = load('/opt/p2/g1-fix.json')
fan = load('/opt/p2/g1-fan.json')
log=''
p=Path('/opt/p2/g1-fix.log')
if p.exists():
    lines=p.read_text(errors='replace').splitlines()
    log=lines[-1] if lines else ''
flog=''
p=Path('/opt/p2/g1-fan.log')
if p.exists():
    lines=p.read_text(errors='replace').splitlines()
    flog=lines[-1] if lines else ''
rlog=''
p=Path('/opt/p2/remeasure-281.out')
if p.exists():
    lines=p.read_text(errors='replace').splitlines()
    rlog=lines[-1] if lines else ''
print(json.dumps({
    'rm': None if not rm else {'n': rm.get('n'), 'ok': rm.get('ok'), 'fail': rm.get('fail_ids') or []},
    'g1': None if not g1 else {'n': g1.get('n'), 'ok': g1.get('ok'), 'fail': g1.get('fail') or []},
    'fan': None if not fan else {'n': fan.get('n'), 'ok': fan.get('ok'), 'fail': fan.get('fail') or []},
    'g1_last': log[-160:],
    'fan_last': flog[-160:],
    'rm_last': rlog[-160:],
}))
"""


def one(name, ip):
    payload = __import__("base64").b64encode(REMOTE.strip().encode()).decode()
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=25)
    rec = {"name": name, "ip": ip, "rc": p.returncode}
    if p.returncode != 0:
        rec["err"] = ((p.stderr or "") + (p.stdout or ""))[-180:]
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["err"] = f"parse:{exc}"
    return rec


def main():
    rows = []
    fails = []
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *b) for b in FLEET]
        for f in as_completed(futs):
            rec = f.result()
            rows.append(rec)
            rm = rec.get("rm") or {}
            g1 = rec.get("g1") or {}
            fan = rec.get("fan")
            print(
                f"{rec['name']:8s} rm={rm.get('ok')}/{rm.get('n')} fail={rm.get('fail')} "
                f"g1={g1.get('ok')}/{g1.get('n')} fan={None if not fan else fan} "
                f"g1last={(rec.get('g1_last') or '')[:50]}",
                flush=True,
            )
            for uid in rm.get("fail") or []:
                fails.append({"box": rec["name"], "ip": rec["ip"], "id": uid})
    rows.sort(key=lambda r: r["name"])
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rm_fail": fails,
        "boxes": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"rm281 fails={len(fails)}", flush=True)


if __name__ == "__main__":
    main()
