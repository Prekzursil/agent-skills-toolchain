"""Conformance corpus: 12 isolate-fail receipts + 1 all-satisfied PASS row.

This is the TST-0002 corpus shape. tests/fixtures/completion/ is absent on
this tree (TST-0002 is not delivered), so the rows live beside this unit.
Each fail_cK mutates exactly one field of the PASS template.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def pass_receipt() -> dict:
    return {
        "unit_id": "SYNTH-PASS",
        "unit_id": "SYNTH-PASS",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYNTH-PASS",
        "min_bytes_threshold": 128,
        "schema_valid": True,
        "artifacts": [
            {
                "path": "command-center/p2-wave/probes/TST-0003/fixtures/SYNTH-PASS.json",
                "exists": True,
                "bytes": 256,
                "sha256": "0" * 64,
            }
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/TST-0003/reducer.py:evaluate",
                "claim": "PASS template satisfies all twelve conditions.",
            }
        ],
        "tests": [{"id": "t1", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "nc1",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {"verdict": "PASS", "independent": True},
        "defects": [],
        "manifest_registration": {"registered": True},
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": True,
                "read_ok": True,
            }
        ],
        "exit_code": 0,
    }


def _fail(cid: int, mutator) -> dict:
    doc = copy.deepcopy(pass_receipt())
    doc["unit_id"] = f"SYNTH-C{cid:02d}"
    doc["unit_id"] = doc["unit_id"]
    doc["sentinel"] = f"SUCCESS:SYNTH-C{cid:02d}"
    mutator(doc)
    return doc


def fail_receipts() -> dict[int, dict]:
    rows: dict[int, dict] = {}
    rows[1] = _fail(1, lambda d: d.update(state="RUNNING"))
    rows[2] = _fail(2, lambda d: d["artifacts"][0].update(exists=False))
    rows[3] = _fail(3, lambda d: d["artifacts"][0].update(bytes=1))
    rows[4] = _fail(4, lambda d: d.update(schema_valid=False))
    rows[5] = _fail(5, lambda d: d.update(sentinel="quoted-mention-not-a-sentinel"))
    rows[6] = _fail(6, lambda d: d.update(evidence=[]))
    rows[7] = _fail(7, lambda d: d["tests"][0].update(result="FAIL"))
    rows[8] = _fail(
        8, lambda d: d["negative_controls"][0].update(fired_on_bad_state=False)
    )
    rows[9] = _fail(9, lambda d: d["reviewer"].update(verdict="NOT-REVIEWED"))
    rows[10] = _fail(
        10,
        lambda d: d.update(
            defects=[{"id": "D-P0", "severity": "P0", "status": "open"}]
        ),
    )
    rows[11] = _fail(11, lambda d: d["manifest_registration"].update(registered=False))
    rows[12] = _fail(12, lambda d: d["downstream_consumers"][0].update(read_ok=False))
    return rows


def all_rows() -> list[dict]:
    fails = fail_receipts()
    return [fails[i] for i in range(1, 13)] + [pass_receipt()]


def write_fixtures() -> list[str]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for row in all_rows():
        name = f"{row['unit_id']}.json"
        path = FIXTURES / name
        path.write_text(
            json.dumps(row, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(f"command-center/p2-wave/probes/TST-0003/fixtures/{name}")
    return written


all_rows = all_rows
