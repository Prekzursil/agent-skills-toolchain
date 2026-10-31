"""Pure-parsing tests for the config topology reader.

Every test feeds an in-memory dict. No filesystem, no real config, no network.
"""

from __future__ import annotations

from mcpctl import topology
from mcpctl.scopes import ScopeId

FAKE_TOKEN = "ghp_" + "Z" * 36


def claude_doc() -> dict[str, object]:
    return {
        "mcpServers": {
            "alpha": {
                "command": "node",
                "args": ["a.js"],
                "env": {"A_TOKEN": FAKE_TOKEN},
            },
            "beta": {"type": "sse", "url": "https://example.invalid/sse"},
            "gamma": {"command": "py", "args": []},
        },
        "disabledMcpServers": ["gamma", "delta"],
        "projects": {
            "C:/work": {"disabledMcpServers": ["beta"]},
            "C:/other": {"disabledMcpServers": ["alpha"]},
        },
    }


def mcp_json_doc() -> dict[str, object]:
    return {
        "mcpServers": {
            "delta": {"command": "uvx", "args": ["d"], "env": {"D_KEY": "${D_KEY}"}},
            "gamma": {"command": "py", "args": ["g"]},
        }
    }


def settings_doc() -> dict[str, object]:
    return {"deniedMcpServers": [{"serverName": "epsilon"}, {"serverName": "alpha"}]}


def settings_local_doc() -> dict[str, object]:
    return {"enabledMcpjsonServers": ["delta"], "enableAllProjectMcpServers": False}


def build(project_key: str | None = "C:/work") -> topology.Topology:
    return topology.build_topology(
        topology.SourceDocs(
            claude_json=claude_doc(),
            mcp_json=mcp_json_doc(),
            settings=settings_doc(),
            settings_local=settings_local_doc(),
            disabled_defaults={"disabledMcpServers": ["beta"]},
        ),
        project_key=project_key,
    )


# --------------------------------------------------------------------------- specs


def test_parse_server_specs_classifies_transport_from_type_then_command_then_url():
    specs = topology.parse_server_specs(
        {
            "s_stdio": {"command": "node"},
            "s_typed": {"type": "sse", "url": "https://x.invalid"},
            "s_url_only": {"url": "https://y.invalid"},
            "s_empty": {},
        }
    )
    assert specs["s_stdio"].transport == "stdio"
    assert specs["s_typed"].transport == "sse"
    assert specs["s_url_only"].transport == "http"
    assert specs["s_empty"].transport == "unknown"


def test_parse_server_specs_never_captures_an_env_value():
    specs = topology.parse_server_specs(
        {"s": {"command": "x", "env": {"TOK": FAKE_TOKEN, "REF": "${REF}", "E": ""}}}
    )
    fields = specs["s"].env_fields
    assert [(f.name, f.kind) for f in fields] == [
        ("E", "absent"),
        ("REF", "reference"),
        ("TOK", "present"),
    ]
    assert FAKE_TOKEN not in repr(specs["s"])


def test_parse_server_specs_redacts_command_and_args():
    specs = topology.parse_server_specs(
        {"s": {"command": "C:/Users/bob/tool.exe", "args": ["--key", "sk-" + "Q" * 20]}}
    )
    assert "bob" not in specs["s"].command
    assert specs["s"].args == ("--key", "[REDACTED:api-key]")


def test_parse_server_specs_strips_control_bytes_from_a_hostile_name():
    specs = topology.parse_server_specs(
        {"ev\x1b]52;c;cHduZWQ=\x07il": {"command": "x"}}
    )
    assert list(specs) == ["ev]52;c;cHduZWQ=il"]


def test_parse_server_specs_skips_a_non_mapping_spec():
    specs = topology.parse_server_specs({"ok": {"command": "x"}, "bad": "not-a-dict"})
    assert sorted(specs) == ["bad", "ok"]
    assert specs["bad"].transport == "unknown"
    assert specs["bad"].malformed is True
    assert specs["ok"].malformed is False


def test_parse_server_specs_tolerates_a_non_mapping_container():
    assert topology.parse_server_specs(None) == {}
    assert topology.parse_server_specs(["a"]) == {}


def test_parse_server_specs_coerces_non_string_args():
    specs = topology.parse_server_specs({"s": {"command": 7, "args": [1, None]}})
    assert specs["s"].command == "7"
    assert specs["s"].args == ("1", "None")


def test_parse_server_specs_ignores_a_non_list_args():
    specs = topology.parse_server_specs({"s": {"command": "x", "args": "oops"}})
    assert specs["s"].args == ()


# ------------------------------------------------------------------- name lists


def test_parse_name_list_accepts_strings_and_drops_non_strings():
    assert topology.parse_name_list(["a", 3, None, "b"]) == ("a", "b")


def test_parse_name_list_tolerates_a_non_list():
    assert topology.parse_name_list(None) == ()
    assert topology.parse_name_list({"a": 1}) == ()


def test_parse_denied_list_reads_the_OBJECT_element_shape():
    """The measured shape: [{"serverName": "markitdown"}] -- not a list of strings."""
    assert topology.parse_denied_list([{"serverName": "x"}, {"serverName": "y"}]) == (
        "x",
        "y",
    )


