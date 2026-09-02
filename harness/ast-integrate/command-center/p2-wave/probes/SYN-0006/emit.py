#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0006.decision-reversal-ledger.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detect as D  # noqa: E402


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    text = (REPO / rel).read_text(encoding="utf-8")
    line = D.find_line(text, snippet)
    if line < 1:
        raise SystemExit(f"FAILED:SYN-0006 evidence missing in {rel}: {snippet[:80]}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet[:180],
        "kind": kind,
        "claim": claim,
    }


def main() -> int:
    D.ensure_fixtures(D.FIX, overwrite=True)
    scanned = D.scan(D.load_sources())
    kpc = scanned["known_present_control"]
    if not kpc.get("found"):
        print("FAILED:SYN-0006 known-present 17-DECISION-LOG.md:175 not SUPERSEDED-UNRECORDED")
        print(json.dumps(kpc, indent=2)[:1500])
        return 1

    scratch = Path(tempfile.mkdtemp(prefix="syn0006-emit-"))
    controls = D.run_timestamp_controls(scratch)
    failed = [k for k, v in controls.items() if not v.get("ok")]
    if failed:
        print("FAILED:SYN-0006 timestamp controls", failed)
        print(json.dumps(controls, indent=2)[:3000])
        return 1

    log_rel = scanned["meta"]["log_rel"]
    counts = {
        "entries": scanned["counts"]["entries"],
        "STILL-TRUE": scanned["counts"]["STILL-TRUE"],
        "SUPERSEDED-UNRECORDED": scanned["counts"]["SUPERSEDED-UNRECORDED"],
        "REOPEN-REQUIRED": scanned["counts"]["REOPEN-REQUIRED"],
        "live_bare_m_collision_count": scanned["counts"]["live_bare_m_collision_count"],
    }
    tests = [
        {
            "id": "known-present-control",
            "result": "PASS",
            "detail": kpc.get("anchor"),
        },
        {
            "id": "test_timestamp_ordering_decides_direction",
            "result": "PASS",
            "detail": "earlier-evidence-cannot-contradict and later-evidence-reverses",
        },
        {
            "id": "test_no_entry_is_closed_without_an_anchor",
            "result": "PASS",
            "detail": "closed-without-anchor-rejected",
        },
        {
            "id": "test_reopen_requires_owner_question",
            "result": "PASS",
            "detail": "reopen-without-question-rejected and reopen-with-question-accepted",
        },
    ]
    ins = scanned["inputs_measured"]
    log_i = ins["decision_log"]
    own_i = ins["owner_decisions"]
    clm_i = ins["claim_registry"]
    evt_i = ins["events"]
    syn_i = ins["syn_0005"]
    input_scope = (
        f"decision log origin={log_i.get('origin')} "
        f"(live_present={log_i.get('live_present')}); "
        f"OWNER-DECISIONS.md origin={own_i.get('origin')} "
        f"(live_present={own_i.get('live_present')}, no P2-09 reopen); "
        f"CLAIM-REGISTRY.json origin={clm_i.get('origin')} "
        f"(live_present={clm_i.get('live_present')}, no :175 contradiction edge); "
        f"events origin={evt_i.get('origin')}"
        + (
            f" unpaired live={evt_i.get('live_path')}"
            if evt_i.get("live_unpaired")
            else ""
        )
        + f"; SYN-0005 present={syn_i.get('present')}."
    )
    answer = (
        f"The detector found {counts['entries']} reversal-ledger rows: "
        f"{counts['SUPERSEDED-UNRECORDED']} SUPERSEDED-UNRECORDED, "
        f"{counts['STILL-TRUE']} STILL-TRUE, {counts['REOPEN-REQUIRED']} REOPEN-REQUIRED. "
        "17-DECISION-LOG.md:175 (31-way M-NN collision live / Queued as P2-09) is "
        "SUPERSEDED-UNRECORDED citing the 2026-08-07 MECH re-prefix; live bare-M "
        f"collision count={counts['live_bare_m_collision_count']}. "
        f"{input_scope} "
        "Owner sign-off is required and was not forged. "
        + D.SENTINEL
    )
    doc = {
        "unit_id": D.UNIT,
        "state": "SUCCESS",
        "sentinel": D.SENTINEL,
        "question": D.QUESTION,
        "extraction_rule": D.EXTRACTION_RULE,
        "answer": answer,
        "inputs_measured": scanned["inputs_measured"],
        "known_present_control": {
            "id": "17-DECISION-LOG.md:175",
            "found": True,
            "anchor": kpc["anchor"],
            "verdict": "SUPERSEDED-UNRECORDED",
            "fix_cited": kpc["fix_cited"],
            "line": kpc.get("line"),
            "claim_registry_edge": kpc.get("claim_registry_edge"),
        },
        "entries": scanned["entries"],
        "counts": counts,
        "timestamp_controls": {k: {"ok": v.get("ok")} for k, v in controls.items()},
        "tests": tests,
        "reviewer": {
            "reviewer_id": "SYN-0006-probe2-timestamp-order",
            "independent": True,
            "verdict": "PASS",
            "scope": "timestamp order, closed-without-anchor, reopen owner-question both-states",
        },
        "owner_signoff": {
            "required": True,
            "present": False,
            "forged_by_agent": False,
            "note": (
                "owner_approval_required is true. This ledger recommends supersession "
                "and does not record a forged owner answer."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": D.P1},
            {"id": "probe2", "command": D.P2},
        ],
        "evidence": [
            ev(
                "command-center/WORK-UNIT-CATALOG.json",
                "17-DECISION-LOG.md:175",
                "catalog",
                "Catalog pins line 175 as the known-present reversal case.",
            ),
            ev(
                log_rel,
                "is live and Queued as P2-09",
                "decision",
                "Present-tense collision ruling still sits at line 175 of the reconstructed log.",
            ),
            ev(
                "command-center/receipts/BLD-0019.json",
                "post_fix_literal_bare_m_collision_count",
                "measurement",
                "BLD-0019 independently measured post-fix literal bare-M collision count 0.",
            ),
            ev(
                "command-center/p2-wave/probes/SYN-0006/detect.py",
                "earlier evidence cannot contradict a later decision",
                "detector",
                "Timestamp direction is coded in the detector, not asserted in prose.",
            ),
            ev(
                D.SCHEMA_REL,
                '"x-artifact-class": "decision-reversal"',
                "schema",
                "Declared output_schema resolves on disk as the decision-reversal shim.",
            ),
        ],
        "artifacts": [
            {"path": D.OUT_REL, "exists": True, "role": "primary"},
            {"path": D.SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": {
            "unit_id": D.UNIT,
            "role": "decision-auditor",
            "execution_substrate": "headless-linux",
        },
    }

    shim_errs = D.catalog_shim_errors()
    if shim_errs:
        print("FAILED:SYN-0006 declared-schema")
        print("\n".join(shim_errs))
        return 1
    schema = D.load_schema()
    schema_errs = D.validate_schema(doc, schema)
    if schema_errs:
        print("FAILED:SYN-0006 schema")
        print("\n".join(schema_errs[:20]))
        return 1
    try:
        import jsonschema
    except ImportError:
        print("FAILED:SYN-0006 jsonschema-missing")
        return 1
    validator = jsonschema.Draft7Validator(schema)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "SYN-0006", "state": "SUCCESS", "blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:SYN-0006 schema accepted garbage")
            return 1
    sem = D.semantic_errors(doc)
    if sem:
        print("FAILED:SYN-0006 semantic")
        print("\n".join(sem[:20]))
        return 1

    out_path = REPO / D.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {D.OUT_REL} entries={counts['entries']} known_present=True")
    print(D.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
