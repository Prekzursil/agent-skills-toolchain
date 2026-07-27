"""Tests for ``monitorcore.mcp_source`` — the MCP inventory adapter, 100% line+branch.

Hermetic: the "live" path reads two COMMITTED config fixtures off disk through the real
:func:`~monitorcore.mcp_source.read_config`; every other path uses an injected reader. No MCP
handshake, no socket, no process table — which is precisely the property under test, since
every health column must stay ``None`` == not measured.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from monitorcore.contract import MonitorSource, SourceState
from monitorcore.mcp_source import (
    DocInventory,
    McpPayload,
    McpServer,
    McpSource,
    build_servers,
    default_paths,
    parse_doc,
    read_config,
    transport_of,
)

NOW = 1_784_283_000.0
FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
USER_DOC = str(FIXTURES / "user-mcp.json")
PROJECT_DOC = str(FIXTURES / "project-mcp.json")


def _reader(docs: dict[str, str | None]):
    return lambda path: docs.get(path)


# ───────────────────────────── transport_of ─────────────────────────────
@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("not-a-dict", "unknown"),
        ({"type": "http"}, "http"),
        ({"transport": "sse"}, "sse"),
        ({"type": "", "url": "http://x"}, "http"),
        ({"command": "python"}, "stdio"),
        ({}, "unknown"),
    ],
)
def test_transport_of_covers_declared_inferred_and_unknown(
    entry: object, expected: str
):
    assert transport_of(entry) == expected


def test_transport_of_scrubs_a_hostile_declared_type():
    assert "\x1b" not in transport_of({"type": "ht\x1btp"})


# ───────────────────────────── parse_doc ─────────────────────────────
def test_parse_doc_reads_servers_and_the_disable_list():
    doc = parse_doc(
        "user", '{"mcpServers": {"a": {"command": "x"}}, "disabledMcpServers": ["a"]}'
    )
    assert doc.scope == "user"
    assert doc.declared == (("a", "stdio"),)
    assert doc.disabled == frozenset({"a"})
    assert doc.problem == ""


def test_parse_doc_reports_unparsable_json_as_a_problem_not_an_exception():
    doc = parse_doc("user", "{not json")
    assert doc.declared == () and doc.problem.startswith("unparsable json")


def test_parse_doc_reports_a_non_object_document():
    assert parse_doc("user", "[1, 2]").problem == "not a json object"


def test_parse_doc_tolerates_a_non_dict_servers_block():
    assert parse_doc("user", '{"mcpServers": ["a"]}').declared == ()


def test_parse_doc_tolerates_a_non_list_disable_block_and_non_string_entries():
    assert parse_doc("user", '{"disabledMcpServers": "a"}').disabled == frozenset()
    assert parse_doc("user", '{"disabledMcpServers": ["a", 7]}').disabled == frozenset(
        {"a"}
    )


def test_parse_doc_scrubs_a_hostile_server_name():
    doc = parse_doc("user\x1b[2J", '{"mcpServers": {"ev\\u001bil": {}}}')
    assert "\x1b" not in doc.scope
    assert all("\x1b" not in name for name, _t in doc.declared)


# ───────────────────────────── build_servers / state ─────────────────────────────
def test_build_servers_merges_scopes_and_keeps_the_first_known_transport():
    docs = [
        DocInventory(scope="user", declared=(("a", "unknown"),)),
        DocInventory(scope="project", declared=(("a", "stdio"),)),
    ]
    (server,) = build_servers(docs)
    assert server.declared_in == ("user", "project")
    assert server.transport == "stdio"
    assert server.state == "enabled"


def test_build_servers_marks_a_uniformly_disabled_server_disabled():
    docs = [
        DocInventory(
            scope="user", declared=(("a", "stdio"),), disabled=frozenset({"a"})
        )
    ]
    assert build_servers(docs)[0].state == "disabled"


def test_build_servers_reports_a_cross_scope_disagreement_as_conflict_not_a_guess():
    docs = [
        DocInventory(scope="user", declared=(("a", "stdio"),)),
        DocInventory(
            scope="project", declared=(("a", "stdio"),), disabled=frozenset({"a"})
        ),
    ]
    assert build_servers(docs)[0].state == "conflict"


def test_build_servers_surfaces_a_name_that_is_only_ever_disabled():
    docs = [DocInventory(scope="user", disabled=frozenset({"ghost"}))]
    (server,) = build_servers(docs)
    assert server.declared_in == () and server.state == "disabled"
    assert server.transport == "unknown"


def test_a_bare_server_reports_unmeasured_health_never_zero():
    server = McpServer(name="a")
    assert server.tool_count is None and server.last_error is None


# ───────────────────────────── read_config / default_paths ─────────────────────────────
def test_read_config_returns_text_and_none_for_an_absent_document(tmp_path: Path):
    present = tmp_path / "x.json"
    present.write_text("{}", encoding="utf-8")
    assert read_config(str(present)) == "{}"
    assert read_config(str(tmp_path / "absent.json")) is None


def test_default_paths_names_the_standard_scopes():
    paths = default_paths()
    assert len(paths) == 3
    assert paths[0].endswith(".mcp.json")
    assert any(p.endswith(".claude.json") for p in paths)
    assert paths[-1] == os.path.join(os.getcwd(), ".mcp.json")


# ───────────────────────────── poll ─────────────────────────────
def test_poll_over_the_committed_fixtures_merges_both_scopes():
    snap = McpSource(paths=[USER_DOC, PROJECT_DOC], clock=lambda: NOW).poll()
    assert snap.reachable is True
    names = {s.name for s in snap.payload.servers}
    assert names == {"cloud-hub", "search-hub", "agent-mail", "mystery", "repo-local"}
    by_name = {s.name: s for s in snap.payload.servers}
    assert by_name["cloud-hub"].state == "enabled"
    assert by_name["cloud-hub"].transport == "stdio"
    assert by_name["agent-mail"].state == "disabled"
    assert (
        by_name["search-hub"].state == "conflict"
    )  # declared in user, disabled in project
    assert by_name["mystery"].transport == "unknown"
    assert by_name["repo-local"].transport == "sse"
    # health is never probed, so every liveness column stays UNMEASURED
    assert all(
        s.tool_count is None and s.last_error is None for s in snap.payload.servers
    )
    assert snap.age_s is None
    assert "health not measured" in snap.headline
    # a conflict is an error state, so an operator is told rather than shown a guess
    assert snap.state is SourceState.ERROR


def test_poll_skips_absent_documents_and_stays_reachable():
    snap = McpSource(
        paths=["/absent", USER_DOC],
        read_text=_reader({USER_DOC: '{"mcpServers": {"a": {"command": "x"}}}'}),
        clock=lambda: NOW,
    ).poll()
    assert snap.reachable is True
    # exactly one document was read, and its scope label is home-collapsed by the redactor
    assert len(snap.payload.docs_read) == 1
    assert snap.payload.docs_read[0].endswith("user-mcp.json")
    assert os.path.expanduser("~") not in snap.payload.docs_read[0]
    assert snap.state is SourceState.IDLE


def test_poll_is_unreachable_when_no_document_can_be_read():
    snap = McpSource(paths=["/absent"], read_text=_reader({}), clock=lambda: NOW).poll()
    assert snap.reachable is False and snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.payload == McpPayload()
    assert snap.error == "no MCP config document found"


def test_poll_reports_a_broken_document_as_an_error_state():
    snap = McpSource(
        paths=["d"], read_text=_reader({"d": "{oops"}), clock=lambda: NOW
    ).poll()
    assert snap.state is SourceState.ERROR
    assert snap.payload.problems and snap.payload.servers == ()


def test_poll_never_raises_and_retains_the_last_good_payload():
    calls = {"n": 0}

    def _flaky(_path: str) -> str | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"mcpServers": {"kept": {"command": "x"}}}'
        raise OSError("locked\x1b[2J")

    src = McpSource(paths=["d"], read_text=_flaky, clock=lambda: NOW)
    good = src.poll()
    bad = src.poll()
    assert good.payload.servers[0].name == "kept"
    assert bad.reachable is False and bad.payload is good.payload
    assert bad.error is not None and "\x1b" not in bad.error


def test_default_paths_are_used_when_none_are_supplied():
    src = McpSource(read_text=lambda _p: None, clock=lambda: NOW)
    assert src.poll().state is SourceState.UNREACHABLE


# ───────────────────────────── contract surface ─────────────────────────────
def test_mcp_source_satisfies_the_monitor_source_protocol():
    assert isinstance(McpSource(), MonitorSource)


def test_render_native_falls_back_to_the_headline_when_nothing_is_declared():
    src = McpSource(paths=["d"], read_text=_reader({"d": "{}"}), clock=lambda: NOW)
    snap = src.poll()
    assert src.render_native(snap) == snap.headline


def test_render_native_lists_the_servers():
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    text = src.render_native(src.poll())
    assert isinstance(text, str) and "cloud-hub" in text


def test_export_model_emits_an_inventory_table_that_prints_unmeasured_tools():
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    doc = src.export_model(src.poll())
    assert doc.title == "mcp"
    (section,) = doc.blocks
    (table,) = section.children  # pyright: ignore[reportAttributeAccessIssue]
    assert table.headers[-1] == "tools"
    assert {row[-1] for row in table.rows} == {"?"}
    assert dict(doc.rollup)["total"] == 4
    assert doc.active is False


def test_export_model_prints_a_measured_tool_count_when_one_is_supplied():
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    snap = src.poll()
    measured = McpPayload(servers=(McpServer(name="a", tool_count=3),))
    doc = src.export_model(
        type(snap)(
            source_id=snap.source_id,
            ts=snap.ts,
            reachable=True,
            stale=False,
            state=SourceState.IDLE,
            headline=snap.headline,
            payload=measured,
        )
    )
    (section,) = doc.blocks
    (table,) = section.children  # pyright: ignore[reportAttributeAccessIssue]
    assert table.rows[0][-1] == "3"


def test_headline_is_the_poll_time_one_liner():
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    snap = src.poll()
    assert src.headline(snap) == snap.headline


def test_alert_classifies_error_unreachable_and_healthy():
    broken = McpSource(
        paths=["d"], read_text=_reader({"d": "{oops"}), clock=lambda: NOW
    )
    critical = broken.alert(broken.poll())
    assert critical is not None and critical.level == "critical"

    absent = McpSource(paths=["d"], read_text=_reader({}), clock=lambda: NOW)
    warn = absent.alert(absent.poll())
    assert warn is not None and warn.level == "warn"

    healthy = McpSource(paths=["d"], read_text=_reader({"d": "{}"}), clock=lambda: NOW)
    assert healthy.alert(healthy.poll()) is None


def test_an_unexpected_server_state_still_tallies_without_a_keyerror():
    class _Odd(McpServer):
        @property
        def state(self) -> str:
            return "mystery"

    src = McpSource(paths=["d"], read_text=_reader({"d": "{}"}), clock=lambda: NOW)
    snap = src.poll()
    doc = src.export_model(
        type(snap)(
            source_id=snap.source_id,
            ts=snap.ts,
            reachable=True,
            stale=False,
            state=SourceState.IDLE,
            headline="h",
            payload=McpPayload(servers=(_Odd(name="a"),)),
        )
    )
    assert dict(doc.rollup)["total"] == 1
