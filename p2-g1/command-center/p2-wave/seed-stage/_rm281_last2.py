#!/usr/bin/env python3
"""Start remesure-281 on de1-a and rbx-c (the two that were skipped)."""
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
BOXES = [("de1-a", "51.75.93.252"), ("rbx-c", "152.228.192.99")]


def one(name, ip):
    host = f"root@{ip}"
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{name} SCP {(p.stderr or '')[-80:]}"
    cmd = (
        "test -f /opt/p2/remeasure-281.json && echo ALREADY || "
        "(nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo STARTED $!)"
    )
    p = run(SSH + [host, cmd], capture_output=True, text=True, timeout=20)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode}"


def main():
    with ThreadPoolExecutor(2) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
