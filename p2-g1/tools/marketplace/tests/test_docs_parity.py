#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(TOOLS))
from marketplace.docs_parity import Ident, compute_parity, drop_documented_entry  # noqa: E402

GOOD = Path(__file__).resolve().parents[1] / "fixtures" / "docs-parity-good"


def test_both_direction_sets_are_empty() -> None:
    report = compute_parity(GOOD)
    assert report.both_empty, report.as_dict()


def test_removed_doc_entry_is_named_exactly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "pkg"
        shutil.copytree(GOOD, clone)
        drop_documented_entry(clone, "status", "command")
        mutated = compute_parity(clone)
        assert mutated.named_commands() == ["status"]
        assert mutated.declared_minus_documented == {Ident("command", "status")}
        assert not mutated.documented_minus_declared