def test_parse_denied_list_also_tolerates_a_bare_string_element():
    assert topology.parse_denied_list(["x", {"serverName": "y"}]) == ("x", "y")


def test_parse_denied_list_drops_an_object_without_servername():
    assert topology.parse_denied_list([{"other": "x"}, {"serverName": "y"}]) == ("y",)


def test_parse_denied_list_drops_an_element_that_is_neither_string_nor_object():
    assert topology.parse_denied_list([{"serverName": "y"}, 5, None, ["nested"]]) == (
        "y",
    )


def test_parse_denied_list_tolerates_a_non_list():
    assert topology.parse_denied_list(None) == ()


# ----------------------------------------------------------------- project rows


def test_project_row_requires_an_exact_key_and_never_an_ancestor():
    row, found = topology.project_row(claude_doc(), "C:/work/sub")
    assert found is False
    assert row == {}
    row, found = topology.project_row(claude_doc(), "C:/work")
    assert found is True
    assert row["disabledMcpServers"] == ["beta"]


def test_project_row_with_no_key_requested_is_not_found():
    row, found = topology.project_row(claude_doc(), None)
    assert (row, found) == ({}, False)


def test_project_row_normalises_backslashes_before_matching():
    _row, found = topology.project_row(claude_doc(), "C:\\work")
    assert found is True


def test_project_row_tolerates_a_non_mapping_projects_value():
    assert topology.project_row({"projects": ["x"]}, "C:/work") == ({}, False)
    assert topology.project_row({"projects": {"C:/work": "bad"}}, "C:/work") == (
        {},
        True,
    )


# -------------------------------------------------------------------- topology


def test_build_topology_records_every_definition_scope():
    top = build()
    assert top.scopes_of("alpha") == (ScopeId.CLAUDE_USER,)
    assert top.scopes_of("delta") == (ScopeId.MCP_JSON,)
    assert top.scopes_of("gamma") == (ScopeId.CLAUDE_USER, ScopeId.MCP_JSON)


def test_build_topology_records_every_verdict_scope_that_mentions_a_server():
    top = build()
    assert top.mentions_of("gamma") == (ScopeId.CLAUDE_USER_DISABLED,)
    assert top.mentions_of("beta") == (
        ScopeId.CLAUDE_PROJECT_DISABLED,
        ScopeId.LOADOUT_TEMPLATE,
    )
    assert top.mentions_of("alpha") == (ScopeId.SETTINGS_DENIED,)
    assert top.mentions_of("delta") == (
        ScopeId.CLAUDE_USER_DISABLED,
        ScopeId.MCPJSON_APPROVED,
    )


def test_build_topology_includes_names_that_are_only_ever_mentioned():
    """`epsilon` is denied but defined nowhere -- it must still appear."""
    top = build()
    assert "epsilon" in top.names()
    assert top.scopes_of("epsilon") == ()


def test_build_topology_ignores_ancestor_project_rows_when_the_cwd_has_no_row():
    top = build(project_key="C:/work/deeper")
    assert top.project_row_found is False
    assert ScopeId.CLAUDE_PROJECT_DISABLED not in top.mentions_of("beta")


def test_build_topology_exposes_the_mcpjson_approval_switches():
    top = build()
    assert top.enable_all_project_servers is False
    assert top.approved_mcpjson == ("delta",)


def test_build_topology_reads_enable_all_true():
    docs = topology.SourceDocs(
        claude_json={},
        mcp_json={},
        settings={},
        settings_local={"enableAllProjectMcpServers": True},
    )
    assert (
        topology.build_topology(docs, project_key=None).enable_all_project_servers
        is True
    )


def test_build_topology_defaults_enable_all_to_false_on_a_non_bool():
    docs = topology.SourceDocs(settings_local={"enableAllProjectMcpServers": "yes"})
    assert (
        topology.build_topology(docs, project_key=None).enable_all_project_servers
        is False
    )


def test_build_topology_over_entirely_absent_sources_is_empty_not_an_error():
    top = topology.build_topology(topology.SourceDocs(), project_key=None)
    assert top.names() == ()
    assert top.project_row_found is False


def test_a_name_repeated_inside_one_scope_records_that_scope_only_once():
    """Otherwise `basis` would list the same scope twice and read as two signals."""
    docs = topology.SourceDocs(
        claude_json={
            "mcpServers": {"dup": {"command": "x"}},
            "disabledMcpServers": ["dup", "dup", "dup"],
        }
    )
    top = topology.build_topology(docs, project_key=None)
    assert top.mentions_of("dup") == (ScopeId.CLAUDE_USER_DISABLED,)


def test_names_are_sorted_and_deduplicated():
    top = build()
    assert top.names() == ("alpha", "beta", "delta", "epsilon", "gamma")


def test_spec_lookup_returns_none_for_a_mention_only_name():
    top = build()
    assert top.spec_of("epsilon") is None
    spec = top.spec_of("alpha")
    assert spec is not None
    assert spec.transport == "stdio"
