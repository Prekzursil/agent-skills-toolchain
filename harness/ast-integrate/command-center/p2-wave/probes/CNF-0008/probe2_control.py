#!/usr/bin/env python3
"""Probe 2: a receipt whose probe WAS run must not be flagged unattested."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from attestation import artifact_controls, opposite_controls  # noqa: E402
from controls import run_both  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0008-execution-attestation.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0008-p2-") as tmp:
        result = run_both(Path(tmp))
    planted = result["planted"]
    genuine = result["genuine"]
    if not result["ok"] or not opposite_controls(planted, genuine):
        print("FAILED:CNF-0008-probe2 controls not classified oppositely")
        print(json.dumps({"planted": planted, "genuine": genuine}, indent=2, default=str)[:4000])
        return 1
    if genuine.get("unattested") is not False:
        print("FAILED:CNF-0008-probe2 genuine control was flagged unattested")
        return 1
    if genuine.get("original_verdict") != "CONFIRMED":
        print("FAILED:CNF-0008-probe2 genuine original verdict was not CONFIRMED")
        return 1
    if genuine.get("attested_verdict") != "CONFIRMED":
        print(
            "FAILED:CNF-0008-probe2 genuine verdict changed: "
            f"{genuine.get('attested_verdict')}"
        )
        return 1
    if not genuine.get("ledger_row_id"):
        print("FAILED:CNF-0008-probe2 genuine missing ledger_row_id")
        return 1
    if not genuine.get("produced_path") or not genuine.get("produced_mtime"):
        print("FAILED:CNF-0008-probe2 genuine missing produced path/mtime")
        return 1
    if genuine.get("id") != "receipt-genuine-control":
        print(f"FAILED:CNF-0008-probe2 genuine id {genuine.get('id')}")
        return 1
    if planted.get("unattested") is not True:
        print("FAILED:CNF-0008-probe2 planted side of opposite pair failed")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0008-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0008-probe2 self-declared {doc.get('state')}")
        return 1
    controls = artifact_controls(doc)
    ctrl = controls.get("genuine") or {}
    if ctrl.get("unattested") is not False:
        print("FAILED:CNF-0008-probe2 artifact genuine control flagged unattested")
        return 1
    if not controls.get("classified_oppositely"):
        print("FAILED:CNF-0008-probe2 artifact classified_oppositely false")
        return 1

    out = {
        "probe": "probe2-control",
        "unit_id": "CNF-0008",
        "genuine_unattested": False,
        "genuine_ledger_row_id": genuine["ledger_row_id"],
        "genuine_produced_path": genuine["produced_path"],
        "genuine_produced_mtime": genuine["produced_mtime"],
        "classified_oppositely": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "genuine id={id} unattested={u} ledger={l} path={p} mtime={m}".format(
            id=genuine["id"],
            u=genuine["unattested"],
            l=genuine["ledger_row_id"],
            p=genuine["produced_path"],
            m=genuine["produced_mtime"],
        )
    )
    print("SUCCESS:CNF-0008-probe2 genuine control receipt not flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
