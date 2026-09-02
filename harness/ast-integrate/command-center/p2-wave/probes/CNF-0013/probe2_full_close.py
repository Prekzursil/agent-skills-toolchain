#!/usr/bin/env python3
"""Named probe 2: a fully dispositioned discrepancy must close cleanly."""
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
        print("FAILED:CNF-0013-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNF-0013-probe2 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0013-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0013-probe2 sentinel-absent")
        return 1
    if not doc.get("fully_dispositioned_close_succeeded"):
        print("FAILED:CNF-0013-probe2 artifact does not record a clean close")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0013-p2-") as tmp:
        result = R.run_gate_controls(Path(tmp) / "ledger")
    if not result.get("fully_dispositioned_close_succeeded"):
        print("FAILED:CNF-0013-probe2 live fully dispositioned close failed")
        print(json.dumps(result, indent=2, sort_keys=True)[:2000])
        return 1
    if not result.get("implementation_defect_opened"):
        print("FAILED:CNF-0013-probe2 implementation-defect did not open a defect")
        return 1
    if not result.get("confirmation_defect_opened"):
        print("FAILED:CNF-0013-probe2 confirmation-defect did not open a defect")
        return 1
    if not result.get("implementer_close_refused"):
        print("FAILED:CNF-0013-probe2 implementer was allowed to close")
        return 1
    if not result.get("confirmation_author_close_refused"):
        print("FAILED:CNF-0013-probe2 confirmation author was allowed to close")
        return 1
    if not result.get("pass"):
        print("FAILED:CNF-0013-probe2 same-run controls did not all pass")
        print(json.dumps(result, indent=2, sort_keys=True)[:2000])
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-full-close",
        "unit_id": "CNF-0013",
        "fully_dispositioned_close_succeeded": True,
        "implementation_defect_opened": True,
        "confirmation_defect_opened": True,
        "implementer_close_refused": True,
        "confirmation_author_close_refused": True,
        "accepted_residual_with_experiment_succeeded": result.get(
            "accepted_residual_with_experiment_succeeded"
        ),
        "closed_record_ids": result.get("closed_record_ids"),
        "router": "tools/command-center/discrepancy_router.py",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "full_close=True impl_defect=True cnf_defect=True "
        "implementer_refused=True confirmer_refused=True"
    )
    print("SUCCESS:CNF-0013-probe2 fully dispositioned close succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
