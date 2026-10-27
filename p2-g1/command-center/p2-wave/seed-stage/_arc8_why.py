#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

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
JOBS = [
    ("de1-a", "51.75.93.252", "ARC-0003 ARC-0012"),
    ("gra9-b", "37.59.27.161", "ARC-0005 ARC-0014"),
    ("rbx-a", "164.132.87.22", "ARC-0007 ARC-0016"),
    ("par-a", "57.130.47.223", "ARC-0009"),
    ("waw1-b", "51.75.63.116", "ARC-0010"),
]
REMOTE = r"""
import json, sys
from pathlib import Path
uids = sys.argv[1:]
WAVE = Path('/opt/p2/ast-integrate/command-center/p2-wave')
done = set()
cp = Path('/opt/p2/completed.json')
if cp.exists():
    done = set(json.loads(cp.read_text()).get('ids') or [])
for uid in uids:
    d = WAVE/'probes'/uid
    retp = d/'SUBAGENT-RETURN.json'
    rec = {'id': uid, 'done': uid in done, 'dir': d.exists(), 'return': retp.exists()}
    sp = Path('/opt/p2/strikes')/f'{uid}.json'
    if sp.exists():
        s = json.loads(sp.read_text())
        rec['strikes'] = s.get('count')
        rec['parked'] = s.get('parked')
        rec['reason'] = s.get('park_reason')
    if retp.exists():
        r = json.loads(retp.read_text())
        rec['status'] = r.get('status') or r.get('state')
        rec['registered'] = r.get('registered')
        rec['mline'] = str(r.get('measure_line') or '')[:100]
    print(json.dumps(rec, separators=(',',':')))
"""


def one(name: str, ip: str, uids: str) -> str:
    payload = __import__("base64").b64encode(REMOTE.strip().encode()).decode()
    cmd = f"echo {payload} | base64 -d | python3 - {uids}"
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=25)
    return f"==== {name}\n{(p.stdout or '').strip()}\n{(p.stderr or '')[-200:]}"


def main() -> None:
    with ThreadPoolExecutor(5) as ex:
        futs = [ex.submit(one, *j) for j in JOBS]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
