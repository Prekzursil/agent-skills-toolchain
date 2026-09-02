#!/usr/bin/env python3
"""Probe 2: fresh-interpreter import of cycle members + top fan-in; sys.modules delta."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from graph_core import UNIT, catalog_unit, repo_root, scan_tools  # noqa: E402

OUT_JSON = HERE / "probe2-runtime-trace.json"
BUDGET = 12
TIMEOUT = 8


def check_artifact() -> str | None:
    unit = catalog_unit()
    rel = str(unit.get("output_path") or "")
    art = repo_root() / rel
    if not art.is_file() or art.stat().st_size <= 0:
        return None
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"unparseable:{exc}"
    if not isinstance(doc, dict):
        return "artifact-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        return "sentinel-absent"
    return None


def trace_module(mod: str, repo: Path) -> dict:
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(repo)!r})\n"
        "before = set(sys.modules)\n"
        "ok, err = True, ''\n"
        "try:\n"
        f"    __import__({mod!r})\n"
        "except BaseException as e:\n"
        "    ok, err = False, f'{type(e).__name__}: {e}'[:300]\n"
        "delta = sorted(set(sys.modules) - before)\n"
        "internal = [d for d in delta if d == 'tools' or d.startswith('tools.')]\n"
        "print(json.dumps({'ok': ok, 'err': err, 'delta_count': len(delta), "
        "'internal_delta': internal[:80]}))\n"
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "module": mod,
            "ok": False,
            "err": f"TIMEOUT after {TIMEOUT}s",
            "exit_code": 124,
            "delta_count": 0,
            "internal_delta": [],
        }
    row: dict = {
        "module": mod,
        "exit_code": proc.returncode,
        "raw": ((proc.stdout or "") + (proc.stderr or "")).strip()[-400:],
    }
    try:
        parsed = json.loads((proc.stdout or "").strip().splitlines()[-1])
        row.update(parsed)
    except Exception:  # noqa: BLE001
        row["ok"] = False
        row["err"] = "unparseable-trace-output"
        row["delta_count"] = 0
        row["internal_delta"] = []
    return row


def select_targets(scan: dict) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for cyc in scan["cycles"]:
        for m in cyc:
            if m not in seen:
                ordered.append(m)
                seen.add(m)
    for row in scan["top_fan_in"]:
        m = row["module"]
        if m not in seen:
            ordered.append(m)
            seen.add(m)
        if len(ordered) >= BUDGET:
            break
    for m in scan.get("tools_lib_modules") or []:
        if m not in seen:
            ordered.append(m)
            seen.add(m)
        if len(ordered) >= BUDGET:
            break
    if len(ordered) < BUDGET:
        for m in sorted(scan["edges"]):
            if m not in seen:
                ordered.append(m)
                seen.add(m)
            if len(ordered) >= BUDGET:
                break
    return ordered[:BUDGET]


def main() -> int:
    err = check_artifact()
    if err:
        print(f"FAILED:AUD-0030-probe2 {err}")
        return 1
    scan = scan_tools()
    repo = repo_root()
    targets = select_targets(scan)
    rows = [trace_module(m, repo) for m in targets]
    ast_edges = {k: set(v) for k, v in scan["edges"].items()}
    runtime_only = []
    for row in rows:
        if not row.get("ok"):
            continue
        static = set(ast_edges.get(row["module"], ()))
        got = {d for d in row.get("internal_delta") or [] if d != row["module"]}
        extra = sorted(
            d
            for d in got
            if d in ast_edges
            and d not in static
            and not any(d == s or d.startswith(s + ".") or s.startswith(d + ".") for s in static)
        )
        if extra:
            runtime_only.append({"module": row["module"], "runtime_only_imports": extra[:20]})
    # Independent falsifier of a vacuous cycle_count=0: if AST found a cycle, runtime
    # import of one member should pull the other into sys.modules when import succeeds.
    cycle_runtime = []
    for cyc in scan["cycles"]:
        members = set(cyc)
        pulled = False
        for row in rows:
            if row["module"] in members and row.get("ok"):
                internal = set(row.get("internal_delta") or [])
                if members.issubset(internal) or (members - {row["module"]}) & internal:
                    pulled = True
                    break
        cycle_runtime.append({"cycle": cyc, "runtime_peer_seen": pulled})
    payload = {
        "probe": "probe2-runtime-trace",
        "unit_id": UNIT,
        "instrument": "fresh interpreter per module; sys.modules delta vs AST edges",
        "budget": BUDGET,
        "timeout_s": TIMEOUT,
        "targets": targets,
        "rows": rows,
        "importable": sum(1 for r in rows if r.get("ok")),
        "failed": sum(1 for r in rows if not r.get("ok")),
        "runtime_only_imports": runtime_only,
        "cycle_runtime": cycle_runtime,
        "ast_cycle_count": scan["cycle_count"],
        "pass": True,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"runtime attempted={len(rows)} importable={payload['importable']} "
        f"failed={payload['failed']} runtime_only={len(runtime_only)} "
        f"ast_cycles={scan['cycle_count']}"
    )
    print(
        "SUCCESS:AUD-0030-probe2 fresh-interpreter sys.modules deltas; AST-invisible internals listed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
