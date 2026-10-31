#!/usr/bin/env python3
from pathlib import Path
from subprocess import run

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
cmd = (
    "python3 /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py BLD-0055; "
    "python3 /opt/p2/remeasure_281.py"
)
p = run(SSH + ["root@141.94.186.60", cmd], capture_output=True, text=True, timeout=180)
print((p.stdout or "")[-1500:])
print((p.stderr or "")[-400:])
print("rc", p.returncode)
