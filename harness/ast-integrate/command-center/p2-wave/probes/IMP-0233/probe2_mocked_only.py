#!/usr/bin/env python3
"""Probe 2: mocked-only flagship e2e is rejected; real-rail e2e is accepted.

The meta-test independently stats and parses the artifact path. It does not
trust a MagicMock return value. Every recorded flagship is run on the real rail.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from flagship_e2e_contract.contract import (  # noqa: E402
    MIN_BYTES,
    evaluate_e2e,
    independent_artifact_path,
)
from flagship_e2e_contract.rail import run_mocked_only, run_real  # noqa: E402
from flagship_e2e_contract.registry import flagship_ids, load_registry  # noqa: E402

RAW = HERE / "probe2-mocked-only.raw.json"
RAIL_REL = "command-center/lib/flagship_e2e_contract/rail.py"


def _rail_ast_signals(src: str) -> dict:
    tree = ast.parse(src)
    real_writes = False
    mock_class = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "write_text":
            real_writes = True
        if isinstance(node, ast.Name) and node.id == "MagicMock":
            mock_class = True
        if isinstance(node, ast.Attribute) and node.attr == "MagicMock":
            mock_class = True
    return {"real_writes_write_text": real_writes, "mentions_MagicMock": mock_class}


def main() -> int:
    doc = load_registry()
    fids = flagship_ids(doc)
    if len(fids) != 40:
        print(f"FAILED:IMP-0233-probe2 expected 40 flagships, computed {len(fids)}")
        return 1

    rail_src = (REPO / RAIL_REL).read_text(encoding="utf-8")
    ast_sig = _rail_ast_signals(rail_src)
    if not ast_sig["real_writes_write_text"] or not ast_sig["mentions_MagicMock"]:
        print("FAILED:IMP-0233-probe2 rail AST missing write_text or MagicMock")
        return 1

    real_results = []
    with tempfile.TemporaryDirectory(prefix="imp0233-real-") as tmp:
        real_dir = Path(tmp)
        for bid in fids:
            ev = evaluate_e2e(bid, real_dir, run_real)
            real_results.append(ev)
            if not ev["accepted"] or ev["rejected"]:
                print("FAILED:IMP-0233-probe2 real rail rejected", bid, ev)
                return 1
            post = ev["postcondition"]
            if post["bytes"] < MIN_BYTES or not post["parsed"] or not post["exists"]:
                print("FAILED:IMP-0233-probe2 postcondition", bid, post)
                return 1

    planted_id = "planted-mocked-flagship"
    with tempfile.TemporaryDirectory(prefix="imp0233-mock-") as tmp:
        mock_dir = Path(tmp)
        planted = evaluate_e2e(planted_id, mock_dir, run_mocked_only)
        leftover = independent_artifact_path(mock_dir, planted_id)
        file_on_disk = leftover.is_file()

    mocked_rejected = bool(planted["rejected"] and not planted["accepted"] and not file_on_disk)
    mocked_is_mock = bool(planted["declared_is_mock"])
    silent_on_good = all(r["accepted"] for r in real_results)
    fired_on_bad = mocked_rejected

    out = {
        "ast": ast_sig,
        "both_states": True,
        "fired_on_mocked_only": fired_on_bad,
        "flagship_n": len(fids),
        "min_bytes": MIN_BYTES,
        "mocked_declared_is_mock": mocked_is_mock,
        "mocked_file_on_disk": file_on_disk,
        "mocked_reason": planted["postcondition"]["reason"],
        "mocked_rejected": mocked_rejected,
        "pass": bool(
            silent_on_good
            and fired_on_bad
            and mocked_is_mock
            and not file_on_disk
            and len(real_results) == 40
            and ast_sig["real_writes_write_text"]
            and ast_sig["mentions_MagicMock"]
        ),
        "real_accepted": sum(1 for r in real_results if r["accepted"]),
        "silent_on_real_rail": silent_on_good,
    }
    RAW.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"real_accepted={out['real_accepted']}/40 mocked_rejected={mocked_rejected} "
        f"mocked_file_on_disk={file_on_disk} declared_is_mock={mocked_is_mock} "
        f"reason={planted['postcondition']['reason']}"
    )
    if not out["pass"]:
        print("FAILED:IMP-0233-probe2 mocked-only not rejected or real rail not accepted")
        return 1
    print("SUCCESS:IMP-0233-probe2 mocked-only rejected, real-rail artifacts parsed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
