"""Tests for scope resolution.

The load-bearing property: a resolution NEVER collapses to a bare boolean. It always
carries the scopes that produced it, and it records a conflict whenever two verdict
scopes disagree -- because a single-scope read is the measured way this goes wrong.
"""

from __future__ import annotations

import pytest

from mcpctl import resolve
from mcpctl.resolve import State
from mcpctl.scopes import ScopeId


def res(
    *,
    defined: tuple[ScopeId, ...] = (ScopeId.CLAUDE_USER,),
    mentions: tuple[ScopeId, ...] = (),
    approved: bool = False,
    enable_all: bool = False,
) -> resolve.Resolution:
    return resolve.resolve_state(
        definitions=defined,
        mentions=mentions,
        approved=approved,
        enable_all_project_servers=enable_all,
    )


def test_an_undefined_name_that_nothing_mentions_is_undefined():
    out = res(defined=(), mentions=())
    assert out.state is State.UNDEFINED
    assert out.basis == ()


def test_a_name_only_denied_is_denied_even_though_it_is_defined_nowhere():
    out = res(defined=(), mentions=(ScopeId.SETTINGS_DENIED,))
    assert out.state is State.DENIED
    assert out.basis == (ScopeId.SETTINGS_DENIED,)


def test_a_plain_user_scope_server_is_enabled():
    out = res()
    assert out.state is State.ENABLED
    assert out.basis == (ScopeId.CLAUDE_USER,)
    assert out.conflicts == ()


def test_denied_outranks_both_disable_lists():
    out = res(
        mentions=(
            ScopeId.SETTINGS_DENIED,
            ScopeId.CLAUDE_PROJECT_DISABLED,
            ScopeId.CLAUDE_USER_DISABLED,
        )
    )
    assert out.state is State.DENIED
    assert out.basis[0] is ScopeId.SETTINGS_DENIED


def test_project_disabled_outranks_user_disabled():
    out = res(mentions=(ScopeId.CLAUDE_PROJECT_DISABLED, ScopeId.CLAUDE_USER_DISABLED))
    assert out.state is State.DISABLED
    assert out.basis[0] is ScopeId.CLAUDE_PROJECT_DISABLED
    assert ScopeId.CLAUDE_USER_DISABLED in out.basis


def test_user_disabled_alone_disables():
    out = res(mentions=(ScopeId.CLAUDE_USER_DISABLED,))
    assert out.state is State.DISABLED


def test_MEASURED_approval_does_not_override_a_user_disable():
    """ghidra-mcp / hexstrike-ai / ida-pro-mcp: approved AND root-disabled AND absent."""
    out = res(
        defined=(ScopeId.CLAUDE_USER, ScopeId.MCP_JSON),
        mentions=(ScopeId.CLAUDE_USER_DISABLED, ScopeId.MCPJSON_APPROVED),
        approved=True,
    )
    assert out.state is State.DISABLED
    assert out.conflicts, (
        "an approved-yet-disabled server must be flagged as a conflict"
    )
    assert "mcpjson-approved" in out.conflicts[0]
    assert "claude-user-disabled" in out.conflicts[0]


def test_a_project_scope_server_that_is_not_approved_is_pending_approval():
    out = res(defined=(ScopeId.MCP_JSON,), approved=False)
    assert out.state is State.PENDING_APPROVAL
    assert out.basis == (ScopeId.MCP_JSON,)


def test_a_project_scope_server_that_is_approved_is_enabled():
    out = res(defined=(ScopeId.MCP_JSON,), approved=True)
    assert out.state is State.ENABLED
    assert ScopeId.MCPJSON_APPROVED in out.basis


def test_enable_all_project_servers_makes_an_unapproved_project_server_enabled():
    out = res(defined=(ScopeId.MCP_JSON,), approved=False, enable_all=True)
    assert out.state is State.ENABLED


def test_a_server_defined_in_both_scopes_is_not_pending_on_the_project_side():
    out = res(defined=(ScopeId.CLAUDE_USER, ScopeId.MCP_JSON), approved=False)
    assert out.state is State.ENABLED


def test_the_loadout_template_never_decides_a_state():
    out = res(mentions=(ScopeId.LOADOUT_TEMPLATE,))
    assert out.state is State.ENABLED
    assert ScopeId.LOADOUT_TEMPLATE not in out.basis
    assert any("advisory" in c for c in out.conflicts)


def test_every_resolution_is_marked_inferred_when_more_than_one_scope_spoke():
    single = res(mentions=(ScopeId.CLAUDE_USER_DISABLED,))
    multi = res(
        mentions=(ScopeId.CLAUDE_USER_DISABLED, ScopeId.CLAUDE_PROJECT_DISABLED)
    )
    assert single.inferred is False
    assert multi.inferred is True


def test_resolution_is_json_able_with_string_scopes():
    payload = res(mentions=(ScopeId.CLAUDE_USER_DISABLED,)).to_dict()
    assert payload["state"] == "disabled"
    assert payload["basis"] == ["claude-user-disabled"]
    assert payload["inferred"] is False
    assert payload["conflicts"] == []


@pytest.mark.parametrize(
    ("mentions", "expected"),
    [
        ((), State.ENABLED),
        ((ScopeId.SETTINGS_DENIED,), State.DENIED),
        ((ScopeId.CLAUDE_USER_DISABLED,), State.DISABLED),
        ((ScopeId.CLAUDE_PROJECT_DISABLED,), State.DISABLED),
    ],
)
def test_state_is_total_over_the_verdict_scopes(mentions, expected):
    assert res(mentions=mentions).state is expected


def test_resolve_topology_maps_every_known_name():
    from mcpctl import topology

    docs = topology.SourceDocs(
        claude_json={
            "mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}},
            "disabledMcpServers": ["b"],
        },
        mcp_json={"mcpServers": {"c": {"command": "z"}}},
        settings={"deniedMcpServers": [{"serverName": "d"}]},
        settings_local={"enabledMcpjsonServers": ["c"]},
    )
    top = topology.build_topology(docs, project_key=None)
    out = resolve.resolve_topology(top)
    assert sorted(out) == ["a", "b", "c", "d"]
    assert out["a"].state is State.ENABLED
    assert out["b"].state is State.DISABLED
    assert out["c"].state is State.ENABLED
    assert out["d"].state is State.DENIED
