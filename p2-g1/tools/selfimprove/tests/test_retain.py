"""Standalone tests for tools/selfimprove/retain.py (TST-0236 receipt test row).

Run: PYTHONPATH=tools python3 -B tools/selfimprove/tests/test_retain.py
No pytest dependency; assert-based with explicit exit code.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS_ROOT))

from selfimprove import retain as retain_mod  # noqa: E402
from selfimprove.retain import IncompleteRevertError, take_snapshot  # noqa: E402

FIXTURE = TOOLS_ROOT / "selfimprove" / "fixtures" / "retain-estate"


def _tree(tmp: Path) -> Path:
    tree = tmp / "subject"
    shutil.copytree(FIXTURE, tree, dirs_exist_ok=True)
    return tree


def test_measured_improvement_band() -> None:
    above = {"delta": 5.0, "noise_band": {"low": -1, "high": 1}, "higher_is_better": True}
    within = {"delta": 0.5, "noise_band": {"low": -1, "high": 1}, "higher_is_better": True}
    assumed = {"delta": 9.9, "noise_band_source": "assumed"}
    below = {"delta": -5.0, "noise_band": {"low": -1, "high": 1}, "higher_is_better": True}
    assert retain_mod.measured_improvement(above) is True
    assert retain_mod.measured_improvement(within) is False
    assert retain_mod.measured_improvement(below) is False
    assert retain_mod.measured_improvement(assumed) is False


def test_retain_three_outcomes() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger = tmp / "ledger.jsonl"
        tree = _tree(tmp)
        win = retain_mod.retain(
            tree=tree,
            candidate_id="t-win",
            files={"score.json": json.dumps({"value": 10})},
            ledger_path=ledger,
        )
        assert win["decision"] == "KEEP", win
        tree = _tree(tmp)
        neutral = retain_mod.retain(
            tree=tree,
            candidate_id="t-neutral",
            files={
                "score.json": json.dumps({"value": 5}),
                "notes.md": "agent rewrite",
            },
            ledger_path=ledger,
            produced_by="agent",
        )
        assert neutral["decision"] == "REVERT" and neutral["reason"] == "neutral", neutral
        tree = _tree(tmp)
        harmful = retain_mod.retain(
            tree=tree,
            candidate_id="t-harmful",
            files={"score.json": json.dumps({"value": 1}), "extra.txt": "stray"},
            ledger_path=ledger,
        )
        assert harmful["decision"] == "REVERT" and harmful["reason"] == "harmful", harmful
        rows = retain_mod.read_ledger(ledger)
        assert [r["decision"] for r in rows] == ["KEEP", "REVERT", "REVERT"], rows


def test_incomplete_revert_detected() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        tree = _tree(tmp)
        before = take_snapshot(tree)
        (tree / "extra.txt").write_text("stray", encoding="utf-8")
        try:
            retain_mod.check_revert(tree, before)
        except IncompleteRevertError:
            return
        raise AssertionError("incomplete revert was not detected")


def test_tree_hash_stable_and_sensitive() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        tree = _tree(tmp)
        h1 = retain_mod.tree_hash(tree)
        h2 = retain_mod.tree_hash(tree)
        assert h1 == h2
        (tree / "unrelated.txt").write_text("changed", encoding="utf-8")
        assert retain_mod.tree_hash(tree) != h1


def main() -> int:
    test_measured_improvement_band()
    test_retain_three_outcomes()
    test_incomplete_revert_detected()
    test_tree_hash_stable_and_sensitive()
    print("SUCCESS:test_retain 4/4 tests passed (band, three-outcomes, incomplete-revert, hash-stable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
