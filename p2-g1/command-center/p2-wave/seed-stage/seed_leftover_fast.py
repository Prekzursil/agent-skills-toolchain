#!/usr/bin/env python3
"""Seed leftover Cursor fleet on live OVH boxes. Parallel. No secrets printed."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
DISPATCH = STAGE / "dispatch_cursor.py"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
MEASURE = WAVE / "_measure_one_delivered.py"
BOOTSTRAP = STAGE / "_box_bootstrap.sh"
TGZ = Path.home() / "p2-emit-tree.tgz"
KEY = Path.home() / ".ssh" / "id_ed25519"
SSH_BASE = [
    "ssh",
    "-i",
    str(KEY),
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "UserKnownHostsFile=" + str(Path.home() / ".ssh" / "known_hosts"),
]
SCP_BASE = [
    "scp",
    "-i",
    str(KEY),
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
]

# name, ip, cap, box_index. BOX_COUNT=18 leftover sharding. 9x80 + 9x40 = 1080.
FLEET: list[tuple[str, str | None, int, int]] = [
    ("p2-ovh-gra11-a", "176.31.201.80", 80, 0),
    ("p2-ovh-gra11-c", "176.31.201.16", 40, 1),
    ("p2-ovh-waw1-b", "54.37.131.145", 80, 2),
    ("p2-ovh-waw1-c", "54.38.138.7", 40, 3),
    ("p2-ovh-de1-a", "57.131.128.129", 80, 4),
    ("p2-ovh-de1-c", "141.95.107.32", 40, 5),
    ("p2-ovh-gra9-b", "57.128.55.65", 80, 6),
    ("p2-ovh-gra9-c", "141.94.40.27", 40, 7),
    ("p2-ovh-rbx-a", "164.132.87.50", 80, 8),
    ("p2-ovh-rbx-c", "152.228.192.41", 40, 9),
    ("p2-ovh-par-a", "57.130.20.141", 80, 10),
    ("p2-ovh-par-c", "57.130.46.182", 40, 11),
    ("p2-ovh-uk1-a", "54.37.2.117", 80, 12),
    ("p2-ovh-uk1-c", "54.37.4.51", 40, 13),
    ("p2-ovh-gra7-a", "51.178.59.183", 80, 14),
    ("p2-ovh-gra7-c", "51.178.56.158", 40, 15),
    ("p2-ovh-sbg5-a", "51.91.146.93", 80, 16),
    ("p2-ovh-sbg5-c", "51.91.145.70", 40, 17),
]
BOX_COUNT = 18
HUB = "176.31.201.16"
UNIT = """[Unit]
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


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ssh(ip: str, remote: str, timeout: int = 90, user: str = "ubuntu") -> subprocess.CompletedProcess:
    return run(SSH_BASE + [f"{user}@{ip}", remote], timeout=timeout)


