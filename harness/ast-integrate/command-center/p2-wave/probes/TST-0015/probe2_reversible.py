#!/usr/bin/env python3
"""Probe 2: each operator is reversible to the pinned SHA.

Catalog test: test_operator_is_reversible (tree restores to the pinned SHA).
Must not touch the shared checkout.
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
from treeutil import cleanup, materialize, tree_sha  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0015.json"


def main() -> int:
    refuse = refuse_shared_checkout()
    print(f"refused_baseline={refuse['refused_baseline']}")
    if not refuse["refused_baseline"]:
        print("FAILED:TST-0015-probe2 operator accepted the baseline fixture")
        return 1

    if not ART.is_file():
        print("FAILED:TST-0015-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0015-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0015" not in text:
        print("FAILED:TST-0015-probe2 sentinel absent")
        return 1

    restored = []
    for op in OPERATORS:
        tree = materialize()
        pinned = tree_sha(tree)
        try:
            rec = op.apply(tree)
            mutated = tree_sha(tree)
            if mutated == pinned:
                print(f"FAILED:TST-0015-probe2 {op.operator_id} was a no-op")
                return 1
            rec.restore(tree)
            first = tree_sha(tree)
            rec.restore(tree)
            second = tree_sha(tree)
            ok = first == pinned == second
            print(
                f"{op.operator_id} pinned={pinned[:12]} mutated={mutated[:12]} "
                f"restored={first[:12]} second={second[:12]} ok={ok}"
            )
            if not ok:
                print(f"FAILED:TST-0015-probe2 {op.operator_id} did not restore pinned SHA")
                return 1
            restored.append(op.operator_id)
        finally:
            cleanup(tree)

    payload = {
        "pass": True,
        "probe": "probe2-reversible",
        "restored": restored,
        "count": len(restored),
        "unit_id": "TST-0015",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0015-probe2 each operator restores the pinned SHA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
