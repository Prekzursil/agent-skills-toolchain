"""Planning is PURE: no filesystem, no process, no socket -- and the inverse scope map."""

from __future__ import annotations

import pytest
from mcpctl.resolve import State
from mcpctl.scopes import PRECEDENCE, ScopeId
from mcpctl.topology import Topology

from mcpapply import plan as P
from conftest import PROJECT_KEY, topology_from


def test_suppressors_are_derived_from_the_measured_read_precedence():
    """The inverse map must never disagree with the reader it inverts."""
    assert P.SUPPRESSORS == tuple(s for s in PRECEDENCE if s in set(P.SUPPRESSORS))
    assert P.SUPPRESSORS == (
        ScopeId.SETTINGS_DENIED,
        ScopeId.CLAUDE_PROJECT_DISABLED,
        ScopeId.CLAUDE_USER_DISABLED,
    )


def test_root_disable_is_not_credited_with_preventing_the_spawn():
    """MEASURED A/B: the project row stops the spawn, the root list does not."""
    assert ScopeId.CLAUDE_PROJECT_DISABLED in P.SPAWN_PREVENTING
    assert ScopeId.CLAUDE_USER_DISABLED not in P.SPAWN_PREVENTING


def test_disable_prefers_the_project_row(top: Topology):
    change = P.plan_disable(top, "cloud-hub")
    assert change.before == State.ENABLED.value
    assert [e.scope for e in change.edits] == [ScopeId.CLAUDE_PROJECT_DISABLED]
    edit = change.edits[0]
    assert edit.key_path == ("projects", PROJECT_KEY, "disabledMcpServers")
    assert edit.op is P.Op.LIST_ADD
    assert edit.label == "claude_json"
    assert change.warnings == ()


def test_disable_without_a_project_key_falls_back_and_says_the_ram_is_not_saved():
    top = topology_from(
        {"claude_json": {"mcpServers": {"a": {"command": "x"}}}}, project_key=None
    )
    change = P.plan_disable(top, "a")
    assert [e.scope for e in change.edits] == [ScopeId.CLAUDE_USER_DISABLED]
    assert change.edits[0].key_path == ("disabledMcpServers",)
    joined = " ".join(change.warnings)
    assert "does NOT prevent the spawn" in joined
    assert "the memory does not" in joined


def test_disable_of_an_already_disabled_server_writes_nothing(top: Topology):
    change = P.plan_disable(top, "chrome-devtools")
    assert change.edits == ()
    assert change.warnings == ("already suppressed; nothing to write",)


def test_disable_of_a_denied_server_writes_nothing(top: Topology):
    change = P.plan_disable(top, "markitdown")
    assert change.before == State.DENIED.value
    assert change.edits == ()


def test_enable_clears_every_suppressing_scope_not_just_the_top_one():
    """One remaining suppressor keeps the server off, which reads as a failed enable."""
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"z": {"command": "x"}},
                "disabledMcpServers": ["z"],
                "projects": {PROJECT_KEY: {"disabledMcpServers": ["z"]}},
            },
            "settings": {"deniedMcpServers": [{"serverName": "z"}]},
        },
        project_key=PROJECT_KEY,
    )
    change = P.plan_enable(top, "z")
    assert [e.scope for e in change.edits] == list(P.SUPPRESSORS)
    assert all(e.op is P.Op.LIST_REMOVE for e in change.edits)
    joined = " ".join(change.warnings)
    assert "EVERY one must be cleared" in joined
    assert "OBJECTS" in joined


def test_enable_of_an_unsuppressed_server_writes_nothing(top: Topology):
    change = P.plan_enable(top, "cloud-hub")
    assert change.edits == ()
    assert change.warnings == ("no scope suppresses this server; nothing to write",)


def test_enable_degrades_when_a_project_mention_has_no_project_key():
    """A hand-built topology can carry the mention without the key; degrade, do not crash."""
    top = Topology(
        specs={},
        definitions={},
        mentions={"orphan": (ScopeId.CLAUDE_PROJECT_DISABLED,)},
        project_key=None,
    )
    change = P.plan_enable(top, "orphan")
    assert change.edits == ()
    assert any("no projects[] key" in w for w in change.warnings)


def test_add_targets_a_definition_scope_and_flags_the_pending_approval(top: Topology):
    change = P.plan_add(
        top, "brand-new", {"command": "node", "args": ["s.js"]}, scope=ScopeId.MCP_JSON
    )
    assert change.edits[0].label == "mcp_json"
    assert change.edits[0].op is P.Op.MAP_SET
    assert change.edits[0].spec == {"command": "node", "args": ["s.js"]}
    assert any("pending-approval" in w for w in change.warnings)


def test_add_over_an_existing_definition_says_it_replaces(top: Topology):
    change = P.plan_add(top, "cloud-hub", {"command": "y"}, scope=ScopeId.CLAUDE_USER)
    assert "a definition already exists; this REPLACES it" in change.warnings


