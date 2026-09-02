#!/usr/bin/env python3
"""SCP remeasure_all.py and nohup it on all 18 OVH boxes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
SCRIPT = STAGE / "remeasure_all.py"
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
FLEET = [
    ("p2-ovh-gra11-a", "176.31.201.117"),
    ("p2-ovh-gra11-c", "176.31.201.215"),
    ("p2-ovh-waw1-b", "51.75.63.116"),
    ("p2-ovh-waw1-c", "54.38.138.226"),
    ("p2-ovh-de1-a", "51.75.93.252"),
    ("p2-ovh-de1-c", "162.19.209.251"),
    ("p2-ovh-gra9-b", "37.59.27.161"),
    ("p2-ovh-gra9-c", "141.94.186.60"),
    ("p2-ovh-rbx-a", "164.132.87.22"),
    ("p2-ovh-rbx-c", "152.228.192.99"),
    ("p2-ovh-par-a", "57.130.47.223"),
    ("p2-ovh-par-c", "57.130.46.182"),
    ("p2-ovh-uk1-a", "54.37.3.247"),
    ("p2-ovh-uk1-c", "54.37.7.164"),
    ("p2-ovh-sbg5-a", "57.128.35.67"),
    ("p2-ovh-sbg5-c", "57.128.111.33"),
    ("p2-ovh-gra7-a", "51.91.140.54"),
    ("p2-ovh-gra7-c", "51.210.248.225"),
]


def one(name: str, ip: str) -> str:
    host = f"root@{ip}"
    p = run(SCP + [str(SCRIPT), f"{host}:/opt/p2/remeasure_all.py"], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return f"{name} SCP-FAIL {(p.stderr or '')[-200:]}"
    start = (
        "rm -f /opt/p2/remeasure.json /opt/p2/remeasure.out; "
        "nohup python3 -u /opt/p2/remeasure_all.py >/opt/p2/remeasure.out 2>&1 & "
        "echo STARTED $!"
    )
    p = run(SSH + [host, start], capture_output=True, text=True, timeout=20)
    return f"{name} {(p.stdout or '').strip()} rc={p.returncode} {(p.stderr or '')[-120:]}"


def main() -> None:
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *row) for row in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
