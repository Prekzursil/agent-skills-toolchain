#!/usr/bin/env python3
"""Create 3 Education boxes, deploy Cursor agent CLI fleet, start supervisors."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
STAGE = Path(__file__).resolve().parent
KEY = Path.home() / ".ssh" / "id_ed25519"
INIT = STAGE / "scw-cloud-init-cursor.yaml"
LOOP = STAGE / "dispatch_cursor.py"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
PROJECT = "9fdb8290-36af-46a5-922d-f62a22f6c04c"
ZONE = "fr-par-1"
BOXES = [
    ("p2-cur-a", "POP2-HM-32C-256G", 96),
    ("p2-cur-b", "POP2-HM-16C-128G", 48),
    ("p2-cur-c", "POP2-32C-128G", 48),
]


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def scw_create(name: str, typ: str) -> str:
    cmd = [
        "scw",
        "instance",
        "server",
        "create",
        f"name={name}",
        f"type={typ}",
        "image=ubuntu_jammy",
        "ip=new",
        f"project-id={PROJECT}",
        f"zone={ZONE}",
        "tags.0=p2-cursor",
        "tags.1=grok-46",
        f"cloud-init=@{INIT}",
        "-o",
        "json",
    ]
    # Prefer block root; fall back if CLI rejects.
    for root in ("root-volume=block:80GB", "root-volume=sbs_volume:80GB", None):
        c = list(cmd)
        if root:
            c.insert(-2, root)
        p = run(c, timeout=180)
        if p.returncode == 0 and p.stdout.strip():
            print(f"CREATE-OK {name} {typ} root={root}", flush=True)
            print(p.stdout[:1500], flush=True)
            return p.stdout
        print(f"CREATE-TRY {name} {root} rc={p.returncode} {(p.stderr or p.stdout)[-400:]}", flush=True)
    raise RuntimeError(f"create failed {name}")


def list_servers() -> str:
    p = run(["scw", "instance", "server", "list", f"zone={ZONE}", f"project-id={PROJECT}"])
    return (p.stdout or "") + (p.stderr or "")


def main() -> int:
    token = os.environ.get("CURSOR_API_TOKEN") or os.environ.get("CURSOR_API_KEY")
    if not token:
        print("FAILED:no CURSOR_API_TOKEN")
        return 2
    print(f"token_len={len(token)} prefix={token[:4]} (not printing rest)", flush=True)
    if not INIT.is_file() or not LOOP.is_file():
        print("FAILED:missing init or dispatcher")
        return 2
    print("===== existing =====", flush=True)
    print(list_servers(), flush=True)
    for name, typ, _cap in BOXES:
        try:
            scw_create(name, typ)
        except Exception as exc:
            print(f"FAILED:create {name} {exc}", flush=True)
            return 1
        time.sleep(2)
    print("===== after create =====", flush=True)
    print(list_servers(), flush=True)
    print("SUCCESS:create-submitted — wait for SSH then deploy", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
