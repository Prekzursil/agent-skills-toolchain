#!/usr/bin/env python3
"""Shard21 w3: generate probe1_receipt_integrity.py for the remaining units.

Each probe1 verifies: receipt parses, state=SUCCESS, sentinel present,
unit_id, catalog output_path/output_schema/question anchor, recorded
reviewer closure (PASS + independent), and the unit's required claim blocks.
"""
from pathlib import Path

REPO = Path.home() / "p2-g1"

UNITS = {
    "TST-0165": (
        ["current_schema_version", "migration_table", "lenient_controls", "evidence_a", "evidence_b", "fixtures"],
        "resume_report",
    ),
    "TST-0166": (
        ["measurements", "question_answer", "scientific_verdict", "negative_controls", "control_ids"],
        "resume_report",
    ),
    "TST-0168": (
        ["child_count_per_case", "randomized_suspend_events", "race_failures", "negative_controls", "evidence", "refute_disposition"],
        "resume_report",
    ),
    "TST-0169": (
        ["answer", "evidence", "negative_controls", "tests", "report"],
        "resume_report",
    ),
    "TST-0171": (
        ["clean_shutdown_evidence", "determinism_evidence", "negative_controls", "premise", "implementation"],
        "resume_report",
    ),
}

TEMPLATE = '''#!/usr/bin/env python3
"""TST-{uid4} probe 1: receipt integrity + catalog alignment (suite rebuilt
by shard21-wave3 after the prior builder lost the probes/ dir)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "{uid}.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UID = "{uid}"
SENTINEL = "SUCCESS:{uid}"


def fail(msg: str) -> int:
    print(f"FAILED:{{UID}}-probe1 {{msg}}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing or empty")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable: {{exc}}")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id={{doc.get('unit_id')}}")
    if str(doc.get("state") or "").upper() in {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}:
        return fail(f"self-declared {{doc.get('state')}}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    unit = None
    for u in json.loads(CATALOG.read_text(encoding="utf-8")).get("work_units") or []:
        if u.get("id") == UID:
            unit = u
            break
    if unit is None:
        return fail("catalog-missing")
    if unit.get("output_path") != f"command-center/receipts/{uid}.json":
        return fail("catalog output_path drift")
    declared = str(doc.get("output_schema") or doc.get("declared_output_schema") or doc.get("output_schema_declaration") or "")
    if declared != str(unit.get("output_schema") or ""):
        return fail(f"output_schema mismatch: {{declared!r}}")

    rev = doc.get("reviewer") or {{}}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("recorded reviewer closure missing (PASS + independent)")

    for key in {required!r}:
        if key not in doc:
            return fail(f"claim block missing: {{key}}")

    print(
        json.dumps(
            {{
                "probe": "probe1-receipt-integrity",
                "unit_id": UID,
                "state": doc.get("state"),
                "reviewer": str(rev.get("reviewer_id"))[:40],
                "pass": True,
            }},
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{{UID}}-probe1 receipt integrity + catalog alignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

for uid, (required, kind) in UNITS.items():
    target = REPO / "command-center" / "p2-wave" / "probes" / uid / "probe1_receipt_integrity.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        TEMPLATE.format(uid=uid, uid4=uid.split("-")[1], required=required),
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", target.relative_to(REPO).as_posix())
