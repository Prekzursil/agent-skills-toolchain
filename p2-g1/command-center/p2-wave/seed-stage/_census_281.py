#!/usr/bin/env python3
"""Union completed.json vs 281 prior IDs; leftover remaining + remesure-281 progress."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
PRIOR = WAVE / "P2-PRIOR-281_2026-08-24.json"
OUT = WAVE / "ovh-monitor" / "census-281.json"
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
done = []
d = load('/opt/p2/completed.json') or {}
done = [str(x) for x in (d.get('ids') or [])]
prior = []
lef = load('/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json') or {}
prior = [str(x) for x in (lef.get('remaining_ids') or [])]
ps = set(prior)
hit = [u for u in done if u in ps]
rm = load('/opt/p2/remeasure-281.json')
hb = load('/opt/p2/supervisor-heartbeat.json') or {}
fan = load('/opt/p2/g1-fan.json')
g1 = load('/opt/p2/g1-fix.json')
print(json.dumps({
    'done_n': len(done),
    'prior_n': len(prior),
    'hit': hit,
    'inf': hb.get('in_flight_n'),
    'queued': hb.get('queued_n'),
    'rm_n': None if not rm else rm.get('n'),
    'rm_ok': None if not rm else rm.get('ok'),
    'rm_fail': None if not rm else (rm.get('fail_ids') or []),
    'fan_ok': None if not fan else fan.get('ok'),
    'fan_n': None if not fan else fan.get('n'),
    'g1_ok': None if not g1 else g1.get('ok'),
    'g1_n': None if not g1 else g1.get('n'),
    'g1_fail': None if not g1 else (g1.get('fail') or []),
}))
"""


def one(name: str, ip: str) -> dict:
    payload = __import__("base64").b64encode(REMOTE.strip().encode()).decode()
    p = run(
        SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"],
        capture_output=True,
        text=True,
        timeout=25,
    )
    rec = {"name": name, "ip": ip, "rc": p.returncode}
    if p.returncode != 0:
        rec["err"] = ((p.stderr or "") + (p.stdout or ""))[-200:]
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["err"] = f"parse:{exc} {(p.stdout or '')[-160:]}"
    return rec


def main() -> None:
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))["remaining_ids"]
    prior_set = set(prior)
    rows = []
    hits = set()
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *b) for b in FLEET]
        for f in as_completed(futs):
            rec = f.result()
            rows.append(rec)
            for uid in rec.get("hit") or []:
                hits.add(uid)
            print(
                f"{rec['name']:8s} 281hit={len(rec.get('hit') or [])} inf={rec.get('inf')} "
                f"q={rec.get('queued')} rm={rec.get('rm_ok')}/{rec.get('rm_n')} "
                f"g1={rec.get('g1_ok')}/{rec.get('g1_n')} fan={rec.get('fan_ok')}/{rec.get('fan_n')}",
                flush=True,
            )
    missing = sorted(prior_set - hits)
    rows.sort(key=lambda r: r["name"])
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prior": len(prior_set),
        "hit": len(hits),
        "missing": len(missing),
        "missing_ids": missing,
        "boxes": [{k: v for k, v in r.items() if k != "hit"} | {"hit_n": len(r.get("hit") or [])} for r in rows],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"281 hit={len(hits)} missing={len(missing)}", flush=True)
    if missing[:12]:
        print("missing sample", missing[:12], flush=True)


if __name__ == "__main__":
    main()
