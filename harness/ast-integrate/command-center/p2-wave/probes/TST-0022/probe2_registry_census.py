#!/usr/bin/env python3
"""Probe 2: mechanically different census + AST order check.

Instrument A: JSON field walk of CLAIM-REGISTRY.json (does not call evaluate).
Instrument B: AST of claim_gate.py proving no-source-probe is issued before
same-probe-rerun inside _check_probes (the live function; there is no
evaluate_claim).
Planted both-states control lives in a scratch registry, not the live file.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import fixtures as F  # noqa: E402

RAW = HERE / "probe2-registry-census.raw.json"


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def ast_order(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = _fn(tree, "_check_probes")
    if fn is None:
        return {
            "evaluate_claim": False,
            "check_probes": False,
            "order_ok": False,
            "why": "_check_probes missing",
        }

    source_line = None
    compare_line = None
    get_source_line = None
    probe_key_line = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and node.value == "no-source-probe":
            source_line = node.lineno if source_line is None else min(source_line, node.lineno)
        if isinstance(node, ast.Constant) and node.value == "same-probe-rerun":
            compare_line = node.lineno if compare_line is None else min(compare_line, node.lineno)
        if isinstance(node, ast.Constant) and node.value == "source_probe":
            get_source_line = (
                node.lineno if get_source_line is None else min(get_source_line, node.lineno)
            )
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == "_probe_key" and probe_key_line is None:
                probe_key_line = node.lineno

    key_fn = _fn(tree, "_probe_key")
    key_src = ast.get_source_segment(source, key_fn) if key_fn is not None else ""
    fingerprint_normalises_none = (
        key_fn is not None
        and "isinstance(probe, dict)" in (key_src or "")
        and "else {}" in (key_src or "")
    )
    order_ok = (
        source_line is not None
        and compare_line is not None
        and source_line < compare_line
        and get_source_line is not None
        and get_source_line < compare_line
    )
    return {
        "evaluate_claim": False,
        "check_probes": True,
        "no_source_probe_line": source_line,
        "same_probe_rerun_line": compare_line,
        "source_probe_get_line": get_source_line,
        "probe_key_call_line": probe_key_line,
        "order_ok": order_ok,
        "fingerprint_normalises_none": fingerprint_normalises_none,
    }


def main() -> int:
    live = C.walk_path(REGISTRY)
    order = ast_order(GATE)

    with tempfile.TemporaryDirectory(prefix="tst0022-p2-") as tmp:
        planted_path = Path(tmp) / "planted-registry.json"
        planted_path.write_text(
            json.dumps(F.planted_registry(), indent=2) + "\n", encoding="utf-8"
        )
        planted = C.walk_path(planted_path)

    fired_on_bad = (
        planted.get("confirmed_missing_source_probe") == 1
        and "PLANT-MISSING" in (planted.get("confirmed_missing_ids") or [])
    )
    silent_on_good = "PLANT-COMPLETE" in (planted.get("confirmed_with_source_ids") or [])
    not_checked_excluded = "PLANT-NOT-CHECKED" not in (
        planted.get("confirmed_missing_ids") or []
    ) and "PLANT-NOT-CHECKED" not in (planted.get("confirmed_with_source_ids") or [])

    fail = False
    if not order.get("order_ok"):
        fail = True
    if not order.get("fingerprint_normalises_none"):
        fail = True
    if not fired_on_bad or not silent_on_good or not not_checked_excluded:
        fail = True
    if planted.get("confirmed_total") != 2:
        fail = True
    if not GATE.is_file():
        fail = True

    payload = {
        "probe": "probe2-registry-census",
        "unit_id": "TST-0022",
        "instrument": "json-field-walk+ast-order",
        "live_registry": live,
        "planted": planted,
        "ast_order": order,
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "not_checked_excluded": not_checked_excluded,
        "pass": not fail,
        "gate": str(GATE.relative_to(REPO)).replace("\\", "/"),
        "registry": str(REGISTRY.relative_to(REPO)).replace("\\", "/"),
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "live present={present} confirmed={total} missing_source={miss} "
        "missing_gate_shaped={shaped} empty_set={empty}".format(
            present=live.get("present"),
            total=live.get("confirmed_total"),
            miss=live.get("confirmed_missing_source_probe"),
            shaped=live.get("confirmed_missing_gate_shaped"),
            empty=live.get("empty_set_not_a_pass"),
        )
    )
    print(
        f"planted missing={planted.get('confirmed_missing_ids')} "
        f"complete={planted.get('confirmed_with_source_ids')} "
        f"ast_order_ok={order.get('order_ok')}"
    )
    if fail:
        print("FAILED:TST-0022-probe2 registry census")
        return 1
    print("SUCCESS:TST-0022-probe2 field-walk census and AST order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
