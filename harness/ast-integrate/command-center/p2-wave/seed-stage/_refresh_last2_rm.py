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
BOXES = [("de1-c", "162.19.209.251"), ("gra9-c", "141.94.186.60")]


def one(name, ip):
    cmd = "nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo REFRESH $!"
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=25)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode}"


def main():
    with ThreadPoolExecutor(2) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
