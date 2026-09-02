"""Planted controls for the three catalog-required tests."""
from __future__ import annotations

from pathlib import Path

from resolver import COMMAND, FILE_LINE, INFERRED, resolve

HERE = Path(__file__).resolve().parent
FIVE = "command-center/p2-wave/probes/TST-0009/fixtures/five_lines.txt"


def test_file_line_beyond_eof_is_unresolved(repo: Path) -> dict:
    path = repo / FIVE
    n = len(path.read_text(encoding="utf-8").splitlines())
    if n != 5:
        raise AssertionError(f"fixture line count {n} != 5")
    ok = resolve(repo, {"kind": FILE_LINE, "path": FIVE, "line": 5})
    beyond = resolve(repo, {"kind": FILE_LINE, "path": FIVE, "line": 6})
    way_beyond = resolve(repo, {"kind": FILE_LINE, "path": FIVE, "line": 999})
    missing = resolve(
        repo,
        {"kind": FILE_LINE, "path": "command-center/p2-wave/probes/TST-0009/fixtures/nope.txt", "line": 1},
    )
    passed = (
        ok["outcome"] == "resolved"
        and ok["reason"] == "file-has-line"
        and beyond["outcome"] == "unresolved"
        and beyond["reason"] == "line-beyond-eof"
        and beyond["line_count"] == 5
        and way_beyond["outcome"] == "unresolved"
        and way_beyond["reason"] == "line-beyond-eof"
        and missing["outcome"] == "unresolved"
        and missing["reason"] == "file-missing"
    )
    return {
        "id": "test_file_line_beyond_eof_is_unresolved",
        "pass": passed,
        "on_line": ok,
        "beyond_eof": beyond,
        "way_beyond": way_beyond,
        "missing_file": missing,
        "fixture_lines": n,
    }


def test_command_anchor_reexecutes(repo: Path) -> dict:
    match0 = resolve(
        repo,
        {"kind": COMMAND, "command": 'python3 -c "raise SystemExit(0)"', "recorded_exit": 0},
    )
    match2 = resolve(
        repo,
        {"kind": COMMAND, "command": 'python3 -c "raise SystemExit(2)"', "recorded_exit": 2},
    )
    mismatch = resolve(
        repo,
        {"kind": COMMAND, "command": 'python3 -c "raise SystemExit(1)"', "recorded_exit": 0},
    )
    missing_rec = resolve(
        repo,
        {"kind": COMMAND, "command": 'python3 -c "raise SystemExit(0)"'},
    )
    passed = (
        match0["outcome"] == "resolved"
        and match0.get("observed_exit") == 0
        and match2["outcome"] == "resolved"
        and match2.get("observed_exit") == 2
        and mismatch["outcome"] == "unresolved"
        and "exit-mismatch" in mismatch["reason"]
        and missing_rec["outcome"] == "unresolved"
        and missing_rec["reason"] == "recorded-exit-missing"
    )
    return {
        "id": "test_command_anchor_reexecutes",
        "pass": passed,
        "match_exit_0": match0,
        "match_exit_2": match2,
        "mismatch": mismatch,
        "missing_recorded_exit": missing_rec,
    }


def test_inferred_anchor_requires_a_named_source(repo: Path) -> dict:
    named = resolve(repo, {"kind": INFERRED, "source": "tools/completion/reducer.py"})
    named_str = resolve(repo, "inferred from command-center/CLAIM-REGISTRY.json")
    empty = resolve(repo, {"kind": INFERRED, "source": ""})
    bare = resolve(repo, "inferred from")
    placeholder = resolve(repo, {"kind": INFERRED, "source": "unknown"})
    # "inferred from" with no name may classify as unknown; either way it
    # must not resolve.
    passed = (
        named["outcome"] == "resolved"
        and named.get("source") == "tools/completion/reducer.py"
        and named_str["outcome"] == "resolved"
        and empty["outcome"] == "unresolved"
        and empty["reason"] == "inferred-source-unnamed"
        and bare["outcome"] == "unresolved"
        and placeholder["outcome"] == "unresolved"
    )
    return {
        "id": "test_inferred_anchor_requires_a_named_source",
        "pass": passed,
        "named": named,
        "named_string": named_str,
        "empty_source": empty,
        "bare_phrase": bare,
        "placeholder": placeholder,
    }


def run_required_tests(repo: Path) -> list[dict]:
    return [
        test_file_line_beyond_eof_is_unresolved(repo),
        test_command_anchor_reexecutes(repo),
        test_inferred_anchor_requires_a_named_source(repo),
    ]
