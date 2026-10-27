#!/usr/bin/env python3
"""Probe SSH on every p2-g1 IP from g1-ovh-ips.json."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parents[1]
IPS = WAVE / "ovh-monitor" / "g1-ovh-ips.json"
KEY = Path.home() / ".ssh" / "id_ed25519"
KH = Path(__file__).resolve().parent / "g1-known-hosts"
SSH = [
    "ssh", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    "-o", "StrictHostKeyChecking=no", f"-oUserKnownHostsFile={KH}",
]


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"ubuntu@{ip}", "echo UP; hostname; test -f /tmp/p2-emit-tree.tgz && echo HAS-TGZ || echo NO-TGZ; systemctl is-active p2-supervisor 2>/dev/null || true"], capture_output=True, text=True, timeout=15)
    body = ((p.stdout or "") + (p.stderr or "")).replace("\n", " | ")[:180]
    return f"{name:16s} {ip:16s} rc={p.returncode} {body}"


def main() -> None:
    boxes = json.loads(IPS.read_text(encoding="utf-8"))["boxes"]
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, b["name"], b["ip"]) for b in boxes]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
