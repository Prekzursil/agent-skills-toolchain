"""IMP-0154 probe2 (mechanically different): a content change on the same URI yields
a NEW row, not a silent overwrite - append-only proven by the hash chain. The probe
does not reuse the double-import path of probe1: it changes bytes, asserts the new
row, then tampers a COPY of the ledger and requires the chain verifier to fail.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.candidate_registry import (  # noqa: E402
    CandidateRegistry,
    LedgerCorruptError,
    verify_chain,
)

URI = "https://example.test/wf.json"


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        ledger = Path(td) / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        v1 = json.dumps({"id": "wf-v1", "step": 1}, sort_keys=True).encode("utf-8")
        v2 = json.dumps({"id": "wf-v1", "step": 2}, sort_keys=True).encode("utf-8")
        r1 = reg.import_bytes(URI, v1, adapter_id="imp0154")
        r2 = reg.import_bytes(URI, v2, adapter_id="imp0154")
        checks["content_change_new_row"] = (
            r2.action == "insert" and r2.candidate_id != r1.candidate_id
        )
        checks["row_count_is_two"] = reg.row_count() == 2
        rows = reg.candidates()
        kept = [e for e in rows if e["content_hash"] == r1.content_hash]
        checks["old_row_not_overwritten"] = len(kept) == 1
        checks["chain_verifies_clean"] = verify_chain(ledger).ok

        # tamper a COPY: flip one payload byte, chain verification must go red
        tampered = Path(td) / "tampered.jsonl"
        shutil.copyfile(ledger, tampered)
        text = tampered.read_text(encoding="utf-8").replace(
            "example.test", "example.tampered", 1
        )
        tampered.write_text(text, encoding="utf-8")
        went_red = False
        try:
            verify_chain(tampered)
        except LedgerCorruptError:
            went_red = True
        res = verify_chain(tampered)
        checks["tamper_detected"] = went_red or (not res.ok)

    out = {
        "unit_id": "IMP-0154",
        "probe": "probe2-content-change-hash-chain",
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0154-probe2 content change on same URI appends a new row; old row survives; a one-byte tamper breaks chain verification")
        return 0
    print("FAILED:IMP-0154-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
