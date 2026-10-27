#!/usr/bin/env python3
"""Parallel leftover harvest: pack output_path+probes on every box, pull, merge locally."""
from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
REPO = WAVE.parent.parent
KEY = Path.home() / ".ssh" / "id_ed25519"
PACK = STAGE / "_pack_leftover_delta.py"
FLEET_PATH = WAVE / "ovh-monitor" / "fleet-now.json"
PULL = WAVE / "ovh-monitor" / "delivery-pull"
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


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def fleet() -> list[tuple[str, str]]:
    data = json.loads(FLEET_PATH.read_text(encoding="utf-8"))
    return [(it["name"], it["ip"]) for it in data["items"]]


def harvest_one(name: str, ip: str) -> str:
    dest = PULL / name
    dest.mkdir(parents=True, exist_ok=True)
    tgz = dest / "p2-leftover-delta.tgz"
    p = run(SCP + [str(PACK), f"ubuntu@{ip}:/tmp/_pack_leftover_delta.py"], timeout=30)
    if p.returncode != 0:
        return f"FAILED:scp-pack {name} {(p.stderr or '')[-200:]}"
    r = run(SSH + [f"ubuntu@{ip}", "sudo python3 /tmp/_pack_leftover_delta.py"], timeout=240)
    body = (r.stdout or "") + (r.stderr or "")
    if "PACK-DELTA-OK" not in body:
        return f"FAILED:pack {name} {body[-300:]}"
    s = run(SCP + [f"ubuntu@{ip}:/tmp/p2-leftover-delta.tgz", str(tgz)], timeout=300)
    if s.returncode != 0 or not tgz.is_file() or tgz.stat().st_size < 100:
        return f"FAILED:scp-tgz {name} size={tgz.stat().st_size if tgz.is_file() else 0} {(s.stderr or '')[-200:]}"
    extract = dest / "delta"
    if extract.exists():
        shutil.rmtree(extract, ignore_errors=True)
    extract.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz, "r:gz") as tf:
        tf.extractall(extract)
    copied = 0
    skipped = 0
    for src in extract.rglob("*"):
        if not src.is_file() or src.name == "completed.json":
            continue
        rel = src.relative_to(extract).as_posix()
        dst = REPO / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_file() and dst.stat().st_size >= src.stat().st_size:
            skipped += 1
            continue
        shutil.copy2(src, dst)
        copied += 1
    return f"SUCCESS:harvest {name} bytes={tgz.stat().st_size} copied={copied} skipped={skipped}"


def leftover_local() -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    left = json.loads((WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json").read_text(encoding="utf-8"))
    ids = left.get("remaining_ids") or []
    by = {u["id"]: u for u in cat.get("work_units") or [] if isinstance(u, dict) and u.get("id")}
    present = []
    missing = []
    for uid in ids:
        rel = str((by.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        ok = bool(rel) and (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0
        (present if ok else missing).append(uid)
    all_units = cat.get("work_units") or []
    all_present = 0
    for u in all_units:
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if rel and (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0:
            all_present += 1
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "leftover": len(ids),
        "leftover_present": len(present),
        "leftover_missing": len(missing),
        "missing_ids": missing,
        "catalog_output_present": all_present,
        "catalog_units": len(all_units),
    }
    (WAVE / "ovh-monitor" / "leftover-local-census.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


def main() -> int:
    PULL.mkdir(parents=True, exist_ok=True)
    boxes = fleet()
    print(f"harvest boxes={len(boxes)}", flush=True)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = {pool.submit(harvest_one, n, ip): n for n, ip in boxes}
        for fut in as_completed(futs):
            msg = fut.result()
            print(msg, flush=True)
            if msg.startswith("SUCCESS:"):
                ok += 1
            else:
                fail += 1
    rec = leftover_local()
    print(
        f"HARVEST ok={ok} fail={fail} leftover_present={rec['leftover_present']}/{rec['leftover']} "
        f"catalog_output={rec['catalog_output_present']}/{rec['catalog_units']}",
        flush=True,
    )
    if rec["leftover_present"] >= rec["leftover"] and rec["catalog_output_present"] >= 2007:
        print("SUCCESS:local-leftover-2007", flush=True)
        return 0
    print("PARTIAL leftover_missing", rec["leftover_missing"], rec["missing_ids"][:20], flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
