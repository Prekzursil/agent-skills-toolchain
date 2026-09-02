#!/usr/bin/env python3
"""Framework tests for the IMP-0047 migration engine."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from plugin.migration import (  # noqa: E402
    MigrationEngine,
    MigrationError,
    Step,
    blake2_tree_digest,
    build_demo_tree,
    censuses,
    censuses_equal,
    demo_engine,
    demo_step_specs,
    sha256_file_census,
    validate_step_spec,
    wrong_inverse_spec,
)


def test_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = build_demo_tree(Path(tmp) / "t")
        before = sha256_file_census(root)
        before_b = blake2_tree_digest(root)
        engine = demo_engine()
        journal = Path(tmp) / "j.json"
        applied = engine.migrate(root, "3", journal=journal)
        assert applied["status"] == "complete"
        assert sha256_file_census(root) != before
        engine.invert(root, "0", journal=journal)
        assert sha256_file_census(root) == before
        assert blake2_tree_digest(root) == before_b


def test_wrong_inverse_diverges() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = build_demo_tree(Path(tmp) / "bad")
        before = censuses(root)
        engine = MigrationEngine([Step(wrong_inverse_spec())])
        engine.migrate(root, "1", journal=Path(tmp) / "bad.json")
        engine.invert(root, "0", journal=Path(tmp) / "bad.json")
        assert not censuses_equal(before, censuses(root))


def test_specs_have_inverse() -> None:
    for spec in demo_step_specs():
        validate_step_spec(spec)
    validate_step_spec(wrong_inverse_spec())


def test_target_cap_skips_s3() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = demo_engine()
        root = build_demo_tree(Path(tmp) / "cap")
        cap = engine.migrate(root, "2", journal=Path(tmp) / "cap.json")
        assert cap["current_version"] == "2"
        assert engine.by_id["s3-dispatch-hooks"].apply_calls == 0
        assert (root / "hooks" / "old.json").is_file()


def main() -> int:
    test_specs_have_inverse()
    test_round_trip()
    test_wrong_inverse_diverges()
    test_target_cap_skips_s3()
    print("SUCCESS:test_migration_framework")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