def test_add_refuses_a_verdict_scope(top: Topology):
    with pytest.raises(ValueError, match="can only be added"):
        P.plan_add(top, "x", {}, scope=ScopeId.SETTINGS_DENIED)


def test_remove_clears_every_definition_scope_and_warns_about_leftovers(top: Topology):
    change = P.plan_remove(top, "ghidra-mcp")
    assert [e.op for e in change.edits] == [P.Op.MAP_DELETE]
    assert any("does NOT clear the curation lists" in w for w in change.warnings)


def test_remove_of_an_undefined_server_writes_nothing(top: Topology):
    change = P.plan_remove(top, "never-heard-of-it")
    assert change.edits == ()
    assert change.before == State.UNDEFINED.value


def test_remove_of_an_unmentioned_server_has_no_leftover_warning(top: Topology):
    change = P.plan_remove(top, "cloud-hub")
    assert change.warnings == ()


def test_edit_replaces_in_place_and_notes_the_next_session_delay(top: Topology):
    change = P.plan_edit(top, "cloud-hub", {"command": "python3"})
    assert change.edits[0].op is P.Op.MAP_SET
    assert any("NEXT session start" in w for w in change.warnings)


def test_edit_of_a_multi_scope_definition_names_the_scope_it_picked():
    top = topology_from(
        {
            "claude_json": {"mcpServers": {"dual": {"command": "a"}}},
            "mcp_json": {"mcpServers": {"dual": {"command": "b"}}},
        },
        project_key=None,
    )
    change = P.plan_edit(top, "dual", {"command": "c"})
    assert len(change.edits) == 1
    assert any("only the first" in w for w in change.warnings)


def test_edit_of_an_undefined_server_writes_nothing(top: Topology):
    change = P.plan_edit(top, "nope", {"command": "x"})
    assert change.edits == ()
    assert change.warnings == ("no definition to edit; use `add` instead",)


def test_reconnect_is_live_only_and_never_touches_disk(top: Topology):
    change = P.plan_reconnect(top, "cloud-hub")
    assert [e.op for e in change.edits] == [P.Op.LIVE_ONLY]
    assert change.touches_disk is False
    assert any("cannot be reached by any local channel" in w for w in change.warnings)


def test_plan_collects_labels_warnings_and_the_competing_writer_note(top: Topology):
    plan = P.build_plan(
        [P.plan_disable(top, "cloud-hub"), P.plan_remove(top, "ghidra-mcp")],
        project_key=PROJECT_KEY,
    )
    assert plan.labels() == ("claude_json",)
    assert plan.empty is False
    assert any("SessionStart hooks" in n for n in plan.notes)
    assert len(plan.warnings()) == 1


def test_a_live_only_plan_carries_no_disk_note(top: Topology):
    plan = P.build_plan([P.plan_reconnect(top, "cloud-hub")], project_key=None)
    assert plan.labels() == ()
    assert not any("SessionStart hooks" in n for n in plan.notes)


def test_an_all_noop_plan_is_empty(top: Topology):
    plan = P.build_plan([P.plan_enable(top, "cloud-hub")], project_key=PROJECT_KEY)
    assert plan.empty is True
    assert "plan is EMPTY" in P.render_plan(plan)


def test_render_and_to_dict_round_trip_every_field(top: Topology):
    plan = P.build_plan([P.plan_disable(top, "cloud-hub")], project_key=PROJECT_KEY)
    text = P.render_plan(plan)
    assert "DISABLE cloud-hub (was: enabled)" in text
    assert "+ claude_json:projects" in text
    payload = plan.to_dict()
    assert payload["project_key"] == PROJECT_KEY
    assert payload["changes"][0]["edits"][0]["op"] == "list-add"


def test_every_edit_shape_renders_a_sign(top: Topology):
    signs = {
        P.Op.LIST_ADD: "+",
        P.Op.LIST_REMOVE: "-",
        P.Op.MAP_SET: "+",
        P.Op.MAP_DELETE: "-",
        P.Op.LIVE_ONLY: "~",
    }
    for op, sign in signs.items():
        edit = P.Edit(
            scope=ScopeId.CLAUDE_USER, label="l", key_path=(), op=op, server="s"
        )
        assert edit.describe().startswith(f"{sign} l:(root)")


def test_a_hostile_server_name_is_made_safe_at_planning_time(top: Topology):
    change = P.plan_disable(top, "ev\x1b[31mil\x07")
    assert "\x1b" not in change.server
    assert "\x07" not in change.server
    assert "\x1b" not in change.edits[0].describe()


def test_a_warning_shared_by_two_changes_is_listed_once(top: Topology):
    """Plan.warnings() deduplicates: two root-scope disables share one caveat."""
    bare = topology_from(
        {"claude_json": {"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}}},
        project_key=None,
    )
    plan = P.build_plan(
        [P.plan_disable(bare, "a"), P.plan_disable(bare, "b")], project_key=None
    )
    assert len(plan.changes) == 2
    assert sum(len(c.warnings) for c in plan.changes) == 4
    assert len(plan.warnings()) == 2
    assert top.names()
