#!/usr/bin/env python3
"""Probe 1: every trusted absence has a live known-present control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import engine as E  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0066-negative-result-recheck.json"
SCHEMA = REPO / "command-center/schema/detector-control.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0066-probe1 {msg}")
    return 1


def main() -> int:
    live = E.retest_all()
    confirmed = [r for r in live["records"] if r["classification"] == "CONFIRMED_ABSENCE"]
    if not confirmed:
        return fail("no confirmed absences")
    for rec in confirmed:
        if rec.get("control_found_known_present") is not True:
            return fail(f"{rec['id']} confirmed without control hit")
        if not rec.get("control_id"):
            return fail(f"{rec['id']} confirmed without control_id")
        print(
            f"absence {rec['id']} control={rec['control_id']} "
            f"found={rec['control_found_known_present']} "
            f"result={rec['absence_result']}"
        )

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNF-0066" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print(errs[0].message)
        return fail("artifact schema-invalid")

    contract_errs = C.check_document(doc)
    if contract_errs:
        print("\n".join(contract_errs[:12]))
        return fail("artifact contract")

    live_ids = {r["id"]: r["classification"] for r in live["records"]}
    art_ids = {r["id"]: r["classification"] for r in doc.get("records") or []}
    if live_ids != art_ids:
        return fail(f"classification drift live={live_ids} art={art_ids}")

    art_abs = {a["id"] for a in doc.get("absences") or []}
    live_abs = {a["id"] for a in live["absences"]}
    if art_abs != live_abs:
        return fail(f"absence-set drift live={live_abs} art={art_abs}")

    payload = {
        "confirmed": len(confirmed),
        "pass": True,
        "probe": "probe1-controls",
        "unit_id": "CNF-0066",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNF-0066-probe1 every absence paired with known-present control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
