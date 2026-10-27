#!/usr/bin/env python3
"""Fix remaining G-1 fails on the HOME box that holds the artifacts.

- Kill the wrong-box RES-0015 fan on de1-a
- Start RES-0015 on rbx-c (do NOT start leftover there yet)
- Start remesure-281 fail fixes on their home boxes via g1-w3.json
"""
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
BOX_IP = {
    "gra11-a": "176.31.201.117",
    "gra11-c": "176.31.201.215",
    "waw1-b": "51.75.63.116",
    "waw1-c": "54.38.138.226",
    "de1-a": "51.75.93.252",
    "de1-c": "162.19.209.251",
    "gra9-b": "37.59.27.161",
    "gra9-c": "141.94.186.60",
    "rbx-a": "164.132.87.22",
    "rbx-c": "152.228.192.99",
    "par-a": "57.130.47.223",
    "par-c": "57.130.46.182",
    "uk1-a": "54.37.3.247",
    "uk1-c": "54.37.7.164",
    "sbg5-a": "57.128.35.67",
    "sbg5-c": "57.128.111.33",
    "gra7-a": "51.91.140.54",
    "gra7-c": "51.210.248.225",
}
# remesure-281 fails by home box
W3 = {
    "par-c": ["ADV-0014", "RES-0152"],
    "rbx-a": ["ADV-0011"],
    "waw1-c": ["ARC-0110"],
    "uk1-a": ["RES-0153"],
    "gra11-c": ["AUD-0095", "RES-0187"],
    "gra11-a": ["CNF-0169"],
    "gra7-c": ["AUD-0028", "RES-0156"],
    "gra9-c": ["ADV-0001"],
}
PATCH = r"""
from pathlib import Path
src = Path('/opt/p2/fix_g1_fails.py').read_text()
src = src.replace('timeout=90', 'timeout=180')
src = src.replace('FAILS = Path("/opt/p2/g1-fails.json")', 'FAILS = Path("/opt/p2/g1-w3-fails.json")')
src = src.replace('LOG = Path("/opt/p2/g1-fix.log")', 'LOG = Path("/opt/p2/g1-w3.log")')
src = src.replace('OUT = Path("/opt/p2/g1-fix.json")', 'OUT = Path("/opt/p2/g1-w3.json")')
src = src.replace('FIX-DONE', 'W3-DONE')
Path('/opt/p2/fix_g1_w3.py').write_text(src)
print('WROTE-W3')
"""


def ssh(ip: str, cmd: str, timeout: int = 25) -> str:
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=timeout)
    return f"rc={p.returncode} {((p.stdout or '') + (p.stderr or '')).strip().replace(chr(10), ' | ')[:400]}"


def b64_py(code: str) -> str:
    payload = __import__("base64").b64encode(code.strip().encode()).decode()
    return f"echo {payload} | base64 -d | python3"


def hints(uids: list[str]) -> list[dict]:
    rows = json.loads(DETAILS.read_text(encoding="utf-8")).get("rows") or []
    by = {r["id"]: r for r in rows}
    out = []
    for uid in uids:
        r = by.get(uid) or {}
        out.append({"id": uid, "hint": "\n".join((r.get("tail") or [])[-8:])})
    return out


def start_w3(box: str, uids: list[str]) -> str:
    ip = BOX_IP[box]
    host = f"root@{ip}"
    tmp = STAGE / f"g1-w3-fails.{box}.json"
    tmp.write_text(json.dumps(hints(uids), indent=2) + "\n", encoding="utf-8")
    p = run(SCP + [str(tmp), f"{host}:/opt/p2/g1-w3-fails.json"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} SCP-FAILS {(p.stderr or '')[-120:]}"
    p = run(SCP + [str(STAGE / "fix_g1_fails.py"), f"{host}:/opt/p2/fix_g1_fails.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} SCP-FIXER {(p.stderr or '')[-120:]}"
    wrote = ssh(ip, b64_py(PATCH))
    start = (
        "set -a; . /opt/p2/cursor.env; set +a; "
        "rm -f /opt/p2/g1-w3.json; "
        "nohup python3 -u /opt/p2/fix_g1_w3.py >/opt/p2/g1-w3.out 2>&1 & echo W3-STARTED $!"
    )
    started = ssh(ip, start)
    tmp.unlink(missing_ok=True)
    return f"{box} n={len(uids)} {wrote} || {started}"


def kill_wrong_fan() -> str:
    # de1-a should not own RES-0015
    cmd = (
        "pkill -f fix_g1_fan.py || true; "
        "pkill -f 'P2-deliver unit RES-0015' || true; "
        "echo KILLED-FAN; "
        "test -f /opt/p2/g1-fan.log && tail -n 2 /opt/p2/g1-fan.log || true"
    )
    return "de1-a " + ssh(BOX_IP["de1-a"], cmd)


def start_res0015_home() -> str:
    return start_w3("rbx-c", ["RES-0015"])


def main() -> None:
    print("=== kill wrong-box fan ===", flush=True)
    print(kill_wrong_fan(), flush=True)
    jobs = dict(W3)
    jobs["rbx-c"] = ["RES-0015"] + jobs.get("rbx-c", [])
    print("=== start home-box W3 ===", flush=True)
    with ThreadPoolExecutor(10) as ex:
        futs = [ex.submit(start_w3, box, uids) for box, uids in jobs.items()]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
