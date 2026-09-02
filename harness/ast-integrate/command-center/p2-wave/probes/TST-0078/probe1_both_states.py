#!/usr/bin/env python3
"""Probe 1: every unsupported cell refuses; every supported cell proceeds."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(HERE))

import compatibility as C  # noqa: E402
from receipt_schema import assert_receipt, matrix_of  # noqa: E402

UNIT = "TST-0078"
OUT = "command-center/receipts/TST-0078.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
PUBLISHED = HERE / "fixtures" / "published"
SENTINEL = "SUCCESS:TST-0078"


def main() -> int:
    art_path = REPO / OUT
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        print("FAILED:TST-0078-probe1 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0078-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    rc = assert_receipt(doc, "TST-0078-probe1")
    if rc != 0:
        return rc
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0078-probe1 self-declared", doc.get("state"))
        return 1

    contract = C.load_contract()
    with tempfile.TemporaryDirectory(prefix="tst0078-p1-") as tmp_s:
        live = C.run_matrix(PUBLISHED, Path(tmp_s) / "cells", contract)

    supported = [c for c in live["cells"] if c["declared"] == "SUPPORTED"]
    unsupported = [c for c in live["cells"] if c["declared"] == "UNSUPPORTED"]
    if not supported or not unsupported:
        print("FAILED:TST-0078-probe1 both-halves-empty")
        return 1
    bad_s = [
        c
        for c in supported
        if not (
            c["outcome"] == "PROCEEDED"
            and c["installed"]
            and c["plugin_present"]
            and c["files_written"] > 0
            and c["match"]
        )
    ]
    bad_u = [
        c
        for c in unsupported
        if not (
            c["outcome"] == "REFUSED"
            and (not c["installed"])
            and (not c["plugin_present"])
            and c["files_written"] == 0
            and c["match"]
        )
    ]
    if bad_s:
        print("FAILED:TST-0078-probe1 supported did not proceed", bad_s[:3])
        return 1
    if bad_u:
        print("FAILED:TST-0078-probe1 unsupported did not refuse", bad_u[:3])
        return 1

    art_cells = {
        (c["os"], c["client"], c["client_version"]): c
        for c in matrix_of(doc)["cells"]
    }
    for c in supported + unsupported:
        rec = art_cells.get((c["os"], c["client"], c["client_version"]))
        if rec is None:
            print("FAILED:TST-0078-probe1 artifact missing cell", c)
            return 1
        if rec.get("outcome") != c["outcome"] or rec.get("declared") != c["declared"]:
            print("FAILED:TST-0078-probe1 artifact drift", rec, c)
            return 1

    unparsable = C.negotiate(
        {"os": "linux", "client": "claude-code", "client_version": "???"}
    )
    if unparsable.action != "refuse":
        print("FAILED:TST-0078-probe1 unparsable not refused")
        return 1

    payload = {
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "supported_proceeded": len(supported),
        "unsupported_refused": len(unsupported),
        "ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:TST-0078-probe1 supported={len(supported)} "
        f"unsupported={len(unsupported)} both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
