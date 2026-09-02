#!/usr/bin/env python3
from subprocess import run
from pathlib import Path

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
JOBS = [
    ("gra9-c", "141.94.186.60", "TST-0122"),
    ("uk1-c", "54.37.7.164", "TST-0029"),
]


def main() -> None:
    for name, ip, uid in JOBS:
        print("====", name, uid, flush=True)
        cmd = (
            "cd /opt/p2/ast-integrate && "
            "command -v node && node --version && "
            f"python3 command-center/p2-wave/_measure_one_delivered.py {uid}"
        )
        p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=90)
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
        for line in out[-12:]:
            print(line, flush=True)
        print("rc", p.returncode, flush=True)


if __name__ == "__main__":
    main()
