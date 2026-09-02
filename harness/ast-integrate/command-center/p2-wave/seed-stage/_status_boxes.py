#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519"
BOXES = [
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
ls -lh /tmp/p2-emit-tree.tgz 2>/dev/null || echo NO-TGZ
sudo systemctl is-active p2-supervisor 2>/dev/null || echo no-svc
sudo python3 -c "import json;from pathlib import Path;p=Path('/opt/p2/completed.json');print('completed', len((json.loads(p.read_text()) or {}).get('ids') or []) if p.is_file() else 0)" 2>/dev/null || true
ps -C curl,tar,python3,agent -o comm,pcpu --no-headers 2>/dev/null | head
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
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"ubuntu@{ip}",
            REMOTE,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    body = ((p.stdout or "") + (p.stderr or "")).replace("\n", " | ")[-400:]
    return f"{name} {ip} rc={p.returncode} {body}"


def main() -> None:
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = [pool.submit(one, n, i) for n, i in BOXES]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
