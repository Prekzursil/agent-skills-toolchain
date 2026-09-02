#!/usr/bin/env python3
"""Probe 2: adversarial refuter — construct a false COMPLETE.

Attempts:
  1. exit code 0 alone
  2. exit 0 + self-attested exists/digest/schema_valid with no files on disk
  3. AST: fold_verdict never names or reads exit_code
  4. AST: no branch in reduce_completion assigns COMPLETE from exit_code == 0
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    exit_zero_alone,
    exit_zero_self_attested,
    materialize,
)
from lib.completion_reducer import (  # noqa: E402
    fold_verdict,
    reduce_completion,
)

ART = REPO / "command-center/receipts/IMP-0415.json"
LIB = REPO / "lib/completion_reducer.py"
SENTINEL = "SENTINEL:IMP-0415:REDUCER-TWELVE-CONDITIONS"


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _names_loaded(fn: ast.FunctionDef) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            out.add(node.id)
        if isinstance(node, ast.arg):
            out.add(node.arg)
    return out


def _complete_from_exit_zero(fn: ast.FunctionDef) -> bool:
    """True if some If comparing exit_code to 0 can yield COMPLETE."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test_src = ast.dump(node.test)
        if "exit_code" not in test_src:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and child.value == "COMPLETE":
                return True
    return False


def main() -> int:
    src = LIB.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fold_fn = _fn(tree, "fold_verdict")
    reduce_fn = _fn(tree, "reduce_completion")
    if fold_fn is None or reduce_fn is None:
        print("FAILED:IMP-0415-probe2 missing fold_verdict or reduce_completion")
        return 1
    fold_names = _names_loaded(fold_fn)
    if "exit_code" in fold_names:
        print(f"FAILED:IMP-0415-probe2 fold_verdict loads exit_code names={sorted(fold_names)}")
        return 1
    if any("exit" in a.arg for a in fold_fn.args.args + fold_fn.args.kwonlyargs):
        print("FAILED:IMP-0415-probe2 fold_verdict takes an exit parameter")
        return 1
    if _complete_from_exit_zero(reduce_fn):
        print("FAILED:IMP-0415-probe2 reduce_completion assigns COMPLETE under an exit_code If")
        return 1

    empty = Path(tempfile.mkdtemp(prefix="imp0415-probe2-empty-"))
    a1 = reduce_completion(exit_zero_alone(), root=empty)
    a2 = reduce_completion(exit_zero_self_attested(), root=empty)
    attacks = [
        {"id": "exit-zero-alone", "verdict": a1.get("verdict"), "ok": a1.get("verdict") != "COMPLETE"},
        {
            "id": "exit-zero-self-attested-missing-files",
            "verdict": a2.get("verdict"),
            "ok": a2.get("verdict") != "COMPLETE",
            "failing": [
                r.get("id")
                for r in (a2.get("conditions") or [])
                if r.get("result") == "FAIL"
            ],
        },
    ]
    if any(not x["ok"] for x in attacks):
        print(json.dumps({"pass": False, "attacks": attacks, "a2": a2}, default=str)[:8000])
        print("FAILED:IMP-0415-probe2 constructed a false COMPLETE")
        return 1

    # Both-states: the same API still returns COMPLETE on the honest positive tree.
    pos_root = Path(tempfile.mkdtemp(prefix="imp0415-probe2-pos-"))
    pos = reduce_completion(materialize(pos_root, violate=None), root=pos_root)
    if pos.get("verdict") != "COMPLETE":
        print("FAILED:IMP-0415-probe2 positive control collapsed (reject-everything)")
        return 1

    # fold_verdict itself refuses a truncated table even if every present row is PASS.
    truncated = [{"id": "C1", "result": "PASS"}]
    if fold_verdict(truncated) == "COMPLETE":
        print("FAILED:IMP-0415-probe2 truncated PASS table folded to COMPLETE")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0415-probe2 self-declared {doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0415-probe2 sentinel-absent in receipt")
            return 1

    payload = {
        "pass": True,
        "probe": "probe2-false-complete",
        "attacks": attacks,
        "positive_verdict": pos.get("verdict"),
        "fold_verdict_names_exit_code": False,
        "complete_assigned_under_exit_if": False,
        "truncated_table_verdict": fold_verdict(truncated),
        "canonical_module": a1.get("canonical_module"),
    }
    print(json.dumps(payload, sort_keys=True))
    print("false-COMPLETE constructions rejected; fold_verdict ignores exit_code")
    print("SUCCESS:IMP-0415-probe2 false-complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
