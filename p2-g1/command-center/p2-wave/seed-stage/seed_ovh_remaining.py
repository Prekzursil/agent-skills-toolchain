#!/usr/bin/env python3
"""Seed the 4 r3-128 boxes that missed systemd."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
DISPATCH = STAGE / "dispatch_cursor.py"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
MEASURE = WAVE / "_measure_one_delivered.py"
TGZ = STAGE / "p2-ast.tgz"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-o", "StrictHostKeyChecking=accept-new"]
SCP = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-o", "StrictHostKeyChecking=accept-new"]
BOXES = [
    ("p2-ovh-par-c", "57.130.46.182", 40, 11),
    ("p2-ovh-uk1-c", "54.37.7.164", 40, 13),
    ("p2-ovh-gra7-c", "51.210.248.225", 40, 15),
    ("p2-ovh-sbg5-c", "57.128.111.33", 40, 17),
]
UNIT = """[Unit]
Description=P2 Cursor leftover supervisor
After=network-online.target
[Service]
Type=simple
WorkingDirectory=/opt/p2
EnvironmentFile=/opt/p2/cursor.env
ExecStart=/usr/bin/python3 -u /opt/p2/dispatch_cursor.py {name} {cap}
Restart=always
RestartSec=5
StandardOutput=append:/opt/p2/supervisor-systemd.log
StandardError=append:/opt/p2/supervisor-systemd.log
[Install]
WantedBy=multi-user.target
"""


def main() -> None:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY") or ""
    if not token:
        raise SystemExit("no token")
    for name, ip, cap, idx in BOXES:
        print("=====", name, ip, flush=True)
        host = f"root@{ip}"
        subprocess.run(SSH + [host, "mkdir -p /opt/p2 /opt/p2/workers /opt/p2/strikes /opt/p2/unit-locks"], timeout=30)
        if TGZ.is_file():
            subprocess.run(SCP + [str(TGZ), f"{host}:/tmp/p2-ast.tgz"], timeout=60)
            subprocess.run(SSH + [host, "tar xzf /tmp/p2-ast.tgz -C /opt/p2"], timeout=60)
        subprocess.run(SCP + [str(DISPATCH), f"{host}:/opt/p2/dispatch_cursor.py"], timeout=30)
        if MEASURE.is_file():
            subprocess.run(
                SCP + [str(MEASURE), f"{host}:/opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py"],
                timeout=30,
            )
        subprocess.run(
            SCP + [str(LEFTOVER), f"{host}:/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"],
            timeout=30,
        )
        env = (
            f"CURSOR_API_KEY={token}\nCURSOR_API_TOKEN={token}\n"
            f"BOX_INDEX={idx}\nBOX_COUNT=18\n"
            "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin\nHOME=/root\n"
        )
        ep = STAGE / f"cursor.env.{name}"
        ep.write_text(env, encoding="utf-8")
        subprocess.run(SCP + [str(ep), f"{host}:/opt/p2/cursor.env"], timeout=30)
        ep.unlink(missing_ok=True)
        up = STAGE / f"{name}.service"
        up.write_text(UNIT.format(name=name, cap=cap), encoding="utf-8")
        subprocess.run(SCP + [str(up), f"{host}:/etc/systemd/system/p2-supervisor.service"], timeout=30)
        up.unlink(missing_ok=True)
        r = subprocess.run(
            SSH
            + [
                host,
                "chmod 600 /opt/p2/cursor.env; systemctl daemon-reload; "
                "systemctl enable --now p2-supervisor; sleep 2; systemctl is-active p2-supervisor; "
                "tail -n 4 /opt/p2/supervisor.log",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        print(r.stdout[-600:], r.stderr[-200:], flush=True)


if __name__ == "__main__":
    main()
