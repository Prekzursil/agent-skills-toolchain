#!/usr/bin/env python3
"""Probe 2: both-states silent pass + import/call-order + reviewer attack.

A valid result with a real, non-empty, parsable file must pass. The pipeline
AST (not a comment) must call evaluate_result before read_digest. A reviewer
who submits a plausible digest with no file behind it must be refused.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

from _boot import PKG_PARENT, REPO, import_pkg

di = import_pkg()

PIPELINE = PKG_PARENT / "dispatch_integrity" / "pipeline.py"


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0159-probe2 {msg}")
    return 1


def _call_name(node: ast.AST) -> str | None:
    func = getattr(node, "func", None)
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def assert_call_order(source: str) -> dict:
    tree = ast.parse(source)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "fan_in":
            fn = node
            break
    if fn is None:
        raise AssertionError("fan_in not found")

    calls: list[tuple[int, str]] = []

    class Walk(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name:
                calls.append((node.lineno, name))
            self.generic_visit(node)

    Walk().visit(fn)
    names = [n for _, n in calls]
    if "evaluate_result" not in names:
        raise AssertionError(f"evaluate_result not called in fan_in: {names}")
    if "read_digest" not in names:
        raise AssertionError(f"read_digest not called in fan_in: {names}")
    i_gate = names.index("evaluate_result")
    i_read = names.index("read_digest")
    if i_gate >= i_read:
        raise AssertionError(
            f"call order wrong: evaluate_result@{i_gate} read_digest@{i_read} names={names}"
        )

    # Early-return If must precede read_digest in source line order.
    ifs = [n for n in fn.body if isinstance(n, ast.If)]
    if not ifs:
        raise AssertionError("fan_in has no If; cannot prove early reject")
    first_if = ifs[0]
    read_lineno = calls[i_read][0]
    if first_if.lineno >= read_lineno:
        raise AssertionError("reject If is not before read_digest")
    # read_digest must not live inside the reject branch
    reject_calls: list[str] = []

    class RejectWalk(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name:
                reject_calls.append(name)
            self.generic_visit(node)

    for stmt in first_if.body:
        RejectWalk().visit(stmt)
    if "read_digest" in reject_calls:
        raise AssertionError("read_digest called on the reject branch")
    return {
        "evaluate_result_index": i_gate,
        "read_digest_index": i_read,
        "reject_if_lineno": first_if.lineno,
        "read_digest_lineno": read_lineno,
        "calls": names,
    }


def main() -> int:
    # --- AST / call-order (not a comment) ---
    src = PIPELINE.read_text(encoding="utf-8")
    try:
        order = assert_call_order(src)
    except AssertionError as exc:
        return _fail(str(exc))
    print(
        "call_order evaluate_result_before_read_digest=True "
        f"if_lineno={order['reject_if_lineno']} "
        f"read_lineno={order['read_digest_lineno']}"
    )

    # --- both-states: valid file passes silently ---
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        payload = {
            "unit_id": "CNF-0000",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:CNF-0000",
            "verdict": "CONFIRMED",
        }
        (root / "ok.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        di.reset_parse_events()
        out = di.fan_in(
            root,
            {
                "result_id": "valid-both-states",
                "result_text": "confirmation complete",
                "contracted_output_path": "ok.json",
            },
        )
        if not out["accepted"]:
            return _fail(f"valid result rejected: {out['gate']}")
        if out["digest"] != payload:
            return _fail("digest mismatch against on-disk file")
        if di.parse_events() != ["ok.json"]:
            return _fail(f"unexpected parse events {di.parse_events()}")
        checks = out["gate"]["checks"]
        if not all(c["passed"] and not c["skipped"] for c in checks):
            return _fail(f"valid checks not all pass: {checks}")
        print("both_states valid_pass_silent=True checks_all_pass=True")

        # reviewer: plausible digest, no file
        di.reset_parse_events()
        reviewer = {
            "result_id": "reviewer-plausible-digest-no-file",
            "result_text": json.dumps(
                {
                    "unit_id": "CNF-0159",
                    "state": "SUCCESS",
                    "sentinel": "SUCCESS:CNF-0159",
                    "verdict": "CONFIRMED",
                    "sha256": "0" * 64,
                    "bytes": 4096,
                }
            ),
            "contracted_output_path": "command-center/receipts/CNF-0159-reviewer-phantom.json",
            "unit_id": "CNF-0159",
        }
        # Reviewer runs against the real repo so the phantom path is actually missing.
        attack = di.fan_in(REPO, reviewer)
        if attack["accepted"]:
            return _fail("reviewer smuggled a plausible digest with no file")
        if di.parse_events():
            return _fail("reviewer attack reached digest reader")
        if attack["gate"]["rejected_by"] != "test_path":
            return _fail(f"reviewer rejected_by={attack['gate']['rejected_by']}")
        print(
            "reviewer_plausible_digest_no_file refused=True "
            f"rejected_by={attack['gate']['rejected_by']}"
        )

    print("SUCCESS:CNF-0159-probe2 both-states call-order reviewer-refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
