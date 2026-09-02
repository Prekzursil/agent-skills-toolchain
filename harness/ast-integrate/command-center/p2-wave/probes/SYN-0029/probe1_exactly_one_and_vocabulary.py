#!/usr/bin/env python3
"""Probe 1: exactly one label per requirement; vocabulary is the declared five.

Independent of probe 2: does not run the planted-omission arm. Re-derives
fixture exactly-one / double-label / illegal-vocab, then schema-checks the
live artifact and recomputes the live join.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import closure as C  # noqa: E402
import controls as T  # noqa: E402
import register as R  # noqa: E402
import report as P  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0029.json"
SCHEMA = REPO / "command-center/schema/requirement-closure.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0029-probe1 {msg}")
    return 1


def main() -> int:
    fx = T.test_exactly_one_and_vocabulary()
    print(
        json.dumps(
            {
                "good_ok": fx["good_ok"],
                "double_fails": fx["double_fails"],
                "vocab_fails": fx["vocab_fails"],
                "good_counts": fx["good_counts"],
            },
            sort_keys=True,
        )
    )
    if not fx["pass"]:
        return fail("fixture exactly-one/vocabulary did not discriminate")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:SYN-0029" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != "SYN-0029":
        return fail("unit_id")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        return fail("schema accepts garbage")

    rows = doc.get("rows") or []
    if not rows:
        return fail("empty rows")
    size = doc.get("register_size")
    if not isinstance(size, int) or size < 1:
        return fail("register-size-unstated")
    if size != len(rows):
        return fail(f"register_size {size} != rows {len(rows)}")
    unlabelled = doc.get("unlabelled_count")
    labelled = doc.get("labelled_count")
    if not isinstance(unlabelled, int):
        return fail("unlabelled_count unstated")
    if not isinstance(labelled, int):
        return fail("labelled_count unstated")
    if unlabelled + labelled != size:
        return fail("counts do not sum to register_size")

    seen = set()
    disappeared = 0
    for row in rows:
        rid = row.get("requirement_id")
        if rid in seen:
            return fail(f"duplicate row {rid}")
        seen.add(rid)
        extra = set(row) - {
            "requirement_id",
            "text",
            "spec_anchor",
            "label",
            "report_anchor",
            "bound_unit_ids",
            "unlabelled",
            "kind",
        }
        if extra:
            return fail(f"extra fields on {rid}: {sorted(extra)}")
        if "labels" in row:
            return fail(f"double-labelled encoding on {rid}")
        lab = row.get("label")
        if lab not in (*C.FIVE, C.DISAPPEARED):
            return fail(f"illegal live label {lab!r} on {rid}")
        if lab == C.DISAPPEARED:
            disappeared += 1
            if row.get("unlabelled") is not True:
                return fail(f"{rid} DISAPPEARED but unlabelled!=True")
        else:
            if row.get("unlabelled") is not False:
                return fail(f"{rid} labelled but unlabelled!=False")
        if not row.get("report_anchor"):
            return fail(f"{rid} missing report_anchor")
        if not row.get("spec_anchor"):
            return fail(f"{rid} missing spec_anchor")
    if disappeared != unlabelled:
        return fail(f"DISAPPEARED {disappeared} != unlabelled_count {unlabelled}")

    live_reg = R.load_register()
    live_rep = P.load_report()
    recomputed = C.close(
        live_reg["records"],
        live_rep["items"],
        {"path": live_rep["path"], "present": live_rep["present"]},
    )
    live_map = {r["requirement_id"]: r["label"] for r in rows}
    rec_map = {r["requirement_id"]: r["label"] for r in recomputed["rows"]}
    if live_map != rec_map:
        return fail("live join drifted from artifact labels")
    if recomputed["unlabelled_count"] != unlabelled:
        return fail("live unlabelled drifted")
    if recomputed["double_labelled"] or recomputed["illegal_labels"]:
        return fail("live join has double-labelled or illegal labels")

    recorded = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    if recorded.get("test_exactly_one_label_per_requirement") != "PASS":
        return fail("artifact test_exactly_one not PASS")
    if recorded.get("test_label_vocabulary_is_the_declared_five") != "PASS":
        return fail("artifact vocabulary test not PASS")

    print(
        f"rows={len(rows)} register_size={size} unlabelled={unlabelled} "
        f"vocab=five+DISAPPEARED double_labelled=0"
    )
    print("SUCCESS:SYN-0029-probe1 exactly-one label and declared-five vocabulary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
