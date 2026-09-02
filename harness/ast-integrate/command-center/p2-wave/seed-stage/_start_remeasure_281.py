#!/usr/bin/env python3
"""Start 281-only remesure on boxes that are not mid G-1-fix/fan."""
from __future__ import annotations

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
# skip rbx-c (TST-0133 in flight) and de1-a (RES-0015 fan in flight)
FLEET = [
    ("gra11-a", "176.31.201.117"),
    ("gra11-c", "176.31.201.215"),
    ("waw1-b", "51.75.63.116"),
    ("waw1-c", "54.38.138.226"),
    ("de1-c", "162.19.209.251"),
    ("gra9-b", "37.59.27.161"),
    ("gra9-c", "141.94.186.60"),
    ("rbx-a", "164.132.87.22"),
    ("par-a", "57.130.47.223"),
    ("par-c", "57.130.46.182"),
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
    ("sbg5-a", "57.128.35.67"),
    ("sbg5-c", "57.128.111.33"),
    ("gra7-a", "51.91.140.54"),
    ("gra7-c", "51.210.248.225"),
]


def one(name: str, ip: str) -> str:
    host = f"root@{ip}"
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{name} SCP-FAIL {(p.stderr or '')[-120:]}"
    start = (
        "test -f /opt/p2/remeasure-281.json && echo ALREADY-DONE && python3 -c "
        "'import json;d=json.load(open(\"/opt/p2/remeasure-281.json\"));print(d.get(\"ok\"),d.get(\"n\"),d.get(\"fail\"))' "
        "|| (nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo STARTED $!)"
    )
    p = run(SSH + [host, start], capture_output=True, text=True, timeout=20)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode} {(p.stderr or '')[-80:]}"


def main() -> None:
    with ThreadPoolExecutor(16) as ex:
        futs = [ex.submit(one, *b) for b in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
