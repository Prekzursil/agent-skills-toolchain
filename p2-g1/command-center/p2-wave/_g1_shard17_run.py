#!/usr/bin/env python3
"""WSL emit-then-G-1 for shard-17. Lives outside ovh-monitor so rsync copies it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[2])
IDS = [
    "ADV-0018",
    "ADV-0047",
    "ADV-0076",
    "ADV-0100",
    "ADV-0123",
    "ARC-0016",
    "ARC-0065",
    "ARC-0108",
    "AUD-0033",
    "AUD-0067",
    "BLD-0008",
    "BLD-0039",
    "CC-0014",
    "CNF-0031",
    "CNF-0081",
    "CNF-0127",
    "CNF-0167",
    "CNL-0036",
    "CNL-0095",
    "IMP-0005",
    "IMP-0031",
    "IMP-0053",
    "IMP-0078",
    "IMP-0104",
    "IMP-0124",
    "IMP-0150",
    "IMP-0189",
    "IMP-0217",
    "IMP-0245",
    "IMP-0270",
    "IMP-0296",
    "IMP-0322",
    "IMP-0344",
    "IMP-0367",
    "IMP-0402",
    "IMP-0428",
    "IMP-0464",
    "RES-0004",
    "RES-0058",
    "RES-0125",
    "RES-0161",
    "RES-0191",
    "SYN-0036",
    "TST-0011",
    "TST-0071",
    "TST-0114",
    "TST-0145",
    "TST-0173",
    "TST-0210",
    "TST-0241",
    "TST-0274",
    "TST-0301",
    "TST-0333",
    "WFA-0045",
    "WFA-0094",
    "WFA-0139",
]
EMIT_NAMES = (
    "emit_receipt.py",
    "emit_artifact.py",
    "emit_refutation.py",
    "emit_report.py",
    "emit_census.py",
    "emit_note.py",
    "emit_spec.py",
    "emit_research.py",
    "emit_engine.py",
    "emit.py",
    "build_artifact.py",
)
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
LOG = Path(os.environ.get("SHARD17_LOG") or str(Path.home() / "p2-g1-shard17.jsonl"))
BACKUP = Path(os.environ.get("SHARD17_BAK") or str(Path.home() / "p2-g1-shard17-bak"))


def pick_emit(uid: str) -> Path | None:
    pdir = REPO / "command-center/p2-wave/probes" / uid
    for name in EMIT_NAMES:
        p = pdir / name
        if p.is_file():
            return p
    wr = pdir / "write_receipts.py"
    return wr if wr.is_file() else None


def run_py(script: Path, timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center/p2-wave/seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools/measure-guard"),
            str(REPO / "platform/lib"),
            str(REPO / "tools/agentspec"),
            str(REPO / "command-center"),
            str(script.parent),
            env.get("PYTHONPATH") or "",
        ]
    )
    try:
        p = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, text[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def measure(uid: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    try:
        p = subprocess.run(
            [sys.executable, "-B", str(MEASURE), uid],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=200,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, text[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def hide_output(uid: str) -> Path | None:
    rel = str((BY.get(uid) or {}).get("output_path") or "").replace("\\", "/")
    if not rel:
        return None
    src = REPO / rel
    if not src.is_file():
        return None
    BACKUP.mkdir(parents=True, exist_ok=True)
    dest = BACKUP / f"{uid}.json"
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return dest


def restore_output(uid: str, bak: Path | None) -> None:
    if bak is None or not bak.is_file():
        return
    rel = str((BY.get(uid) or {}).get("output_path") or "").replace("\\", "/")
    dest = REPO / rel
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(bak), str(dest))


def last_line(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:240] if lines else ""


def already() -> dict[str, dict]:
    rows = {}
    if LOG.is_file():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                rows[rec["id"]] = rec
    return rows


def main() -> int:
    os.environ["AST_INTEGRATE_ROOT"] = str(REPO)
    a9 = REPO / "command-center/phase3/A9/DESIGN.json"
    if a9.is_file():
        BACKUP.mkdir(parents=True, exist_ok=True)
        dest = BACKUP / "A9-DESIGN.json"
        if dest.exists():
            dest.unlink()
        shutil.move(str(a9), str(dest))
        print("moved A9 DESIGN")
    prior = already()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    ids = only or IDS
    with LOG.open("a", encoding="utf-8") as fh:
        for uid in ids:
            old = prior.get(uid)
            if old and old.get("g1") == "SUCCESS:delivered" and not only:
                print("skip-ok", uid)
                continue
            emit = pick_emit(uid)
            rec = {"id": uid, "emit": None if emit is None else str(emit.relative_to(REPO))}
            if emit is not None:
                rc, tail = run_py(emit)
                rec["emit_rc"] = rc
                rec["emit_last"] = last_line(tail)
                rec["emit_tail"] = tail[-800:]
                if rc != 0:
                    bak = hide_output(uid)
                    rec["hid"] = bool(bak)
                    rc2, tail2 = run_py(emit)
                    rec["emit_rc2"] = rc2
                    rec["emit_last2"] = last_line(tail2)
                    rec["emit_tail2"] = tail2[-800:]
                    if rc2 != 0:
                        restore_output(uid, bak)
            rc_m, tail_m = measure(uid)
            rec["measure_rc"] = rc_m
            rec["measure_last"] = last_line(tail_m)
            rec["measure_tail"] = tail_m[-1200:]
            rec["g1"] = (
                "SUCCESS:delivered"
                if "SUCCESS:delivered" in tail_m.splitlines()[-1:]
                or tail_m.strip().endswith(f"SUCCESS:delivered {uid}")
                or any(ln.strip() == f"SUCCESS:delivered {uid}" for ln in tail_m.splitlines())
                else "FAIL"
            )
            if rec["g1"] != "SUCCESS:delivered" and rec.get("measure_last", "").startswith("SUCCESS:delivered"):
                rec["g1"] = "SUCCESS:delivered"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(rec["g1"], uid, rec.get("measure_last") or rec.get("emit_last") or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
