#!/usr/bin/env python3
"""Inventory false-DONE / INFRA / strike-fail IDs on the OVH leftover fleet."""
from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

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
FLEET = [
    ("p2-ovh-gra11-a", "176.31.201.117"),
    ("p2-ovh-gra11-c", "176.31.201.215"),
    ("p2-ovh-waw1-b", "51.75.63.116"),
    ("p2-ovh-waw1-c", "54.38.138.226"),
    ("p2-ovh-de1-a", "51.75.93.252"),
    ("p2-ovh-de1-c", "162.19.209.251"),
    ("p2-ovh-gra9-b", "37.59.27.161"),
    ("p2-ovh-gra9-c", "141.94.186.60"),
    ("p2-ovh-rbx-a", "164.132.87.22"),
    ("p2-ovh-rbx-c", "152.228.192.99"),
    ("p2-ovh-par-a", "57.130.47.223"),
    ("p2-ovh-par-c", "57.130.46.182"),
    ("p2-ovh-uk1-a", "54.37.3.247"),
    ("p2-ovh-uk1-c", "54.37.7.164"),
    ("p2-ovh-gra7-a", "51.91.140.54"),
    ("p2-ovh-gra7-c", "51.210.248.225"),
    ("p2-ovh-sbg5-a", "57.128.35.67"),
    ("p2-ovh-sbg5-c", "57.128.111.33"),
]
REMOTE = r"""
import json, re
from pathlib import Path
UID = re.compile(r'[A-Z]{2,5}-\d{4}')
logp = Path('/opt/p2/supervisor.log')
false_done = []
infra = []
if logp.exists():
    for line in logp.read_text(errors='replace').splitlines():
        if ' DONE-OK ' in line and ('measure=FAILED' in line or 'FAILED:delivered' in line):
            m = UID.search(line)
            false_done.append({'line': line[-220:], 'id': m.group(0) if m else None})
        if ' INFRA ' in line:
            m = UID.search(line)
            infra.append({'line': line[-220:], 'id': m.group(0) if m else None})
strikes = []
sd = Path('/opt/p2/strikes')
if sd.is_dir():
    for p in sorted(sd.glob('*.json')):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if d.get('parked') or (d.get('attempts') or d.get('count')):
            strikes.append({
                'id': d.get('id') or p.stem,
                'count': d.get('count'),
                'parked': d.get('parked'),
                'reason': d.get('park_reason'),
                'attempts': d.get('attempts') or [],
            })
print(json.dumps({
    'false_done': false_done,
    'infra': infra,
    'strikes': strikes,
}, separators=(',', ':')))
"""
OUT = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull"


def one(name: str, ip: str) -> dict:
    payload = base64.b64encode(REMOTE.strip().encode()).decode()
    p = run(
        SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    rec = {"name": name, "ip": ip, "ok": p.returncode == 0}
    if p.returncode != 0:
        rec["error"] = ((p.stderr or "") + (p.stdout or ""))[-400:]
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["ok"] = False
        rec["error"] = f"{exc} {(p.stdout or '')[-200:]}"
    return rec


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    boxes = []
    with ThreadPoolExecutor(18) as ex:
        futs = [ex.submit(one, *row) for row in FLEET]
        for f in as_completed(futs):
            rec = f.result()
            boxes.append(rec)
            print(
                f"{rec['name']:18s} false={len(rec.get('false_done') or [])} "
                f"infra={len(rec.get('infra') or [])} strikes={len(rec.get('strikes') or [])} "
                f"ok={rec.get('ok')}",
                flush=True,
            )
    boxes.sort(key=lambda b: b["name"])
    false_ids = {}
    infra_ids = {}
    strike_ids = {}
    for b in boxes:
        for item in b.get("false_done") or []:
            uid = item.get("id")
            if uid:
                false_ids.setdefault(uid, []).append({"box": b["name"], "ip": b["ip"], "line": item.get("line")})
        for item in b.get("infra") or []:
            uid = item.get("id")
            if uid:
                infra_ids.setdefault(uid, []).append({"box": b["name"], "ip": b["ip"], "line": item.get("line")})
        for item in b.get("strikes") or []:
            uid = item.get("id")
            if uid:
                strike_ids.setdefault(uid, []).append({"box": b["name"], "ip": b["ip"], **item})
    inv = {
        "false_done_n": len(false_ids),
        "infra_n": len(infra_ids),
        "strike_n": len(strike_ids),
        "false_done_ids": sorted(false_ids),
        "infra_ids": sorted(infra_ids),
        "strike_ids": sorted(strike_ids),
        "false_done": false_ids,
        "infra": infra_ids,
        "strikes": strike_ids,
        "boxes": [
            {
                "name": b["name"],
                "ip": b["ip"],
                "ok": b.get("ok"),
                "false_n": len(b.get("false_done") or []),
                "infra_n": len(b.get("infra") or []),
                "strike_n": len(b.get("strikes") or []),
                "error": b.get("error"),
            }
            for b in boxes
        ],
    }
    path = OUT / "inventory.json"
    path.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")
    print("WROTE", path)
    print("FALSE", inv["false_done_n"], inv["false_done_ids"])
    print("INFRA", inv["infra_n"], inv["infra_ids"])
    print("STRIKES", inv["strike_n"], inv["strike_ids"])


if __name__ == "__main__":
    main()
