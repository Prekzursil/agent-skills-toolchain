#!/usr/bin/env python3
"""Probe 2: anti-patterns + NOT-CHECKED distinctness + seven-site import identity."""
from __future__ import annotations

import ast
import importlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "platform" / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(HERE))

import completion_predicate as cp  # noqa: E402
from scenario import gold_tree, mutant_tree  # noqa: E402

SITES = [
    "local_runner",
    "cloud_dispatcher",
    "monitor",
    "harvester",
    "workflow_fanin",
    "cross_vendor_adapter",
    "final_synthesis",
]


def _no_exit_zero_shortcut(src: str) -> bool:
    """COMPLETE must never be returned from an exit-code comparison."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        names = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                names.append(child.id)
            if isinstance(child, ast.Attribute):
                names.append(child.attr)
        if "exit_code" in names or "returncode" in names:
            parent_return = False
            # Structural: a compare involving exit_code is allowed only as recording,
            # never as the predicate for COMPLETE. We reject `if exit_code == 0`.
            # The behavioral test below is the load-bearing check; this flags a
            # direct equality against 0 next to exit_code.
            for cmp_op, comparator in zip(node.ops, node.comparators):
                if isinstance(cmp_op, ast.Eq) and isinstance(
                    comparator, ast.Constant
                ) and comparator.value == 0:
                    parent_return = True
            if parent_return:
                return False
    return True


def main() -> int:
    fail = False
    src = (LIB / "completion_predicate.py").read_text(encoding="utf-8")
    if not _no_exit_zero_shortcut(src):
        print("FAILED:CC-0003-probe2 source compares exit_code == 0")
        fail = True
    else:
        print("ast_exit_zero_shortcut=absent")

    # --- exit-zero with missing artifact ---
    with tempfile.TemporaryDirectory(prefix="cc0003-ez-") as tmp:
        root = Path(tmp)
        receipt = mutant_tree(root, 2)
        v = cp.evaluate(
            receipt,
            repo=root,
            schema_path="artifact.schema.json",
            process={"exit_code": 0},
        )
        ez_ok = (
            v.verdict == cp.INCOMPLETE
            and 2 in v.failing_condition_ids
            and v.process_exit_code == 0
        )
        print(
            f"exit_zero_missing_artifact verdict={v.verdict} "
            f"failing={v.failing_condition_ids} exit={v.process_exit_code} ok={ez_ok}"
        )
        if not ez_ok:
            fail = True
            print("FAILED:CC-0003-probe2 exit-zero-with-missing-artifact returned COMPLETE")

    # --- fabricated digest, no file ---
    with tempfile.TemporaryDirectory(prefix="cc0003-dg-") as tmp:
        root = Path(tmp)
        receipt = mutant_tree(root, 2)
        digest = receipt["artifacts"][0]["sha256"]
        hex_ok = len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
        v = cp.evaluate(receipt, repo=root, schema_path="artifact.schema.json")
        dg_ok = v.verdict == cp.INCOMPLETE and 2 in v.failing_condition_ids and hex_ok
        print(
            f"fabricated_digest_no_file hex64={hex_ok} verdict={v.verdict} "
            f"failing={v.failing_condition_ids} ok={dg_ok}"
        )
        if not dg_ok:
            fail = True
            print("FAILED:CC-0003-probe2 fabricated digest with no file was not INCOMPLETE")

    # --- NOT-CHECKED is distinct from PASS and does not fold ---
    with tempfile.TemporaryDirectory(prefix="cc0003-nc-") as tmp:
        root = Path(tmp)
        receipt = gold_tree(root)
        skipped = cp.evaluate(
            receipt,
            repo=root,
            schema_path="artifact.schema.json",
            skip={7},
        )
        row7 = next(c for c in skipped.conditions if c.n == 7)
        nc_distinct = row7.outcome == cp.NOT_CHECKED and row7.outcome != cp.PASS
        # Production: NOT-CHECKED on any condition yields INDETERMINATE, never COMPLETE.
        nc_blocks = (
            skipped.verdict != cp.COMPLETE
            and skipped.verdict in {cp.INCOMPLETE, cp.INDETERMINATE}
            and 7 in skipped.not_checked_ids
        )
        gold = cp.evaluate(receipt, repo=root, schema_path="artifact.schema.json")
        gold_pass = gold.verdict == cp.COMPLETE
        print(
            f"not_checked outcome={row7.outcome} distinct_from_PASS={nc_distinct} "
            f"blocks_complete={nc_blocks} skipped_verdict={skipped.verdict} "
            f"gold_complete={gold_pass}"
        )
        if not (nc_distinct and nc_blocks and gold_pass):
            fail = True
            print("FAILED:CC-0003-probe2 NOT-CHECKED folded into PASS or gold broken")

    # --- seven call sites import the same evaluate object ---
    imported = []
    for name in SITES:
        mod = importlib.import_module(f"fanin.{name}")
        imported.append((name, mod.evaluate, mod.reduce_unit))
    same = all(fn is cp.evaluate for _, fn, _ in imported)
    print("call_sites=" + ",".join(n for n, _, _ in imported))
    print(f"shared_evaluate_identity={same}")
    if not same or len(imported) != 7:
        fail = True
        print("FAILED:CC-0003-probe2 fan-in sites do not share evaluate")
    else:
        with tempfile.TemporaryDirectory(prefix="cc0003-sites-") as tmp:
            root = Path(tmp)
            receipt = mutant_tree(root, 2)
            verdicts = []
            for name, _, reduce_unit in imported:
                v = reduce_unit(
                    receipt, repo=root, schema_path="artifact.schema.json"
                )
                verdicts.append((name, v.verdict, tuple(v.failing_condition_ids)))
            agree = len({row[1:] for row in verdicts}) == 1
            print(f"seven_site_parity agree={agree} sample={verdicts[0][1:]}")
            if not agree:
                fail = True
                print("FAILED:CC-0003-probe2 call sites disagree")
                print(json.dumps(verdicts, indent=2))

    print(
        json.dumps(
            {
                "probe": "probe2-antipatterns",
                "unit_id": "CC-0003",
                "exit_zero_missing_artifact": ez_ok,
                "fabricated_digest_no_file": dg_ok,
                "not_checked_distinct": nc_distinct and nc_blocks,
                "shared_evaluate_identity": same,
                "pass": not fail,
            }
        )
    )
    if fail:
        print("FAILED:CC-0003-probe2 anti-patterns")
        return 1
    print("SUCCESS:CC-0003-probe2 anti-patterns and seven-site import identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
