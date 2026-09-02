#!/usr/bin/env python3
"""rbx-c G-1 loop finished 6/7; restart leftover 281 + start remesure-281."""
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
IP = "152.228.192.99"
host = f"root@{IP}"


def main() -> None:
    p = run(SCP + [str(STAGE / "remeasure_281.py"), f"{host}:/opt/p2/remeasure_281.py"], capture_output=True, text=True, timeout=20)
    print("scp", p.returncode, (p.stderr or "")[-80:], flush=True)
    cmd = (
        "systemctl start p2-supervisor; sleep 1; "
        "echo SVC $(systemctl is-active p2-supervisor); "
        "test -f /opt/p2/remeasure-281.json && echo RM-DONE || "
        "(nohup python3 -u /opt/p2/remeasure_281.py >/opt/p2/remeasure-281.stdout 2>&1 & echo RM-STARTED $!)"
    )
    p = run(SSH + [host, cmd], capture_output=True, text=True, timeout=20)
    print((p.stdout or "") + (p.stderr or ""), flush=True)


if __name__ == "__main__":
    main()
