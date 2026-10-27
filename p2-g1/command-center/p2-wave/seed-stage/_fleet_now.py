#!/usr/bin/env python3
"""One-shot 18-box probe: leftover 281 + G-1 fix + agent counts."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
OUT = WAVE / "ovh-monitor" / "fleet-now.json"
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
import json, subprocess
from pathlib import Path

def jload(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None

hb = jload('/opt/p2/supervisor-heartbeat.json') or {}
fix = jload('/opt/p2/g1-fix.json')
fails = jload('/opt/p2/g1-fails.json') or []
fan = jload('/opt/p2/g1-fan.json')
lp = Path('/opt/p2/g1-fix.log')
log_lines = lp.read_text(errors='replace').splitlines() if lp.exists() else []
ok_ids = []
fixing = None
for line in log_lines:
    if line.startswith('FIX '):
        fixing = line.split()[1] if len(line.split())>1 else None
    elif line.startswith('OK '):
        ok_ids.append(line.split()[1])
fail_ids = []
for rec in fails:
    uid = rec['id'] if isinstance(rec, dict) else rec
    fail_ids.append(uid)
pending = [u for u in fail_ids if u not in ok_ids]
svc = subprocess.run(['systemctl','is-active','p2-supervisor'], capture_output=True, text=True).stdout.strip()
def cnt(pat):
    r = subprocess.run(['pgrep','-cf', pat], capture_output=True, text=True)
    try:
        return int((r.stdout or '0').strip() or 0)
    except Exception:
        return 0
print(json.dumps({
    'svc': svc,
    'hb_ok': hb.get('ok'),
    'in_flight': hb.get('in_flight_n'),
    'queued': hb.get('queued_n'),
    'launched': hb.get('launched'),
    'queued_head': (hb.get('queued_head') or [])[:3],
    'g1_done': bool(fix),
    'g1_ok': (fix or {}).get('ok'),
    'g1_n': (fix or {}).get('n'),
    'g1_fail': (fix or {}).get('fail') or [],
    'g1_last': (log_lines[-1] if log_lines else '')[-160:],
    'g1_ok_ids': ok_ids,
    'g1_pending': pending,
    'g1_fixing': None if fix else fixing,
    'leftover_agents': cnt('on this Linux worktree'),
    'g1fix_agents': cnt('Fix THIS unit only'),
    'fixpy': cnt('fix_g1_fails.py'),
    'fanpy': cnt('fix_g1_fan.py'),
    'fan_ok': (fan or {}).get('ok') if fan else None,
    'fan_n': (fan or {}).get('n') if fan else None,
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
        rec["err"] = ((p.stderr or "") + (p.stdout or ""))[-240:]
        rec["st"] = "DOWN"
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["err"] = f"parse:{exc} {(p.stdout or '')[-180:]}"
        rec["st"] = "DOWN"
    return rec


def main() -> None:
    rows = []
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *b) for b in FLEET]
        for f in as_completed(futs):
            rec = f.result()
            rows.append(rec)
            g1 = "DONE" if rec.get("g1_done") else ("RUN" if rec.get("g1_fixing") else "IDLE")
            print(
                f"{rec['name']:8s} svc={rec.get('svc')} hb_ok={rec.get('hb_ok')} "
                f"inf={rec.get('in_flight')} q={rec.get('queued')} leftover={rec.get('leftover_agents')} "
                f"g1fix={rec.get('g1fix_agents')} {g1} pending={rec.get('g1_pending')} "
                f"last={(rec.get('g1_last') or '')[:70]}",
                flush=True,
            )
    rows.sort(key=lambda r: r["name"])
    pending = []
    for r in rows:
        for uid in r.get("g1_pending") or []:
            pending.append({"box": r["name"], "ip": r["ip"], "id": uid, "fixing": r.get("g1_fixing")})
    payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "boxes": rows,
        "g1_pending": pending,
        "leftover_ok": sum(int(r.get("hb_ok") or 0) for r in rows),
        "leftover_inf": sum(int(r.get("in_flight") or 0) for r in rows),
        "leftover_q": sum(int(r.get("queued") or 0) for r in rows),
        "leftover_agents": sum(int(r.get("leftover_agents") or 0) for r in rows),
        "g1fix_agents": sum(int(r.get("g1fix_agents") or 0) for r in rows),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"SUM leftover_ok={payload['leftover_ok']} inf={payload['leftover_inf']} "
        f"q={payload['leftover_q']} leftover_agents={payload['leftover_agents']} "
        f"g1fix_agents={payload['g1fix_agents']} g1_pending={len(pending)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
