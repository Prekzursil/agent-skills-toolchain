#!/usr/bin/env python3
"""Named probe 2: nonempty harvest SUCCESS, and the classifier discriminates.

A harvester that PASSes both empty and nonempty runs is not discriminating.
Independent walk counts must match the snapshot. AST: classify is not
exit-zero-as-success; harvest.py calls classify. Retry: empty then fill
succeeds on attempt 2.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HARVEST = REPO / "tools" / "harvester"
sys.path.insert(0, str(HARVEST))

from harvest import run_harvest  # noqa: E402
from postcondition import (  # noqa: E402
    REASON_OK,
    REASON_SILENT_NOOP,
    independent_walk_counts,
    snapshot,
)

UNIT = "IMP-0431"
SENTINEL = "SENTINEL:IMP-0431:HARVEST-POSTCONDITION"
ART = REPO / "command-center" / "receipts" / "IMP-0431.json"
NONEMPTY = HERE / "fixtures" / "remote-nonempty"
CLI = HARVEST / "harvest.py"
POST_PY = HARVEST / "postcondition.py"
HARVEST_PY = HARVEST / "harvest.py"

PLANTED_EXIT_ZERO = """
def classify(before, after, process_exit_code, attempts=1):
    if process_exit_code == 0:
        return {"state": "SUCCESS"}
    return {"state": "FAILED"}
"""

PLANTED_DELTA_GATE = """
def classify(before, after, process_exit_code, attempts=1):
    nonempty = after.file_count > before.file_count
    if process_exit_code != 0:
        return {"state": "FAILED"}
    elif not nonempty:
        return {"state": "FAILED"}
    else:
        return {"state": "SUCCESS"}
