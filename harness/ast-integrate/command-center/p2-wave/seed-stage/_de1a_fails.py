#!/usr/bin/env python3
from pathlib import Path
from subprocess import run

ssh = [
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
    "root@51.75.93.252",
    "python3 -c \"import json;d=json.load(open('/opt/p2/remeasure.json'));print(d.get('ok'),d.get('fail'));print(d.get('fail_ids'));\nprint('\\n'.join(r['id']+' | '+r['line'][:160] for r in d.get('results') if not r.get('ok')))\"",
]
p = run(ssh, capture_output=True, text=True, timeout=20)
print(p.stdout)
print(p.stderr[-300:] if p.stderr else "")
print("rc", p.returncode)
