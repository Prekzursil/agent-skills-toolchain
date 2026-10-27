#!/usr/bin/env python3
from pathlib import Path
from subprocess import run

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
CMD = r"""
import json
from pathlib import Path
hb=json.loads(Path('/opt/p2/supervisor-heartbeat.json').read_text()) if Path('/opt/p2/supervisor-heartbeat.json').exists() else {}
print('inf', hb.get('in_flight_n'), 'ids', hb.get('in_flight'))
done=json.loads(Path('/opt/p2/completed.json').read_text()).get('ids') or []
print('IMP-0109_in_done', 'IMP-0109' in done)
print('RES-0141_in_done', 'RES-0141' in done)
print('last', Path('/opt/p2/supervisor.log').read_text(errors='replace').splitlines()[-2:])
print('w3', Path('/opt/p2/g1-w3.log').read_text(errors='replace').splitlines()[-3:] if Path('/opt/p2/g1-w3.log').exists() else None)
print('w3json', Path('/opt/p2/g1-w3.json').exists())
print('res0156log', Path('/opt/p2/workers/g1fix-RES-0156/worker.log').stat().st_size if Path('/opt/p2/workers/g1fix-RES-0156/worker.log').exists() else 'missing')
"""
payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
for name, ip in [("rbx-c", "152.228.192.99"), ("gra7-c", "51.210.248.225")]:
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    print(f"=== {name} ===")
    print((p.stdout or "") + (p.stderr or "")[-150:])
