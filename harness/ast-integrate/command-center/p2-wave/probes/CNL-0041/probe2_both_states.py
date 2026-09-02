#!/usr/bin/env python3
"""Probe 2: both-states identity-leak check + independent fixture recount.

Mechanism B (this probe): count family=ANONYMOUS records in fixtures/protocols.json
and re-tabulate leak detector results from knobs fixtures. Does not read the
author's design-note argument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"
ARTIFACT = (
    REPO
    / "command-center/design/council/CNL-0041-executable-runtime-semantics-for-the-6-anonymous-protocols.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
EXPECTED_IDS = ["P20", "P21", "P22", "P23", "P24", "P25"]


def _load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    proto_doc = _load("protocols.json")
    members = [
        p
        for p in (proto_doc.get("protocols") or [])
        if isinstance(p, dict) and p.get("family") == "ANONYMOUS"
    ]
    ids = [p["id"] for p in members]
    recount_ok = ids == EXPECTED_IDS and len(members) == 6

    good_knobs = _load("known_good_knobs.json")
    bad_knobs = _load("planted_bad_knobs.json")
    good_rows = []
    bad_p20 = None
    fail = False
    reasons: list[str] = []

    if not recount_ok:
        fail = True
        reasons.append(f"independent protocols.json recount {ids}")

    for proto in members:
        good_run = R.run_protocol(proto, knobs=good_knobs)
        good_det = R.detect_pre_lift_identity_leaks(good_run)
        good_rows.append(
            {
                "id": proto["id"],
                "silent": good_det["silent"],
                "fired": good_det["fired"],
                "leak_count": good_det["leak_count"],
            }
        )
        if not good_det["silent"]:
            fail = True
            reasons.append(f"known-good {proto['id']} not silent: {good_det['leaks'][:2]}")

    p20 = next(p for p in members if p["id"] == "P20")
    bad_run = R.run_protocol(p20, knobs=bad_knobs)
    bad_det = R.detect_pre_lift_identity_leaks(bad_run)
    bad_p20 = {
        "fired": bad_det["fired"],
        "silent": bad_det["silent"],
        "leak_count": bad_det["leak_count"],
        "leaks": bad_det["leaks"],
        "channels": sorted({x.get("channel") for x in bad_det["leaks"]}),
    }
    if not bad_det["fired"]:
        fail = True
        reasons.append("planted-bad P20 did not fire")
    if "writing_style" not in bad_p20["channels"]:
        fail = True
        reasons.append(f"planted-bad channels {bad_p20['channels']} missing writing_style")

    # Negative control: the check on the state it is meant to reject (verbatim).
    negative = {
        "id": "NC-P20-style-forward-before-unseal",
        "rejects": bad_knobs.get("rejects"),
        "observed": (
            f"FIRES fired={bad_det['fired']} silent={bad_det['silent']} "
            f"channels={bad_p20['channels']} leak_count={bad_det['leak_count']} "
            f"first={bad_det['leaks'][0] if bad_det['leaks'] else None}"
        ),
    }

    schema_ok = None
    if ARTIFACT.is_file() and SCHEMA.is_file():
        import jsonschema

        note = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft7Validator(schema).validate(note)
            schema_ok = True
        except jsonschema.ValidationError as exc:
            schema_ok = False
            fail = True
            reasons.append(f"design-note schema: {exc.message}")
        if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            fail = True
            reasons.append(f"design-note self-declared {note.get('state')}")
        if "SUCCESS:CNL-0041" not in ARTIFACT.read_text(encoding="utf-8"):
            fail = True
            reasons.append("sentinel absent in artifact")

        # Garbage must be rejected (vacuity control on the schema).
        garbage = {"totally": "unrelated", "passing_tests": 999999}
        g_errs = list(jsonschema.Draft7Validator(schema).iter_errors(garbage))
        if not g_errs:
            fail = True
            reasons.append("schema accepted garbage (vacuous contract)")

    doc = {
        "independent_recount_ids": ids,
        "independent_recount_n": len(members),
        "independent_recount_ok": recount_ok,
        "known_good": good_rows,
        "known_good_all_silent": all(r["silent"] for r in good_rows),
        "planted_bad_p20": bad_p20,
        "negative_control": negative,
        "artifact_schema_ok": schema_ok,
        "pass": not fail,
        "reasons": reasons,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"recount_n={len(members)} good_silent={doc['known_good_all_silent']} "
        f"bad_fired={bad_p20['fired']} schema_ok={schema_ok}"
    )
    print(f"NEGATIVE_CONTROL {negative['observed']}")
    if fail:
        print("FAILED:CNL-0041-probe2 " + "; ".join(reasons))
        return 1
    print("SUCCESS:CNL-0041-probe2 both-states leak check and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
