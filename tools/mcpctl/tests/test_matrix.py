"""Tests for the health/status matrix.

Liveness is INJECTED. No test here reads a process table, spawns anything, or opens a
socket -- so the matrix is exercised hermetically and the same code path runs in CI as
on the box.
"""

from __future__ import annotations

from mcpctl import matrix, topology
from mcpctl.resolve import State
from mcpctl.scopes import ScopeId

FAKE_TOKEN = "ghp_" + "K" * 36


def sample_topology() -> topology.Topology:
    return topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {
                    "alpha": {
                        "command": "node",
                        "args": ["a.js"],
                        "env": {"ALPHA_TOKEN": FAKE_TOKEN},
                    },
                    "beta": {"type": "sse", "url": "https://example.invalid/sse"},
                },
                "disabledMcpServers": ["beta"],
            },
            mcp_json={"mcpServers": {"gamma": {"command": "uvx", "args": ["g"]}}},
            settings={"deniedMcpServers": [{"serverName": "delta"}]},
            settings_local={"enabledMcpjsonServers": ["gamma"]},
        ),
        project_key=None,
    )


def test_build_rows_covers_every_known_server_sorted_by_name():
    rows = matrix.build_rows(sample_topology(), liveness={})
    assert [r.name for r in rows] == ["alpha", "beta", "delta", "gamma"]


def test_a_row_carries_state_basis_and_the_inferred_flag():
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness={})}
    assert rows["beta"].state == State.DISABLED.value
    assert rows["beta"].basis == (ScopeId.CLAUDE_USER_DISABLED.value,)
    assert rows["beta"].inferred is False
    assert rows["gamma"].state == State.ENABLED.value
    assert rows["delta"].state == State.DENIED.value


def test_a_row_carries_definition_scopes_and_transport():
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness={})}
    assert rows["alpha"].scopes == (ScopeId.CLAUDE_USER.value,)
    assert rows["alpha"].transport == "stdio"
    assert rows["beta"].transport == "sse"
    assert rows["gamma"].scopes == (ScopeId.MCP_JSON.value,)


def test_a_mention_only_row_has_no_definition_scope_and_unknown_transport():
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness={})}
    assert rows["delta"].scopes == ()
    assert rows["delta"].transport == "unknown"


def test_injected_liveness_lands_on_the_matching_row_only():
    live = {
        "alpha": matrix.Liveness(tool_count=17, pid=4242, rss_bytes=1024 * 1024),
    }
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness=live)}
    assert rows["alpha"].tool_count == 17
    assert rows["alpha"].pid == 4242
    assert rows["alpha"].rss_bytes == 1024 * 1024
    assert rows["beta"].tool_count is None
    assert rows["beta"].pid is None
    assert rows["beta"].rss_bytes is None


def test_a_liveness_last_error_is_redacted_and_control_stripped():
    live = {
        "alpha": matrix.Liveness(
            last_error=f"401 from C:/Users/bob/x \x1b]8;;http://evil\x07 key={FAKE_TOKEN}"
        )
    }
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness=live)}
    err = rows["alpha"].last_error
    assert err is not None
    assert FAKE_TOKEN not in err
    assert "bob" not in err
    assert "\x1b" not in err
    assert "\x07" not in err
    assert "401" in err


def test_env_fields_reach_the_row_as_names_and_kinds_only():
    rows = {r.name: r for r in matrix.build_rows(sample_topology(), liveness={})}
    assert [(f.name, f.kind) for f in rows["alpha"].env_fields] == [
        ("ALPHA_TOKEN", "present")
    ]


def test_the_whole_matrix_dump_contains_no_secret_value():
    """The headline security assertion: a token-bearing config leaks nothing."""
    live = {"alpha": matrix.Liveness(last_error=f"boom {FAKE_TOKEN}")}
    rows = matrix.build_rows(sample_topology(), liveness=live)
    dumped = repr([r.to_dict() for r in rows])
    assert FAKE_TOKEN not in dumped
    assert "ALPHA_TOKEN" in dumped


def test_row_to_dict_is_json_able_and_flat():
    import json

    rows = matrix.build_rows(sample_topology(), liveness={})
    text = json.dumps([r.to_dict() for r in rows])
    assert '"name": "alpha"' in text
    assert '"env_fields": [{"name": "ALPHA_TOKEN", "kind": "present"}]' in text


def test_conflicts_reach_the_row():
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {"g": {"command": "x"}},
                "disabledMcpServers": ["g"],
            },
            mcp_json={"mcpServers": {"g": {"command": "x"}}},
            settings_local={"enabledMcpjsonServers": ["g"]},
        ),
        project_key=None,
    )
    (row,) = matrix.build_rows(top, liveness={})
    assert row.state == State.DISABLED.value
    assert any("MEASURED" in c for c in row.conflicts)


def test_summarise_counts_states_and_flags_conflicts():
    rows = matrix.build_rows(sample_topology(), liveness={})
    counts = matrix.summarise(rows)
    assert counts == {
        "total": 4,
        "enabled": 2,
        "disabled": 1,
        "denied": 1,
        "pending-approval": 0,
        "undefined": 0,
        "with_conflicts": 0,
        "credential_bearing": 1,
    }


def test_summarise_counts_pending_and_conflicting_rows():
    top = topology.build_topology(
        topology.SourceDocs(
            mcp_json={"mcpServers": {"p": {"command": "x"}}},
            disabled_defaults={"disabledMcpServers": ["p"]},
        ),
        project_key=None,
    )
    counts = matrix.summarise(matrix.build_rows(top, liveness={}))
    assert counts["pending-approval"] == 1
    assert counts["with_conflicts"] == 1


def test_liveness_defaults_are_all_none():
    blank = matrix.Liveness()
    assert (blank.tool_count, blank.last_error, blank.pid, blank.rss_bytes) == (
        None,
        None,
        None,
        None,
    )
