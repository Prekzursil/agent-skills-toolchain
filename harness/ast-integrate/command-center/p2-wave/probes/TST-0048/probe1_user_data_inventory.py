#!/usr/bin/env python3
"""Named probe 1: rollback against a tree carrying user data; inventory zero-loss.

Different field from probe 2: set-difference of user-owned paths, not suite vacuity.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import run_prepared  # noqa: E402
from ledger import default_ledger  # noqa: E402
from suite import evaluate_result, inventory_proof  # noqa: E402

ART = REPO / "command-center/receipts/TST-0048.json"
RAW = HERE / "probe1-user-data-inventory.raw.json"
SENTINEL = "SUCCESS:TST-0048"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0048-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "TST-0048":
        print("FAILED:TST-0048-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0048-probe1 sentinel absent")
        return 1
    if doc.get("kind") != "conformance-report":
        print("FAILED:TST-0048-probe1 kind", doc.get("kind"))
        return 1
    answer = doc.get("answer")
    if not isinstance(answer, str) or "by construction" not in answer.lower():
        print("FAILED:TST-0048-probe1 construction claim missing from answer")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0048-probe1 self-declared", doc.get("state"))
        return 1

    ledger = default_ledger()
    with tempfile.TemporaryDirectory(prefix="tst0048-p1-") as tmp:
        result = run_prepared("conforming", Path(tmp) / "tree", ledger)
        ev = evaluate_result(result, ledger)
        proof = inventory_proof(ev)

    if not ev["pass"]:
        print("FAILED:TST-0048-probe1 conforming rollback failed rules", ev["failed"])
        return 1
    if not proof["zero_loss"]:
        print("FAILED:TST-0048-probe1 user-owned loss", proof)
        return 1
    if not proof["before"]:
        print("FAILED:TST-0048-probe1 tree did not carry user data")
        return 1
    recorded = doc.get("inventory") or {}
    if recorded.get("zero_loss") is not True:
        print("FAILED:TST-0048-probe1 receipt inventory.zero_loss is not true")
        return 1
    if set(proof["before"]) != set(recorded.get("before") or []):
        print("FAILED:TST-0048-probe1 inventory path-set drift versus receipt")
        print(json.dumps({"live": proof["before"], "receipt": recorded.get("before")}, indent=2))
        return 1
    if (doc.get("live_rollback") or {}).get("tree_carried_user_data") is not True:
        print("FAILED:TST-0048-probe1 receipt did not record user-data tree")
        return 1
    if (doc.get("construction") or {}).get("inverse_restricted_to_creation_set") is not True:
        print("FAILED:TST-0048-probe1 construction claim missing")
        return 1

    payload = {
        "probe": "probe1-user-data-inventory",
        "unit_id": "TST-0048",
        "pass": True,
        "zero_loss": True,
        "user_owned_before": proof["before"],
        "user_owned_after": proof["after"],
        "deleted": proof["deleted"],
        "changed": proof["changed"],
        "installer_restored": ev["failed"] == [],
    }
    RAW.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "zero_loss=True deleted=0 user_owned="
        + str(len(proof["before"]))
        + " restored_ok=True"
    )
    print("SUCCESS:TST-0048-probe1 user-data inventory zero-loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
