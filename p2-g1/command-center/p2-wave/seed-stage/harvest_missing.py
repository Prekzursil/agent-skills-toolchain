#!/usr/bin/env python3
"""Pull only leftover IDs still missing locally. Receipts-only packs."""
from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
REPO = WAVE.parent.parent
KEY = Path.home() / ".ssh" / "id_ed25519"
PACK = STAGE / "_pack_missing.py"
CENSUS = WAVE / "ovh-monitor" / "leftover-local-census.json"
FLEET = json.loads((WAVE / "ovh-monitor" / "fleet-now.json").read_text(encoding="utf-8"))["items"]
PULL = WAVE / "ovh-monitor" / "missing-pull"
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
]
SCP = [
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


def run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def harvest_one(name: str, ip: str) -> str:
    dest = PULL / name
    dest.mkdir(parents=True, exist_ok=True)
    tgz = dest / "p2-missing-delta.tgz"
    run(SCP + [str(CENSUS.parent / "missing_ids.json"), f"ubuntu@{ip}:/tmp/missing_ids.json"], timeout=20)
    run(SCP + [str(PACK), f"ubuntu@{ip}:/tmp/_pack_missing.py"], timeout=20)
    ssh = run(SSH + [f"ubuntu@{ip}", "sudo cp /tmp/missing_ids.json /tmp/missing_ids.json; sudo python3 /tmp/_pack_missing.py"], timeout=120)
    body = (ssh.stdout or "") + (ssh.stderr or "")
    if "PACK-MISSING-OK" not in body:
        return f"FAILED:pack {name} {body[-250:]}"
    s = run(SCP + [f"ubuntu@{ip}:/tmp/p2-missing-delta.tgz", str(tgz)], timeout=180)
    if s.returncode != 0 or not tgz.is_file():
        return f"FAILED:scp {name} {(s.stderr or '')[-200:]}"
    extract = dest / "delta"
    if extract.exists():
        shutil.rmtree(extract, ignore_errors=True)
    extract.mkdir(parents=True, exist_ok=True)
    if tgz.stat().st_size < 32:
        return f"SUCCESS:empty {name} bytes={tgz.stat().st_size}"
    with tarfile.open(tgz, "r:gz") as tf:
        tf.extractall(extract)
    copied = 0
    for src in extract.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(extract).as_posix()
        dst = REPO / rel
        if dst.is_file() and dst.stat().st_size >= src.stat().st_size:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return f"SUCCESS:harvest {name} bytes={tgz.stat().st_size} copied={copied} {body.splitlines()[0] if body.strip() else ''}"


def main() -> int:
    missing = json.loads(CENSUS.read_text(encoding="utf-8")).get("missing_ids") or []
    (CENSUS.parent / "missing_ids.json").write_text(json.dumps(missing) + "\n", encoding="utf-8")
    print(f"missing={len(missing)} boxes={len(FLEET)}", flush=True)
    PULL.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = {pool.submit(harvest_one, it["name"], it["ip"]): it["name"] for it in FLEET}
        for fut in as_completed(futs):
            msg = fut.result()
            print(msg, flush=True)
            if msg.startswith("SUCCESS:"):
                ok += 1
            else:
                fail += 1
    print(f"PULL ok={ok} fail={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
