#!/usr/bin/env python3
"""Run per-unit emit/build scripts for shard-17 (Windows, not G-1)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-17.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OUT = HERE / "_shard17_emit.jsonl"
TRASH = HERE / "_trash"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}

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
    "write_receipts.py",
)


def pick_emit(pdir: Path) -> Path | None:
    for name in EMIT_NAMES:
        p = pdir / name
        if p.is_file():
            return p
    return None


def hide_output(uid: str) -> Path | None:
    unit = BY.get(uid) or {}
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not rel:
        return None
    src = REPO / rel
    if not src.is_file():
        return None
    dest = TRASH / f"{uid}.output.bak.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return dest


def restore_output(uid: str, bak: Path | None) -> None:
    if bak is None or not bak.is_file():
        return
    unit = BY.get(uid) or {}
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not rel:
        return
    dest = REPO / rel
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(bak), str(dest))


def run_py(script: Path, timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
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


def already_ok() -> set[str]:
    done = set()
    if not OUT.is_file():
        return done
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("ok"):
            done.add(rec["id"])
    return done


def main() -> None:
    done = already_ok()
    TRASH.mkdir(parents=True, exist_ok=True)
    a9 = REPO / "command-center/phase3/A9/DESIGN.json"
    if a9.is_file():
        dest = TRASH / "A9-DESIGN.json.bak"
        if dest.exists():
            dest.unlink()
        shutil.move(str(a9), str(dest))
        print("moved A9 DESIGN aside for ARC-0065")

    with OUT.open("a", encoding="utf-8") as fh:
        for uid in IDS:
            if uid in done:
                print("skip-ok", uid)
                continue
            pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
            emit = pick_emit(pdir)
            rec = {"id": uid, "emit": str(emit) if emit else None, "ok": False}
            if emit is None:
                rec["fail"] = "no-emit-script"
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                print("FAIL", uid, rec["fail"])
                continue
            rc, tail = run_py(emit)
            rec["rc"] = rc
            rec["tail"] = tail[-1500:]
            if rc != 0:
                bak = hide_output(uid)
                rec["hid_output"] = bool(bak)
                rc2, tail2 = run_py(emit)
                rec["rc2"] = rc2
                rec["tail2"] = tail2[-1500:]
                if rc2 == 0:
                    rec["ok"] = True
                    rec["via"] = "hide-then-emit"
                else:
                    restore_output(uid, bak)
                    rec["ok"] = False
                    rec["fail"] = (tail2.splitlines()[-1] if tail2 else tail.splitlines()[-1] if tail else "emit-fail")[:240]
            else:
                rec["ok"] = True
                rec["via"] = "emit"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            mark = "OK" if rec.get("ok") else "FAIL"
            extra = rec.get("via") or rec.get("fail") or ""
            print(mark, uid, extra[:160])


if __name__ == "__main__":
    main()
