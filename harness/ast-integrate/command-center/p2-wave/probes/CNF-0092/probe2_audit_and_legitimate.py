#!/usr/bin/env python3
"""Probe 2: mechanically different from probe 1.

1. Live post-brief unanimity must stay silent (legitimate vs instant).
2. Instant remediation must appear in the transcript, not only as a boolean.
3. Artifact must parse against council-audit.schema.json; garbage must not.
4. Evidence anchors must resolve.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import runtime as R  # noqa: E402
import unanimity as U  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0092-instant-unanimity-trigger.json"
SCHEMA = REPO / "command-center/schema/council-audit.schema.json"


def fail(why: str) -> int:
    print(f"FAILED:CNF-0092-probe2 {why}")
    return 1


def main() -> int:
    live = R.run_all()
    print(
        json.dumps(
            {
                "legitimate_silent": live["legitimate_silent"],
                "blind": live["blind_re_evaluation_in_transcript"],
                "independent": live["independent_position_recorded"],
                "threshold": dict(U.THRESHOLD),
            },
            sort_keys=True,
        )
    )
    if not live["legitimate_silent"]:
        return fail("trigger-overfires: post-brief unanimity fired")
    if not live["blind_re_evaluation_in_transcript"]:
        return fail("audit-gap: no blind_re_evaluation round in transcript")
    if not live["independent_position_recorded"]:
        return fail("remediation cosmetic: no independent position recorded")
    kinds = [t.get("kind") for t in live["instant"]["transcript"]]
    if "blind_re_evaluation" not in kinds:
        return fail("transcript missing blind_re_evaluation kind")
    rem_events = {e.get("event") for e in live["instant"]["audit_events"]}
    needed = {
        U.EVENT_CRITIC,
        U.EVENT_COUNTEREXAMPLE,
        U.EVENT_FORCED_DISSENT,
        U.EVENT_BLIND_REEVAL,
    }
    missing = sorted(needed - rem_events)
    if missing:
        return fail(f"remediation events missing {missing}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"$schema": "http://json-schema.org/draft-07/schema#", "blob": "x" * 2000},
        {"unit_id": "CNF-0092", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0092"},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            pass
        else:
            return fail("schema accepts garbage")

    by = {r["fixture_id"]: r for r in (doc.get("runs") or []) if isinstance(r, dict)}
    legit = by.get("legitimate-post-brief-unanimity") or {}
    inst = by.get("instant-unanimity-clones") or {}
    if legit.get("trigger_fired") is not False:
        return fail("artifact post-brief run not silent")
    t_kinds = [t.get("kind") for t in (inst.get("transcript") or [])]
    if "blind_re_evaluation" not in t_kinds:
        return fail("artifact transcript missing blind re-evaluation")
    if inst.get("independent_position_recorded") is not True:
        return fail("artifact missing independent position")

    n_ok = 0
    for i, row in enumerate(doc.get("evidence") or []):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok, why = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            return fail(f"unresolved evidence {why}")
        n_ok += 1
    if n_ok < 3:
        return fail(f"evidence too thin n={n_ok}")

    print("SUCCESS:CNF-0092-probe2 post-brief-silent audit-log schema anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
