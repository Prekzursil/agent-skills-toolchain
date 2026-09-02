#!/usr/bin/env python3
"""Named probe 1: null-disposition close must be refused; settling-experiment required."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import discrepancy_router as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0013-discrepancy-router.json"
SENTINEL = (
    "SUCCESS:CNF-0013 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the null-disposition close "
    "was refused and the fully dispositioned close succeeded in the same run. "
    "Any other terminal state is FAILED:CNF-0013 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0013-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNF-0013-probe1 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0013-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0013-probe1 sentinel-absent")
        return 1
    if not doc.get("null_disposition_close_refused"):
        print("FAILED:CNF-0013-probe1 artifact does not record null-disposition refuse")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0013-p1-") as tmp:
        result = R.run_gate_controls(Path(tmp) / "ledger")
    if not result.get("null_disposition_refused"):
        print("FAILED:CNF-0013-probe1 live null-disposition close was not refused")
        print(json.dumps(result, indent=2, sort_keys=True)[:2000])
        return 1
    if not result.get("accepted_residual_without_experiment_refused"):
        print("FAILED:CNF-0013-probe1 accepted-residual without experiment was not refused")
        return 1
    if not result.get("naive_close_silent"):
        print("FAILED:CNF-0013-probe1 naive_close control did not demonstrate the hole")
        return 1
    if not result.get("persist_silent_close_refused"):
        print("FAILED:CNF-0013-probe1 persist of silent close was not refused")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-null-disposition",
        "unit_id": "CNF-0013",
        "naive_close_silent": True,
        "null_disposition_refused": True,
        "accepted_residual_without_experiment_refused": True,
        "persist_silent_close_refused": True,
        "null_disposition_code": result.get("null_disposition_code"),
        "router": "tools/command-center/discrepancy_router.py",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "null_refused=True settling_refused=True naive_silent=True persist_refused=True"
    )
    print("SUCCESS:CNF-0013-probe1 null-disposition close refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
