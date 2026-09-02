#!/usr/bin/env python3
"""Measure every shard-12 ID under WSL p2-g1. Writes jsonl to this directory."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

WIN_SHARDS = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or str(Path.home() / "p2-g1"))
IDS_PATH = WIN_SHARDS / "shard-12.txt"
JSONL = WIN_SHARDS / "_shard12_measure.jsonl"
HEART = WIN_SHARDS / "_shard12_heartbeat.json"
COUNTS = WIN_SHARDS / "_shard12_measure.counts"
MEASURE = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"


def load_measure():
    os.chdir(str(ROOT))
    os.environ["AST_INTEGRATE_ROOT"] = str(ROOT)
    py_path = os.pathsep.join(
        [
            str(ROOT),
            str(ROOT / "tools"),
            str(ROOT / "tools" / "measure-guard"),
            str(ROOT / "platform" / "lib"),
            str(ROOT / "command-center" / "p2-wave" / "seed-stage"),
            str(ROOT / "tools" / "agentspec"),
        ]
    )
    old = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = py_path + ((os.pathsep + old) if old else "")
    spec = importlib.util.spec_from_file_location("measure_one_delivered", MEASURE)
    if spec is None or spec.loader is None:
        raise RuntimeError("measure missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fail_class(line: str, tail: str) -> str:
    t = (line or "").strip()
    blob = (tail or "").lower()
    if t.startswith("SUCCESS:delivered"):
        return "SUCCESS"
    if "modulenotfounderror" in blob:
        return "ModuleNotFoundError"
    if "unresolvable" in blob or "refresolutionerror" in blob:
        return "schema-ref"
    if "can't open file" in blob or "no such file" in blob:
        return "probe-file-missing"
    if "FAILED:delivered" in t:
        rest = t.split("FAILED:delivered", 1)[-1].strip()
        parts = rest.split(" ", 1)
        why = parts[1] if len(parts) > 1 else rest
        return (why.split(":")[0] or "FAILED")[:80]
    return (t[:80] or "unknown")


def main() -> int:
    if not ROOT.is_dir():
        print(f"MISSING-ROOT {ROOT}", flush=True)
        return 2
    ids = [
        ln.strip().replace("\r", "")
        for ln in IDS_PATH.read_text(encoding="utf-8").splitlines()
        if ln.strip().replace("\r", "")
    ]
    only = [a.strip() for a in sys.argv[1:] if a.strip()]
    if only:
        ids = only
    print(f"MEASURE n={len(ids)} root={ROOT}", flush=True)
    JSONL.write_text("", encoding="utf-8")
    mod = load_measure()
    ok = fail = 0
    started = time.time()
    for i, uid in enumerate(ids, 1):
        old = sys.argv[:]
        sys.argv = ["_measure_one_delivered.py", uid]
        import io
        from contextlib import redirect_stderr, redirect_stdout

        buf = io.StringIO()
        rc = 2
        t0 = time.time()
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                rc = mod.main()
        except Exception as exc:
            buf.write(f"\n{type(exc).__name__}:{exc}\n")
            rc = 2
        finally:
            sys.argv = old
        text = buf.getvalue()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        last = lines[-1] if lines else f"exit={rc}"
        success = last.startswith("SUCCESS:delivered") and rc == 0
        tail_lines = lines[-16:]
        tail = "\n".join(tail_lines)
        cls = fail_class(last, tail)
        rec = {
            "id": uid,
            "ok": success,
            "rc": rc,
            "cls": cls,
            "last": last[:400],
            "tail": tail_lines,
            "sec": round(time.time() - t0, 2),
        }
        with JSONL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        if success:
            ok += 1
            mark = "OK"
        else:
            fail += 1
            mark = "FAIL"
        print(f"[{i}/{len(ids)}] {mark} {uid} {cls} {last[:160]}", flush=True)
        HEART.write_text(
            json.dumps(
                {
                    "done": i,
                    "n": len(ids),
                    "ok": ok,
                    "fail": fail,
                    "elapsed": round(time.time() - started, 1),
                    "last": uid,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    COUNTS.write_text(f"{len(ids)} {ok} {fail}\n", encoding="utf-8")
    print(f"BATCH-DONE n={len(ids)} ok={ok} fail={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
