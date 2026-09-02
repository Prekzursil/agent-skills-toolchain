"""Apply one operator in an isolated copy and re-run the close-test replay."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mutants import OPERATORS, by_id

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SRC = REPO / "tools" / "command-center"
NOW = "2026-08-09T12:00:00+00:00"


def materialize(op: dict, tmp: Path) -> Path:
    pkg = tmp / "pkg"
    pkg.mkdir(parents=True)
    shutil.copy(SRC / "close.py", pkg / "close.py")
    shutil.copy(SRC / "validate.py", pkg / "validate.py")
    target = pkg / op["file"]
    text = target.read_text(encoding="utf-8")
    needle = op["old"]
    n = text.count(needle)
    if n != 1:
        raise RuntimeError(f"{op['id']}: want unique anchor, found {n} in {op['file']}")
    target.write_text(text.replace(needle, op["new"], 1), encoding="utf-8")
    return pkg


def unified_diff(op: dict) -> str:
    return (
        f"--- a/tools/command-center/{op['file']}\n"
        f"+++ b/tools/command-center/{op['file']}\n"
        f"@@ mutation {op['id']} @@\n"
        f"-{op['old']}\n"
        f"+{op['new']}\n"
    )


def run_suite(pkg: Path, timeout: int = 160) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(pkg), str(SRC), str(HERE)]
    )
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "suite.py")],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    summary = {}
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"ok"' in line:
            try:
                summary = json.loads(line)
            except json.JSONDecodeError:
                summary = {}
            break
    return {
        "exit_code": proc.returncode,
        "ok": bool(summary.get("ok")) and proc.returncode == 0,
        "passed": summary.get("passed"),
        "n": summary.get("n"),
        "failed": summary.get("failed") or [],
        "verbatim": text[-6000:],
    }


def defer_until_without_days(pkg: Path) -> str:
    """Semantic non-equivalence: omit --days so the argparse default is used."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join([str(pkg), str(SRC), str(HERE)])
    code = r"""
import json, tempfile
from pathlib import Path
import catalog as cat, close, suite
ws_root = Path(tempfile.mkdtemp(prefix="res0096-sem-"))
ws = suite.workspace(ws_root)
code, out = suite.run_close(ws, "R-M14", "--defer", "semantic-default")
catg = suite.read_cat(ws)
until = catg["items"]
item = next(i for i in until if i["id"]=="R-M14")
print(json.dumps({"code": code, "until": item.get("defer",{}).get("until"), "out": out[-400:]}))
"""
    proc = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = (proc.stdout or "").strip().splitlines()
    if not text:
        return f"FAILED semantic rc={proc.returncode} {(proc.stderr or '')[-800:]}"
    return text[-1]


def expected_until(days: int) -> str:
    moment = datetime.fromisoformat(NOW)
    return (moment + timedelta(days=days)).astimezone(timezone.utc).isoformat(
        timespec="seconds"
    )


def classify(suite: dict[str, Any], baseline_failed: list[str]) -> dict[str, Any]:
    """Kill/survive vs the unmutated tree, not vs an idealized all-green suite.

    test_closing_every_open_item currently fails on HEAD because REGISTER.md is
    missing (REACH-6). That is fixture drift, not a property of the mutant.
    A mutant is KILLED only when it adds at least one new failing test.
    """
    failed = list(suite["failed"] or [])
    extra = sorted(set(failed) - set(baseline_failed))
    vanished = sorted(set(baseline_failed) - set(failed))
    killed = bool(extra)
    return {
        "verdict": "KILLED" if killed else "SURVIVED",
        "extra_failures": extra,
        "vanished_failures": vanished,
        "failed_tests": failed,
        "suite_ok": suite["ok"],
    }


def run_operator(
    oid: str,
    baseline_failed: list[str] | None = None,
    tmp: Path | None = None,
) -> dict[str, Any]:
    op = by_id(oid)
    own = tmp is None
    root = Path(tempfile.mkdtemp(prefix=f"res0096-{oid.lower()}-")) if own else tmp
    base_failed = list(baseline_failed or [])
    try:
        pkg = materialize(op, root)
        suite = run_suite(pkg)
        cls = classify(suite, base_failed)
        row: dict[str, Any] = {
            "id": op["id"],
            "target": f"tools/command-center/{op['file']}",
            "operator": f"{op['old']!r} -> {op['new']!r}",
            "mechanism": op["mechanism"],
            "expect": op["expect"],
            "verdict": cls["verdict"],
            "expect_met": cls["verdict"] == op["expect"],
            "suite_ok": suite["ok"],
            "mutated_diff": unified_diff(op),
            "pkg_close": str(pkg / "close.py"),
            "pkg_validate": str(pkg / "validate.py"),
            "verbatim_output": suite["verbatim"],
            "failed_tests": cls["failed_tests"],
            "extra_failures": cls["extra_failures"],
            "vanished_failures": cls["vanished_failures"],
            "passed": suite["passed"],
            "n": suite["n"],
            "exit_code": suite["exit_code"],
        }
        if oid == "M-SURVIVE-DEFER-DAYS":
            row["semantic_omit_days"] = defer_until_without_days(pkg)
            row["expected_until_if_default_7"] = expected_until(7)
            row["expected_until_if_default_99"] = expected_until(99)
        return row
    finally:
        if own:
            shutil.rmtree(root, ignore_errors=True)


def run_baseline(tmp: Path | None = None) -> dict[str, Any]:
    own = tmp is None
    root = Path(tempfile.mkdtemp(prefix="res0096-base-")) if own else tmp
    try:
        pkg = root / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)
        shutil.copy(SRC / "close.py", pkg / "close.py")
        shutil.copy(SRC / "validate.py", pkg / "validate.py")
        suite = run_suite(pkg)
        return {
            "id": "BASELINE",
            "verdict": "GREEN" if suite["ok"] else "RED",
            "suite_ok": suite["ok"],
            "verbatim_output": suite["verbatim"],
            "failed_tests": suite["failed"],
            "passed": suite["passed"],
            "n": suite["n"],
            "exit_code": suite["exit_code"],
        }
    finally:
        if own:
            shutil.rmtree(root, ignore_errors=True)


def campaign() -> dict[str, Any]:
    base = run_baseline()
    base_failed = list(base.get("failed_tests") or [])
    rows = [run_operator(op["id"], baseline_failed=base_failed) for op in OPERATORS]
    return {"baseline": base, "operators": rows, "n_operators": len(rows)}


if __name__ == "__main__":
    print(json.dumps(campaign(), indent=2)[:8000])
