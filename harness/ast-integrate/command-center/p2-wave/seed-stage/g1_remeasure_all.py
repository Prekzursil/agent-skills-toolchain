#!/usr/bin/env python3
"""Full local G-1 remesure of every catalog unit.

On Linux/WSL: in-process workers calling _measure_one_delivered.py.
On native Windows: remesure_local.windows_run_cmd (still cannot import Unix-only
modules such as `resource`; run this script under WSL on this box).
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
REPO = WAVE.parent.parent
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
_WIN_OUT = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
OUT_DIR = _WIN_OUT if _WIN_OUT.exists() else (WAVE / "ovh-monitor")
JSONL = OUT_DIR / "g1-local-full.jsonl"
SUMMARY = OUT_DIR / "g1-local-full.json"
HEART = OUT_DIR / "g1-local-heartbeat.json"
MEASURE = WAVE / "_measure_one_delivered.py"
WORKERS = int(os.environ.get("G1_WORKERS", "24"))

MOD = None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail_class(line: str) -> str:
    t = (line or "").strip()
    if t.startswith("SUCCESS:delivered"):
        return "SUCCESS"
    if "FAILED:delivered" in t:
        rest = t.split("FAILED:delivered", 1)[-1].strip()
        parts = rest.split(" ", 1)
        why = parts[1] if len(parts) > 1 else rest
        return (why.split(":")[0] or "FAILED")[:80]
    if "TIMEOUT" in t:
        return "timeout"
    return (t[:80] or "unknown")


def _init_worker() -> None:
    global MOD
    os.chdir(str(REPO))
    os.environ["AST_INTEGRATE_ROOT"] = str(REPO)
    py_path = os.pathsep.join(
        [
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
        ]
    )
    old = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = py_path + ((os.pathsep + old) if old else "")
    spec = importlib.util.spec_from_file_location("measure_one_delivered", MEASURE)
    if spec is None or spec.loader is None:
        raise RuntimeError("measure missing")
    MOD = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(MOD)
    if os.name == "nt":
        from remeasure_local import windows_run_cmd  # type: ignore

        MOD.run_cmd = windows_run_cmd


def one(uid: str) -> dict:
    buf = io.StringIO()
    old = sys.argv[:]
    sys.argv = ["_measure_one_delivered.py", uid]
    rc = 2
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            rc = MOD.main()
    except Exception as exc:
        return {
            "id": uid,
            "ok": False,
            "rc": 2,
            "line": f"{type(exc).__name__}:{exc}"[:400],
            "cls": "infra",
        }
    finally:
        sys.argv = old
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    last = lines[-1] if lines else f"exit={rc}"
    ok = last.startswith("SUCCESS:delivered") and rc == 0
    tail = "\n".join(lines[-12:])[:1500]
    fp = fail_class(last)
    blob = tail.lower()
    if not ok:
        if "modulenotfounderror" in blob:
            fp = "ModuleNotFoundError"
        elif "unresolvable" in blob or "refresolutionerror" in blob or "ast-integrate.invalid" in blob:
            fp = "schema-ref"
        elif "can't open file" in blob or "no such file" in blob:
            fp = "probe-file-missing"
        elif "unexpectedly present" in blob:
            fp = "live-present"
        elif "self-declared" in last:
            fp = "self-declared"
    return {
        "id": uid,
        "ok": ok,
        "rc": rc,
        "line": last[:400],
        "cls": fp,
        "tail": tail,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = [u["id"] for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]]
    if JSONL.is_file() and JSONL.stat().st_size > 0 and not os.environ.get("G1_ALLOW_TRUNCATE"):
        # 02.09: this file is an overlay base / audit ledger. Refuse to wipe it (prune lens FIND 1);
        # the append-only equivalent is seed-stage/_g1_regen_par.py <ids|ALL> <wave> --no-regen.
        raise SystemExit(f"REFUSED: {JSONL} already holds rows; set G1_ALLOW_TRUNCATE=1 to overwrite")
    JSONL.write_text("", encoding="utf-8")
    n = len(ids)
    print(f"G1-START n={n} workers={WORKERS} python={sys.executable} posix={os.name!='nt'}", flush=True)
    started = time.time()
    ok = fail = done = 0
    classes: Counter[str] = Counter()
    fail_ids: list[str] = []
    with ProcessPoolExecutor(max_workers=WORKERS, initializer=_init_worker) as pool:
        futs = {pool.submit(one, uid): uid for uid in ids}
        for fut in as_completed(futs):
            rec = fut.result()
            done += 1
            classes[rec["cls"]] += 1
            if rec["ok"]:
                ok += 1
            else:
                fail += 1
                fail_ids.append(rec["id"])
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(
                f"{done}/{n} ok={ok} fail={fail} {rec['id']} {rec['cls']}",
                flush=True,
            )
            if done % 10 == 0 or done == n:
                HEART.write_text(
                    json.dumps(
                        {
                            "ts": utc_now(),
                            "done": done,
                            "n": n,
                            "ok": ok,
                            "fail": fail,
                            "elapsed_s": int(time.time() - started),
                            "classes": dict(classes.most_common(12)),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
    summary = {
        "ts": utc_now(),
        "n": n,
        "ok": ok,
        "fail": fail,
        "workers": WORKERS,
        "elapsed_s": int(time.time() - started),
        "classes": dict(classes.most_common()),
        "fail_ids_head": fail_ids[:80],
        "fail_n": len(fail_ids),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n", "ok", "fail", "elapsed_s", "classes")}), flush=True)
    if fail == 0:
        print(f"SUCCESS:g1-local-full {ok}/{n}", flush=True)
        return 0
    print(f"FAILED:g1-local-full ok={ok} fail={fail} n={n}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
