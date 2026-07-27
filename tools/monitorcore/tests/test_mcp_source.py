"""Tests for ``monitorcore.mcp_source`` — the MCP inventory adapter, 100% line+branch.

Hermetic: the "live" path reads COMMITTED config fixtures off disk through the real
:func:`~monitorcore.mcp_source.read_config`; every other path uses an injected reader. No MCP
handshake, no socket, no process table — which is precisely the property under test, since
every health column must stay ``None`` == not measured.

The fixture set deliberately covers the two scope SHAPES a naive reader misses, because
missing either one silently paints a suppressed server ``enabled``:

* ``settings-denied.json`` — ``deniedMcpServers`` holds ``{"serverName": ...}`` OBJECTS.
* ``project-scope/.mcp.json`` — a project-scope definition, which is only live once it is
  approved (``enabledMcpjsonServers`` / ``enableAllProjectMcpServers``).
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
    resolve,
    transport_of,
)

NOW = 1_784_283_000.0
FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
USER_DOC = str(FIXTURES / "user-mcp.json")
PROJECT_DOC = str(FIXTURES / "project-mcp.json")
DENIED_DOC = str(FIXTURES / "settings-denied.json")
LOCAL_DOC = str(FIXTURES / "settings-local.json")
PROJECT_SCOPE_DOC = str(FIXTURES / "project-scope" / ".mcp.json")


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
    assert doc.project_scope is False


def test_parse_doc_reports_unparsable_json_as_a_problem_carrying_the_scope():
    doc = parse_doc("user", "{not json")
    assert doc.declared == ()
    assert doc.problem.startswith("user: unparsable json")


def test_parse_doc_reports_a_non_object_document():
    assert parse_doc("user", "[1, 2]").problem == "user: not a json object"


def test_parse_doc_tolerates_a_non_dict_servers_block():
    assert parse_doc("user", '{"mcpServers": ["a"]}').declared == ()


def test_parse_doc_tolerates_a_non_list_disable_block_and_non_string_entries():
    assert parse_doc("user", '{"disabledMcpServers": "a"}').disabled == frozenset()
    assert parse_doc("user", '{"disabledMcpServers": ["a", 7]}').disabled == frozenset(
        {"a"}
    )


def test_parse_doc_reads_denied_servers_which_are_OBJECTS_not_strings():
    """The shape that blinds a ``list[str]`` reader: ``[{"serverName": "markitdown"}]``."""
    doc = parse_doc(
        "settings",
        '{"deniedMcpServers": [{"serverName": "a"}, {"notAName": 1}, "b", 7]}',
    )
    # objects AND bare strings are both accepted; junk elements are dropped, not raised on
    assert doc.denied == frozenset({"a", "b"})


def test_parse_doc_tolerates_a_non_list_denied_block():
    assert parse_doc("settings", '{"deniedMcpServers": {}}').denied == frozenset()


def test_parse_doc_reads_the_approval_list_and_the_enable_all_flag():
    doc = parse_doc(
        "local",
        '{"enabledMcpjsonServers": ["a"], "enableAllProjectMcpServers": true}',
    )
    assert doc.approved == frozenset({"a"}) and doc.enable_all is True


def test_parse_doc_reads_the_project_row_for_the_EXACT_cwd_only():
    text = (
        '{"projects": {"C:/proj": {"disabledMcpServers": ["mine"]},'
        ' "C:/proj/child": {"disabledMcpServers": ["theirs"]},'
        ' "bad-row": 7, "7": {}}}'
    )
    mine = parse_doc("claude", text, cwd="C:/proj")
    assert mine.project_disabled == frozenset({"mine"})
    # an ANCESTOR row must not leak into a child session, nor a child into the ancestor
    assert parse_doc("claude", text, cwd="C:/elsewhere").project_disabled == frozenset()


def test_parse_doc_matches_a_project_row_across_separator_styles():
    text = '{"projects": {"C:/proj/sub": {"disabledMcpServers": ["x"]}}}'
    assert parse_doc("claude", text, cwd="C:\\proj\\sub").project_disabled == frozenset(
        {"x"}
    )


def test_parse_doc_skips_the_project_lookup_without_a_cwd_or_a_projects_map():
    text = '{"projects": {"C:/proj": {"disabledMcpServers": ["x"]}}}'
    assert parse_doc("claude", text).project_disabled == frozenset()
    assert parse_doc("claude", '{"projects": 7}', cwd="C:/proj").project_disabled == (
        frozenset()
    )


def test_parse_doc_flags_a_dot_mcp_json_as_project_scope():
    assert parse_doc("/x/.mcp.json", "{}").project_scope is True


def test_parse_doc_scrubs_a_hostile_server_name():
    doc = parse_doc("user\x1b[2J", '{"mcpServers": {"ev\\u001bil": {}}}')
    assert "\x1b" not in doc.scope
    assert all("\x1b" not in name for name, _t in doc.declared)


def test_parse_doc_scrubs_a_hostile_scope_into_the_problem_row():
    assert "\x1b" not in parse_doc("sc\x1bope", "{oops").problem


# ───────────────────────────── resolve (the mirrored precedence) ─────────────────────────
def _resolve(**kw: object):
    base: dict[str, object] = {
        "definitions": (),
        "denied_in": (),
        "project_disabled_in": (),
        "user_disabled_in": (),
        "approved": False,
        "enable_all": False,
    }
    base.update(kw)
    return resolve(**base)  # pyright: ignore[reportArgumentType]


def test_resolve_enables_a_user_scope_definition_with_no_suppressor():
    state, basis, notes = _resolve(definitions=(("user", False),))
    assert state == "enabled" and basis == ("user:mcpServers",) and notes == ()


def test_resolve_prefers_denied_over_disabled_and_records_both_in_the_basis():
    state, basis, _notes = _resolve(
        definitions=(("user", False),), denied_in=("settings",), user_disabled_in=("u",)
    )
    assert state == "denied"
    assert basis == ("settings:deniedMcpServers", "u:disabledMcpServers")


def test_resolve_reports_a_project_disable_as_disabled():
    state, basis, _notes = _resolve(
        definitions=(("user", False),), project_disabled_in=("claude",)
    )
    assert state == "disabled"
    assert basis == ("claude:projects[cwd].disabledMcpServers",)


def test_resolve_keeps_approved_but_suppressed_as_a_NOTE_never_as_the_state():
    """The MEASURED case: ghidra-mcp / hexstrike-ai / ida-pro-mcp. Suppression wins."""
    state, _basis, notes = _resolve(
        definitions=(("user", False),), user_disabled_in=("u",), approved=True
    )
    assert state == "disabled"
    assert notes and "suppressed by" in notes[0]


def test_resolve_reports_a_name_no_scope_defines_as_undefined():
    state, basis, notes = _resolve(approved=True)
    assert state == "undefined" and basis == ()
    assert notes == ("named by a verdict scope but defined by none",)


def test_resolve_holds_an_unapproved_project_definition_at_pending_approval():
    state, _basis, notes = _resolve(definitions=(("proj", True),))
    assert state == "pending-approval" and "awaiting approval" in notes[0]


@pytest.mark.parametrize(("approved", "enable_all"), [(True, False), (False, True)])
def test_resolve_releases_a_project_definition_once_approved_or_enabled_all(
    approved: bool, enable_all: bool
):
    state, _basis, notes = _resolve(
        definitions=(("proj", True),), approved=approved, enable_all=enable_all
    )
    assert state == "enabled" and notes == ()


def test_resolve_does_not_gate_a_mixed_user_and_project_definition():
    state, _basis, _notes = _resolve(definitions=(("proj", True), ("user", False)))
    assert state == "enabled"


# ───────────────────────────── build_servers ─────────────────────────────
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


def test_build_servers_resolves_a_cross_scope_disagreement_instead_of_erroring():
    """A disable in ANY scope suppresses — that is the measured precedence, not a guess.

    The previous ``conflict`` pseudo-state made this the source's steady ERROR state on a
    correctly-curated fleet; the disagreement now rides in ``disabled_in`` for the audit.
    """
    docs = [
        DocInventory(scope="user", declared=(("a", "stdio"),)),
        DocInventory(
            scope="project", declared=(("a", "stdio"),), disabled=frozenset({"a"})
        ),
    ]
    (server,) = build_servers(docs)
    assert server.state == "disabled"
    assert server.declared_in == ("user", "project")
    assert server.disabled_in == ("project",)


def test_build_servers_marks_a_host_denied_server_denied_not_enabled():
    """The live defect: ``markitdown`` is in ``deniedMcpServers`` yet rendered ``enabled``."""
    docs = [
        DocInventory(scope="claude", declared=(("markitdown", "stdio"),)),
        DocInventory(scope="settings", denied=frozenset({"markitdown"})),
    ]
    (server,) = build_servers(docs)
    assert server.state == "denied"
    assert server.basis == ("settings:deniedMcpServers",)


def test_build_servers_surfaces_a_name_that_is_only_ever_disabled():
    docs = [DocInventory(scope="user", disabled=frozenset({"ghost"}))]
    (server,) = build_servers(docs)
    assert server.declared_in == () and server.state == "disabled"
    assert server.transport == "unknown"


def test_build_servers_surfaces_a_stale_approval_of_an_undefined_server():
    docs = [DocInventory(scope="local", approved=frozenset({"ghost"}))]
    (server,) = build_servers(docs)
    assert server.name == "ghost" and server.state == "undefined"


def test_build_servers_ignores_an_unparsable_document_entirely():
    docs = [
        DocInventory(scope="good", declared=(("a", "stdio"),)),
        DocInventory(
            scope="bad",
            problem="bad: unparsable json",
            disabled=None or frozenset({"a"}),
        ),
    ]
    (server,) = build_servers(docs)
    # the broken document neither declares nor suppresses — its contents were never read
    assert server.state == "enabled" and server.disabled_in == ()


def test_build_servers_honours_enable_all_from_any_document():
    docs = [
        DocInventory(scope="proj", declared=(("a", "stdio"),), project_scope=True),
        DocInventory(scope="local", enable_all=True),
    ]
    assert build_servers(docs)[0].state == "enabled"


def test_a_bare_server_reports_unmeasured_health_never_zero():
    server = McpServer(name="a")
    assert server.tool_count is None and server.last_error is None


# ───────────────────────────── read_config / default_paths ─────────────────────────────
def test_read_config_returns_text_and_none_for_an_absent_document(tmp_path: Path):
    present = tmp_path / "x.json"
    present.write_text("{}", encoding="utf-8")
    assert read_config(str(present)) == "{}"
    assert read_config(str(tmp_path / "absent.json")) is None


def test_default_paths_names_every_measured_scope():
    paths = default_paths(cwd=os.path.join("C:", os.sep, "elsewhere"))
    assert len(paths) == 5
    tails = [os.path.basename(p) for p in paths]
    assert tails == [
        ".mcp.json",
        ".claude.json",
        "settings.json",
        "settings.local.json",
        ".mcp.json",
    ]
    assert paths[-1] == os.path.join("C:", os.sep, "elsewhere", ".mcp.json")


def test_default_paths_deduplicates_when_the_cwd_IS_the_home_directory():
    """Reading one document twice would double-count every scope it declares."""
    paths = default_paths(cwd=os.path.expanduser("~"))
    assert len(paths) == 4
    assert len(set(os.path.normcase(p) for p in paths)) == 4


def test_default_paths_falls_back_to_the_real_cwd():
    assert default_paths()[-1] == os.path.join(os.getcwd(), ".mcp.json")


# ───────────────────────────── poll ─────────────────────────────
def test_poll_over_the_committed_fixtures_resolves_every_scope():
    snap = McpSource(
        paths=[USER_DOC, PROJECT_DOC, DENIED_DOC, LOCAL_DOC, PROJECT_SCOPE_DOC],
        clock=lambda: NOW,
    ).poll()
    assert snap.reachable is True
    by_name = {s.name: s for s in snap.payload.servers}
    assert by_name["cloud-hub"].state == "enabled"
    assert by_name["cloud-hub"].transport == "stdio"
    # disabled in the user doc AND host-denied: the denial has the higher authority
    assert by_name["agent-mail"].state == "denied"
    # declared in the user doc, disabled by the project doc -> RESOLVED, not "conflict"
    assert by_name["search-hub"].state == "disabled"
    # ...and its approval in settings.local is kept as an audit note, not as the state
    assert (
        by_name["search-hub"].notes
        and "suppressed by" in by_name["search-hub"].notes[0]
    )
    # the OBJECT-shaped host denial is read; without it this row would say "enabled"
    assert by_name["mystery"].state == "denied"
    assert by_name["mystery"].transport == "unknown"
    # a project-scope .mcp.json definition is not live until it is approved
    assert by_name["awaiting-approval"].state == "pending-approval"
    # an approval naming a server no scope defines is surfaced, not silently dropped
    assert by_name["never-declared"].state == "undefined"
    assert by_name["repo-local"].transport == "sse"
    # health is never probed, so every liveness column stays UNMEASURED
    assert all(
        s.tool_count is None and s.last_error is None for s in snap.payload.servers
    )
    assert snap.age_s is None
    assert "health not measured" in snap.headline
    # a correctly-curated fleet is NOT an error state and raises NO critical alert
    assert snap.state is SourceState.IDLE
    assert snap.error is None


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


def test_poll_is_unreachable_when_EVERY_document_found_is_unparsable():
    """Nothing was measured, so the pane must say "not measured", not "0 servers"."""
    snap = McpSource(
        paths=["a", "b"],
        read_text=_reader({"a": "{oops", "b": "[]"}),
        clock=lambda: NOW,
    ).poll()
    assert snap.reachable is False
    assert snap.payload.servers == ()
    assert snap.error is not None and "unparsable json" in snap.error


def test_poll_surfaces_a_PARTIAL_read_instead_of_silently_shrinking_the_fleet():
    """One corrupt document must not drop its servers with only a bare ``[error]`` token."""
    snap = McpSource(
        paths=["good", "broken"],
        read_text=_reader(
            {"good": '{"mcpServers": {"kept": {"command": "x"}}}', "broken": "{oops"}
        ),
        clock=lambda: NOW,
    ).poll()
    assert snap.state is SourceState.ERROR
    assert [s.name for s in snap.payload.servers] == ["kept"]
    assert snap.payload.problems and snap.payload.docs_attempted == 2
    # the count is READ/ATTEMPTED and the failure is named in the headline AND in error
    assert "configs 1/2 (1 UNREADABLE)" in snap.headline
    assert snap.error is not None and "unparsable json" in snap.error


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


def test_an_explicit_cwd_drives_the_project_row_lookup():
    text = (
        '{"mcpServers": {"a": {"command": "x"}},'
        ' "projects": {"C:/proj": {"disabledMcpServers": ["a"]}}}'
    )
    off = McpSource(
        paths=["claude"],
        cwd="C:/proj",
        read_text=_reader({"claude": text}),
        clock=lambda: NOW,
    ).poll()
    on = McpSource(
        paths=["claude"],
        cwd="C:/other",
        read_text=_reader({"claude": text}),
        clock=lambda: NOW,
    ).poll()
    assert off.payload.servers[0].state == "disabled"
    assert on.payload.servers[0].state == "enabled"


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
    assert table.headers == ("server", "state", "transport", "basis", "tools", "notes")
    assert {row[4] for row in table.rows} == {"?"}
    assert len(table.rows) == 4
    assert doc.active is False


def test_export_model_leaves_the_agent_shaped_rollup_EMPTY():
    """``enabled`` is not ``running``: nothing was probed, so no rollup is honest here."""
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    assert src.export_model(src.poll()).rollup == ()


def test_export_model_adds_a_section_naming_the_unreadable_documents():
    src = McpSource(
        paths=["good", "broken"],
        read_text=_reader({"good": '{"mcpServers": {"a": {}}}', "broken": "{oops"}),
        clock=lambda: NOW,
    )
    doc = src.export_model(src.poll())
    inventory, problems = doc.blocks
    assert inventory.anchor == "mcp-inventory"  # pyright: ignore[reportAttributeAccessIssue]
    assert problems.anchor == "mcp-problems"  # pyright: ignore[reportAttributeAccessIssue]
    (table,) = problems.children  # pyright: ignore[reportAttributeAccessIssue]
    assert "unparsable json" in table.rows[0][0]


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
    assert table.rows[0][4] == "3"


def test_headline_is_the_poll_time_one_liner():
    src = McpSource(paths=[USER_DOC], clock=lambda: NOW)
    snap = src.poll()
    assert src.headline(snap) == snap.headline


def test_alert_classifies_error_unreachable_and_healthy():
    broken = McpSource(
        paths=["good", "bad"],
        read_text=_reader({"good": "{}", "bad": "{oops"}),
        clock=lambda: NOW,
    )
    critical = broken.alert(broken.poll())
    assert critical is not None and critical.level == "critical"

    absent = McpSource(paths=["d"], read_text=_reader({}), clock=lambda: NOW)
    warn = absent.alert(absent.poll())
    assert warn is not None and warn.level == "warn"

    healthy = McpSource(paths=["d"], read_text=_reader({"d": "{}"}), clock=lambda: NOW)
    assert healthy.alert(healthy.poll()) is None


def test_a_scope_disagreement_alone_never_raises_a_critical_alert():
    """The regression this guards: 6 correctly-curated servers = a critical alert / tick."""
    src = McpSource(
        paths=["u", "p"],
        read_text=_reader(
            {
                "u": '{"mcpServers": {"a": {"command": "x"}}}',
                "p": '{"mcpServers": {"a": {"command": "x"}},'
                ' "disabledMcpServers": ["a"]}',
            }
        ),
        clock=lambda: NOW,
    )
    snap = src.poll()
    assert snap.state is SourceState.IDLE and src.alert(snap) is None


def test_an_unexpected_server_state_still_tallies_without_a_keyerror():
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
            payload=McpPayload(servers=(McpServer(name="a", state="mystery"),)),
        )
    )
    (section,) = doc.blocks
    (table,) = section.children  # pyright: ignore[reportAttributeAccessIssue]
    assert table.rows[0][1] == "mystery"
