#!/usr/bin/env python3
"""Count leftover remaining_ids whose catalog output_path exists on each OVH box."""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519"
FLEET = [
    ("gra11-a", "176.31.201.80"),
    ("gra11-c", "176.31.201.16"),
    ("waw1-b", "54.37.131.145"),
    ("waw1-c", "54.38.138.7"),
    ("de1-a", "57.131.128.129"),
    ("de1-c", "141.95.107.32"),
    ("gra9-b", "57.128.55.65"),
    ("gra9-c", "141.94.40.27"),
    ("rbx-a", "164.132.87.50"),
    ("rbx-c", "152.228.192.41"),
    ("par-a", "57.130.20.141"),
    ("par-c", "57.130.46.182"),
    ("uk1-a", "54.37.2.117"),
    ("uk1-c", "54.37.4.51"),
    ("gra7-a", "51.178.59.183"),
    ("gra7-c", "51.178.56.158"),
    ("sbg5-a", "51.91.146.93"),
    ("sbg5-c", "51.91.145.70"),
]
REMOTE = r"""
sudo python3 -c '
import json
from pathlib import Path
root=Path("/opt/p2/ast-integrate")
cat=json.loads((root/"command-center/WORK-UNIT-CATALOG.json").read_text())
left=json.loads((root/"command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json").read_text())
ids=left.get("remaining_ids") or []
by={u["id"]:u for u in cat.get("work_units") or [] if isinstance(u,dict) and u.get("id")}
cp=Path("/opt/p2/completed.json")
done=set((json.loads(cp.read_text()) or {}).get("ids") or []) if cp.is_file() else set()
present=missing=present_done=ghost=0
for uid in ids:
    u=by.get(uid) or {}
    rel=str(u.get("output_path") or "").replace("\\","/")
    ok=bool(rel) and (root/rel).is_file() and (root/rel).stat().st_size>0
    if ok:
        present += 1
        if uid in done:
            present_done += 1
    else:
        missing += 1
        if uid in done:
            ghost += 1
print("leftover",len(ids),"present",present,"missing",missing,"completed",len(done),"present_done",present_done,"ghost_completed",ghost)
'
"""


def one(name: str, ip: str) -> str:
    p = subprocess.run(
        [
            "ssh",
            "-i",
            str(KEY),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"ubuntu@{ip}",
            REMOTE,
        ],
        capture_output=True,
        text=True,
        timeout=40,
    )
    body = ((p.stdout or "") + (p.stderr or "")).replace("\n", " | ")[-500:]
    return f"{name} {ip} rc={p.returncode} {body}"


def main() -> None:
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = [pool.submit(one, n, i) for n, i in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
