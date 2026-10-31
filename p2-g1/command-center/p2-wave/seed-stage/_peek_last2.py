#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

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
BOXES = [
    ("rbx-c", "152.228.192.99"),
    ("de1-a", "51.75.93.252"),
]
CMD = r"""
from pathlib import Path
import json
def last(p, n=4):
    fp=Path(p)
    if not fp.exists():
        return 'missing'
    lines=fp.read_text(errors='replace').splitlines()
    return ' | '.join(lines[-n:])[-240:]
g1=Path('/opt/p2/g1-fix.json')
fan=Path('/opt/p2/g1-fan.json')
print('G1JSON', 'yes' if g1.exists() else 'no', end=' ')
if g1.exists():
    d=json.loads(g1.read_text()); print(d.get('ok'), d.get('n'), d.get('fail'))
else:
    print()
print('FANJSON', 'yes' if fan.exists() else 'no', end=' ')
if fan.exists():
    d=json.loads(fan.read_text()); print(d.get('ok'), d.get('n'), d.get('fail'))
else:
    print()
print('G1LOG', last('/opt/p2/g1-fix.log'))
print('FANLOG', last('/opt/p2/g1-fan.log'))
print('FANOUT', last('/opt/p2/g1-fan.out'))
print('W0133', Path('/opt/p2/workers/g1fix-TST-0133/worker.log').stat().st_size if Path('/opt/p2/workers/g1fix-TST-0133/worker.log').exists() else 'missing')
print('W0015', Path('/opt/p2/workers/g1fix-RES-0015/worker.log').stat().st_size if Path('/opt/p2/workers/g1fix-RES-0015/worker.log').exists() else 'missing')
"""


def one(name, ip):
    payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    return f"=== {name} ===\n{(p.stdout or '')}{(p.stderr or '')[-200:]}"


def main():
    with ThreadPoolExecutor(2) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
