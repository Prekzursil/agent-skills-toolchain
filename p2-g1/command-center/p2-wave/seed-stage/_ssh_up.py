#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
BOXES = [
    ("rbx-c", "152.228.192.99"),
    ("gra7-c", "51.210.248.225"),
    ("par-a", "57.130.47.223"),
    ("uk1-c", "54.37.7.164"),
    ("de1-a", "51.75.93.252"),
    ("waw1-c", "54.38.138.226"),
]


def one(name, ip):
    p = run(SSH + [f"root@{ip}", "echo UP"], capture_output=True, text=True, timeout=12)
    return f"{name:8s} rc={p.returncode} {(p.stdout or p.stderr or '')[:60].strip()}"


def main():
    with ThreadPoolExecutor(6) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