def scp(src: Path, dest: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return run(SCP_BASE + [str(src), dest], timeout=timeout)


def wait_ssh(ip: str, tries: int = 40) -> str | None:
    for _ in range(tries):
        p = ssh(ip, "echo SSH-OK; sudo -n true && echo SUDO-OK || echo SUDO-FAIL", timeout=20)
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0 and "SSH-OK" in out:
            return "ubuntu"
        time.sleep(8)
    return None


def seed_one(name: str, ip: str, cap: int, idx: int, token: str, hub_ready: bool) -> str:
    user = wait_ssh(ip, tries=24)
    if not user:
        return f"FAILED:ssh {name} {ip}"
    prefix = "sudo "
    ssh(ip, f"{prefix}mkdir -p /opt/p2 /opt/p2/workers /opt/p2/strikes /opt/p2/unit-locks /opt/p2/ast-integrate /root/.local/bin", timeout=30)
    got = ssh(ip, "test -f /tmp/p2-emit-tree.tgz && echo HAS-TGZ || echo NO-TGZ", timeout=20)
    if "HAS-TGZ" not in (got.stdout or ""):
        if hub_ready and ip != HUB:
            w = ssh(
                ip,
                f"curl -fsSL --retry 8 --retry-delay 3 -o /tmp/p2-emit-tree.tgz http://{HUB}:8000/p2-emit-tree.tgz && echo CURL-OK || echo CURL-FAIL",
                timeout=600,
            )
            if "CURL-OK" not in (w.stdout or ""):
                p = scp(TGZ, f"{user}@{ip}:/tmp/p2-emit-tree.tgz", timeout=900)
                if p.returncode != 0:
                    return f"FAILED:tgz {name} {(p.stderr or '')[-200:]}"
        else:
            p = scp(TGZ, f"{user}@{ip}:/tmp/p2-emit-tree.tgz", timeout=900)
            if p.returncode != 0:
                return f"FAILED:tgz {name} {(p.stderr or '')[-200:]}"
    ssh(ip, f"{prefix}tar xzf /tmp/p2-emit-tree.tgz -C /opt/p2/ast-integrate", timeout=300)
    scp(DISPATCH, f"{user}@{ip}:/tmp/dispatch_cursor.py", timeout=60)
    ssh(ip, f"{prefix}cp /tmp/dispatch_cursor.py /opt/p2/dispatch_cursor.py", timeout=20)
    if MEASURE.is_file():
        scp(MEASURE, f"{user}@{ip}:/tmp/_measure_one_delivered.py", timeout=60)
        ssh(
            ip,
            f"{prefix}mkdir -p /opt/p2/ast-integrate/command-center/p2-wave && "
            f"{prefix}cp /tmp/_measure_one_delivered.py /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py",
            timeout=20,
        )
    scp(LEFTOVER, f"{user}@{ip}:/tmp/leftover.json", timeout=60)
    ssh(
        ip,
        f"{prefix}cp /tmp/leftover.json /opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json",
        timeout=20,
    )
    if BOOTSTRAP.is_file():
        scp(BOOTSTRAP, f"{user}@{ip}:/tmp/_box_bootstrap.sh", timeout=30)
        ssh(ip, f"{prefix}bash /tmp/_box_bootstrap.sh", timeout=300)
    ssh(
        ip,
        f"{prefix}bash -lc 'curl -fsSL https://cursor.com/install | bash' || true; "
        f"{prefix}ln -sf /root/.local/bin/agent /usr/local/bin/agent || true; "
        f"{prefix}ln -sf /root/.local/bin/cursor-agent /usr/local/bin/cursor-agent || true",
        timeout=180,
    )
    env_body = (
        f"CURSOR_API_KEY={token}\n"
        f"CURSOR_API_TOKEN={token}\n"
        f"BOX_INDEX={idx}\n"
        f"BOX_COUNT={BOX_COUNT}\n"
        "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin\n"
        "HOME=/root\n"
    )
    ep = STAGE / f"cursor.env.{name}"
    ep.write_text(env_body, encoding="utf-8")
    try:
        scp(ep, f"{user}@{ip}:/tmp/cursor.env", timeout=30)
        ssh(ip, f"{prefix}cp /tmp/cursor.env /opt/p2/cursor.env && {prefix}chmod 600 /opt/p2/cursor.env", timeout=20)
    finally:
        ep.unlink(missing_ok=True)
    up = STAGE / f"{name}.service"
    up.write_text(UNIT.format(name=name, cap=cap), encoding="utf-8")
    try:
        scp(up, f"{user}@{ip}:/tmp/p2-supervisor.service", timeout=30)
        ssh(
            ip,
            f"{prefix}cp /tmp/p2-supervisor.service /etc/systemd/system/p2-supervisor.service && "
            f"{prefix}rm -f /opt/p2/completed.json /opt/p2/QUEUE-EMPTY && "
            f"{prefix}systemctl daemon-reload && {prefix}systemctl enable --now p2-supervisor && "
            f"{prefix}systemctl restart p2-supervisor",
            timeout=40,
        )
    finally:
        up.unlink(missing_ok=True)
    st = ssh(ip, f"{prefix}systemctl is-active p2-supervisor; {prefix}tail -n 6 /opt/p2/supervisor.log 2>/dev/null || true", timeout=20)
    body = (st.stdout or "") + (st.stderr or "")
    if "active" in body:
        return f"SUCCESS:seed {name} {ip} cap={cap} idx={idx}"
    return f"FAILED:seed {name} {ip} {body[-400:]}"


def start_hub(token: str) -> bool:
    user = wait_ssh(HUB, tries=8)
    if not user:
        print("FAILED:hub-ssh", HUB, flush=True)
        return False
    print("hub ssh up", HUB, flush=True)
    ssh(HUB, "sudo mkdir -p /opt/p2 /tmp", timeout=20)
    has = ssh(HUB, "test -f /tmp/p2-emit-tree.tgz && echo HAS || echo NO", timeout=15)
    if "HAS" not in (has.stdout or ""):
        print("scp tgz to hub", TGZ, "size", TGZ.stat().st_size if TGZ.exists() else 0, flush=True)
        p = scp(TGZ, f"ubuntu@{HUB}:/tmp/p2-emit-tree.tgz", timeout=900)
        print("scp hub rc", p.returncode, (p.stderr or "")[-200:], flush=True)
        if p.returncode != 0:
            return False
    ssh(HUB, "sudo pkill -f 'http.server 8000' || true; nohup python3 -m http.server 8000 --directory /tmp >/tmp/http-seed.log 2>&1 &", timeout=20)
    time.sleep(2)
    chk = ssh(HUB, "ss -ltn | grep 8000 || netstat -ltn | grep 8000 || echo NO-PORT", timeout=15)
    print("hub port", (chk.stdout or "").strip(), flush=True)
    return True


def main() -> int:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY") or ""
    if not token:
        print("FAILED:no CURSOR_API_TOKEN")
        return 2
    if not TGZ.is_file():
        print("FAILED:missing", TGZ)
        return 2
    if not DISPATCH.is_file() or not LEFTOVER.is_file():
        print("FAILED:missing dispatch or leftover")
        return 2
    print(f"token_len={len(token)} prefix={token[:4]} tgz={TGZ.stat().st_size}", flush=True)
    extra = json_ips()
    fleet = []
    for name, ip, cap, idx in FLEET:
        if not ip and name in extra:
            ip = extra[name]
        fleet.append((name, ip, cap, idx))
        print("fleet", name, ip, cap, idx, flush=True)
    hub_ok = start_hub(token)
    print("hub_ok", hub_ok, flush=True)
    ok = 0
    todo = [(n, ip, c, i) for n, ip, c, i in fleet if ip]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(seed_one, n, ip, c, i, token, hub_ok): n for n, ip, c, i in todo}
        for fut in as_completed(futs):
            msg = fut.result()
            print(msg, flush=True)
            if msg.startswith("SUCCESS:"):
                ok += 1
    print(f"SEEDED {ok}/{len(todo)}", flush=True)
    return 0 if ok else 1


def json_ips() -> dict[str, str]:
    """Optional override file written by the monitor."""
    path = WAVE / "ovh-monitor" / "fleet-now.json"
    if not path.is_file():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, str] = {}
    items = data.get("items") or data.get("boxes") or []
    if isinstance(data, list):
        items = data
    for it in items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "")
        ips = it.get("ipAddresses") or []
        ip = it.get("ip")
        if not ip:
            for a in ips:
                if isinstance(a, dict) and a.get("version") == 4 and a.get("type") == "public":
                    ip = a.get("ip")
                    break
        if name and ip:
            out[name] = str(ip)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
