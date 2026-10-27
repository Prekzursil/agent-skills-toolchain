#!/usr/bin/env python3
"""probe2 for TST-0010: severity downgrades are append-only audited.

Drives downgrade() live: blank reason refused; a real downgrade appends exactly
one JSONL row; replayed audit clears the P1; a ledger field-mutation P1->P2
without an audit row still blocks (naive-ledger negative control); an audit
resolve on a P1 does not block.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0010"
FIX = Path(__file__).resolve().parent / "fixtures"


def load_c10():
    spec = importlib.util.spec_from_file_location(
        "completion_c10_live", REPO / "tools" / "command-center" / "completion_c10.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["completion_c10_live"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    c10 = load_c10()
    checks = {}
    audit = FIX / "downgrade_audit_row.jsonl"
    FIX.mkdir(parents=True, exist_ok=True)
    audit.write_bytes(b"")
    cand = dict(c10.isolation_candidate())
    cand["defects"] = [{"id": "D-AUD-1", "severity": "P1", "status": "open"}]
    refused = False
    try:
        c10.downgrade(cand, defect_id="D-AUD-1", to_severity="P2", reason="", actor="probe2", audit_path=audit)
    except c10.GateError:
        refused = True
    except Exception:
        refused = False
    checks["blank_reason_refused"] = refused and audit.stat().st_size == 0
    row = c10.downgrade(cand, defect_id="D-AUD-1", to_severity="P2", reason="triage: not a P1", actor="probe2", audit_path=audit, ts="2026-10-25T00:00:00Z")
    checks["row_returned"] = row is not None
    raw = audit.read_bytes()
    lines = [ln for ln in raw.decode("utf-8").splitlines() if ln.strip()]
    checks["exactly_one_row"] = len(lines) == 1
    checks["row_names_defect_and_target"] = b"D-AUD-1" in raw and b"P2" in raw
    replayed = c10.evaluate_c10(cand, c10.load_audit(audit))
    checks["audit_cleared_p1"] = replayed["outcome"] == "SATISFIED"
    mutated = dict(cand)
    mutated["defects"] = [{"id": "D-AUD-1", "severity": "P2", "status": "open", "opened_severity": "P1"}]
    blocked = c10.evaluate_c10(mutated, [])
    checks["ledger_mutation_without_audit_blocks"] = (
        blocked["outcome"] == "UNSATISFIED" and "D-AUD-1" in (blocked.get("unauthorized_downgrade_ids") or [])
    )
    resolve_rows = [{"action": "resolve", "defect_id": "D-AUD-1", "ts": "2026-10-25T00:00:00Z"}]
    cleared = c10.evaluate_c10(cand, resolve_rows)
    checks["resolved_p1_does_not_block"] = cleared["outcome"] == "SATISFIED"
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-downgrade-audit", "pass": ok, "checks": checks}, default=str))
    if ok:
        print(f"SUCCESS:{UID}-probe2 blank downgrade refused; one append-only JSONL row; replay clears P1; unaudited mutation blocks naming the id; resolved P1 does not block")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
