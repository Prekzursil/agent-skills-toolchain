#!/usr/bin/env python3
"""Probe 2: adversarial reviewer — three independent broken states + schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from detectors.adapters import (  # noqa: E402
    APPEND_ONLY_TOPO,
    CLEAN_PY,
    HONEST_TOPO,
    REQUESTS_PY,
    ROTATE_KEY_PY,
    _fired_list,
)
from detectors.two_state import (  # noqa: E402
    VERDICT_DIFFERS,
    VERDICT_SILENT_BOTH,
    harness_self_test,
    run_two_state,
)
from jsonschema import Draft7Validator  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0471.json"
SCHEMA = REPO / "command-center" / "schema" / "mutation-report.schema.json"
SENTINEL = "SENTINEL:IMP-0471:DETECTORS-TWO-STATE-VALIDATED"


def _static_independent(state: str) -> dict:
    import static_audit as sa

    src = CLEAN_PY if state == "good" else REQUESTS_PY
    return _fired_list(sa.audit_snippet(src, rel="reviewer-requests.py"))


def _marketplace_independent(state: str) -> dict:
    from marketplace.audit import scan_source

    src = CLEAN_PY if state == "good" else ROTATE_KEY_PY
    hits = scan_source(src, "reviewer-rotate.py")
    return _fired_list([h.__dict__ for h in hits])


def _kernel_independent(state: str) -> dict:
    from council.kernel import audit_source

    src = HONEST_TOPO if state == "good" else APPEND_ONLY_TOPO
    return _fired_list(audit_source(src, label="reviewer-append"))


def main() -> int:
    self_test = harness_self_test()
    print(json.dumps({"harness_self_test": self_test["pass"]}, sort_keys=True))
    if not self_test["pass"]:
        print("FAILED:IMP-0471-probe2 harness self-test")
        return 1
    if self_test["two_state_valid"]["verdict"] != VERDICT_DIFFERS:
        print("FAILED:IMP-0471-probe2 valid control not DIFFERS")
        return 1
    if self_test["inert_stub"]["verdict"] != VERDICT_SILENT_BOTH:
        print("FAILED:IMP-0471-probe2 inert stub not SILENT-BOTH")
        return 1

    rows = []
    for detector_id, check in (
        ("plugin/static_audit.py:audit_snippet", _static_independent),
        ("marketplace/audit.py:scan_source", _marketplace_independent),
        ("council/kernel.py:audit_source", _kernel_independent),
    ):
        rec = run_two_state(check, detector_id=detector_id)
        rows.append(rec.to_dict())
        print(
            f"reviewer {detector_id} verdict={rec.verdict} "
            f"good_fired={rec.good and rec.good['fired']} "
            f"broken_fired={rec.broken and rec.broken['fired']}"
        )
        if rec.verdict != VERDICT_DIFFERS:
            print("FAILED:IMP-0471-probe2 independent broken state did not DIFFERS", detector_id)
            return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    for garbage in ({}, {"passing_tests": 999999}, {"blob": "x" * 2000}):
        errs = list(validator.iter_errors(garbage))
        if not errs:
            print("FAILED:IMP-0471-probe2 schema accepted garbage")
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0471-probe2 self-declared", st)
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0471-probe2 sentinel-absent")
            return 1
        art_errs = list(validator.iter_errors(doc))
        if art_errs:
            print("FAILED:IMP-0471-probe2 artifact schema", art_errs[0].message)
            return 1
        table = doc.get("table") or []
        if len(table) < 1:
            print("FAILED:IMP-0471-probe2 empty table")
            return 1
        for row in table:
            if row.get("verdict") == "NOT-CHECKED" and row.get("has_known_broken_fixture") is True:
                print("FAILED:IMP-0471-probe2 fixture row marked NOT-CHECKED", row.get("detector_id"))
                return 1

    print(
        json.dumps(
            {
                "probe": "probe2-reviewer-independent-broken",
                "unit_id": "IMP-0471",
                "independent_broken": rows,
                "pass": True,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    print("SUCCESS:IMP-0471-probe2 three independent broken states + schema + inert stub")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
