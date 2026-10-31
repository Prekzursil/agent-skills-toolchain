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
BOXES = [
    ("par-c", "57.130.46.182"),
    ("sbg5-a", "57.128.35.67"),
    ("gra11-c", "176.31.201.215"),
    ("de1-a", "51.75.93.252"),
    ("par-a", "57.130.47.223"),
    ("gra7-c", "51.210.248.225"),
    ("waw1-b", "51.75.63.116"),
    ("gra9-b", "37.59.27.161"),
    ("gra7-a", "51.91.140.54"),
    ("gra9-c", "141.94.186.60"),
]


def one(name, ip):
    host = f"root@{ip}"
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return f"{name} SCP {(p.stderr or '')[-100:]}"
    cmd = "nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo REFRESH $!"
    p = run(SSH + [host, cmd], capture_output=True, text=True, timeout=25)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode} {(p.stderr or '')[-80:]}"


def main():
    with ThreadPoolExecutor(5) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
