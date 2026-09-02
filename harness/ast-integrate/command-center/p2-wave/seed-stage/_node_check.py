#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    __import__("pathlib").Path.home().as_posix() + "/.ssh/id_ed25519",
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
REMOTE = "command -v node; command -v nodejs; node --version 2>/dev/null; dpkg -s nodejs 2>/dev/null | awk '/Status:|Version:/{print}'"


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"root@{ip}", REMOTE], capture_output=True, text=True, timeout=25)
    body = ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " | ")
    return f"{name:10s} rc={p.returncode} {body[:220]}"


def main() -> None:
    with ThreadPoolExecutor(9) as ex:
        futs = [ex.submit(one, *row) for row in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
