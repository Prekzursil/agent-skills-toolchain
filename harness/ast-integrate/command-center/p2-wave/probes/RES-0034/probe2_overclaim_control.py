#!/usr/bin/env python3
"""Probe 2: overclaim, mutation, schema-garbage, and partitioned reviewer.

Does not treat the artifact's conclusion as evidence. Re-runs capture,
then:
  * a leak missing one vendor output is rejected as overclaim
  * an agreeing pair is not counted as a leak
  * equalizing Codex unknown-key policy makes leak-hooks-unknown-key vanish
  * the declared schema rejects three garbage documents
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/research/RES-0034.json"
SCHEMA = REPO / "command-center/schema/research-claim-record.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
PARTITION_B = frozenset(
    {"leak-instruction-locator", "leak-plugin-discovery-path"}
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0034-probe2 {msg}")
    return 1


def main() -> int:
    pairs = I.capture_all()
    try:
        leaks, controls = I.assert_inventory(pairs)
    except I.OverclaimError as exc:
        return fail(f"live inventory {exc}")
    by_id = {p["id"]: p for p in pairs}

    # Overclaim: drop Codex output from a leak.
    planted = deepcopy(by_id["leak-hooks-unknown-key"])
    planted["codex"] = None
    planted["codex_answer"] = None
    try:
        I.assert_inventory([planted, *controls])
    except I.OverclaimError as exc:
        print(f"overclaim_rejected={exc}")
    else:
        return fail("overclaim (missing Codex output) was accepted")

    # Agreeing pair must not classify as a leak.
    fake_leak = deepcopy(controls[0])
    fake_leak["id"] = "fake-leak-from-control"
    fake_leak["kind"] = "leak"
    fake_leak["divergent"] = False
    try:
        I.assert_inventory([fake_leak, *leaks[:2], *controls])
    except I.OverclaimError as exc:
        print(f"agreeing_not_leak={exc}")
    else:
        return fail("agreeing pair accepted as a leak")

    # Mutation: Codex permissive unknown keys → hooks leak vanishes.
    mutated = I.capture_all(codex_hooks_fail_closed=False)
    mut_hooks = next(p for p in mutated if p["id"] == "leak-hooks-unknown-key")
    print(
        f"mutation_hooks_divergent={mut_hooks['divergent']} "
        f"claude={mut_hooks['claude_answer']} codex={mut_hooks['codex_answer']}"
    )
    if mut_hooks["divergent"]:
        return fail("hooks leak still diverges after equalizing unknown-key policy")
    try:
        I.assert_inventory(mutated)
    except I.OverclaimError as exc:
        print(f"mutation_inventory_dropped_hooks_leak={exc}")
    else:
        return fail("mutated inventory still claims 3 leaks including hooks")

    # Schema discriminates garbage (disk $ref store; no network).
    rejected = 0
    for garbage in GARBAGE:
        if S.errors_of(garbage):
            rejected += 1
    print(f"schema_garbage_rejected={rejected}/3")
    if rejected != 3:
        return fail("schema did not reject all garbage documents")

    # Partitioned reviewer: independently re-check instruction + plugin leaks.
    for pid in PARTITION_B:
        row = by_id[pid]
        print(
            f"partition_b[{pid}] divergent={row['divergent']} "
            f"claude={row['claude_answer']} codex={row['codex_answer']}"
        )
        if not row["divergent"]:
            return fail(f"partition B {pid} did not diverge")
        if row["loud_degradation"]["verdict"] != "DEGRADED":
            return fail(f"partition B {pid} not DEGRADED")

    if not ART.is_file():
        return fail("research artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema_errs = S.errors_of(doc)
    if schema_errs:
        return fail("artifact schema-invalid " + schema_errs[0])
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict not PASS")
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    body = S.payload(doc)
    if len(body.get("captured_divergent_pairs") or []) < 3:
        return fail("artifact missing captured divergent pairs")
    print("SUCCESS:RES-0034-probe2 overclaim mutation schema partitioned-review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
