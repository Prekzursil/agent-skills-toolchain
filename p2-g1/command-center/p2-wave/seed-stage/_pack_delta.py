#!/usr/bin/env python3
"""Pack remesure receipts + 281/58 probe dirs only (not the whole probes tree)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
PRIOR = json.loads((WAVE / "P2-PRIOR-281_2026-08-24.json").read_text(encoding="utf-8"))["remaining_ids"]
FAIL58 = [
    r["id"]
    for r in json.loads((WAVE / "ovh-monitor" / "error-pull" / "g1-fail-details.json").read_text(encoding="utf-8")).get("rows")
    or []
    if not r.get("ok")
]
IDS = sorted(set(PRIOR) | set(FAIL58))
LIST_FILE = WAVE / "ovh-monitor" / "harvest-delta-ids.txt"
LIST_FILE.write_text("\n".join(IDS) + "\n", encoding="utf-8")
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
SCP = [
    "scp",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=15",
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
import json, subprocess, tarfile
from pathlib import Path
ids=Path('/tmp/harvest-delta-ids.txt').read_text().split()
root=Path('/opt/p2/ast-integrate/command-center/p2-wave/probes')
out=Path('/tmp/p2-delta.tgz')
members=[]
for p in ['/opt/p2/completed.json','/opt/p2/remeasure-281.json','/opt/p2/g1-fix.json','/opt/p2/g1-w3.json','/opt/p2/g1-w4.json']:
    if Path(p).exists():
        members.append(p)
dirs=[]
for uid in ids:
    d=root/uid
    if d.is_dir():
        dirs.append(str(d))
tf=tarfile.open(out,'w:gz')
for p in members:
    tf.add(p, arcname=Path(p).name)
for d in dirs:
    tf.add(d, arcname='probes/'+Path(d).name, filter=lambda m: None if 'node_modules' in m.name or m.name.endswith('.pyc') else m)
tf.close()
print('PACK', out.stat().st_size, 'files', len(members), 'dirs', len(dirs))
"""


def one(name, ip):
    host = f"root@{ip}"
    p = run(SCP + [str(LIST_FILE), f"{host}:/tmp/harvest-delta-ids.txt"], capture_output=True, text=True, timeout=25)
    if p.returncode != 0:
        return f"{name} SCP-LIST {(p.stderr or '')[-100:]}"
    payload = __import__("base64").b64encode(REMOTE.strip().encode()).decode()
    p = run(SSH + [host, f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=120)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode} {(p.stderr or '')[-80:]}"


def main():
    print(f"delta ids {len(IDS)}", flush=True)
    with ThreadPoolExecutor(4) as ex:
        for f in as_completed([ex.submit(one, *b) for b in FLEET]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
