#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
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
SCP = [
    "scp",
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
# skip gra7-c (W3 last unit) and rbx-c (last 2 leftover 281 in flight)
BOXES = [
    ("gra9-c", "141.94.186.60"),
    ("de1-c", "162.19.209.251"),
    ("par-c", "57.130.46.182"),
    ("sbg5-a", "57.128.35.67"),
    ("uk1-a", "54.37.3.247"),
]


def one(name, ip):
    host = f"root@{ip}"
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{name} SCP {(p.stderr or '')[-80:]}"
    cmd = "nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo REFRESH $!"
    p = run(SSH + [host, cmd], capture_output=True, text=True, timeout=20)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode}"


def main():
    with ThreadPoolExecutor(5) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
