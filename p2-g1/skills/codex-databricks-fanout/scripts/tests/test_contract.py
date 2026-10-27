import importlib.util
import pathlib
import re
import sys

import pytest

from harness import contract
from harness.contract import Unit

COVERAGE_FIELDS = [
    "file",
    "uncovered_before",
    "tests_added",
    "suite_status",
    "coverage_after",
    "branch_ready",
    "patch_file",
]


def _u():
    return Unit(id="u1", lane="coverage", prompt="p", artifact="/dbfs/x/u1.md")


def test_rail_and_codex():
    assert contract.RAIL["policy_id"] == "0002189219BF8EF3"
    assert contract.RAIL["concurrency"] == 48 and contract.RAIL["stagger_s"] == "3.0"
    assert (
        contract.CODEX["model"] == "gpt-5.6-sol" and contract.CODEX["effort"] == "ultra"
    )


def test_codex_carries_the_headless_priority_and_permission_posture():
    # service_tier=priority is the headless-exec fast/priority lever (codex 0.145 has NO
    # `fast` config key); approval_policy/sandbox_mode record the intended node posture.
    assert contract.CODEX["service_tier"] == "priority"
    assert contract.CODEX["approval_policy"] == "never"
    assert contract.CODEX["sandbox_mode"] == "danger-full-access"


def test_node_codex_flags_restore_the_profile_dropped_by_ignore_user_config():
    # --ignore-user-config drops ~/.codex/config.toml, so BOTH levers must ride on -c.
    flags = contract.node_codex_flags()
    assert "-c service_tier=priority" in flags
    assert "-c model_reasoning_effort=ultra" in flags
    # the permission posture is a FLAG on the node, never -c -- it must not leak in here.
    assert "sandbox_mode" not in flags and "approval_policy" not in flags


def test_node_type_defaults_to_the_largest_size_under_the_18_dbu_policy_cap():
    # r6id.32xlarge is 32.64 DBU and is REJECTED by the policy's dbus_per_hour<=18 cap.
    assert contract.RAIL["node_type_id"] == "r6id.16xlarge"


def test_node_type_is_overridable_via_derive_node_type_env(monkeypatch):
    # Loaded as a FRESH module object so the cached harness.contract (and its Unit class,
    # which other tests hold a reference to) is left untouched.
    monkeypatch.setenv("DERIVE_NODE_TYPE", "r5d.2xlarge")
    spec = importlib.util.spec_from_file_location("_m03_envprobe", contract.__file__)
    fresh = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec_module: under `from __future__ import annotations` the @dataclass
    # machinery resolves its string annotations via sys.modules[cls.__module__] (py3.14), so an
    # unregistered module raises during Unit's construction. monkeypatch removes it again.
    monkeypatch.setitem(sys.modules, "_m03_envprobe", fresh)
    spec.loader.exec_module(fresh)
    assert fresh.RAIL["node_type_id"] == "r5d.2xlarge"
    assert contract.RAIL["node_type_id"] == "r6id.16xlarge"  # cache not mutated


def test_floors_at_or_above_node_gate_1024():
    assert contract.floor_for("coverage") >= 1024
    assert contract.floor_for("smoke") >= 1024
    assert contract.floor_for("anything-unknown") >= 1024  # default


def test_skeleton_sentinel_is_ascii():  # [G3-FIX #1] cross-platform round-trip guard
    assert contract.SKELETON.isascii(), (
        "sentinel must be ASCII or cp1252 harvest defeats the guard"
    )


def test_unit_timeout_default_is_a_node_consumable_positive_int():
    u = _u()
    assert u.timeout_s == contract.DEFAULT_UNIT_TIMEOUT_S
    assert isinstance(u.timeout_s, int) and u.timeout_s > 0


def test_emitted_payload_timeout_survives_the_node_int_coercion():
    """The node runs `int(u.get("timeout_s", 2400))` (batch_runner.py:157). build_batch emits the
    key UNCONDITIONALLY, so a None DEFAULT would arrive as null, the node's own 2400 fallback
    would never apply, and int(None) would raise for every unit. This pins the reason
    DEFAULT_UNIT_TIMEOUT_S is a positive int and not None."""
    from harness.build_batch import build_batch

    emitted = build_batch([_u()], "m03")["units"][0]
    assert "timeout_s" in emitted, (
        "key is emitted unconditionally -- that is the coupling"
    )
    assert int(emitted.get("timeout_s", 2400)) == contract.DEFAULT_UNIT_TIMEOUT_S