"""


def _solely_exit_zero_test(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq):
        return False
    left, right = node.left, node.comparators[0]
    names = []
    consts = []
    for side in (left, right):
        if isinstance(side, ast.Name):
            names.append(side.id)
        elif isinstance(side, ast.Constant):
            consts.append(side.value)
    exit_names = {"process_exit_code", "exit_code", "process_exit"}
    return any(n in exit_names for n in names) and 0 in consts and len(names) == 1


def _returns_success(body: list[ast.stmt]) -> bool:
    for stmt in body:
        if isinstance(stmt, ast.Return):
            val = stmt.value
            if isinstance(val, ast.Constant) and str(val.value).upper() == "SUCCESS":
                return True
            if isinstance(val, ast.Dict):
                for k, v in zip(val.keys, val.values):
                    if (
                        isinstance(k, ast.Constant)
                        and k.value == "state"
                        and isinstance(v, ast.Constant)
                        and str(v.value).upper() == "SUCCESS"
                    ):
                        return True
            if isinstance(val, ast.Name) and val.id == "SUCCESS":
                return True
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "state":
                    if (
                        isinstance(stmt.value, ast.Constant)
                        and str(stmt.value.value).upper() == "SUCCESS"
                    ):
                        # SUCCESS assigned inside this arm; only a problem if
                        # the enclosing if is solely exit==0 (caller checks).
                        return True
    return False


def exit_zero_sufficient_for_success(src: str) -> bool:
    tree = ast.parse(src)
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name != "classify":
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.If) and _solely_exit_zero_test(node.test):
                if _returns_success(node.body):
                    return True
    return False


def calls_classify(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "classify":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "classify":
                return True
    return False


def classify_uses_delta(src: str) -> bool:
    tree = ast.parse(src)
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name != "classify":
            continue
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
        markers = {
            "nonempty",
            "compute_delta",
            "delta",
            "added_paths",
            "changed_paths",
            "artifact_count_delta",
        }
        return bool(markers & names) or bool(markers & attrs)
    return False


def run_cli(remote: Path, dest: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CLI),
            "--remote",
            str(remote),
            "--dest",
            str(dest),
            "--max-attempts",
            "1",
            "--backoff-seconds",
            "0",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            print("FAILED:IMP-0431-probe2 catalog sentinel absent from receipt")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0431-probe2 self-declared {st}")
            return 1

    post_src = POST_PY.read_text(encoding="utf-8")
    harvest_src = HARVEST_PY.read_text(encoding="utf-8")
    planted_bad = exit_zero_sufficient_for_success(PLANTED_EXIT_ZERO)
    planted_good = exit_zero_sufficient_for_success(PLANTED_DELTA_GATE)
    live_exit_zero_ok = not exit_zero_sufficient_for_success(post_src)
    uses_delta = classify_uses_delta(post_src)
    harvest_calls = calls_classify(harvest_src)

    with tempfile.TemporaryDirectory(prefix="imp0431-p2-") as tmp:
        tmp_path = Path(tmp)
        dest = tmp_path / "dest-full"
        dest.mkdir()
        empty_remote = tmp_path / "remote-empty"
        empty_remote.mkdir()

        empty_v = run_harvest(
            empty_remote, dest, max_attempts=1, backoff_seconds=(0.0,)
        )
        full_v = run_harvest(
            NONEMPTY, dest, max_attempts=1, backoff_seconds=(0.0,)
        )
        walk_n, walk_b = independent_walk_counts(dest)
        snap = snapshot(dest)
        cli_rc, cli_out = run_cli(NONEMPTY, tmp_path / "dest-cli")

        retry_remote = tmp_path / "remote-retry"
        retry_remote.mkdir()
        retry_dest = tmp_path / "dest-retry"
        retry_dest.mkdir()

        def fill_remote(attempt, _verdict, _transfer):
            if attempt == 1:
                for src_dir, _dirs, files in os.walk(NONEMPTY):
                    rel = Path(src_dir).relative_to(NONEMPTY)
                    target_dir = retry_remote / rel
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for name in files:
                        shutil.copy2(Path(src_dir) / name, target_dir / name)

        retry_v = run_harvest(
            retry_remote,
            retry_dest,
            max_attempts=2,
            backoff_seconds=(0.0,),
            between_attempts=fill_remote,
        )

        nonempty_ok = (
            full_v.state == "SUCCESS"
            and full_v.reason_id == REASON_OK
            and full_v.delta.nonempty
            and full_v.after.file_count > full_v.before.file_count
            and full_v.after.total_bytes > full_v.before.total_bytes
            and full_v.process_exit_code == 0
        )
        empty_ok = (
            empty_v.state == "FAILED"
            and empty_v.reason_id == REASON_SILENT_NOOP
            and not empty_v.delta.nonempty
        )
        discriminates = nonempty_ok and empty_ok
        walk_matches = (
            walk_n == snap.file_count == full_v.after.file_count
            and walk_b == snap.total_bytes == full_v.after.total_bytes
            and walk_n >= 3
        )
        cli_ok = cli_rc == 0 and "SUCCESS:harvest" in cli_out
        retry_ok = (
            retry_v.state == "SUCCESS"
            and retry_v.attempts == 2
            and retry_v.delta.nonempty
        )
        ast_ok = (
            planted_bad
            and not planted_good
            and live_exit_zero_ok
            and uses_delta
            and harvest_calls
        )

        out = {
            "probe": "probe2-nonempty-harvest-discriminating",
            "unit_id": UNIT,
            "nonempty": {
                "classification": full_v.state,
                "reason_id": full_v.reason_id,
                "before_file_count": full_v.before.file_count,
                "after_file_count": full_v.after.file_count,
                "before_total_bytes": full_v.before.total_bytes,
                "after_total_bytes": full_v.after.total_bytes,
                "artifact_count_delta": full_v.delta.artifact_count_delta,
                "bytes_delta": full_v.delta.bytes_delta,
                "added_paths": list(full_v.delta.added_paths),
            },
            "empty_still_failed": empty_ok,
            "discriminates": discriminates,
            "independent_walk": {
                "file_count": walk_n,
                "total_bytes": walk_b,
                "matches": walk_matches,
            },
            "cli_exit_code": cli_rc,
            "retry_empty_then_fill": {
                "state": retry_v.state,
                "attempts": retry_v.attempts,
                "reason_id": retry_v.reason_id,
                "added": list(retry_v.delta.added_paths),
            },
            "ast": {
                "planted_exit_zero_detected": planted_bad,
                "planted_delta_gate_accepted": not planted_good,
                "live_exit_zero_not_sufficient": live_exit_zero_ok,
                "classify_uses_delta": uses_delta,
                "harvest_calls_classify": harvest_calls,
            },
            "pass": bool(
                nonempty_ok
                and empty_ok
                and discriminates
                and walk_matches
                and cli_ok
                and retry_ok
                and ast_ok
            ),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"nonempty={full_v.state} delta_files={full_v.delta.artifact_count_delta} "
            f"delta_bytes={full_v.delta.bytes_delta} empty={empty_v.state} "
            f"walk={walk_n}/{walk_b} retry={retry_v.state}@{retry_v.attempts} "
            f"cli_rc={cli_rc} ast_ok={ast_ok}"
        )
        if not out["pass"]:
            print("FAILED:IMP-0431-probe2 nonempty harvest did not discriminate")
            print(cli_out[-1500:])
            return 1
        print(
            "SUCCESS:IMP-0431-probe2 nonempty harvest SUCCESS; empty still FAILED"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
