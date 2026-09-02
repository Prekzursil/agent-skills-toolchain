#!/usr/bin/env python3
"""Wave-2 speed: fan leftover G-1 IDs onto idle boxes; restart leftover on G-1-done boxes."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
DETAILS = WAVE / "ovh-monitor" / "error-pull" / "g1-fail-details.json"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
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
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]

# remaining not-yet-OK from fleet-now; skip IDs already being fixed on their home box
FAN = [
    # id, dest_box, dest_ip
    ("RES-0015", "de1-a", "51.75.93.252"),
]
RESTART_LEFTOVER = [
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
]
WORKER_PEEK = [
    ("par-c", "57.130.46.182", "TST-0009"),
    ("rbx-c", "152.228.192.99", "TST-0133"),
]
FIXER_REMOTE = r"""
from pathlib import Path
src = Path('/opt/p2/fix_g1_fails.py').read_text()
src = src.replace('FAILS = Path("/opt/p2/g1-fails.json")', 'FAILS = Path("/opt/p2/g1-fan-fails.json")')
src = src.replace('LOG = Path("/opt/p2/g1-fix.log")', 'LOG = Path("/opt/p2/g1-fan.log")')
src = src.replace('OUT = Path("/opt/p2/g1-fix.json")', 'OUT = Path("/opt/p2/g1-fan.json")')
src = src.replace('FIX-DONE', 'FAN-DONE')
Path('/opt/p2/fix_g1_fan.py').write_text(src)
print('WROTE-FAN')
"""


def ssh(ip: str, cmd: str, timeout: int = 25) -> str:
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=timeout)
    body = ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " | ")
    return f"rc={p.returncode} {body[:500]}"


def b64_py(code: str) -> str:
    payload = __import__("base64").b64encode(code.strip().encode()).decode()
    return f"echo {payload} | base64 -d | python3"


def hint_for(uid: str) -> str:
    rows = json.loads(DETAILS.read_text(encoding="utf-8")).get("rows") or []
    for r in rows:
        if r.get("id") == uid:
            return "\n".join((r.get("tail") or [])[-8:])
    return ""


def fan_one(uid: str, box: str, ip: str) -> str:
    host = f"root@{ip}"
    tmp = STAGE / f"g1-fan-fails.{uid}.json"
    tmp.write_text(json.dumps([{"id": uid, "hint": hint_for(uid)}], indent=2) + "\n", encoding="utf-8")
    p = run(SCP + [str(tmp), f"{host}:/opt/p2/g1-fan-fails.json"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} {uid} SCP-FAIL {(p.stderr or '')[-160:]}"
    p = run(SCP + [str(STAGE / "fix_g1_fails.py"), f"{host}:/opt/p2/fix_g1_fails.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} {uid} SCP-FIXER {(p.stderr or '')[-160:]}"
    wrote = ssh(ip, b64_py(FIXER_REMOTE))
    start = (
        "set -a; . /opt/p2/cursor.env; set +a; "
        "rm -f /opt/p2/g1-fan.json; "
        "nohup python3 -u /opt/p2/fix_g1_fan.py >/opt/p2/g1-fan.out 2>&1 & echo FAN-STARTED $!"
    )
    started = ssh(ip, start)
    tmp.unlink(missing_ok=True)
    return f"{box} {uid} {wrote} || {started}"


def peek_worker(name: str, ip: str, uid: str) -> str:
    cmd = (
        f"echo FIXPY $(pgrep -cf fix_g1_fails.py || true); "
        f"echo G1FIX $(pgrep -cf 'Fix THIS unit only' || true); "
        f"echo LOG $(wc -c /opt/p2/workers/g1fix-{uid}/worker.log 2>/dev/null || echo missing); "
        f"echo AGE $(ps -o etime= -p $(pgrep -f 'Fix THIS unit only' | head -1) 2>/dev/null || echo none); "
        f"tail -n 2 /opt/p2/g1-fix.log 2>/dev/null"
    )
    return f"{name} {uid} {ssh(ip, cmd)}"


def restart_one(name: str, ip: str) -> str:
    cmd = (
        "systemctl start p2-supervisor; sleep 1; "
        "echo SVC $(systemctl is-active p2-supervisor); "
        "echo AGENTS $(pgrep -cf 'on this Linux worktree' || true)"
    )
    return f"{name} {ssh(ip, cmd)}"


def main() -> None:
    print("=== peek in-flight g1fix ===", flush=True)
    with ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(peek_worker, *r) for r in WORKER_PEEK]
        for f in as_completed(futs):
            print(f.result(), flush=True)
    print("=== fan remaining ===", flush=True)
    with ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(fan_one, *r) for r in FAN]
        for f in as_completed(futs):
            print(f.result(), flush=True)
    print("=== restart leftover on G-1-done boxes ===", flush=True)
    with ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(restart_one, *r) for r in RESTART_LEFTOVER]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
