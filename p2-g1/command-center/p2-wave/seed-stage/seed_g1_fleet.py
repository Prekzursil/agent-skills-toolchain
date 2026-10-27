#!/usr/bin/env python3
"""Seed 18 p2-g1 OVH boxes with leftover G-1 fail IDs. High concurrency."""
from __future__ import annotations

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
DISPATCH = STAGE / "dispatch_cursor.py"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
MEASURE = WAVE / "_measure_one_delivered.py"
BOOTSTRAP = STAGE / "_box_bootstrap.sh"
THREAD_HTTP = STAGE / "thread_http.py"
IPS = WAVE / "ovh-monitor" / "g1-ovh-ips.json"
TGZ = Path.home() / "p2-emit-tree.tgz"
KEY = Path.home() / ".ssh" / "id_ed25519"
KH = STAGE / "g1-known-hosts"
if not KH.exists():
    KH.write_text("", encoding="utf-8")
SSH_BASE = [
    "ssh", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=12",
    "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={KH}",
]
SCP_BASE = [
    "scp", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=12",
    "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={KH}",
]
UNIT = """[Unit]
Description=P2 Cursor G-1 leftover supervisor
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


def load_fleet() -> list[tuple[str, str, int, int]]:
    data = json.loads(IPS.read_text(encoding="utf-8"))
    boxes = sorted(data["boxes"], key=lambda b: str(b["name"]))
    out = []
    for i, b in enumerate(boxes):
        name = str(b["name"])
        ip = str(b["ip"])
        cap = 40 if name.endswith("-c") else 80
        out.append((name, ip, cap, i))
    return out


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ssh(ip: str, remote: str, timeout: int = 90) -> subprocess.CompletedProcess:
    return run(SSH_BASE + [f"ubuntu@{ip}", remote], timeout=timeout)


def scp(src: Path, dest: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return run(SCP_BASE + [str(src), dest], timeout=timeout)


def wait_ssh(ip: str, tries: int = 30) -> bool:
    for _ in range(tries):
        p = ssh(ip, "echo SSH-OK", timeout=20)
        if p.returncode == 0 and "SSH-OK" in (p.stdout or ""):
            return True
        time.sleep(6)
    return False


def seed_one(name: str, ip: str, cap: int, idx: int, token: str, hub: str, hub_ready: bool) -> str:
    if not wait_ssh(ip, tries=20):
        return f"FAILED:ssh {name} {ip}"
    pre = "sudo "
    ssh(ip, f"{pre}mkdir -p /opt/p2 /opt/p2/workers /opt/p2/strikes /opt/p2/unit-locks /opt/p2/ast-integrate /root/.local/bin", timeout=30)
    has = ssh(ip, "test -f /tmp/p2-emit-tree.tgz && echo HAS-TGZ || echo NO-TGZ", timeout=20)
    if "HAS-TGZ" not in (has.stdout or ""):
        if hub_ready and ip != hub:
            w = ssh(
                ip,
                f"curl -fsSL --retry 12 --retry-delay 2 -o /tmp/p2-emit-tree.tgz http://{hub}:8000/p2-emit-tree.tgz && echo CURL-OK || echo CURL-FAIL",
                timeout=600,
            )
            if "CURL-OK" not in (w.stdout or ""):
                p = scp(TGZ, f"ubuntu@{ip}:/tmp/p2-emit-tree.tgz", timeout=900)
                if p.returncode != 0:
                    return f"FAILED:tgz {name} {(p.stderr or '')[-180:]}"
        else:
            p = scp(TGZ, f"ubuntu@{ip}:/tmp/p2-emit-tree.tgz", timeout=900)
            if p.returncode != 0:
                return f"FAILED:tgz {name} {(p.stderr or '')[-180:]}"
    ssh(ip, f"{pre}tar xzf /tmp/p2-emit-tree.tgz -C /opt/p2/ast-integrate", timeout=300)
    scp(DISPATCH, f"ubuntu@{ip}:/tmp/dispatch_cursor.py", timeout=40)
    ssh(ip, f"{pre}cp /tmp/dispatch_cursor.py /opt/p2/dispatch_cursor.py", timeout=20)
    scp(MEASURE, f"ubuntu@{ip}:/tmp/_measure_one_delivered.py", timeout=40)
    ssh(
        ip,
        f"{pre}mkdir -p /opt/p2/ast-integrate/command-center/p2-wave && "
        f"{pre}cp /tmp/_measure_one_delivered.py /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py",
        timeout=20,
    )
    scp(LEFTOVER, f"ubuntu@{ip}:/tmp/leftover.json", timeout=40)
    ssh(ip, f"{pre}cp /tmp/leftover.json /opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json", timeout=20)
    if BOOTSTRAP.is_file():
        scp(BOOTSTRAP, f"ubuntu@{ip}:/tmp/_box_bootstrap.sh", timeout=30)
        ssh(ip, f"{pre}bash /tmp/_box_bootstrap.sh", timeout=300)
    ssh(
        ip,
        f"{pre}bash -lc 'curl -fsSL https://cursor.com/install | bash' || true; "
        f"{pre}ln -sf /root/.local/bin/agent /usr/local/bin/agent || true; "
        f"{pre}ln -sf /root/.local/bin/cursor-agent /usr/local/bin/cursor-agent || true",
        timeout=180,
    )
    env_body = (
        f"CURSOR_API_KEY={token}\nCURSOR_API_TOKEN={token}\n"
        f"BOX_INDEX={idx}\nBOX_COUNT=18\n"
        "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin\nHOME=/root\n"
    )
    ep = STAGE / f"cursor.env.{name}"
    ep.write_text(env_body, encoding="utf-8")
    try:
        scp(ep, f"ubuntu@{ip}:/tmp/cursor.env", timeout=30)
        ssh(ip, f"{pre}cp /tmp/cursor.env /opt/p2/cursor.env && {pre}chmod 600 /opt/p2/cursor.env", timeout=20)
    finally:
        ep.unlink(missing_ok=True)
    up = STAGE / f"{name}.service"
    up.write_text(UNIT.format(name=name, cap=cap), encoding="utf-8")
    try:
        scp(up, f"ubuntu@{ip}:/tmp/p2-supervisor.service", timeout=30)
        ssh(
            ip,
            f"{pre}cp /tmp/p2-supervisor.service /etc/systemd/system/p2-supervisor.service && "
            f"{pre}rm -f /opt/p2/completed.json /opt/p2/QUEUE-EMPTY && "
            f"{pre}systemctl daemon-reload && {pre}systemctl enable --now p2-supervisor && "
            f"{pre}systemctl restart p2-supervisor",
            timeout=40,
        )
    finally:
        up.unlink(missing_ok=True)
    st = ssh(ip, f"{pre}systemctl is-active p2-supervisor; {pre}tail -n 8 /opt/p2/supervisor.log 2>/dev/null || true", timeout=20)
    body = (st.stdout or "") + (st.stderr or "")
    if "active" in body:
        return f"SUCCESS:seed {name} {ip} cap={cap} idx={idx}"
    return f"FAILED:seed {name} {ip} {body[-400:]}"


def start_hub(hub: str) -> bool:
    if not wait_ssh(hub, tries=20):
        print("FAILED:hub-ssh", hub, flush=True)
        return False
    ssh(hub, "sudo mkdir -p /opt/p2 /tmp", timeout=20)
    has = ssh(hub, "test -f /tmp/p2-emit-tree.tgz && echo HAS || echo NO", timeout=15)
    if "HAS" not in (has.stdout or ""):
        print("scp tgz hub", TGZ.stat().st_size, flush=True)
        p = scp(TGZ, f"ubuntu@{hub}:/tmp/p2-emit-tree.tgz", timeout=900)
        if p.returncode != 0:
            print("FAILED:hub-scp", (p.stderr or "")[-200:], flush=True)
            return False
    if THREAD_HTTP.is_file():
        scp(THREAD_HTTP, f"ubuntu@{hub}:/tmp/thread_http.py", timeout=30)
        ssh(hub, "sudo pkill -f 'http.server 8000' || true; sudo pkill -f thread_http.py || true; nohup python3 /tmp/thread_http.py >/tmp/http-seed.log 2>&1 &", timeout=20)
    else:
        ssh(hub, "sudo pkill -f 'http.server 8000' || true; nohup python3 -m http.server 8000 --directory /tmp >/tmp/http-seed.log 2>&1 &", timeout=20)
    time.sleep(2)
    chk = ssh(hub, "ss -ltn | grep 8000 || echo NO-PORT", timeout=15)
    print("hub port", (chk.stdout or "").strip(), flush=True)
    return "8000" in (chk.stdout or "")


def main() -> int:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY") or ""
    if not token:
        print("FAILED:no CURSOR_API_TOKEN")
        return 2
    fleet = load_fleet()
    hub = next(ip for name, ip, cap, idx in fleet if name.endswith("gra11-a"))
    print(f"token_len={len(token)} prefix={token[:4]} hub={hub} n={len(fleet)} leftover_ok", flush=True)
    for row in fleet:
        print("fleet", *row, flush=True)
    hub_ok = start_hub(hub)
    print("hub_ok", hub_ok, flush=True)
    ok = 0
    with ThreadPoolExecutor(max_workers=9) as pool:
        futs = {pool.submit(seed_one, n, ip, c, i, token, hub, hub_ok): n for n, ip, c, i in fleet}
        for fut in as_completed(futs):
            msg = fut.result()
            print(msg, flush=True)
            if msg.startswith("SUCCESS:"):
                ok += 1
    print(f"SEEDED {ok}/{len(fleet)}", flush=True)
    return 0 if ok >= 16 else 1


if __name__ == "__main__":
    raise SystemExit(main())
