#!/usr/bin/env python3
"""Run python and javascript reducers on the same corpus; require byte identity."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import build_corpus, corpus_stats  # noqa: E402
from python_reducer import evaluate_corpus  # noqa: E402

NODE_REDUCER = HERE / "monitor_reducer.js"
PY_REDUCER = HERE / "python_reducer.py"


def _node_bin() -> str:
    found = shutil.which("node")
    if not found:
        raise FileNotFoundError("node binary not on PATH")
    return found


def run_python(rows: list[dict[str, Any]], skip: list[str] | None = None) -> list[dict[str, Any]]:
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=True)
    cmd = [
        sys.executable,
        "-B",
        str(PY_REDUCER),
    ]
    for item in skip or []:
        cmd.extend(["--skip", item])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError(f"python reducer rc={p.returncode} err={p.stderr[-1500:]}")
    return json.loads(p.stdout)


def run_monitor(rows: list[dict[str, Any]], skip: list[str] | None = None) -> list[dict[str, Any]]:
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=True)
    cmd = [_node_bin(), str(NODE_REDUCER)]
    for item in skip or []:
        cmd.extend(["--skip", item])
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError(f"monitor reducer rc={p.returncode} err={p.stderr[-1500:]}")
    return json.loads(p.stdout)


def _by_id(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in results}


def compare(
    rows: list[dict[str, Any]],
    py_rows: list[dict[str, Any]],
    js_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    py_map = _by_id(py_rows)
    js_map = _by_id(js_rows)
    disagreements: list[dict[str, Any]] = []
    for row in rows:
        rid = str(row.get("id"))
        left = py_map.get(rid)
        right = js_map.get(rid)
        if left is None or right is None:
            disagreements.append(
                {
                    "id": rid,
                    "input_verbatim": row.get("input_verbatim"),
                    "python": left,
                    "monitor": right,
                    "why": "missing-result",
                }
            )
            continue
        if left.get("canonical") != right.get("canonical"):
            disagreements.append(
                {
                    "id": rid,
                    "input_verbatim": row.get("input_verbatim"),
                    "python_canonical": left.get("canonical"),
                    "monitor_canonical": right.get("canonical"),
                    "python": left.get("verdict"),
                    "monitor": right.get("verdict"),
                }
            )
    stats = corpus_stats(rows)
    return {
        "corpus_size": stats["size"],
        "malformed_count": stats["malformed_count"],
        "classes": stats["classes"],
        "ids": stats["ids"],
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "python_count": len(py_rows),
        "monitor_count": len(js_rows),
        "byte_identical": len(disagreements) == 0
        and len(py_rows) == len(rows)
        and len(js_rows) == len(rows),
    }


def run_differential(skip_python: list[str] | None = None, skip_monitor: list[str] | None = None) -> dict[str, Any]:
    rows = build_corpus()
    py_rows = run_python(rows, skip=skip_python)
    js_rows = run_monitor(rows, skip=skip_monitor)
    report = compare(rows, py_rows, js_rows)
    report["skip_python"] = skip_python or []
    report["skip_monitor"] = skip_monitor or []
    report["in_process_python_matches_cli"] = evaluate_corpus(json.loads(json.dumps(rows)))[0][
        "canonical"
    ] == py_rows[0]["canonical"]
    return report


def divergence_control() -> dict[str, Any]:
    """Patch python to skip C08; the C08-failing row must disagree."""
    rows = build_corpus()
    target = [r for r in rows if r["id"] == "inert-negative-control"]
    healthy = [r for r in rows if r["id"] == "healthy-complete"]
    if len(target) != 1 or len(healthy) != 1:
        return {"ok": False, "why": "fixture-missing"}
    patched = run_python(target, skip=["C08"])
    honest_py = run_python(target, skip=None)
    honest_js = run_monitor(target, skip=None)
    healthy_patched = run_python(healthy, skip=["C08"])
    healthy_js = run_monitor(healthy, skip=None)
    detected = patched[0]["canonical"] != honest_js[0]["canonical"]
    honest_agree = honest_py[0]["canonical"] == honest_js[0]["canonical"]
    healthy_still_complete = (
        healthy_patched[0]["verdict"]["verdict"] == "COMPLETE"
        and healthy_js[0]["verdict"]["verdict"] == "COMPLETE"
    )
    patched_passes_bad = patched[0]["verdict"]["verdict"] == "COMPLETE"
    honest_fails_c08 = honest_js[0]["verdict"]["failing_condition_id"] == "C08"
    return {
        "ok": bool(
            detected
            and honest_agree
            and healthy_still_complete
            and patched_passes_bad
            and honest_fails_c08
        ),
        "detected": detected,
        "honest_agree_on_c08_row": honest_agree,
        "healthy_skip_still_complete": healthy_still_complete,
        "patched_python_on_c08_row": patched[0],
        "honest_monitor_on_c08_row": honest_js[0],
        "input_verbatim": target[0]["input_verbatim"],
    }


if __name__ == "__main__":
    print(json.dumps(run_differential(), indent=2, sort_keys=True)[:4000])
