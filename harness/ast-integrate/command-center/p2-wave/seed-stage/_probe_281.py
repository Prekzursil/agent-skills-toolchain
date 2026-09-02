#!/usr/bin/env python3
"""See how many of the 281 log-success IDs already have probe trees on one OVH box."""
import json
from pathlib import Path
from subprocess import run

ids = json.loads(
    Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\CLOUD-DONE-FROM-LOGS-2026-08-21.json").read_text(
        encoding="utf-8"
    )
)["ids"]
payload = json.dumps(ids)
# keep remote small: send via stdin file
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
    "root@176.31.201.117",
    "python3 -c \"import json,sys; from pathlib import Path; ids=json.load(sys.stdin); P=Path('/opt/p2/ast-integrate/command-center/p2-wave/probes'); d=sum(1 for i in ids if (P/i).is_dir()); r=sum(1 for i in ids if (P/i/'SUBAGENT-RETURN.json').is_file()); m=sum(1 for i in ids if (P/i/'UNIT-ARTIFACT-MANIFEST.json').is_file()); print('dirs',d,'returns',r,'manifests',m,'n',len(ids))\"",
]
p = run(ssh, input=payload, capture_output=True, text=True, timeout=30)
print(p.stdout)
print(p.stderr[-300:] if p.stderr else "")
print("rc", p.returncode)
