#!/usr/bin/env python3
"""Probe 2: squash-merged AHEAD is not unmerged; independent git re-derive; schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import gate as G  # noqa: E402
import tests as T  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/TST-0101.json"
SCHEMA = REPO / "command-center/schema/test-receipt.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def _independent_squash_read() -> dict:
    """Re-read git without using GateResult.blocked as an input."""
    with F.with_fixture("squash-merged-ahead") as box:
        merge_base = box.git("merge-base", "main", "HEAD").stdout.strip()
        counts = box.git(
            "rev-list", "--left-right", "--count", "main...HEAD"
        ).stdout.strip()
        behind_s, ahead_s = counts.split()
        ahead = int(ahead_s)
        tree_main = box.git("rev-parse", "main^{tree}").stdout.strip()
        tree_head = box.git("rev-parse", "HEAD^{tree}").stdout.strip()
        three = box.git("diff", "--numstat", "main...HEAD").stdout
        two = box.git("diff", "--numstat", "main..HEAD").stdout
        three_lines = [ln for ln in three.splitlines() if ln.strip()]
        two_lines = [ln for ln in two.splitlines() if ln.strip()]
        gate = G.evaluate(box.root, "main", "HEAD")
        return {
            "merge_base": merge_base,
            "ahead": ahead,
            "behind": int(behind_s),
            "trees_identical": tree_main == tree_head,
            "three_dot_rows": len(three_lines),
            "two_dot_rows": len(two_lines),
            "gate_unmerged": gate.unmerged,
            "gate_squash_merged_ahead": gate.squash_merged_ahead,
            "gate_ahead": gate.ahead,
        }


def main() -> int:
    row = T.test_squash_merged_branch_is_not_treated_as_unmerged()
    if row.get("result") != "PASS":
        print("FAILED:TST-0101-probe2 squash catalog test")
        return 1
    indep = _independent_squash_read()
    print(json.dumps({"independent": indep}, sort_keys=True))
    if indep["ahead"] <= 0:
        print("FAILED:TST-0101-probe2 independent read did not see AHEAD")
        return 1
    if not indep["trees_identical"]:
        print("FAILED:TST-0101-probe2 independent trees were not identical")
        return 1
    if indep["two_dot_rows"] != 0:
        print("FAILED:TST-0101-probe2 independent two-dot was not empty")
        return 1
    if indep["gate_unmerged"] or not indep["gate_squash_merged_ahead"]:
        print("FAILED:TST-0101-probe2 gate still treated squash as unmerged")
        return 1
    if indep["gate_ahead"] != indep["ahead"]:
        print("FAILED:TST-0101-probe2 ahead mismatch vs independent read")
        return 1
    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:TST-0101-probe2 artifact or schema missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0101" not in text:
        print("FAILED:TST-0101-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0101-probe2 self-declared:{doc.get('state')}")
        return 1
    squash = ((doc.get("evidence") or {}).get("squash_merged_ahead") or {})
    if not squash.get("squash_merged_ahead") or squash.get("unmerged") is not False:
        print("FAILED:TST-0101-probe2 artifact squash evidence missing")
        return 1
    if int(squash.get("ahead") or 0) <= 0:
        print("FAILED:TST-0101-probe2 artifact did not record AHEAD")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0101-probe2 schema errors")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0101-probe2 schema accepted garbage")
            return 1
    print(
        "schema_ok=True independent_ahead="
        f"{indep['ahead']} trees_identical=True two_dot_empty=True unmerged=False"
    )
    print("SUCCESS:TST-0101-probe2 squash-merged-ahead schema independent-numstat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
