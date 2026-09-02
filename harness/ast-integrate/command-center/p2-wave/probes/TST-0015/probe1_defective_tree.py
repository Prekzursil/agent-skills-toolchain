#!/usr/bin/env python3
"""Probe 1: each operator produces a valid but defective isolated tree.

Catalog test: test_each_operator_produces_a_valid_but_defective_tree.
The tree must differ from the pinned SHA in exactly the intended way.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from operators import OPERATORS  # noqa: E402
from suite import refuse_shared_checkout  # noqa: E402
from treeutil import (  # noqa: E402
    BASELINE,
    cleanup,
    file_digest,
    materialize,
    relpaths,
    tree_sha,
)

ART = REPO / "command-center" / "receipts" / "TST-0015.json"


def _receipt_ok() -> tuple[bool, str]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return False, "receipt-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"unparseable:{exc}"
    if not isinstance(doc, dict):
        return False, "not-object"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    if "SUCCESS:TST-0015" not in text:
        return False, "sentinel-absent"
    ops = doc.get("operators") or []
    ids = [o.get("operator_id") for o in ops if isinstance(o, dict)]
    want = [op.operator_id for op in OPERATORS]
    if ids != want:
        return False, f"operator-ids {ids} != {want}"
    for row in ops:
        if not row.get("unified_diffs"):
            return False, f"{row.get('operator_id')} missing diff"
        if not row.get("intended_change_holds"):
            return False, f"{row.get('operator_id')} intended_change_holds false"
    return True, "ok"


def main() -> int:
    refuse = refuse_shared_checkout()
    print(f"refused_baseline={refuse['refused_baseline']} msg={refuse['message']}")
    if not refuse["refused_baseline"]:
        print("FAILED:TST-0015-probe1 operator accepted the baseline fixture")
        return 1

    results = []
    for op in OPERATORS:
        tree = materialize()
        pinned = tree_sha(tree)
        before = {rel: file_digest(tree / rel) for rel in relpaths(tree)}
        try:
            rec = op.apply(tree)
            after_sha = tree_sha(tree)
            intended = op.intended(tree, rec)
            valid = op.valid_tree(tree, rec)
            after = {rel: file_digest(tree / rel) for rel in relpaths(tree)}
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            extra = [c for c in changed if c not in rec.targets]
            ok = (
                after_sha != pinned
                and intended
                and valid
                and extra == []
                and changed == sorted(rec.targets)
            )
            row = {
                "operator_id": op.operator_id,
                "pinned_before": pinned,
                "changed": changed,
                "intended": intended,
                "valid_tree": valid,
                "extra": extra,
                "ok": ok,
            }
            results.append(row)
            print(
                f"{op.operator_id} ok={ok} intended={intended} valid={valid} "
                f"changed={changed} extra={extra}"
            )
            if not ok:
                print(f"FAILED:TST-0015-probe1 {op.operator_id}")
                return 1
        finally:
            cleanup(tree)

    rok, rwhy = _receipt_ok()
    print(f"receipt_ok={rok} {rwhy}")
    if not rok:
        print(f"FAILED:TST-0015-probe1 receipt {rwhy}")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-defective-tree",
        "operators": len(results),
        "refused_baseline": True,
        "baseline": str(BASELINE.relative_to(REPO).as_posix()),
        "unit_id": "TST-0015",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0015-probe1 each operator produces a valid but defective tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
