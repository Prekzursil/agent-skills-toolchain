"""IMP-0024: ``update`` never silently overwrites a user-modified deployed file.

Runnable directly (``python3 -B tools/plugin/tests/test_update_preserves_overrides.py``)
and under pytest. Covers the three classifications (unchanged / user-changed /
conflicted), the negative control (classifier off -> the unique-line census goes
red) and the v1->v2->v3 chain preserving the same edit.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import unique_line_differ as differ  # noqa: E402
import update as upd  # noqa: E402


def _tree(td: str, name: str) -> Path:
    root = Path(td) / name
    upd.seed_live_tree(root, upd.payload_v1(), version="1.0.0")
    return root


def test_unchanged_by_user_is_replaced() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0024-t-") as td:
        root = _tree(td, "unchanged")
        res = upd.update(root, upd.payload_v1(), upd.payload_v2(), "1.0.0", "1.1.0")
        assert res.proceeded and res.wrote
        assert {p.classification for p in res.files} == {upd.UNCHANGED_BY_USER}
        assert (root / "notes.md").read_bytes() == upd.payload_v2()["notes.md"]
        assert (root / "VERSION").read_text() == "1.1.0\n"


def test_user_changed_is_three_way_merged() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0024-t-") as td:
        root = _tree(td, "edited")
        ours = upd.apply_user_override(root)
        res = upd.update(root, upd.payload_v1(), upd.payload_v2(), "1.0.0", "1.1.0")
        assert res.proceeded and res.wrote and res.reason == upd.REASON_MERGED
        assert {p.classification for p in res.files} == {upd.MERGED}
        after = (root / "notes.md").read_bytes()
        differ.assert_unique_lines_survive(upd.payload_v1()["notes.md"], ours["notes.md"], after)
        assert b"shipped-v2" in after
        settings = upd.parsed_settings(root)
        assert settings["accent"] == upd.USER_ACCENT_VALUE
        assert settings["telemetry"] is False


def test_conflicted_stops_and_writes_nothing() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0024-t-") as td:
        root = _tree(td, "conflict")
        upd.apply_user_theme_conflict(root)
        before = upd.tree_sha(root)
        res = upd.update(root, upd.payload_v1(), upd.payload_conflict_theirs(), "1.0.0", "1.1.0")
        assert not res.proceeded and not res.wrote and res.reason == upd.REASON_CONFLICT
        assert res.conflicted == ["settings.json"]
        plan = next(p for p in res.files if p.relpath == "settings.json")
        assert plan.classification == upd.CONFLICTED and plan.conflicts == ["theme"]
        assert upd.tree_sha(root) == before
        assert (root / "VERSION").read_text() == "1.0.0\n"


def test_line_conflict_when_both_sides_rewrite_the_same_line() -> None:
    base = b"# plugin notes\nshipped-v1\n"
    ours = b"# plugin notes\nshipped-v1 (annotated by user)\n"
    theirs = b"# plugin notes\nshipped-v1 (deprecated)\n"
    merged, conflicts = upd.three_way_lines(base, ours, theirs)
    assert conflicts and merged == b""
    plan, data = upd.classify("notes.md", base, ours, theirs)
    assert plan.classification == upd.CONFLICTED and data == b""


def test_negative_control_classifier_off_goes_red() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0024-t-") as td:
        root = _tree(td, "no-classifier")
        ours = upd.apply_user_override(root)
        res = upd.update(
            root, upd.payload_v1(), upd.payload_v2(), "1.0.0", "1.1.0", classifier_enabled=False
        )
        assert res.proceeded and res.reason == upd.REASON_NO_CLASSIFIER
        row = differ.census(upd.payload_v1()["notes.md"], ours["notes.md"], (root / "notes.md").read_bytes())
        assert row["all_unique_present"] is False and row["missing_count"] == 1
        assert row["unique_sha256"] != row["present_sha256"]


def test_chain_v1_v2_v3_preserves_the_same_edit() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0024-t-") as td:
        root = _tree(td, "chain")
        ours = upd.apply_user_override(root)
        assert upd.update(root, upd.payload_v1(), upd.payload_v2(), "1.0.0", "1.1.0").proceeded
        assert upd.update(root, upd.payload_v2(), upd.payload_v3(), "1.1.0", "1.2.0").proceeded
        after = (root / "notes.md").read_bytes()
        row = differ.census(upd.payload_v1()["notes.md"], ours["notes.md"], after)
        assert row["all_unique_present"] and not row["truncated"]
        assert b"shipped-v3" in after
        settings = upd.parsed_settings(root)
        assert settings["accent"] == upd.USER_ACCENT_VALUE
        assert settings["keymap"] == "vim" and settings["telemetry"] is False


def test_truncated_twin_is_distinguished() -> None:
    base = upd.payload_v1()["notes.md"]
    ours = base + (upd.USER_NOTE_LINE + "\n").encode("ascii")
    row = differ.census(base, ours, b"# notes\nshipped-v2\n")
    assert row["truncated"] and row["missing_count"] == 1 and not row["all_unique_present"]


TESTS = [
    test_unchanged_by_user_is_replaced,
    test_user_changed_is_three_way_merged,
    test_conflicted_stops_and_writes_nothing,
    test_line_conflict_when_both_sides_rewrite_the_same_line,
    test_negative_control_classifier_off_goes_red,
    test_chain_v1_v2_v3_preserves_the_same_edit,
    test_truncated_twin_is_distinguished,
]


def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
