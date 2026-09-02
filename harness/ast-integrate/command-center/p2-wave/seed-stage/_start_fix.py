#!/usr/bin/env python3
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
FIXER = STAGE / "fix_g1_fails.py"
DETAILS = STAGE.parent / "ovh-monitor" / "error-pull" / "g1-fail-details.json"
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


def one(box: str, ip: str, recs: list) -> str:
    host = f"root@{ip}"
    tmp = STAGE / f"g1-fails.{box}.json"
    payload = [{"id": r["id"], "hint": "\n".join((r.get("tail") or [])[-8:])} for r in recs]
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    p = run(SCP + [str(tmp), f"{host}:/opt/p2/g1-fails.json"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} SCP-FAILS {(p.stderr or '')[-120:]}"
    p = run(SCP + [str(FIXER), f"{host}:/opt/p2/fix_g1_fails.py"], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        return f"{box} SCP-FIXER {(p.stderr or '')[-120:]}"
    start = (
        "set -a; . /opt/p2/cursor.env; set +a; "
        "rm -f /opt/p2/g1-fix.json /opt/p2/g1-fix.log; "
        "nohup python3 -u /opt/p2/fix_g1_fails.py >/opt/p2/g1-fix.out 2>&1 & echo STARTED"
    )
    p = run(SSH + [host, start], capture_output=True, text=True, timeout=20)
    tmp.unlink(missing_ok=True)
    return f"{box} n={len(recs)} {(p.stdout or '').strip()} rc={p.returncode}"


def main() -> None:
    rows = json.loads(DETAILS.read_text(encoding="utf-8")).get("rows") or []
    by = defaultdict(list)
    for r in rows:
        if r.get("ok"):
            continue
        by[r["box"]].append(r)
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(one, box, BOX_IP[box], recs) for box, recs in by.items()]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
