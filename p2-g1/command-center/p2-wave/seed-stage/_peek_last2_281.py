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
print('inf', hb.get('in_flight_n'), 'q', hb.get('queued_n'), 'head', (hb.get('queued_head') or [])[:4], 'inflight', (hb.get('in_flight') or [])[:6])
lp=Path('/opt/p2/supervisor.log')
if lp.exists():
    lines=lp.read_text(errors='replace').splitlines()
    for line in lines[-6:]:
        print(line[-180:])
print('svc', Path('/opt/p2/g1-w3.log').read_text(errors='replace').splitlines()[-3:] if Path('/opt/p2/g1-w3.log').exists() else None)
"""
payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
p = run(SSH + ["root@152.228.192.99", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
print("=== rbx-c leftover ===")
print((p.stdout or "") + (p.stderr or "")[-200:])
p = run(SSH + ["root@51.210.248.225", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
print("=== gra7-c ===")
print((p.stdout or "") + (p.stderr or "")[-200:])
