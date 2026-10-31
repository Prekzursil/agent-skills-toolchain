#!/usr/bin/env python3
"""Home-box G-1 fix for the last two remesure-281 fails."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
SCP = [
    "scp",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
JOBS = [
    ("de1-c", "162.19.209.251", "IMP-0051"),
    ("gra9-c", "141.94.186.60", "BLD-0055"),
]
PATCH = r"""
from pathlib import Path
src = Path('/opt/p2/fix_g1_fails.py').read_text()
src = src.replace('timeout=90', 'timeout=180')
src = src.replace('FAILS = Path("/opt/p2/g1-fails.json")', 'FAILS = Path("/opt/p2/g1-w4-fails.json")')
src = src.replace('LOG = Path("/opt/p2/g1-fix.log")', 'LOG = Path("/opt/p2/g1-w4.log")')
src = src.replace('OUT = Path("/opt/p2/g1-fix.json")', 'OUT = Path("/opt/p2/g1-w4.json")')
src = src.replace('FIX-DONE', 'W4-DONE')
Path('/opt/p2/fix_g1_w4.py').write_text(src)
print('WROTE-W4')
"""


def ssh(ip, cmd, timeout=25):
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=timeout)
    return f"rc={p.returncode} {((p.stdout or '')+(p.stderr or '')).strip().replace(chr(10),' | ')[:300]}"


def one(box, ip, uid):
    host = f"root@{ip}"
    tmp = STAGE / f"g1-w4-fails.{uid}.json"
    tmp.write_text(json.dumps([{"id": uid, "hint": "remeasure-281 fail; fix then remesure"}], indent=2) + "\n", encoding="utf-8")
    p = run(SCP + [str(tmp), f"{host}:/opt/p2/g1-w4-fails.json"], capture_output=True, text=True, timeout=25)
    if p.returncode != 0:
        return f"{box} SCP-FAILS {(p.stderr or '')[-120:]}"
    p = run(SCP + [str(STAGE / "fix_g1_fails.py"), f"{host}:/opt/p2/fix_g1_fails.py"], capture_output=True, text=True, timeout=25)
    if p.returncode != 0:
        return f"{box} SCP-FIXER {(p.stderr or '')[-120:]}"
    payload = __import__("base64").b64encode(PATCH.strip().encode()).decode()
    wrote = ssh(ip, f"echo {payload} | base64 -d | python3")
    start = (
        "set -a; . /opt/p2/cursor.env; set +a; "
        "rm -f /opt/p2/g1-w4.json; "
        "nohup python3 -u /opt/p2/fix_g1_w4.py >/opt/p2/g1-w4.out 2>&1 & echo W4-STARTED $!"
    )
    started = ssh(ip, start)
    tmp.unlink(missing_ok=True)
    return f"{box} {uid} {wrote} || {started}"


def main():
    for j in JOBS:
        print(one(*j), flush=True)


if __name__ == "__main__":
    main()
