#!/usr/bin/env python3
"""Probe 2: every CONFIRMED premise has then-and-now; control is current.

Re-runs the sweep, checks the live artifact, validates the schema, and
rejects a mutant that drops then-and-now from a CONFIRMED row.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0125-stale-premise-sweep.json"
SCHEMA = REPO / "command-center/schema/confirmation-audit.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0125 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every CONFIRMED premise "
    "has a then-and-now comparison and the unchanged control was classified "
    "as current. Any other terminal state is FAILED:CNF-0125 <classification> "
    "with the diagnostic tail attached."
)


def confirmed_then_and_now(premises: list) -> tuple[bool, int, int]:
    confirmed = [p for p in premises if p.get("original_verdict") == "CONFIRMED"]
    ok = True
    for p in confirmed:
        if not (
            isinstance(p.get("then_state"), str)
            and len(p["then_state"]) >= 8
            and isinstance(p.get("now_state"), str)
            and len(p["now_state"]) >= 8
            and isinstance(p.get("comparison"), str)
            and len(p["comparison"]) >= 8
        ):
            ok = False
            break
    return ok, len(confirmed), len(premises)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0125-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0125-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0125-probe2 self-declared {doc.get('state')}")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0125-probe2 schema errors")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 400}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0125-probe2 schema accepted garbage")
            return 1
    print("schema_ok=True schema_rejects_garbage=True")

    ok, n_conf, n_all = confirmed_then_and_now(doc.get("premises") or [])
    print(f"artifact_confirmed={n_conf} premises={n_all} then_and_now={ok}")
    if n_conf < 1:
        print("FAILED:CNF-0125-probe2 no CONFIRMED premises harvested")
        return 1
    if not ok:
        print("FAILED:CNF-0125-probe2 CONFIRMED row missing then-and-now")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["premises"]:
        if row.get("original_verdict") == "CONFIRMED":
            row.pop("comparison", None)
            row["then_state"] = ""
            stripped = True
            break
    if not stripped:
        print("FAILED:CNF-0125-probe2 no CONFIRMED row to mutate")
        return 1
    m_ok, _, _ = confirmed_then_and_now(mutant["premises"])
    print(f"mutant_then_and_now_ok={m_ok}")
    if m_ok:
        print("FAILED:CNF-0125-probe2 mutant without then-and-now was accepted")
        return 1
    # Shared confirmation-audit schema does not constrain premises[].then_state;
    # the then-and-now checker (not the shared schema) is the mutant detector.

    live = S.run_sweep(REPO)
    live_ok, live_conf, _ = confirmed_then_and_now(live["premises"])
    print(f"live_confirmed={live_conf} live_then_and_now={live_ok}")
    if not live_ok:
        print("FAILED:CNF-0125-probe2 live sweep CONFIRMED missing then-and-now")
        return 1
    # Do not require live harvest count == artifact count: parallel units may
    # add CONFIRMED rows after this unit's first observation (spec 11039
    # discrepancy, not a probe failure). Re-measure every CONFIRMED row that
    # THIS artifact recorded.
    for p in doc.get("premises") or []:
        if p.get("original_verdict") != "CONFIRMED":
            continue
        measured = S.remeasure_confirmed(
            REPO,
            {
                "source": p.get("source"),
                "claim": p.get("claim"),
                "anchor": p.get("anchor") or p.get("source"),
            },
        )
        if not (
            measured.get("then_state")
            and measured.get("now_state")
            and measured.get("comparison")
        ):
            print(f"FAILED:CNF-0125-probe2 remeasure missing then-and-now {p.get('id')}")
            return 1
        if p.get("is_control") is True and measured.get("classification") != "current":
            print(f"FAILED:CNF-0125-probe2 control remeasure not current {p.get('id')}")
            return 1
    print("artifact_confirmed_remeasured=True")

    h = doc.get("headline") or {}
    if h.get("current_control_classified_current") is not True:
        print("FAILED:CNF-0125-probe2 headline control not current")
        return 1
    controls = [
        p
        for p in (doc.get("premises") or [])
        if p.get("is_control") is True
    ]
    print(f"control_rows={len(controls)}")
    if not controls:
        print("FAILED:CNF-0125-probe2 no designated control")
        return 1
    if any(p.get("classification") != "current" for p in controls):
        print("FAILED:CNF-0125-probe2 control not classified current")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNF-0125-probe2 reviewer not independent")
        return 1
    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        print("FAILED:CNF-0125-probe2 fewer than two reviewers")
        return 1
    if any(r.get("saw_peer_verdict") is True for r in reviewers):
        print("FAILED:CNF-0125-probe2 reviewers saw each other's verdict")
        return 1
    ids = {r.get("reviewer_id") for r in reviewers}
    if len(ids) < 2:
        print("FAILED:CNF-0125-probe2 reviewers share an id")
        return 1

    print(
        "SUCCESS:CNF-0125-probe2 then-and-now control-current "
        "schema-garbage mutant"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
