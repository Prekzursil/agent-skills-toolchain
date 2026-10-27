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
    ("gra7-c", "51.210.248.225"),
    ("gra9-c", "141.94.186.60"),
    ("par-c", "57.130.46.182"),
    ("uk1-a", "54.37.3.247"),
]
CMD = r"""
from pathlib import Path
print('LOG', Path('/opt/p2/g1-w3.log').read_text(errors='replace').splitlines()[-4:] if Path('/opt/p2/g1-w3.log').exists() else 'missing')
for p in sorted(Path('/opt/p2/workers').glob('g1fix-*/worker.log')):
    sz=p.stat().st_size
    if sz>=0:
        print(p.parent.name, sz)
"""


def one(name, ip):
    payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    return f"=== {name} ===\n{(p.stdout or '')}{(p.stderr or '')[-120:]}"


def main():
    with ThreadPoolExecutor(4) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
