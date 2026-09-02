#!/usr/bin/env python3
"""Probe 1: 5000-tree monotone property + both evidence signals + schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import scenario as S  # noqa: E402

if str(C.SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(C.SPEC_ROOT))

from agentspec.permission_bound import (  # noqa: E402
    N_TREES,
    SEED,
    run_property_corpus,
)

import jsonschema  # noqa: E402

ART = C.REPO / C.OUT_REL
SCHEMA = C.REPO / C.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = run_property_corpus(n_trees=N_TREES, seed=SEED)
    if not live["pass"]:
        return fail(
            f"property red violations={live['violations']} "
            f"mismatches={live['call_mismatches']}"
        )
    if live["n_trees"] < 5000:
        return fail(f"n_trees={live['n_trees']}")
    if live["widening_attempts"] < 1:
        return fail("no widening declarations in corpus")
    if live["widening_calls_denied"] < 1:
        return fail("no denied privileged calls")
    if live["widening_calls_allowed"] != 0:
        return fail("widening call was allowed")

    fixture = S.run_executor_fixture()
    if not fixture["denied_write"] or fixture["leaked_secret"]:
        return fail(f"executor write not contained: {fixture}")
    if not fixture["allowed_read"]:
        return fail("executor Read twin did not write")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("completion_sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != C.UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    garbage = [{}, {"totally": "unrelated"}, {"unit_id": "NOPE", "state": "SUCCESS"}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage rejected={rejected}/3")
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        return fail(f"schema {errs[0].message} path={list(errs[0].path)}")

    pt = doc.get("property_test") or {}
    if int(pt.get("n_trees") or 0) < 5000 or pt.get("pass") is not True:
        return fail(f"artifact property_test {pt}")
    if pt.get("violations") != 0:
        return fail(f"artifact reports violations {pt.get('violations')}")
    depths = doc.get("nesting_depths") or []
    if len(depths) < 2:
        return fail("missing nesting-depth evidence")
    for row in depths:
        if row.get("monotone") is not True:
            return fail(f"non-monotone depth row {row}")
    call = doc.get("privileged_call") or {}
    if call.get("allowed") is not False or call.get("spawn_count") != 0:
        return fail(f"privileged_call not denied: {call}")
    ex = doc.get("executor_fixture") or {}
    if ex.get("denied_write") is not True or ex.get("leaked_secret") is not False:
        return fail(f"executor_fixture {ex}")
    if ex.get("allowed_read") is not True:
        return fail("executor allowed_read missing")

    payload = {
        "probe": "probe1-property-trees",
        "unit_id": C.UNIT,
        "n_trees": live["n_trees"],
        "violations": live["violations"],
        "widening_attempts": live["widening_attempts"],
        "widening_calls_denied": live["widening_calls_denied"],
        "executor_denied_write": fixture["denied_write"],
        "executor_leaked": fixture["leaked_secret"],
        "schema_garbage_rejected": rejected,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n_trees={live['n_trees']} violations={live['violations']} "
        f"widening_attempts={live['widening_attempts']} "
        f"denied_calls={live['widening_calls_denied']} "
        f"executor_deny={fixture['denied_write']} leaked={fixture['leaked_secret']}"
    )
    print(
        "SUCCESS:TST-0223-probe1 5000-tree monotone narrowing; "
        "deepest privileged Write denied with zero spawns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
