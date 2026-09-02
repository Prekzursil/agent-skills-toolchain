#!/usr/bin/env python3
"""Probe 2: writer refuses when the manifest gate has not passed in-window."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from emit_report import emit  # noqa: E402
from gate import (  # noqa: E402
    GATE_PATHS,
    GATE_RECEIPT_REL,
    GateBlocked,
    WINDOW_SECONDS,
    authorize_write,
    verify_entries,
)

CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SCHEMA = "command-center/schema/final-report.schema.json"


def _seed(tmp: Path) -> None:
    for rel in (CATALOG, SCHEMA):
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dest)


def main() -> int:
    now = time.time()
    with tempfile.TemporaryDirectory(prefix="syn0041-p2-") as td:
        tmp = Path(td)
        _seed(tmp)
        live = verify_entries(tmp)
        if live["status"] != "PERMITTED":
            print(f"FAILED:SYN-0041-probe2 scratch gate not clean {live}")
            return 1

        # 1. No receipt, no rerun -> blocked.
        try:
            authorize_write(tmp, now, rerun=False, receipt_path=tmp / GATE_RECEIPT_REL)
            print("FAILED:SYN-0041-probe2 absent receipt authorised a write")
            return 1
        except GateBlocked as exc:
            print(f"absent-receipt blocked reason={exc.reason}")
            if exc.reason != "manifest-gate-absent":
                print("FAILED:SYN-0041-probe2 unexpected absent reason")
                return 1

        # 2. Stale permitted receipt, no rerun -> blocked.
        stale = dict(live)
        stale["verified_at_unix"] = now - (WINDOW_SECONDS + 30)
        receipt = tmp / GATE_RECEIPT_REL
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(stale), encoding="utf-8")
        try:
            authorize_write(tmp, now, rerun=False, receipt_path=receipt)
            print("FAILED:SYN-0041-probe2 stale receipt authorised a write")
            return 1
        except GateBlocked as exc:
            print(f"stale-receipt blocked reason={exc.reason}")
            if exc.reason != "manifest-gate-stale":
                print("FAILED:SYN-0041-probe2 unexpected stale reason")
                return 1

        # 3. Writer emit with rerun=False and stale receipt must not write.
        out_rel = "command-center/synthesis/SYN-0041.final-report.json"
        rc = emit(tmp, now=now, rerun=False, out_rel=out_rel)
        if rc == 0 or (tmp / out_rel).is_file():
            print("FAILED:SYN-0041-probe2 emit wrote under stale gate")
            return 1
        print("emit-stale rc!=0 and no output file")

        # 4. Planted deletion of a listed input, rerun=True -> blocked.
        catalog = tmp / CATALOG
        catalog.unlink()
        try:
            authorize_write(tmp, now, rerun=True, receipt_path=receipt)
            print("FAILED:SYN-0041-probe2 deletion did not block")
            return 1
        except GateBlocked as exc:
            print(f"planted-deletion blocked reason={exc.reason}")
            if "missing:" not in exc.reason:
                print("FAILED:SYN-0041-probe2 deletion reason not missing")
                return 1
        shutil.copy2(REPO / CATALOG, catalog)

        # 5. Truncation to empty, rerun=True -> blocked.
        schema = tmp / SCHEMA
        schema.write_bytes(b"")
        try:
            authorize_write(tmp, now, rerun=True, receipt_path=receipt)
            print("FAILED:SYN-0041-probe2 truncation did not block")
            return 1
        except GateBlocked as exc:
            print(f"planted-truncation blocked reason={exc.reason}")
        shutil.copy2(REPO / SCHEMA, schema)

        # 6. Clean rerun permits; fresh cache without rerun also permits.
        ok = authorize_write(tmp, now, rerun=True, receipt_path=receipt)
        if ok.get("status") != "PERMITTED":
            print(f"FAILED:SYN-0041-probe2 clean rerun not permitted {ok}")
            return 1
        print("clean-rerun PERMITTED")
        cached = authorize_write(tmp, now + 1, rerun=False, receipt_path=receipt)
        if cached.get("status") != "PERMITTED":
            print("FAILED:SYN-0041-probe2 fresh cache not permitted")
            return 1
        print("fresh-cache PERMITTED")

        if len(GATE_PATHS) < 2:
            print("FAILED:SYN-0041-probe2 gate path list too small")
            return 1

    print("SUCCESS:SYN-0041-probe2 manifest-gate window and planted defects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
