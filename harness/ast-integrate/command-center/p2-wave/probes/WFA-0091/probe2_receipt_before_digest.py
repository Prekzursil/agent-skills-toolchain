#!/usr/bin/env python3
"""Probe 2: mechanically independent receipt-before-digest + wait ledger.

Does not reuse probe 1's naive/repaired summary assertions as the source of
truth. Instead:

  1. Runtime event order: every exists event is recorded before any
     read_digest event; the planted unit has exists present=false and zero
     read_digest events.
  2. AST order: in repaired_fan_in, the existence_check call appears at an
     earlier line than read_claimed_digest.
  3. Wait ledger: waited_for lists every contract; U-ABSENT is not_received.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fanin as F  # noqa: E402
import fixtures as FX  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0091-repair-schema-typed-fanin.json"
SRC = HERE / "fanin.py"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0091-probe2 {msg}")
    return 1


def repaired_ast_order(src: str) -> tuple[int, int]:
    tree = ast.parse(src)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "repaired_fan_in":
            fn = node
            break
    if fn is None:
        raise RuntimeError("repaired_fan_in missing")
    exists_line = None
    digest_line = None
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        if name == "existence_check" and exists_line is None:
            exists_line = node.lineno
        if name == "read_claimed_digest" and digest_line is None:
            digest_line = node.lineno
    if exists_line is None or digest_line is None:
        raise RuntimeError(f"call-order missing exists={exists_line} digest={digest_line}")
    return exists_line, digest_line


def main() -> int:
    FX.assert_fixture_layout()
    contracts = FX.contracts()
    inbound = FX.inbound()
    ws = FX.workspace()
    repaired = F.repaired_fan_in(contracts, inbound, ws)
    events = repaired["events"]

    exists_idx = [i for i, e in enumerate(events) if e.get("op") == "exists"]
    digest_idx = [i for i, e in enumerate(events) if e.get("op") == "read_digest"]
    print(
        json.dumps(
            {
                "exists_indices": exists_idx,
                "read_digest_indices": digest_idx,
                "waited_for": repaired["waited_for"],
                "not_received": repaired["not_received"],
                "missing_null": repaired["missing_null"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if len(exists_idx) != len(contracts):
        return fail(f"exists-count {len(exists_idx)} != {len(contracts)}")
    if exists_idx and digest_idx and max(exists_idx) >= min(digest_idx):
        return fail("digest-parsed-before-all-existence-checks")

    planted_exists = [
        e for e in events if e.get("op") == "exists" and e.get("unit_id") == "U-PLANTED"
    ]
    planted_digest = [
        e for e in events if e.get("op") == "read_digest" and e.get("unit_id") == "U-PLANTED"
    ]
    if not planted_exists or planted_exists[0].get("present") is not False:
        return fail("planted-exists-not-false")
    if planted_digest:
        return fail("planted-digest-was-read")

    src = SRC.read_text(encoding="utf-8")
    exists_line, digest_line = repaired_ast_order(src)
    print(f"ast repaired_fan_in existence_check:{exists_line} read_claimed_digest:{digest_line}")
    if exists_line >= digest_line:
        return fail("ast-digest-before-exists")

    waited = set(repaired["waited_for"])
    want = {c["unit_id"] for c in contracts}
    if waited != want:
        return fail(f"waited_for mismatch {waited} vs {want}")
    if "U-ABSENT" not in repaired["not_received"]:
        return fail("U-ABSENT-not-in-not_received")
    if "U-NULL" not in repaired["missing_null"]:
        return fail("U-NULL-not-in-missing_null")

    # Load-bearing: naive still reads the planted digest (independent of probe1's
    # accepted-ids check — we only assert the event order inversion).
    naive = F.naive_fan_in(contracts, inbound, ws)
    naive_digest_first = next(
        (e for e in naive["events"] if e.get("op") == "read_digest" and e.get("unit_id") == "U-PLANTED"),
        None,
    )
    if naive_digest_first is None:
        return fail("naive-did-not-read-planted-digest")
    naive_ops = [e.get("op") for e in naive["events"]]
    if "exists" in naive_ops[:1]:
        return fail("naive-started-with-exists")

    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    evb = doc.get("evidence_B_receipt_before_digest") or {}
    if evb.get("all_existence_checks_before_any_digest_parse") is not True:
        return fail("artifact-B-order")
    if evb.get("planted_digest_parsed") is True:
        return fail("artifact-B-planted-parsed")
    ledger = doc.get("wait_ledger") or {}
    if "U-ABSENT" not in (ledger.get("not_received") or []):
        return fail("artifact-ledger-absent")
    if "U-NULL" not in (ledger.get("missing_null") or []):
        return fail("artifact-ledger-null")

    print("SUCCESS:WFA-0091-probe2 receipt-before-digest wait-ledger ast-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
