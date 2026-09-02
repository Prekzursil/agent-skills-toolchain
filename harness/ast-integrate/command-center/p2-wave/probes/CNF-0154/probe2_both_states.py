#!/usr/bin/env python3
"""Probe 2: planted-false from CNF-0133 is REFUTED; planted-true CONFIRMED; AND-gate."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from claims import p0_ids  # noqa: E402
from dispatch_one import run_claim  # noqa: E402
from record_schema import schema_valid  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CNF-0154.json"
ORACLE = HERE / "fixtures" / "planted_oracle.json"
PLANTED_FALSE = "CNF-0133-PF-001"
PLANTED_TRUE = "CNF-0154-P0-001"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0154-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0154" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
    if oracle[PLANTED_FALSE].get("from") != "CNF-0133":
        return fail("planted-false not attributed to CNF-0133")
    if oracle[PLANTED_FALSE].get("kind") != "planted-false":
        return fail("CNF-0133 item is not planted-false")

    with tempfile.TemporaryDirectory(prefix="cnf0154-p2-") as tmp:
        root = Path(tmp)
        refuted = run_claim(PLANTED_FALSE, root)
        confirmed = run_claim(PLANTED_TRUE, root)
        third = run_claim("CNF-0154-P0-003", root)

    if refuted.get("classification") != "SUCCESS":
        return fail(f"planted-false class={refuted.get('classification')}")
    if refuted.get("verdict") != "REFUTED":
        return fail(f"planted-false verdict={refuted.get('verdict')} want REFUTED")
    if confirmed.get("verdict") != "CONFIRMED":
        return fail(f"planted-true verdict={confirmed.get('verdict')} want CONFIRMED")
    if third.get("verdict") != "CONFIRMED":
        return fail(f"P0-003 verdict={third.get('verdict')}")

    for name, row in ("false", refuted), ("true", confirmed), ("p003", third):
        rec = row.get("record")
        if not isinstance(rec, dict) or not schema_valid(rec):
            return fail(f"{name} record schema-invalid")
        if rec.get("source_probe") == rec.get("verifier_probe"):
            return fail(f"{name} same-probe-rerun")
        if not row.get("prompt_file_path"):
            return fail(f"{name} missing prompt_file_path")
        if not row.get("output_last_message_path"):
            return fail(f"{name} missing output-last-message")
        if int(row.get("output_bytes") or 0) <= 0:
            return fail(f"{name} empty output-last-message")
        if row.get("exit_code") != 0:
            return fail(f"{name} exit {row.get('exit_code')}")
        schema = row.get("schema_validation") or {}
        if not schema.get("ok"):
            return fail(f"{name} schema_validation not ok")
        if "--background" in (row.get("command_string") or "").split():
            return fail(f"{name} used --background")
        if "--prompt-file" not in (row.get("command_string") or ""):
            return fail(f"{name} not prompt-by-file")
        if "implementer already CONFIRMED" in json.dumps(rec):
            return fail(f"{name} confirmer saw implementer conclusion")

    art_records = {r.get("claim_id"): r for r in (doc.get("confirmation_records") or [])}
    if PLANTED_FALSE not in art_records:
        return fail("artifact missing CNF-0133 planted-false record")
    if art_records[PLANTED_FALSE].get("verdict") != "REFUTED":
        return fail("artifact planted-false not REFUTED")
    for cid in p0_ids():
        if cid not in art_records:
            return fail(f"artifact missing confirmation for {cid}")
        if not schema_valid(art_records[cid]):
            return fail(f"artifact record schema-invalid {cid}")

    dispatches = {r.get("claim_id"): r for r in (doc.get("dispatch_records") or [])}
    for cid in p0_ids():
        row = dispatches.get(cid) or {}
        for key in (
            "prompt_file_path",
            "output_last_message_path",
            "output_bytes",
            "exit_code",
            "schema_validation",
        ):
            if key not in row:
                return fail(f"artifact dispatch {cid} missing {key}")
        if row.get("classification") != "SUCCESS":
            return fail(f"artifact dispatch {cid} class={row.get('classification')}")

    out = {
        "probe": "probe2-both-states",
        "unit_id": "CNF-0154",
        "planted_false_refuted": True,
        "planted_false_id": PLANTED_FALSE,
        "planted_true_confirmed": True,
        "p0_dispatched": p0_ids(),
        "and_gate": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0154-probe2 both-states REFUTED planted-false from CNF-0133")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
