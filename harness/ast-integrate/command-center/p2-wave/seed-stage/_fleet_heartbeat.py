#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519"
FLEET = [
    ("gra11-a", "176.31.201.80", 80),
    ("gra11-c", "176.31.201.16", 40),
    ("waw1-b", "54.37.131.145", 80),
    ("waw1-c", "54.38.138.7", 40),
    ("de1-a", "57.131.128.129", 80),
    ("de1-c", "141.95.107.32", 40),
    ("gra9-b", "57.128.55.65", 80),
    ("gra9-c", "141.94.40.27", 40),
    ("rbx-a", "164.132.87.50", 80),
    ("rbx-c", "152.228.192.41", 40),
    ("par-a", "57.130.20.141", 80),
    ("par-c", "57.130.46.182", 40),
    ("uk1-a", "54.37.2.117", 80),
    ("uk1-c", "54.37.4.51", 40),
    ("gra7-a", "51.178.59.183", 80),
    ("gra7-c", "51.178.56.158", 40),
    ("sbg5-a", "51.91.146.93", 80),
    ("sbg5-c", "51.91.145.70", 40),
]
REMOTE = r"""
sudo systemctl is-active p2-supervisor 2>/dev/null || echo inactive
sudo python3 - << 'PY'
import json
from pathlib import Path
h=Path("/opt/p2/supervisor-heartbeat.json")
c=Path("/opt/p2/completed.json")
if h.is_file():
    d=json.loads(h.read_text())
    print("hb", d.get("cap"), "live", d.get("live_grok"), "flight", d.get("in_flight_n"), "queued", d.get("queued_n"), "ok", d.get("ok"), "parked", d.get("parked"), "launched", d.get("launched"))
else:
    print("hb missing")
n=0
if c.is_file():
    n=len((json.loads(c.read_text()) or {}).get("ids") or [])
print("completed", n)
left=Path("/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json")
if left.is_file():
    print("remaining", len((json.loads(left.read_text()) or {}).get("remaining_ids") or []))
PY
"""


def one(name, ip, cap):
    p = subprocess.run(
        ["ssh", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new", f"ubuntu@{ip}", REMOTE],
        capture_output=True,
        text=True,
        timeout=25,
    )
    body = ((p.stdout or "") + (p.stderr or "")).replace("\n", " | ")[-500:]
    return f"{name} {ip} cap={cap} rc={p.returncode} {body}"


def main():
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = [pool.submit(one, n, i, c) for n, i, c in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
