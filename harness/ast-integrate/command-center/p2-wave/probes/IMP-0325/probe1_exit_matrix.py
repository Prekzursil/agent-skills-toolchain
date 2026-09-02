#!/usr/bin/env python3
"""Probe 1: exit-code matrix across all subcommands via the shell harness.

Asserts: each subcommand's documented success code is distinct; every matrix
row matches; no failure row returns 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "council" / "cli"))

import exit_codes as EC  # noqa: E402

UNIT = "IMP-0325"
HARNESS = HERE / "harness.sh"
SUCCESS_CASES = {
    "run/happy": EC.EXIT_RUN_OK,
    "resume/checkpoint": EC.EXIT_RESUME_OK,
    "inspect/success": EC.EXIT_INSPECT_OK,
    "list-presets/default": EC.EXIT_LIST_PRESETS_OK,
    "explain/success": EC.EXIT_EXPLAIN_OK,
}
FAILURE_CASES = {
    "run/failed-council": EC.EXIT_COUNCIL_FAILED,
    "run/no-write": EC.EXIT_MISSING_ARTIFACT,
    "resume/missing": EC.EXIT_NO_CHECKPOINT,
    "inspect/missing": EC.EXIT_MISSING_ARTIFACT,
    "list-presets/empty": EC.EXIT_NO_PRESETS,
    "explain/no-rule": EC.EXIT_NO_LINEAGE,
    "unknown/verb": EC.EXIT_USAGE,
}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def parse_tsv(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("case\t"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        name, expected, actual, ok = parts
        rows.append(
            {
                "case": name,
                "expected": int(expected),
                "actual": int(actual),
                "ok": ok,
            }
        )
    return rows


def main() -> int:
    proc = subprocess.run(
        ["bash", str(HARNESS)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**{k: v for k, v in __import__("os").environ.items()}, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    rows = parse_tsv(proc.stdout or "")
    payload = {
        "probe": "probe1-exit-matrix",
        "unit_id": UNIT,
        "harness_exit": proc.returncode,
        "rows": rows,
        "success_codes": SUCCESS_CASES,
        "failure_codes": FAILURE_CASES,
    }
    print(json.dumps(payload, sort_keys=True, default=str))

    if proc.returncode != 0:
        print(text[-2000:])
        return fail(f"harness exit={proc.returncode}")
    got = {r["case"]: r for r in rows}
    missing = [k for k in list(SUCCESS_CASES) + list(FAILURE_CASES) if k not in got]
    if missing:
        return fail(f"matrix rows missing: {missing}")
    for name, expected in {**SUCCESS_CASES, **FAILURE_CASES}.items():
        row = got[name]
        if row["actual"] != expected or row["expected"] != expected or row["ok"] != "PASS":
            return fail(f"{name} expected={expected} actual={row}")
    success_values = list(SUCCESS_CASES.values())
    if len(set(success_values)) != len(success_values):
        return fail("success codes are not pairwise distinct")
    if 0 in success_values:
        return fail("a subcommand success code is 0; distinctness would collapse with POSIX ok")
    for name in FAILURE_CASES:
        if got[name]["actual"] == 0:
            return fail(f"failure case {name} exited 0")
    if EC.EXIT_COUNCIL_FAILED == 0:
        return fail("EXIT_COUNCIL_FAILED is 0")
    print(
        "distinct_success="
        + ",".join(str(v) for v in success_values)
        + f" harness_rows={len(rows)} failed_council={got['run/failed-council']['actual']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 exit-code matrix across all subcommands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
