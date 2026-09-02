#!/usr/bin/env python3
"""Re-run incremental remesure-281 on boxes not currently in W3."""
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
# skip current W3 RUN homes
BOXES = [
    ("de1-a", "51.75.93.252"),
    ("de1-c", "162.19.209.251"),
    ("gra9-b", "37.59.27.161"),
    ("sbg5-a", "57.128.35.67"),
    ("sbg5-c", "57.128.111.33"),
    ("par-a", "57.130.47.223"),
    ("uk1-c", "54.37.7.164"),
    ("gra7-a", "51.91.140.54"),
    ("waw1-b", "51.75.63.116"),
    ("waw1-c", "54.38.138.226"),
]


def one(name, ip):
    host = f"root@{ip}"
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{name} SCP {(p.stderr or '')[-80:]}"
    cmd = (
        "nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo REFRESH $!"
    )
    p = run(SSH + [host, cmd], capture_output=True, text=True, timeout=20)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode}"


def main():
    with ThreadPoolExecutor(10) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
