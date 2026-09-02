#!/usr/bin/env python3
"""Parallel, resumable regen+measure wave (coordinator 02.09).

For each ID: if probes/<id>/write_receipts.py exists in the mirror, run it, copy
the primary artifact + probe receipts back to Windows; then ALWAYS measure with
_measure_one_delivered.py so every row carries a real tail (the older
_g1_regen_wave.py recorded "no-write-receipts" without measuring).

Usage (WSL): G1_WORKERS=6 python3 _g1_regen_par.py <ids-file> <wave-name> [--no-regen]
Usage (cloud Linux, 02.09): G1_WORKERS=8 python3 _g1_regen_par.py ALL <wave-name> --no-regen
  ``ALL`` measures every catalog unit (a full census as a wave). Paths resolve via
  _g1_paths: with no Windows mirror the repo tree is both ROOT and WIN, so the
  copy-back step is a no-op. Rows carry a ``ts`` (UTC) since 02.09.
Appends rows to ovh-monitor/repair-claude/<wave-name>.jsonl (skips IDs already
present) and lines to the append-only repair log. Safe to re-run after a kill.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import CATALOG as _CATALOG_PATH  # noqa: E402
from _g1_paths import COPY_BACK, LOG, MON, ROOT, WIN  # noqa: E402

MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
WORKERS = int(os.environ.get("G1_WORKERS", "6"))

CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}


def run(cmd: list[str], cwd: Path, timeout: int = 420) -> tuple[int, str]:
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
    if not COPY_BACK:
        return []
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


def fail_class(last: str, tail: str, ok: bool) -> str:
    """Same taxonomy as g1_remeasure_all.one() so census waves are comparable."""
    if ok:
        return "SUCCESS"
    t = (last or "").strip()
    blob = (tail or "").lower()
    if "modulenotfounderror" in blob:
        return "ModuleNotFoundError"
    if "unresolvable" in blob or "refresolutionerror" in blob or "ast-integrate.invalid" in blob:
        return "schema-ref"
    if "can't open file" in blob or "no such file" in blob:
        return "probe-file-missing"
    if "unexpectedly present" in blob:
        return "live-present"
    if "self-declared" in t:
        return "self-declared"
    if "FAILED:delivered" in t:
        rest = t.split("FAILED:delivered", 1)[-1].strip()
        parts = rest.split(" ", 1)
        why = parts[1] if len(parts) > 1 else rest
        return (why.split(":")[0] or "FAILED")[:80]
    if "TIMEOUT" in t:
        return "timeout"
    return (t[:80] or "unknown")


def one(uid: str, regen: bool) -> dict:
    probe_dir = ROOT / "command-center" / "p2-wave" / "probes" / uid
    wr = probe_dir / "write_receipts.py"
    rec: dict = {"id": uid, "regen": False}
    if regen and wr.is_file():
        rc, out = run([sys.executable, "-B", str(wr)], ROOT)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        rec["regen"] = True
        rec["regen_rc"] = rc
        rec["regen_line"] = (lines[-1] if lines else "")[:300]
        if rc == 0:
            rec["copied"] = copy_back(uid)
    elif regen:
        rec["regen_line"] = "write_receipts.py absent"
    t0 = time.time()
    rc2, out2 = run([sys.executable, str(MEAS), uid], ROOT)
    lines2 = [ln for ln in out2.splitlines() if ln.strip()]
    last2 = lines2[-1] if lines2 else ""
    ok = last2 == f"SUCCESS:delivered {uid}"
    rec.update(ok=ok, stage="measure", rc=rc2, line=last2[:400], tail=out2[-2500:],
               cls=fail_class(last2, out2, ok),
               ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               secs=round(time.time() - t0, 1))
    return rec


def main() -> int:
    name = sys.argv[2]
    regen = "--no-regen" not in sys.argv[3:]
    out = MON / "repair-claude" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "ALL":
        ids = [u["id"] for u in CATALOG["work_units"]]
    else:
        ids_file = Path(sys.argv[1])
        ids = [ln.strip() for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    done = set()
    if out.is_file():
        for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    todo = [u for u in ids if u not in done]
    print(f"REGEN-PAR {name} total={len(ids)} done={len(done)} todo={len(todo)} workers={WORKERS} regen={regen}", flush=True)
    ok = fail = 0
    started = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(one, uid, regen): uid for uid in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            uid = futs[fut]
            try:
                rec = fut.result()
            except Exception as exc:  # noqa: BLE001
                rec = {"id": uid, "ok": False, "stage": "infra", "line": f"{type(exc).__name__}:{exc}"[:300], "tail": ""}
            ok += 1 if rec["ok"] else 0
            fail += 0 if rec["ok"] else 1
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"{name}\t{uid}\t{'regen' if rec.get('regen') else 'measure'}\t{'OK' if rec['ok'] else 'FAIL'}\t{rec.get('line','')[:160]}\n")
            print(f"{i}/{len(todo)} ok={ok} fail={fail} {int(time.time()-started)}s {uid} {rec.get('line','')[:110]}", flush=True)
    print(f"DONE {name} ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
