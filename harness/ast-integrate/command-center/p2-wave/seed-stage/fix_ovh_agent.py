#!/usr/bin/env python3
"""Reinstall Cursor agent + restart supervisors on OVH fleet."""
from __future__ import annotations

import subprocess
from pathlib import Path

STAGE = Path(__file__).resolve().parent
DISPATCH = STAGE / "dispatch_cursor.py"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
]
SCP = [
    "scp",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
]
IPS = [
    "176.31.201.117",
    "176.31.201.215",
    "51.75.63.116",
    "54.38.138.226",
    "51.75.93.252",
    "162.19.209.251",
    "37.59.27.161",
    "141.94.186.60",
    "164.132.87.22",
    "152.228.192.99",
    "57.130.47.223",
    "54.37.3.247",
    "57.128.35.67",
    "51.91.140.54",
    # likely up by now
    "57.130.46.182",
    "54.37.7.164",
    "51.210.248.225",
    "57.128.111.33",
]
REMOTE = (
    "curl -fsSL https://cursor.com/install | bash && "
    "test -x /root/.local/bin/agent && /root/.local/bin/agent --version && "
    "cp /tmp/dispatch_cursor.py /opt/p2/dispatch_cursor.py && "
    "systemctl reset-failed p2-supervisor || true && "
    "systemctl restart p2-supervisor && sleep 2 && "
    "systemctl is-active p2-supervisor && tail -n 8 /opt/p2/supervisor.log"
)


def main() -> None:
    for ip in IPS:
        print(f"===== {ip} =====", flush=True)
        scp = subprocess.run(SCP + [str(DISPATCH), f"root@{ip}:/tmp/dispatch_cursor.py"], capture_output=True, text=True, timeout=30)
        if scp.returncode != 0:
            print("SCP-FAIL", (scp.stderr or "")[-200:], flush=True)
            continue
        r = subprocess.run(SSH + [f"root@{ip}", REMOTE], capture_output=True, text=True, timeout=180)
        print((r.stdout or "")[-1200:], flush=True)
        if r.returncode != 0:
            print("FAIL", (r.stderr or "")[-400:], flush=True)
        else:
            print("OK", flush=True)


if __name__ == "__main__":
    main()