def test_none_timeout_is_type_legal_but_still_blocked_at_the_node():
    """`int | None` makes the owner's "no timeout" posture EXPRESSIBLE, which is why the union type
    is kept. It is NOT yet usable end-to-end, and this pins both halves of that so the type is
    never mistaken for a working opt-out: the dataclass accepts None, the payload carries it as
    null, and the node's coercion dies on it. Unblocking it is one line at batch_runner.py:157
    (`int(u.get("timeout_s") or 2400)`) -- which is a different merge group's file."""
    from harness.build_batch import build_batch

    u = Unit(id="u1", lane="coverage", prompt="p", artifact="/a", timeout_s=None)
    assert u.timeout_s is None  # contract level: expressible
    emitted = build_batch([u], "m03")["units"][0]
    assert emitted["timeout_s"] is None  # reaches the node as null, key PRESENT
    with pytest.raises(TypeError):  # ...where the node's own fallback cannot save it
        int(emitted.get("timeout_s", 2400))


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


def test_and_gate_window_is_exactly_sentinel_tail_bytes(tmp_path):
    # The window is the named constant, not a magic 600, and it is load-bearing: a sentinel
    # pushed one window's worth of padding past the end must FAIL while one that lands
    # inside must PASS. Measured in bytes because trailing prose has no fixed line length.
    win = contract.SENTINEL_TAIL_BYTES
    sentinel = "UNIT-COMPLETE: u1"
    inside = tmp_path / "in.md"
    inside.write_text("x" * 2000 + sentinel + "y" * (win - len(sentinel)), "utf-8")
    ok, reason, _ = contract.and_gate_artifact("u1", inside, 1024)
    assert ok and reason == "and-gate-pass"
    outside = tmp_path / "out.md"
    outside.write_text("x" * 2000 + sentinel + "y" * win, encoding="utf-8")
    ok, reason, _ = contract.and_gate_artifact("u1", outside, 1024)
    assert not ok and reason == "missing-UNIT-COMPLETE"


def test_sentinel_window_and_floor_match_the_node_side_hardcoded_gate():
    """`batch_runner.py` is a Databricks NOTEBOOK export: it runs on the node, where `harness/` is
    not importable (ruff.toml excludes it for exactly that reason), so it hardcodes its own copy of
    the AND-gate -- `fh.read()[-600:]` and `size >= 1024`. Nothing else pins the two copies
    together, so changing SENTINEL_TAIL_BYTES or the lane floor alone would silently split the
    orchestrator gate from the node gate: one would accept an artifact the other calls incomplete.
    The test above is self-referential (it reads the constant it checks), so it CANNOT catch that
    drift -- measured: widening the constant left it green. Compare against the node source."""
    node = pathlib.Path(contract.__file__).parents[1] / "batch_runner.py"
    src = node.read_text(encoding="utf-8")
    windows = {int(m) for m in re.findall(r"read\(\)\[-(\d+):\]", src)}
    assert windows == {contract.SENTINEL_TAIL_BYTES}, (
        f"node sentinel window {windows} != SENTINEL_TAIL_BYTES "
        f"{contract.SENTINEL_TAIL_BYTES}"
    )
    floors = {int(m) for m in re.findall(r"size >= (\d+)", src)}
    assert floors == {contract.floor_for("coverage")}, (
        f"node byte floor {floors} != floor_for('coverage') "
        f"{contract.floor_for('coverage')}"
    )


def test_gate_module_shares_the_one_sentinel_window_not_a_second_copy():
    """SENTINEL_TAIL_BYTES is documented as the single source of truth for BOTH gates. A window
    re-hardcoded inside gate.py would keep every value-level assertion green while the two gates
    diverged, so assert the wiring itself: gate.py imports the name and never assigns it."""
    from harness import gate

    src = pathlib.Path(gate.__file__).read_text(encoding="utf-8")
    assert "from harness.contract import SENTINEL_TAIL_BYTES" in src
    assert "SENTINEL_TAIL_BYTES =" not in src, "gate.py must not hold a second copy"
    assert gate.SENTINEL_TAIL_BYTES == contract.SENTINEL_TAIL_BYTES


