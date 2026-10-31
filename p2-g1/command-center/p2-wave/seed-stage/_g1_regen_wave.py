#!/usr/bin/env python3
"""Regenerate-receipts wave: for each ID run its write_receipts.py in the mirror,
copy the primary artifact + probe-dir receipts back to Windows, then measure.

Usage (WSL): python3 _g1_regen_wave.py <ids-file> <wave-name>
Appends per-ID rows to ovh-monitor/repair-claude/<wave-name>.jsonl (skips IDs
already present) and lines to the append-only repair log. Resumable.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate")
MON = WIN / "command-center" / "p2-wave" / "ovh-monitor"
LOG = MON / "g1-repair-claude_2026-08-27.log"
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"

CATALOG = json.loads((WIN / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}


def run(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def copy_back(uid: str) -> list[str]:
    """Copy the unit's primary artifact and probe-dir receipts mirror->Windows."""
    copied = []
    unit = UNITS.get(uid) or {}
    out_rel = unit.get("output_path")
    paths = []
    if isinstance(out_rel, str) and out_rel:
        paths.append(out_rel)
    for name in ("SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"):
        paths.append(f"command-center/p2-wave/probes/{uid}/{name}")
    for rel in paths:
        src = ROOT / rel
        if src.is_file():
            dst = WIN / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
    return copied


def one(uid: str) -> dict:
    probe_dir = ROOT / "command-center" / "p2-wave" / "probes" / uid
    wr = probe_dir / "write_receipts.py"
    rec: dict = {"id": uid}
    if not wr.is_file():
        rec.update(ok=False, stage="no-write-receipts", line="write_receipts.py absent")
        return rec
    rc, out = run([sys.executable, "-B", str(wr)], ROOT)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if rc != 0:
        rec.update(ok=False, stage="write_receipts", rc=rc, line=last[:400], tail=out[-1500:])
        return rec
    rec["copied"] = copy_back(uid)
    rc2, out2 = run([sys.executable, str(MEAS), uid], ROOT)
    lines2 = [ln for ln in out2.splitlines() if ln.strip()]
    last2 = lines2[-1] if lines2 else ""
    ok = last2 == f"SUCCESS:delivered {uid}"
    rec.update(ok=ok, stage="measure", rc=rc2, line=last2[:400], tail=out2[-1500:])
    return rec


def main() -> int:
    ids_file = Path(sys.argv[1])
    name = sys.argv[2]
    out = MON / "repair-claude" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    ids = [ln.strip() for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    done = set()
    if out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["id"])
    todo = [u for u in ids if u not in done]
    print(f"REGEN-WAVE {name} total={len(ids)} done={len(done)} todo={len(todo)}", flush=True)
    ok = fail = 0
    for i, uid in enumerate(todo, 1):
        rec = one(uid)
        ok += 1 if rec["ok"] else 0
        fail += 0 if rec["ok"] else 1
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{name}\t{uid}\tregen\t{'OK' if rec['ok'] else 'FAIL'}\t{rec.get('line','')[:160]}\n")
        print(f"{i}/{len(todo)} ok={ok} fail={fail} {uid} {rec.get('line','')[:110]}", flush=True)
    print(f"DONE {name} ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
