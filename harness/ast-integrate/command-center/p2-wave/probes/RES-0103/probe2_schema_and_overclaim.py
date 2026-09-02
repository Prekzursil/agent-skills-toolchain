#!/usr/bin/env python3
"""Probe 2: schema discriminates; E3 without baseline cannot promote."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Repo-root `platform/` shadows stdlib pieces that jsonschema imports.
sys.path = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))
import grader as G  # noqa: E402
import reviewer as R  # noqa: E402
from schema_bind import load_discriminator  # noqa: E402

ART = REPO / "command-center/research/RES-0103.json"
SCHEMA = REPO / "command-center/schema/research-claim-record.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0103-probe2 {msg}")
    return 1


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        return fail("jsonschema not installed")

    if not ART.is_file():
        return fail("artifact missing")
    if not SCHEMA.is_file():
        return fail("schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    try:
        schema, which = load_discriminator()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return fail(f"discriminator: {exc}")
    print(f"discriminator={which} catalog_ref={SCHEMA.is_file()}")

    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
        except Exception as exc:
            name = type(exc).__name__
            if "Ref" in name or "Unresolvable" in name:
                return fail(
                    "schema $ref unresolvable; bound.schema.json missing or unused"
                )
            raise
    print(f"schema_garbage_rejected={garbage_rejected}/3")
    if garbage_rejected != 3:
        return fail("schema accepts garbage")
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        return fail(f"artifact fails schema: {exc.message}")
    print("schema_accepts_artifact=True")

    mutant = copy.deepcopy(doc)
    mutant["threshold_recommendation"]["tau"] = "high"
    adj = False
    try:
        jsonschema.validate(mutant, schema)
    except jsonschema.ValidationError:
        adj = True
    print(f"adjective_tau_rejected={adj}")
    if not adj:
        return fail("schema accepted adjective tau")

    stripped = copy.deepcopy(doc)
    stripped.pop("source_lineage", None)
    lineage_fail = False
    try:
        jsonschema.validate(stripped, schema)
    except jsonschema.ValidationError:
        lineage_fail = True
    print(f"missing_source_lineage_rejected={lineage_fail}")
    if not lineage_fail:
        return fail("schema accepted missing source_lineage")

    planted = {
        "id": "M-PLANTED-E3",
        "name": "known-present headline without baseline",
        "paper_id": "doi:10.0/planted",
        "locator": "Table 99",
        "effect_size": "99% better",
        "baseline": None,
        "evidence_tier": "E1",
        "promoted": True,
    }
    planted_tier = G.grade_mechanism(planted)
    print(f"detector_control_planted_e3_tier={planted_tier}")
    if planted_tier != "E3":
        return fail("detector-control: planted no-baseline headline not graded E3")
    if G.can_promote(planted):
        return fail("detector-control: planted E3 was promotable")

    e3_promoted = []
    for m in doc.get("mechanisms") or []:
        tier = G.grade_mechanism(m)
        if tier == "E3" and (
            m.get("promoted") is True
            or m.get("id") in (doc.get("promoted_mechanism_ids") or [])
        ):
            e3_promoted.append(m.get("id"))
    print(f"e3_promoted={e3_promoted}")
    if e3_promoted:
        return fail(f"E3 promoted: {e3_promoted}")

    if not any(
        m.get("id") == "M-HEADLINE-NO-BASELINE" and G.grade_mechanism(m) == "E3"
        for m in doc.get("mechanisms") or []
    ):
        return fail("negative-control headline-without-baseline row missing")

    transfer = str(doc.get("transfer_verdict") or "").upper()
    print(f"transfer_verdict={transfer}")
    if transfer in {"CONFIRMED", "TRANSFERS", "YES"}:
        return fail("overclaim: judge-abstention transfer marked confirmed")

    dep = (doc.get("dependencies_measured") or {}).get("RES-0100", "")
    print(f"RES-0100_note={dep!r}")
    if "absent" not in str(dep).lower() and (
        REPO / "command-center/research/RES-0100.json"
    ).is_file():
        pass
    elif "absent" not in str(dep).lower():
        return fail("overclaim: RES-0100 treated as present")

    rev = R.review(doc)
    print(f"reviewer_verdict={rev['verdict']} independent={rev['independent']}")
    if rev["verdict"] != "PASS":
        return fail(f"reviewer {rev}")
    if not rev.get("rerun"):
        return fail("reviewer did not rerun")

    print("SUCCESS:RES-0103-probe2 schema overclaim E3-gate reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
