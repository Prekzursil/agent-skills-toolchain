#!/usr/bin/env python3
"""Probe 2: cell arithmetic, both-states, schema-can-fail — different field than probe 1.

Probe 1 compares live trap fingerprints to the receipt. This probe checks that
the matrix is a complete product, that a portable claim is green in every
column, that collapsing two shells would hide a trap, and that the declared
contract rejects the three garbage probes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0150.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0150-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0150-probe2 receipt schema-invalid", errs[0].message)
        return 1
    garbage_counts = []
    for g in GARBAGE:
        n = len(S.iter_errors(g))
        garbage_counts.append(n)
        if n < 1:
            print("FAILED:CNF-0150-probe2 contract accepted garbage")
            return 1

    payload = M.payload_of(doc)
    rows = [r["id"] for r in (payload.get("axes") or {}).get("rows") or []]
    cols = [c["id"] for c in (payload.get("axes") or {}).get("columns") or []]
    cells = [c for c in (payload.get("cells") or []) if isinstance(c, dict)]
    expected = len(rows) * len(cols)
    if expected < 4:
        print("FAILED:CNF-0150-probe2 axes too small")
        return 1
    keys = {(c.get("row_id"), c.get("column_id")) for c in cells}
    if len(cells) != expected or len(keys) != expected:
        print(f"FAILED:CNF-0150-probe2 empty/duplicate cells have={len(cells)} want={expected}")
        return 1
    for r in rows:
        for c in cols:
            if (r, c) not in keys:
                print(f"FAILED:CNF-0150-probe2 missing cell {(r, c)}")
                return 1
    if payload.get("empty_cells") != 0:
        print("FAILED:CNF-0150-probe2 empty_cells not 0")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0150-probe2 self-declared failure")
        return 1
    if "SUCCESS:CNF-0150" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0150-probe2 sentinel absent")
        return 1
    if payload.get("kind") not in (None, "reproduction-matrix"):
        print("FAILED:CNF-0150-probe2 report.kind", payload.get("kind"))
        return 1

    by_row: dict[str, list[dict]] = {r: [] for r in rows}
    for cell in cells:
        by_row[cell["row_id"]].append(cell)

    portable = by_row.get("portable-lf-printf") or []
    if len(portable) != len(cols) or any(c["verdict"] != "PASS" for c in portable):
        print("FAILED:CNF-0150-probe2 portable claim not PASS in every shell")
        return 1
    argv_row = by_row.get("pytest-argv-portable") or []
    if any(c["verdict"] != "PASS" for c in argv_row):
        print("FAILED:CNF-0150-probe2 argv pytest row not portable")
        return 1

    shim = {c["column_id"]: c["verdict"] for c in by_row.get("cmd-shim-presence") or []}
    if shim.get("powershell-7") != "PASS" or shim.get("git-bash-msys") != "FAIL":
        print("FAILED:CNF-0150-probe2 cmd-shim not two-sided")
        return 1
    if shim.get("powershell-7") == shim.get("git-bash-msys"):
        print("FAILED:CNF-0150-probe2 collapsing shells would hide cmd-shim")
        return 1

    launchers = by_row.get("plugin-launchers") or []
    if launchers and any(c["verdict"] == "PASS" for c in launchers):
        print("FAILED:CNF-0150-probe2 absent launchers folded into PASS")
        return 1
    if launchers and not all(c["verdict"] == "NOT-CHECKED" for c in launchers):
        print("FAILED:CNF-0150-probe2 absent launchers not NOT-CHECKED")
        return 1

    live = M.run_live()
    rec_portable = payload.get("portable_subset") or doc.get("portable_subset") or []
    if set(live["portable_subset"]) != set(rec_portable):
        print("FAILED:CNF-0150-probe2 portable_subset drift")
        return 1
    rec_tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    for tid in (
        "known-present-cmd-shim",
        "path-conversion-sdcard-and-nopathconv",
        "crlf-wsl-bash-n-not-git-bash",
        "both-states-portable",
    ):
        if rec_tests.get(tid) != "PASS":
            print(f"FAILED:CNF-0150-probe2 catalog test {tid} not PASS")
            return 1

    out = {
        "probe": "probe2-cell-contract",
        "unit_id": "CNF-0150",
        "expected_cells": expected,
        "present_cells": len(cells),
        "garbage_error_counts": garbage_counts,
        "portable_subset": rec_portable,
        "cmd_shim_verdicts": shim,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0150-probe2 matrix contract and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