def test_schema_valid_requires_all_lane_fields(tmp_path):
    a = tmp_path / "u.md"
    a.write_text("file: x\nsuite_status: green\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason.startswith("schema-missing-fields")


def test_coverage_lane_requires_branch_ready_and_patch_file(tmp_path):
    """R1: the node has NO write token, clones read-only and commits LOCALLY, so the field is
    `branch_ready` -- `branch_pushed` would assert a push that cannot happen. patch_file is
    required because a local sha on an ephemeral node is lost work without an exported patch."""
    assert "branch_ready" in contract.LANE_SCHEMAS["coverage"]
    assert "patch_file" in contract.LANE_SCHEMAS["coverage"]
    assert "branch_pushed" not in contract.LANE_SCHEMAS["coverage"]
    legacy = (
        "file: src/a.py\nuncovered_before: [10]\ntests_added: 2\nsuite_status: green\n"
        "coverage_after: 91.2\nbranch_pushed: agent/E-x\n" + "x" * 1100
    )
    a = tmp_path / "u.md"
    a.write_text(legacy, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason == "schema-missing-fields:branch_ready,patch_file"


def test_schema_valid_rejects_all_unknown_skeleton(tmp_path):
    body = "\n".join(f"{f}: {contract.SKELETON}" for f in COVERAGE_FIELDS)
    a = tmp_path / "u.md"
    a.write_text(body + "\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason == "all-unknown-skeleton"


def test_schema_valid_rejects_skeleton_written_platform_default(tmp_path):
    # [G3-FIX #1] regression: writing with the OS default encoding must STILL be rejected.
    body = (
        "\n".join(f"{f}: {contract.SKELETON}" for f in COVERAGE_FIELDS)
        + "\n"
        + "x" * 1100
    )
    a = tmp_path / "u.md"
    with open(a, "w") as fh:  # NO encoding -> platform default (cp1252 on this box)
        fh.write(body)
    ok, reason = contract.schema_valid(_u(), a)
    assert not ok and reason == "all-unknown-skeleton"


def test_schema_valid_passes_full_measured_artifact(tmp_path):
    body = (
        "file: src/a.py\nuncovered_before: [10,11]\ntests_added: 2\n"
        "suite_status: green\ncoverage_after: 91.2\nbranch_ready: agent/E-x\n"
        "patch_file: /dbfs/tmp/E-coverage/patches/u.patch\n"
    )
    a = tmp_path / "u.md"
    a.write_text(body + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(_u(), a)
    assert ok and reason == "schema-ok"


RESEARCH_BODY = (
    "target: harness/poll.py\nlens: security\nfindings: unbounded poll\n"
    "severity: high\nevidence: harness/poll.py:12\nrecommendation: bound it\n"
)


def test_research_lane_is_read_only_and_demands_a_confidence(tmp_path):
    # Read-only lane: the artifact IS the deliverable, so NO branch and NO patch field.
    schema = contract.LANE_SCHEMAS["research"]
    assert "branch_ready" not in schema and "patch_file" not in schema
    u = Unit(id="r1", lane="research", prompt="p", artifact="/dbfs/x/r1.md")
    a = tmp_path / "r.md"
    a.write_text(RESEARCH_BODY + "x" * 1100, encoding="utf-8")  # confidence omitted
    ok, reason = contract.schema_valid(u, a)
    assert not ok and reason == "schema-missing-fields:confidence"
    a.write_text(RESEARCH_BODY + "confidence: likely\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(u, a)
    assert ok and reason == "schema-ok"


DERIVE_BODY = (
    "unit: R-042\nverdict: STILL_TRUE\nseverity: medium\n"
    "evidence: engine/verify.py:88\ntargets: engine/verify.py\n"
)


def test_derive_lane_is_read_only_and_demands_an_actionable_verdict(tmp_path):
    schema = contract.LANE_SCHEMAS["derive"]
    assert "branch_ready" not in schema and "patch_file" not in schema
    u = Unit(id="d1", lane="derive", prompt="p", artifact="/dbfs/x/d1.md")
    a = tmp_path / "d.md"
    a.write_text(DERIVE_BODY + "x" * 1100, encoding="utf-8")  # actionable omitted
    ok, reason = contract.schema_valid(u, a)
    assert not ok and reason == "schema-missing-fields:actionable"
    a.write_text(DERIVE_BODY + "actionable: yes\n" + "x" * 1100, encoding="utf-8")
    ok, reason = contract.schema_valid(u, a)
    assert ok and reason == "schema-ok"


@pytest.mark.parametrize("lane", ["research", "derive"])
def test_read_only_lane_skeleton_is_still_rejected(tmp_path, lane):
    # The write-as-you-go guard must hold on the read-only lanes too, not just coverage.
    fields = sorted(contract.LANE_SCHEMAS[lane])
    body = "\n".join(f"{f}: {contract.SKELETON}" for f in fields) + "\n" + "x" * 1100
    a = tmp_path / f"{lane}.md"
    a.write_text(body, encoding="utf-8")
    u = Unit(id="x1", lane=lane, prompt="p", artifact=str(a))
    ok, reason = contract.schema_valid(u, a)
    assert not ok and reason == "all-unknown-skeleton"


def test_schema_valid_smoke_incidental_sentinel_not_flagged(tmp_path):
    # [G5-FIX] smoke lane has ONE required field ('echo'); a sentinel string in free prose (not
    # the echo: value) must NOT trip the guard. The old count>=1 guard would false-FAIL this.
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
