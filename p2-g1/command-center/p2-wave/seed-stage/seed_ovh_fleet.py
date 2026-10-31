#!/usr/bin/env python3
"""Seed OVH Cursor leftover fleet. Does not print secrets."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
LOCAL_DISPATCH = STAGE / "dispatch_cursor.py"
LOCAL_LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
LOCAL_MEASURE = WAVE / "_measure_one_delivered.py"
SCW = "root@163.172.168.194"
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

# (name, ip, cap, box_index) BOX_COUNT=18
FLEET = [
    ("p2-ovh-gra11-a", "176.31.201.117", 80, 0),
    ("p2-ovh-gra11-c", "176.31.201.215", 40, 1),
    ("p2-ovh-waw1-b", "51.75.63.116", 80, 2),
    ("p2-ovh-waw1-c", "54.38.138.226", 40, 3),
    ("p2-ovh-de1-a", "51.75.93.252", 80, 4),
    ("p2-ovh-de1-c", "162.19.209.251", 40, 5),
    ("p2-ovh-gra9-b", "37.59.27.161", 80, 6),
    ("p2-ovh-gra9-c", "141.94.186.60", 40, 7),
    ("p2-ovh-rbx-a", "164.132.87.22", 80, 8),
    ("p2-ovh-rbx-c", "152.228.192.99", 40, 9),
    ("p2-ovh-par-a", "57.130.47.223", 80, 10),
    ("p2-ovh-uk1-a", "54.37.3.247", 80, 12),
    ("p2-ovh-sbg5-a", "57.128.35.67", 80, 16),
    ("p2-ovh-gra7-a", "51.91.140.54", 80, 14),
]
BOX_COUNT = 18


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ssh_host(ip: str, remote: str, user: str = "ubuntu", timeout: int = 90) -> subprocess.CompletedProcess:
    return run(SSH + [f"{user}@{ip}", remote], timeout=timeout)


def main() -> int:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY")
    if not token:
        print("FAILED:no CURSOR_API_TOKEN")
        return 2
    print(f"token_len={len(token)} prefix={token[:4]}", flush=True)
    if not LOCAL_DISPATCH.is_file() or not LOCAL_LEFTOVER.is_file():
        print("FAILED:missing local dispatch or leftover")
        return 2

    print("===== pack scaleway lean tree =====", flush=True)
    p = run(
        SSH
        + [
            SCW,
            "tar czf /tmp/p2-ast.tgz -C /opt/p2 ast-integrate && ls -lh /tmp/p2-ast.tgz && test -f /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py && echo MEASURE-OK",
        ],
        timeout=120,
    )
    print((p.stdout or "")[-500:], (p.stderr or "")[-300:], "rc", p.returncode, flush=True)
    if p.returncode != 0:
        print("FAILED:scaleway pack")
        return 1
    local_tgz = STAGE / "p2-ast.tgz"
    p = run(SCP + [f"{SCW}:/tmp/p2-ast.tgz", str(local_tgz)], timeout=120)
    print("scp tgz rc", p.returncode, "size", local_tgz.stat().st_size if local_tgz.exists() else 0, flush=True)
    p = run(
        SCP
        + [
            f"{SCW}:/opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py",
            str(LOCAL_MEASURE),
        ],
        timeout=60,
    )
    print("scp measure rc", p.returncode, "exists", LOCAL_MEASURE.is_file(), flush=True)

    unit = """[Unit]
Description=P2 Cursor leftover supervisor
After=network-online.target
Wants=network-online.target

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

    ok = 0
    for name, ip, cap, idx in FLEET:
        print(f"===== seed {name} {ip} idx={idx} cap={cap} =====", flush=True)
        who = ssh_host(ip, "whoami; sudo -n true && echo SUDO-OK || echo SUDO-FAIL")
        print(who.stdout.strip(), who.stderr[-200:], flush=True)
        user = "ubuntu"
        # Prefer root if it works
        root_try = run(SSH + [f"root@{ip}", "echo ROOT-OK"], timeout=20)
        if root_try.returncode == 0:
            user = "root"
            print("login=root", flush=True)
        else:
            print("login=ubuntu", flush=True)

        def rssh(cmd: str, timeout: int = 120) -> subprocess.CompletedProcess:
            return run(SSH + [f"{user}@{ip}", cmd], timeout=timeout)

        def rscp(src: Path, dest: str) -> subprocess.CompletedProcess:
            return run(SCP + [str(src), f"{user}@{ip}:{dest}"], timeout=120)

        prefix = "" if user == "root" else "sudo "
        rssh(f"{prefix}mkdir -p /opt/p2 /opt/p2/workers /opt/p2/strikes /opt/p2/unit-locks /root/.local/bin")
        rscp(local_tgz, "/tmp/p2-ast.tgz")
        rssh(f"{prefix}tar xzf /tmp/p2-ast.tgz -C /opt/p2")
        rscp(LOCAL_DISPATCH, "/tmp/dispatch_cursor.py")
        rssh(f"{prefix}cp /tmp/dispatch_cursor.py /opt/p2/dispatch_cursor.py")
        if LOCAL_MEASURE.is_file():
            rscp(LOCAL_MEASURE, "/tmp/_measure_one_delivered.py")
            rssh(
                f"{prefix}mkdir -p /opt/p2/ast-integrate/command-center/p2-wave && "
                f"{prefix}cp /tmp/_measure_one_delivered.py /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py"
            )
        rscp(LOCAL_LEFTOVER, "/tmp/leftover.json")
        rssh(
            f"{prefix}cp /tmp/leftover.json /opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
        )
        env_body = (
            f"CURSOR_API_KEY={token}\n"
            f"CURSOR_API_TOKEN={token}\n"
            f"BOX_INDEX={idx}\n"
            f"BOX_COUNT={BOX_COUNT}\n"
            "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin\n"
            "HOME=/root\n"
        )
        env_path = STAGE / f"cursor.env.{name}"
        env_path.write_text(env_body, encoding="utf-8")
        try:
            rscp(env_path, "/tmp/cursor.env")
            rssh(f"{prefix}cp /tmp/cursor.env /opt/p2/cursor.env && {prefix}chmod 600 /opt/p2/cursor.env")
        finally:
            env_path.unlink(missing_ok=True)
        unit_path = STAGE / f"{name}.service"
        unit_path.write_text(unit.format(name=name, cap=cap), encoding="utf-8")
        rscp(unit_path, f"/tmp/{name}.service")
        rssh(
            f"{prefix}cp /tmp/{name}.service /etc/systemd/system/p2-supervisor.service && "
            f"{prefix}systemctl daemon-reload && {prefix}systemctl enable --now p2-supervisor"
        )
        unit_path.unlink(missing_ok=True)
        st = rssh(f"{prefix}systemctl is-active p2-supervisor; {prefix}tail -n 5 /opt/p2/supervisor.log 2>/dev/null || true")
        print(st.stdout[-800:], flush=True)
        if "active" in (st.stdout or ""):
            ok += 1
            print(f"SUCCESS:seed {name}", flush=True)
        else:
            print(f"FAILED:seed {name}", flush=True)
    print(f"SEEDED {ok}/{len(FLEET)}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
