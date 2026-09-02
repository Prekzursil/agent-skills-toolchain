#!/usr/bin/env python3
"""Probe 1: four param-violation fixtures yield four distinct closed ids.

Also: unknown-key is strict-parser (spec:11302); the valid twin loads and
run_unit is unreachable unless load succeeded; a runtime-shaped call cannot
bypass load-time checks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.validate import (  # noqa: E402
    DOCUMENTED_VIOLATION_IDS,
    FAILURE_CLASS_STRICT_PARSER,
    VIOLATION_PARAM_UNKNOWN_KEY,
    load_workflow,
    run_unit,
)

FIX = Path(__file__).resolve().parent / "fixtures"
FIXTURE_FILES = (
    "missing-required.json",
    "type-mismatch.json",
    "out-of-enum.json",
    "unknown-key.json",
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0134-probe1 {msg}")
    return 1


def main() -> int:
    ids: list[str] = []
    rows: list[dict] = []
    for name in FIXTURE_FILES:
        doc = json.loads((FIX / name).read_text(encoding="utf-8"))
        result = load_workflow(doc["workflow"], doc["values"])
        if result.ok or result.loaded is not None:
            return fail(f"{name}: expected load failure, got ok={result.ok}")
        got = [v.id for v in result.violations]
        if not got:
            return fail(f"{name}: no violation ids")
        primary = got[0]
        expected = doc["expected_id"]
        if primary != expected:
            return fail(f"{name}: expected {expected!r} got {got!r}")
        if primary not in DOCUMENTED_VIOLATION_IDS:
            return fail(f"{name}: {primary!r} not in documented closed set")
        if name == "unknown-key.json":
            v0 = result.violations[0]
            if v0.id != VIOLATION_PARAM_UNKNOWN_KEY:
                return fail("unknown-key id mismatch")
            if v0.failure_class != FAILURE_CLASS_STRICT_PARSER:
                return fail(f"unknown-key class {v0.failure_class!r} != strict-parser")
            if "11302" not in v0.detail:
                return fail("unknown-key detail missing spec:11302")
            try:
                run_unit(result)  # type: ignore[arg-type]
            except TypeError:
                pass
            else:
                return fail("run_unit accepted a failed LoadResult")
        ids.append(primary)
        rows.append({"fixture": name, "id": primary, "all": got})

    if len(ids) != 4 or len(set(ids)) != 4:
        return fail(f"need 4 distinct ids, got {ids}")

    valid = json.loads((FIX / "valid-twin.json").read_text(encoding="utf-8"))
    good = load_workflow(valid["workflow"], valid["values"])
    if not good.ok or good.loaded is None:
        return fail(f"valid twin failed: {[v.id for v in good.violations]}")
    if good.loaded.values.get("replicas") != 3:
        return fail(f"coercion failed: {good.loaded.values!r}")
    ran = run_unit(good.loaded)
    if ran.get("ran") is not True:
        return fail("run_unit did not run loaded twin")

    # Load-time, not run-time: a bad mapping never becomes LoadedWorkflow.
    bad = json.loads((FIX / "missing-required.json").read_text(encoding="utf-8"))
    bad_res = load_workflow(bad["workflow"], bad["values"])
    if bad_res.loaded is not None:
        return fail("failed load still produced LoadedWorkflow (run-time leak)")

    payload = {
        "probe": "probe1_four_ids",
        "ids": ids,
        "distinct": sorted(set(ids)),
        "closed": True,
        "strict_parser_unknown_key": True,
        "valid_twin_ok": True,
        "coerced_replicas": 3,
        "rows": rows,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "four_ids="
        + ",".join(ids)
        + " distinct=4 closed=True unknown_key=strict-parser valid_twin=True"
    )
    print("SUCCESS:IMP-0134-probe1 four distinct param-violation ids at load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
