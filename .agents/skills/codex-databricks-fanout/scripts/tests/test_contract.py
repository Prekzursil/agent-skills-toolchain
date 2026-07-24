from harness import contract
from harness.contract import Unit


def _u():
    return Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/x/u1.md")


def test_rail_and_codex():
    assert contract.RAIL["policy_id"] == "0002189219BF8EF3"
    assert contract.RAIL["concurrency"] == 48 and contract.RAIL["stagger_s"] == "3.0"
    assert (
        contract.CODEX["model"] == "gpt-5.6-sol" and contract.CODEX["effort"] == "ultra"
    )


def test_floors_at_or_above_node_gate_1024():
    assert contract.floor_for("coverage") >= 1024
    assert contract.floor_for("smoke") >= 1024
    assert contract.floor_for("anything-unknown") >= 1024  # default


def test_skeleton_sentinel_is_ascii():  # cross-platform round-trip guard
    assert contract.SKELETON.isascii(), (
        "sentinel must be ASCII or cp1252 harvest defeats the guard"
    )


def test_and_gate_rejects_missing_sentinel(tmp_path):
    a = tmp_path / "u.md"
    a.write_text("x" * 2000, encoding="utf-8")
    ok, reason, _ = contract.and_gate_artifact("u1", a, 1024)
    assert not ok and reason == "missing-UNIT-COMPLETE"


def test_and_gate_passes_with_sentinel(tmp_path):
    a = tmp_path / "u.md"
    a.write_text("x" * 2000 + "\nUNIT-COMPLETE: u1\n", encoding="utf-8")
    ok, reason, _ = contract.and_gate_artifact("u1", a, 1024)
    assert ok and reason == "and-gate-pass"


def test_schema_valid_requires_all_lane_fields(tmp_path):
    a = tmp_path / "u.md"
    a.write_text("file: x\nsuite_status: green\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason.startswith("schema-missing-fields")


def test_schema_valid_rejects_all_unknown_skeleton(tmp_path):
    fields = [
        "file",
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_pushed",
    ]
    body = "\n".join(f"{f}: {contract.SKELETON}" for f in fields)
    a = tmp_path / "u.md"
    a.write_text(body + "\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason == "all-unknown-skeleton"


def test_schema_valid_rejects_skeleton_written_platform_default(tmp_path):
    # regression: writing with the OS default encoding must STILL be rejected.
    fields = [
        "file",
        "uncovered_before",
        "tests_added",
        "suite_status",
        "coverage_after",
        "branch_pushed",
    ]
    body = "\n".join(f"{f}: {contract.SKELETON}" for f in fields) + "\n" + "x" * 1100
    a = tmp_path / "u.md"
    with open(a, "w") as fh:  # NO encoding -> platform default (cp1252 on this box)
        fh.write(body)
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason == "all-unknown-skeleton"


def test_schema_valid_passes_full_measured_artifact(tmp_path):
    body = (
        "file: src/a.py\nuncovered_before: [10,11]\ntests_added: 2\n"
        "suite_status: green\ncoverage_after: 91.2\nbranch_pushed: agent/E-x\n"
    )
    a = tmp_path / "u.md"
    a.write_text(body + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert ok and reason == "schema-ok"


def test_schema_valid_smoke_incidental_sentinel_not_flagged(tmp_path):
    # smoke lane has ONE required field ('echo'); a sentinel string in free prose (not the echo:
    # value) must NOT trip the guard. The old count>=1 guard would false-FAIL this.
    smoke = Unit(id="s0", lane="smoke", prompt="p", artifact="/d/s0.md")
    body = (
        "echo: hello from smoke 0\n"
        "context: an earlier draft said 'UNKNOWN - not yet measured' before completion\n"
        + "x"
        * 1100
    )
    a = tmp_path / "s.md"
    a.write_text(body, encoding="utf-8")
    ok, reason = contract.schema_valid(smoke, a)
    assert ok and reason == "schema-ok"
