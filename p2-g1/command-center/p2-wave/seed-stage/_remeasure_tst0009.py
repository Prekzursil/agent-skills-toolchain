#!/usr/bin/env python3
from pathlib import Path
from subprocess import run

ssh = [
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
    "root@57.130.46.182",
    "cd /opt/p2/ast-integrate && python3 command-center/p2-wave/_measure_one_delivered.py TST-0009",
]
p = run(ssh, capture_output=True, text=True, timeout=90)
lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
for line in lines[-15:]:
    print(line)
print("rc", p.returncode)
