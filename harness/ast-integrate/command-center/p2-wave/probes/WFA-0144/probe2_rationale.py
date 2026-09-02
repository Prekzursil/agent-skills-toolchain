#!/usr/bin/env python3
"""Named probe 2: rationale names every loser; schema; typed failure.

Mechanically different from probe 1: this probe's primary signal is that
the rationale text contains every rejected variant_id and its measured
score, that stripping those lines fails the completeness detector, that
the cosmetic BUILD is not returned, and that the artifact validates
against $defs/forge-pipeline while garbage documents do not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    ART,
    CATALOG_SCHEMA,
    LOCAL_SCHEMA,
    empty_scout_typed_failure,
    looks_right_not_returned,
    rationale_complete,
    resolve_anchor,
    schema_accepts,
    schema_rejects_garbage,
    strip_rejected_rationale,
)
from fixtures import ADOPTION_GOAL, UNCOVERED_GOAL  # noqa: E402
from forge import forge  # noqa: E402

UNIT = "WFA-0144"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    if not CATALOG_SCHEMA.is_file() or CATALOG_SCHEMA.stat().st_size <= 0:
        return fail("catalog output_schema path missing")
    if not LOCAL_SCHEMA.is_file() or LOCAL_SCHEMA.stat().st_size <= 0:
        return fail("local artifact.schema.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0144" not in json.dumps(doc):
        return fail("sentinel absent")

    live_a = forge(ADOPTION_GOAL)
    live_u = forge(UNCOVERED_GOAL)
    if not live_a.get("ok") or not live_u.get("ok"):
        return fail("live forge")

    for label, live in (("adoption", live_a), ("uncovered", live_u)):
        complete = rationale_complete(live)
        if not complete["ok"]:
            return fail(f"rationale incomplete {label}", complete)
        mutant = strip_rejected_rationale(live)
        if rationale_complete(mutant)["ok"]:
            return fail(f"completeness detector silent on stripped rationale {label}")

    cosmetic = looks_right_not_returned(live_a)
    if not cosmetic["ok"]:
        return fail("looks-right BUILD leaked or missing", cosmetic)
    empty = empty_scout_typed_failure()
    if not empty["ok"]:
        return fail("empty scout not typed failure", empty)

    if not schema_rejects_garbage():
        return fail("schema accepts garbage")
    ok, errors = schema_accepts(doc)
    if not ok:
        return fail("artifact schema", errors)

    runs = {r.get("id"): r for r in (doc.get("runs") or []) if isinstance(r, dict)}
    rec_a = runs.get("adoption-goal") or {}
    if rec_a.get("scoreboard_sha256") != live_a.get("scoreboard_sha256"):
        return fail(
            "adoption scoreboard mismatch",
            {
                "live": live_a.get("scoreboard_sha256"),
                "artifact": rec_a.get("scoreboard_sha256"),
            },
        )
    rec_u = runs.get("uncovered-goal") or {}
    if rec_u.get("scoreboard_sha256") != live_u.get("scoreboard_sha256"):
        return fail("uncovered scoreboard mismatch")

    forge_py = HERE / "forge.py"
    line = resolve_anchor(forge_py, 'f"REJECTED {v[\'variant_id\']}')
    if line < 1:
        return fail("rationale-loser anchor missing")
    evidence = doc.get("evidence") or []
    if not any(e.get("kind") == "rationale-names-losers" for e in evidence):
        return fail("artifact evidence missing rationale-names-losers")

    typed = doc.get("typed_failure_control") or {}
    if typed.get("empty_scout_error_type") != "FORGE_INPUT_INVALID":
        return fail("artifact typed_failure_control", typed)
    if not typed.get("looks_right_build_not_returned"):
        return fail("artifact looks_right flag")

    payload = {
        "pass": True,
        "probe": "probe2-rationale",
        "unit_id": UNIT,
        "rejected_named_adoption": len(live_a.get("rejected") or []),
        "rejected_named_uncovered": len(live_u.get("rejected") or []),
        "schema_ok": True,
        "garbage_rejected": True,
        "looks_right_not_returned": True,
        "empty_scout_typed": True,
        "scoreboard_sha256": live_a.get("scoreboard_sha256"),
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"rejected_named={payload['rejected_named_adoption']} "
        f"schema_ok=True looks_right_blocked=True"
    )
    print("SUCCESS:WFA-0144-probe2 rationale completeness and typed failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
