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
    ("waw1-b", "51.75.63.116"),
    ("par-a", "57.130.47.223"),
    ("uk1-c", "54.37.7.164"),
    ("sbg5-a", "57.128.35.67"),
    ("gra7-c", "51.210.248.225"),
]
CMD = (
    "python3 -c "
    "'import json;from pathlib import Path;"
    "d=json.loads(Path(\"/opt/p2/supervisor-heartbeat.json\").read_text()) if Path(\"/opt/p2/supervisor-heartbeat.json\").exists() else {};"
    "print(d.get(\"in_flight_n\"), d.get(\"queued_n\"), d.get(\"ok\"), (d.get(\"queued_head\") or [])[:4])'"
)


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"root@{ip}", CMD], capture_output=True, text=True, timeout=20)
    return f"{name:10s} {(p.stdout or '').strip()} {(p.stderr or '')[-80:]}"


def main() -> None:
    with ThreadPoolExecutor(6) as ex:
        for f in as_completed([ex.submit(one, *r) for r in FLEET]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
