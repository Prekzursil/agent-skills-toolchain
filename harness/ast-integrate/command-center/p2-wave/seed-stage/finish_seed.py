#!/usr/bin/env python3
"""Finish leftover seed: recurl incomplete tgz, extract, start supervisor. Skip live boxes."""
from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
DISPATCH = STAGE / "dispatch_cursor.py"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
MEASURE = WAVE / "_measure_one_delivered.py"
KEY = Path.home() / ".ssh" / "id_ed25519"
HUB = "176.31.201.16"
NEED = 657033137
BOX_COUNT = 18
FLEET = [
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
SSH = [
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
SCP = ["scp", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "-o", "StrictHostKeyChecking=accept-new"]


def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ssh(ip, remote, timeout=90):
    return run(SSH + [f"ubuntu@{ip}", remote], timeout=timeout)


def finish_one(name, ip, cap, idx, token):
    st = ssh(ip, "sudo systemctl is-active p2-supervisor 2>/dev/null || echo inactive", timeout=20)
    if "active" in (st.stdout or "") and "inactive" not in (st.stdout or "").split():
        return f"SKIP-LIVE {name} {ip}"
    ssh(ip, "sudo mkdir -p /opt/p2 /opt/p2/workers /opt/p2/strikes /opt/p2/unit-locks /opt/p2/ast-integrate", timeout=20)
    chk = ssh(
        ip,
        f"python3 - <<'PY'\nfrom pathlib import Path\np=Path('/tmp/p2-emit-tree.tgz')\nprint(p.stat().st_size if p.is_file() else 0)\nPY",
        timeout=20,
    )
    try:
        size = int((chk.stdout or "0").strip().split()[-1])
    except ValueError:
        size = 0
    if size != NEED:
        ssh(ip, "rm -f /tmp/p2-emit-tree.tgz", timeout=20)
        w = ssh(
            ip,
            f"curl -fL --retry 12 --retry-delay 2 --retry-all-errors -o /tmp/p2-emit-tree.tgz http://{HUB}:8000/p2-emit-tree.tgz && python3 -c \"import os; print(os.path.getsize('/tmp/p2-emit-tree.tgz'))\"",
            timeout=600,
        )
        if str(NEED) not in (w.stdout or ""):
            return f"FAILED:curl {name} size={(w.stdout or '')[-80:]}"
    x = ssh(ip, "sudo tar xzf /tmp/p2-emit-tree.tgz -C /opt/p2/ast-integrate && echo TAR-OK", timeout=300)
    if "TAR-OK" not in (x.stdout or ""):
        return f"FAILED:tar {name} {(x.stderr or x.stdout or '')[-200:]}"
    run(SCP + [str(DISPATCH), f"ubuntu@{ip}:/tmp/dispatch_cursor.py"], timeout=30)
    ssh(ip, "sudo cp /tmp/dispatch_cursor.py /opt/p2/dispatch_cursor.py", timeout=15)
    if MEASURE.is_file():
        run(SCP + [str(MEASURE), f"ubuntu@{ip}:/tmp/_measure_one_delivered.py"], timeout=30)
        ssh(
            ip,
            "sudo mkdir -p /opt/p2/ast-integrate/command-center/p2-wave && sudo cp /tmp/_measure_one_delivered.py /opt/p2/ast-integrate/command-center/p2-wave/_measure_one_delivered.py",
            timeout=15,
        )
    run(SCP + [str(LEFTOVER), f"ubuntu@{ip}:/tmp/leftover.json"], timeout=30)
    ssh(ip, "sudo cp /tmp/leftover.json /opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json", timeout=15)
    env = (
        f"CURSOR_API_KEY={token}\nCURSOR_API_TOKEN={token}\n"
        f"BOX_INDEX={idx}\nBOX_COUNT={BOX_COUNT}\n"
        "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin\nHOME=/root\n"
    )
    ep = STAGE / f"cursor.env.{name}"
    ep.write_text(env, encoding="utf-8")
    run(SCP + [str(ep), f"ubuntu@{ip}:/tmp/cursor.env"], timeout=20)
    ep.unlink(missing_ok=True)
    ssh(ip, "sudo cp /tmp/cursor.env /opt/p2/cursor.env && sudo chmod 600 /opt/p2/cursor.env", timeout=15)
    ssh(
        ip,
        "command -v agent >/dev/null || command -v cursor-agent >/dev/null || curl -fsSL https://cursor.com/install | sudo bash; "
        "sudo ln -sf /root/.local/bin/agent /usr/local/bin/agent; sudo ln -sf /root/.local/bin/cursor-agent /usr/local/bin/cursor-agent; "
        "sudo python3 -m pip install -q --break-system-packages jsonschema referencing || true",
        timeout=180,
    )
    up = STAGE / f"{name}.service"
    up.write_text(UNIT.format(name=name, cap=cap), encoding="utf-8")
    run(SCP + [str(up), f"ubuntu@{ip}:/tmp/p2-supervisor.service"], timeout=20)
    up.unlink(missing_ok=True)
    ssh(
        ip,
        "sudo cp /tmp/p2-supervisor.service /etc/systemd/system/p2-supervisor.service && "
        "sudo rm -f /opt/p2/completed.json /opt/p2/QUEUE-EMPTY && "
        "sudo systemctl daemon-reload && sudo systemctl enable --now p2-supervisor",
        timeout=40,
    )
    st2 = ssh(ip, "sudo systemctl is-active p2-supervisor; sudo tail -n 4 /opt/p2/supervisor.log 2>/dev/null || true", timeout=20)
    body = (st2.stdout or "") + (st2.stderr or "")
    if "active" in body and "inactive" not in body.split()[:3]:
        return f"SUCCESS:seed {name} {ip} cap={cap} idx={idx}"
    return f"FAILED:seed {name} {ip} {body[-300:]}"


def main() -> int:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY") or ""
    if not token:
        print("FAILED:no token")
        return 2
    print(f"token_len={len(token)} prefix={token[:4]}", flush=True)
    ok = skip = fail = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = {pool.submit(finish_one, n, ip, c, i, token): n for n, ip, c, i in FLEET}
        for fut in as_completed(futs):
            msg = fut.result()
            print(msg, flush=True)
            if msg.startswith("SUCCESS:"):
                ok += 1
            elif msg.startswith("SKIP-LIVE"):
                skip += 1
            else:
                fail += 1
    print(f"FINISH ok={ok} skip={skip} fail={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
