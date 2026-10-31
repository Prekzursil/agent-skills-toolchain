#!/usr/bin/env python3
"""Poll leftover fleet, pack receipts (not probes-only), pull until ready_units 2007."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
REPO = WAVE.parent.parent
KEY = Path.home() / ".ssh" / "id_ed25519"
OUT = WAVE / "ovh-monitor"
PULL = OUT / "delivery-pull"
SSH = [
    "ssh",
    "-i",
    str(KEY),
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
]
SCP = [
    "scp",
    "-i",
    str(KEY),
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
]
PACK = r"""
set -e
cd /opt/p2/ast-integrate
rm -f /tmp/p2-delivery.tgz
python3 - <<'PY'
import json
from pathlib import Path
p=Path("/opt/p2/completed.json")
n=0
if p.is_file():
    try:
        n=len((json.loads(p.read_text()) or {}).get("ids") or [])
    except Exception:
        n=0
print("COMPLETED", n)
PY
# Catalog output_path lives under command-center/ (design, phase3/4, receipts, ...).
# p2-wave/ is probes+harvest and is NOT the delivery surface.
tar --ignore-failed-read --warning=no-file-changed --warning=no-file-removed \
  --exclude=command-center/p2-wave \
  --exclude=node_modules --exclude=__pycache__ --exclude='*.pyc' \
  -czf /tmp/p2-delivery.tgz \
  command-center \
  tools/command-center \
  tools/fan_in \
  platform/schema
ls -lh /tmp/p2-delivery.tgz
echo PACK-DELIVERY-OK
"""


def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def load_fleet():
    path = OUT / "fleet-now.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") or data.get("boxes") or []
    out = []
    for it in items:
        name = it.get("name")
        ip = it.get("ip")
        if not ip:
            for a in it.get("ipAddresses") or []:
                if a.get("version") == 4 and a.get("type") == "public":
                    ip = a.get("ip")
                    break
        if name and ip:
            out.append((name, ip))
    return out


def census_local() -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = cat.get("work_units") or []
    present = 0
    missing = []
    for u in units:
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if rel and (REPO / rel).is_file():
            present += 1
        elif rel:
            missing.append(u.get("id"))
    ready = None
    ru = REPO / "command-center" / "ready_units.py"
    if ru.is_file():
        p = run(["python", str(ru)], timeout=180)
        ready = ((p.stdout or "") + (p.stderr or ""))[-1500:]
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "catalog": len(units),
        "output_present": present,
        "output_missing": len(missing),
        "ready_tail": ready,
    }
    (OUT / "delivery-census.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(
        f"{rec['ts']} output_present={present}/{len(units)} missing={len(missing)}",
        flush=True,
    )
    if ready:
        print(ready[-400:], flush=True)
    return rec


def pull_one(name: str, ip: str) -> str:
    dest_dir = PULL / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    p = run(SSH + [f"ubuntu@{ip}", PACK], timeout=240)
    print(name, (p.stdout or "")[-300:], (p.stderr or "")[-200:], flush=True)
    if "PACK-DELIVERY-OK" not in (p.stdout or ""):
        return f"FAILED:pack {name}"
    tgz = dest_dir / "p2-delivery.tgz"
    s = run(SCP + [f"ubuntu@{ip}:/tmp/p2-delivery.tgz", str(tgz)], timeout=240)
    if s.returncode != 0 or not tgz.is_file():
        return f"FAILED:scp {name}"
    extract = dest_dir / "tree"
    extract.mkdir(parents=True, exist_ok=True)
    run(["tar", "xzf", str(tgz), "-C", str(extract)], timeout=180)
    # merge receipts into repo
    for rel in ["command-center/receipts", "command-center/adversarial", "command-center/research", "command-center/audit"]:
        src = extract / rel
        dst = REPO / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            run(["robocopy", str(src), str(dst), "/E", "/XO", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"], timeout=180)
    return f"SUCCESS:pull {name} size={tgz.stat().st_size}"


def main() -> int:
    PULL.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 55 * 60
    while time.time() < deadline:
        fleet = load_fleet()
        print("fleet", len(fleet), flush=True)
        for name, ip in fleet:
            try:
                msg = pull_one(name, ip)
            except Exception as exc:
                msg = f"FAILED:{name} {exc}"
            print(msg, flush=True)
        rec = census_local()
        if rec.get("output_present") >= 2007:
            print("SUCCESS:local-output 2007", flush=True)
            return 0
        time.sleep(180)
    rec = census_local()
    print("TIMEOUT census", rec.get("output_present"), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
