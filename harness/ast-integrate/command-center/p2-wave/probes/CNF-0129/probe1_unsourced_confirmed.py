#!/usr/bin/env python3
"""Probe 1: unsourced CONFIRMED is schema-invalid AND live gate exits non-zero.

Also the both-states control: a well-formed record with two distinct probes
validates silently (no false positive).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))

from fixtures import (  # noqa: E402
    empty_source_confirmed_record,
    unsourced_confirmed_record,
    well_formed_record,
    write_fixtures,
)
from record_gate import schema_errors, validate_record  # noqa: E402

LIVE_GATE = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
SCHEMA = REPO / "command-center/schema/confirmation-record.schema.json"


def run_gate(payload_path: Path) -> tuple[int, dict]:
    p = subprocess.run(
        [sys.executable, "-B", str(LIVE_GATE), str(payload_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**dict(**__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        doc = json.loads(p.stdout)
    except json.JSONDecodeError:
        doc = {"ok": None, "stdout": p.stdout, "stderr": p.stderr}
    return p.returncode, doc


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0129-probe1 {msg}")
    return 1


def main() -> int:
    if not SCHEMA.is_file():
        return fail(f"schema absent {SCHEMA}")
    if not LIVE_GATE.is_file():
        return fail(f"live gate absent {LIVE_GATE}")

    fx = HERE / "fixtures"
    write_fixtures(fx)

    absent_errs = schema_errors(unsourced_confirmed_record())
    if not absent_errs:
        return fail("unsourced CONFIRMED record was schema-valid")
    empty_errs = schema_errors(empty_source_confirmed_record())
    if not empty_errs:
        return fail("empty-string source_probe CONFIRMED was schema-valid")

    good = validate_record(well_formed_record())
    if not good.get("ok") or not good.get("schema_valid"):
        return fail(f"well-formed record rejected {json.dumps(good)[:800]}")

    rc_bad, doc_bad = run_gate(fx / "claim-unsourced-confirmed.json")
    if rc_bad == 0 or doc_bad.get("ok") is True:
        return fail(f"live gate accepted unsourced CONFIRMED rc={rc_bad} {doc_bad}")
    rules = []
    for claim in doc_bad.get("claims") or []:
        rules.extend(v.get("rule") for v in claim.get("violations") or [])
    if "no-source-probe" not in rules:
        return fail(f"live gate missing no-source-probe rules={rules} doc={doc_bad}")

    rc_rec, doc_rec = run_gate(fx / "record-unsourced-confirmed.json")
    if rc_rec == 0 or doc_rec.get("ok") is True:
        return fail(f"live gate accepted unsourced confirmation-record rc={rc_rec}")

    rc_ok, doc_ok = run_gate(fx / "claim-well-formed.json")
    if rc_ok != 0 or doc_ok.get("ok") is not True:
        return fail(f"both-states well-formed claim rejected rc={rc_ok} {doc_ok}")

    rc_rec_ok, doc_rec_ok = run_gate(fx / "record-well-formed.json")
    if rc_rec_ok != 0 or doc_rec_ok.get("ok") is not True:
        return fail(f"both-states well-formed record rejected rc={rc_rec_ok} {doc_rec_ok}")

    out = {
        "probe": "probe1-unsourced-confirmed",
        "schema_unsourced_errors": absent_errs,
        "schema_empty_source_errors": empty_errs,
        "schema_well_formed_ok": True,
        "gate_unsourced_claim_exit": rc_bad,
        "gate_unsourced_claim_ok": doc_bad.get("ok"),
        "gate_unsourced_rules": rules,
        "gate_unsourced_record_exit": rc_rec,
        "gate_well_formed_claim_exit": rc_ok,
        "gate_well_formed_record_exit": rc_rec_ok,
        "both_states_silent_on_good": True,
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "schema_invalid=True gate_exit="
        f"{rc_bad} no-source-probe=True both_states_ok=True"
    )
    print("SUCCESS:CNF-0129-probe1 unsourced CONFIRMED unrepresentable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
