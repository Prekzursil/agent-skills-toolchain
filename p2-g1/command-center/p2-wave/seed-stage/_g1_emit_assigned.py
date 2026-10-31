#!/usr/bin/env python3
"""Run per-unit emit scripts for envelope-rest IDs.

Stashes the leftover catalog output first so probes that inspect a BLOCKED
envelope do not fail the emit. Restores the stash if emit fails.
Writes to whatever AST_INTEGRATE_ROOT/cwd tree this process uses.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[3])
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
# Results always land on the Windows shard dir when mounted.
WIN_SHARDS = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
OUT_DIR = WIN_SHARDS if WIN_SHARDS.exists() else SHARDS
PROBES = WAVE / "probes"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}

EMIT_NAMES = (
    "emit_artifact.py",
    "emit.py",
    "emit_receipt.py",
    "emit_inventory.py",
    "emit_report.py",
    "emit_contract.py",
    "emit_migration.py",
    "emit_registry.py",
    "emit_proof.py",
    "emit_dataflow.py",
    "emit_record.py",
    "emit_result.py",
    "emit_baseline.py",
    "emit_map.py",
    "emit_model.py",
    "emit_scan.py",
    "emit_spec.py",
    "emit_finding.py",
    "emit_census.py",
    "emit_register.py",
    "build_artifact.py",
    "build_receipt.py",
    "build.py",
    "write_receipts.py",
)
SKIP_SCHEMA = True
WORKERS = int(os.environ.get("G1_EMIT_WORKERS", "4"))
TIMEOUT = int(os.environ.get("G1_EMIT_TIMEOUT", "180"))


def assigned_ids() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    src = OUT_DIR if OUT_DIR.exists() else SHARDS
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        p = src / name
        if not p.is_file():
            p = SHARDS / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
    return out


def pick_emit(probe_dir: Path) -> Path | None:
    for name in EMIT_NAMES:
        p = probe_dir / name
        if p.is_file():
            return p
    return None


def is_schema_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and ("$schema" in doc or "$id" in doc) and "unit_id" not in doc


def run_one(uid: str) -> dict:
    unit = BY_ID.get(uid)
    rec = {"id": uid, "ok": False, "action": "skip"}
    if unit is None:
        rec["action"] = "catalog-missing"
        return rec
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    dest = REPO / rel
    probe_dir = PROBES / uid
    emit = pick_emit(probe_dir)
    if emit is None:
        rec["action"] = "no-emit"
        rec["ok"] = True
        return rec
    if SKIP_SCHEMA and is_schema_file(dest):
        rec["action"] = "schema-skip"
        rec["ok"] = True
        rec["emit"] = emit.name
        return rec
    stash = dest.with_name(dest.name + ".g1-stash")
    stashed = False
    if dest.is_file():
        try:
            if stash.exists():
                stash.unlink()
            dest.replace(stash)
            stashed = True
        except OSError as exc:
            rec["action"] = f"stash-fail:{exc}"
            return rec
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    py = sys.executable
    cmd = [py, "-B", str(emit)]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=TIMEOUT,
        )
        rc = proc.returncode
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-1500:]
    except subprocess.TimeoutExpired:
        rc = 124
        tail = "TIMEOUT"
    rec["rc"] = rc
    rec["sec"] = round(time.time() - t0, 2)
    rec["emit"] = emit.name
    rec["tail"] = tail[-400:]
    if rc == 0 and dest.is_file() and dest.stat().st_size > 0:
        rec["ok"] = True
        rec["action"] = "emitted"
        if stashed and stash.is_file():
            try:
                stash.unlink()
            except OSError:
                pass
        return rec
    rec["action"] = "emit-failed"
    if stashed and stash.is_file() and (not dest.is_file() or dest.stat().st_size <= 0):
        try:
            stash.replace(dest)
            rec["action"] = "restored"
        except OSError:
            rec["action"] = "restore-fail"
    elif stashed and stash.is_file() and rc != 0:
        # keep leftover as fallback; do not clobber a partial emit if dest exists
        if not dest.is_file() or dest.stat().st_size <= 0:
            stash.replace(dest)
            rec["action"] = "restored"
        else:
            rec["action"] = "emit-failed-kept"
    return rec


def main() -> int:
    ids = assigned_ids()
    only = sys.argv[1:]
    if only:
        ids = [u for u in ids if u in set(only)]
    print(f"EMIT n={len(ids)} workers={WORKERS} repo={REPO}", flush=True)
    rows = []
    ok = fail = skip = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(run_one, uid): uid for uid in ids}
        done = 0
        for fut in as_completed(futs):
            rec = fut.result()
            rows.append(rec)
            done += 1
            if rec.get("action") in {"no-emit", "schema-skip"}:
                skip += 1
            elif rec.get("ok"):
                ok += 1
            else:
                fail += 1
            print(
                f"{done}/{len(ids)} ok={ok} fail={fail} skip={skip} {rec['id']} {rec.get('action')} {rec.get('emit','')}",
                flush=True,
            )
    payload = {
        "n": len(ids),
        "ok": ok,
        "fail": fail,
        "skip": skip,
        "rows": sorted(rows, key=lambda r: r["id"]),
    }
    dest = OUT_DIR / "_envelope_emit.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(ids), "ok": ok, "fail": fail, "skip": skip, "out": str(dest)}), flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
