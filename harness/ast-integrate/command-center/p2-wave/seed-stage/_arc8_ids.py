#!/usr/bin/env python3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
FLEET = [
    ("p2-ovh-gra11-a", "176.31.201.117", 0),
    ("p2-ovh-gra11-c", "176.31.201.215", 1),
    ("p2-ovh-waw1-b", "51.75.63.116", 2),
    ("p2-ovh-waw1-c", "54.38.138.226", 3),
    ("p2-ovh-de1-a", "51.75.93.252", 4),
    ("p2-ovh-de1-c", "162.19.209.251", 5),
    ("p2-ovh-gra9-b", "37.59.27.161", 6),
    ("p2-ovh-gra9-c", "141.94.186.60", 7),
    ("p2-ovh-rbx-a", "164.132.87.22", 8),
    ("p2-ovh-rbx-c", "152.228.192.99", 9),
    ("p2-ovh-par-a", "57.130.47.223", 10),
    ("p2-ovh-par-c", "57.130.46.182", 11),
    ("p2-ovh-uk1-a", "54.37.3.247", 12),
    ("p2-ovh-uk1-c", "54.37.7.164", 13),
    ("p2-ovh-gra7-a", "51.91.140.54", 14),
    ("p2-ovh-gra7-c", "51.210.248.225", 15),
    ("p2-ovh-sbg5-a", "57.128.35.67", 16),
    ("p2-ovh-sbg5-c", "57.128.111.33", 17),
]
CMD = (
    "python3 -c "
    "\"import json;from pathlib import Path;"
    "p=Path('/opt/p2/completed.json');"
    "ids=json.loads(p.read_text()).get('ids') if p.exists() else [];"
    "print(' '.join(i for i in ids if str(i).startswith('ARC-')));"
    "import os;"
    "print('IDX',open('/opt/p2/cursor.env').read().split('BOX_INDEX=')[-1].splitlines()[0] if Path('/opt/p2/cursor.env').exists() else 'noenv')\""
)
WAVE = Path(__file__).resolve().parent.parent
LEFT = json.loads((WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json").read_text(encoding="utf-8"))
ARC = [i for i in LEFT.get("remaining_ids") or [] if str(i).startswith("ARC-")]


def slot(uid: str, n: int = 18) -> int:
    return sum(ord(c) for c in uid) % n


def one(name: str, ip: str, idx: int) -> tuple[str, set[str], str]:
    p = run(SSH + [f"root@{ip}", CMD], capture_output=True, text=True, timeout=25)
    lines = (p.stdout or "").strip().splitlines()
    ids: set[str] = set()
    env = ""
    for line in lines:
        if line.startswith("IDX"):
            env = line
        else:
            ids.update(line.split())
    return name, ids, env + " rc=" + str(p.returncode)


def main() -> None:
    done: set[str] = set()
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *row) for row in FLEET]
        for f in as_completed(futs):
            name, ids, env = f.result()
            print(f"{name:18s} arc_done={len(ids):3d} {env}", flush=True)
            done |= ids
    leftover = set(ARC)
    remain = sorted(leftover - done)
    print("LEFTOVER_ARC", len(leftover), "FLEET_DONE_ARC", len(done), "REMAIN", len(remain))
    idx_to_name = {row[2]: row[0] for row in FLEET}
    for uid in remain:
        print(f"  {uid} slot={slot(uid)} owner={idx_to_name.get(slot(uid))}")


if __name__ == "__main__":
    main()
