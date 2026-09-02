#!/usr/bin/env python3
"""Single conformance runner: one report shape, four-way suite verdict, exit contract.

PASS / FAIL / ERROR / SKIPPED are distinct protocol values. Collapsing FAIL and
ERROR into a single non-zero, or SKIPPED into PASS, is the green-means-nothing
failure this unit exists to prevent.

FAIL is a structured assertion (exit 1 + SUITE-FAIL marker). ERROR is everything
unexpected, including a Python traceback that also happens to exit 1.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_SUITES = HERE / "fixtures" / "suites"
MARKER_PASS = "SUITE-PASS"
MARKER_FAIL = "SUITE-FAIL"
VERDICT_PREFIX = "CONFORMANCE-VERDICT:"

EXIT_BY_OVERALL = {
    "PASS": 0,
    "FAIL": 1,
    "ERROR": 2,
    "PASS-WITH-SKIPS": 3,
}

UPSTREAM_CONTRACTS = (
    ("ARC-0083", "command-center/phase4/contracts/ARC-0083.json"),
    ("ARC-0084", "command-center/phase4/contracts/ARC-0084.json"),
    ("ARC-0087", "command-center/phase4/contracts/ARC-0087.json"),
)


def classify_process(
    returncode: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool,
    skipped: bool,
) -> str:
    if skipped:
        return "SKIPPED"
    if timed_out:
        return "ERROR"
    text = f"{stdout or ''}\n{stderr or ''}"
    if returncode == 0 and MARKER_PASS in text:
        return "PASS"
    if returncode == 1 and MARKER_FAIL in text:
        return "FAIL"
    return "ERROR"


def overall_from_verdicts(verdicts: list[str]) -> str:
    if not verdicts:
        return "ERROR"
    if "ERROR" in verdicts:
        return "ERROR"
    if "FAIL" in verdicts:
        return "FAIL"
    if "SKIPPED" in verdicts:
        return "PASS-WITH-SKIPS"
    if all(v == "PASS" for v in verdicts):
        return "PASS"
    return "ERROR"


def verdict_line(overall: str) -> str:
    return f"{VERDICT_PREFIX} {overall}"


def _resolve_argv(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("empty argv")
    out = list(argv)
    if out[0] in {"python", "python3"}:
        out[0] = sys.executable
    return out


def load_suite(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("id"):
        raise ValueError(f"invalid suite.json: {path}")
    doc["_dir"] = path.parent
    doc["_manifest"] = path
    return doc


def discover_suites(suites_dir: Path, select: list[str] | None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if suites_dir.is_dir():
        for manifest in sorted(suites_dir.glob("*/suite.json")):
            found.append(load_suite(manifest))
    if select:
        wanted = set(select)
        found = [s for s in found if s["id"] in wanted]
        missing = wanted - {s["id"] for s in found}
        if missing:
            raise FileNotFoundError(f"suites not found: {sorted(missing)}")
    return found


def discover_upstream_contracts(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid, rel in UPSTREAM_CONTRACTS:
        contract = repo / rel
        probe_suite = (
            repo / "command-center" / "p2-wave" / "probes" / cid / "suite.json"
        )
        if probe_suite.is_file():
            rows.append(load_suite(probe_suite))
            continue
        if contract.is_file():
            rows.append(
                {
                    "id": f"contract:{cid}",
                    "skip": True,
                    "skip_reason": "artifact-absent",
                    "_dir": contract.parent,
                    "_manifest": contract,
                }
            )
            continue
        rows.append(
            {
                "id": f"contract:{cid}",
                "skip": True,
                "skip_reason": "artifact-absent",
                "_dir": repo / "command-center" / "phase4" / "contracts",
                "_manifest": contract,
            }
        )
    return rows


def run_suite(suite: dict[str, Any], timeout: float) -> dict[str, Any]:
    sid = str(suite["id"])
    if suite.get("skip"):
        return {
            "id": sid,
            "verdict": "SKIPPED",
            "skip_reason": str(suite.get("skip_reason") or "unspecified"),
            "returncode": None,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": "",
        }
    argv = _resolve_argv(list(suite.get("argv") or []))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    timed_out = False
    try:
        proc = subprocess.run(
            argv,
            cwd=str(suite["_dir"]),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "TIMEOUT"
    except OSError as exc:
        rc = 127
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"
    verdict = classify_process(rc, stdout, stderr, timed_out, skipped=False)
    return {
        "id": sid,
        "verdict": verdict,
        "skip_reason": None,
        "returncode": rc,
        "timed_out": timed_out,
        "stdout_tail": stdout[-800:],
        "stderr_tail": stderr[-800:],
    }


def counts_from(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "passed": sum(1 for r in rows if r["verdict"] == "PASS"),
        "failed": sum(1 for r in rows if r["verdict"] == "FAIL"),
        "errored": sum(1 for r in rows if r["verdict"] == "ERROR"),
        "skipped": sum(1 for r in rows if r["verdict"] == "SKIPPED"),
        "total": len(rows),
    }


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = [r["verdict"] for r in rows]
    overall = overall_from_verdicts(verdicts)
    line = verdict_line(overall)
    return {
        "overall_verdict": overall,
        "exit_code": EXIT_BY_OVERALL[overall],
        "unqualified_pass": overall == "PASS",
        "verdict_line": line,
        "counts": counts_from(rows),
        "skipped_ids": [r["id"] for r in rows if r["verdict"] == "SKIPPED"],
        "suites": rows,
        "exit_contract": dict(EXIT_BY_OVERALL),
    }


def run_report(
    suites_dir: Path,
    select: list[str] | None = None,
    discover_contracts: bool = False,
    timeout: float = 30.0,
    repo: Path | None = None,
) -> dict[str, Any]:
    repo = repo or REPO
    rows = [run_suite(s, timeout) for s in discover_suites(suites_dir, select)]
    if discover_contracts:
        rows.extend(run_suite(s, timeout) for s in discover_upstream_contracts(repo))
    return build_report(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARC-0098 conformance runner")
    parser.add_argument("--suites-dir", type=Path, default=DEFAULT_SUITES)
    parser.add_argument("--select", default="", help="comma-separated suite ids")
    parser.add_argument("--discover-contracts", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    select = [s.strip() for s in args.select.split(",") if s.strip()] or None
    report = run_report(
        args.suites_dir,
        select=select,
        discover_contracts=args.discover_contracts,
        timeout=args.timeout,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(report["verdict_line"])
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
