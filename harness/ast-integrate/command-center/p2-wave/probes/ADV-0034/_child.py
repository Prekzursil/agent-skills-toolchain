#!/usr/bin/env python3
"""Child jobs for ADV-0034. rlimits are applied by the parent preexec_fn."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center" / "schema"))


def emit(doc: dict) -> None:
    print(json.dumps(doc, sort_keys=True), flush=True)


def json_load(path: str) -> None:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    emit({"ok": True, "app_bound": False, "n": len(data), "job": "json_load"})


def extract(blob: str, dest: str) -> None:
    import importlib.util

    installer_path = REPO / "tools" / "plugin" / "installer.py"
    spec = importlib.util.spec_from_file_location("adv0034_plugin_installer", installer_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {installer_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _safe_extract = mod._safe_extract

    dest_path = Path(dest)
    if dest_path.exists():
        shutil.rmtree(dest_path)
    dest_path.mkdir(parents=True, exist_ok=True)
    _safe_extract(Path(blob), dest_path, on_extract=None)
    total = sum(p.stat().st_size for p in dest_path.rglob("*") if p.is_file())
    emit(
        {
            "ok": True,
            "app_bound": False,
            "extracted_bytes": total,
            "job": "extract",
        }
    )


def validate_wf(path: str) -> None:
    import validate_workflow

    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    result = validate_workflow.validate_document(doc)
    vid = result.get("violation_id")
    app_bound = vid == validate_workflow.WF_CYCLIC_SUBWORKFLOW
    emit(
        {
            "ok": True,
            "app_bound": app_bound,
            "valid": bool(result.get("ok")),
            "violation_id": vid,
            "cycle_dfs_calls": result.get("cycle_dfs_calls"),
            "cycle_dfs_bound": result.get("cycle_dfs_bound"),
            "job": "validate_wf",
        }
    )


def fanout_capped(n_s: str, cap_s: str) -> None:
    from arrival_scheduler.scheduler import (
        WINDOW_TICKS,
        max_sliding_window_count,
        schedule_arrivals,
    )

    n = int(n_s)
    cap = int(cap_s)
    sched = schedule_arrivals(n, cap, seed=1)
    observed = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
    emit(
        {
            "ok": True,
            "app_bound": observed <= cap,
            "exceeds_cap": observed > cap,
            "observed_window": observed,
            "cap": cap,
            "n": n,
            "job": "fanout_capped",
        }
    )


def fanout_naive(n_s: str, cap_s: str) -> None:
    from arrival_scheduler.scheduler import (
        WINDOW_TICKS,
        max_sliding_window_count,
        naive_burst,
    )

    n = int(n_s)
    cap = int(cap_s)
    sched = naive_burst(n, cap)
    observed = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
    emit(
        {
            "ok": True,
            "app_bound": False,
            "exceeds_cap": observed > cap,
            "observed_window": observed,
            "cap": cap,
            "n": n,
            "job": "fanout_naive",
        }
    )


def main() -> int:
    job = sys.argv[1]
    payload = sys.argv[2] if len(sys.argv) > 2 else ""
    extra = sys.argv[3] if len(sys.argv) > 3 else ""
    if job == "json_load":
        json_load(payload)
    elif job == "extract":
        extract(payload, extra)
    elif job == "validate_wf":
        validate_wf(payload)
    elif job == "fanout_capped":
        fanout_capped(payload, extra)
    elif job == "fanout_naive":
        fanout_naive(payload, extra)
    else:
        emit({"ok": False, "error": f"unknown job {job}"})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
