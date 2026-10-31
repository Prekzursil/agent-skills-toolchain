#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
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
CMD = (
    "if test -f /opt/p2/remeasure.json; then echo DONE; "
    "python3 -c 'import json;d=json.load(open(\"/opt/p2/remeasure.json\"));print(d.get(\"n\"),d.get(\"ok\"),d.get(\"fail\"),len(d.get(\"fail_ids\") or []))'; "
    "else echo RUN; tail -n 1 /opt/p2/remeasure.out 2>/dev/null || echo no-log; "
    "pgrep -af remeasure_all.py | head -n 1; fi"
)


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"root@{ip}", CMD], capture_output=True, text=True, timeout=20)
    body = ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " | ")
    return f"{name:10s} {body[:240]}"


def main() -> None:
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *row) for row in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
