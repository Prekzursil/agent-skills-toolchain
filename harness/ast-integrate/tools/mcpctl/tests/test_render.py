"""Tests for the pure text renderers."""

from __future__ import annotations

from mcpctl import matrix, render, topology

FAKE_TOKEN = "ghp_" + "M" * 36


def rows() -> tuple[matrix.Row, ...]:
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {
                    "alpha": {"command": "node", "env": {"ALPHA_TOKEN": FAKE_TOKEN}},
                    "beta": {"type": "sse", "url": "https://x.invalid"},
                },
                "disabledMcpServers": ["beta"],
            },
            settings={"deniedMcpServers": [{"serverName": "gamma"}]},
        ),
        project_key=None,
    )
    return matrix.build_rows(
        top, liveness={"alpha": matrix.Liveness(tool_count=9, pid=7, rss_bytes=2048)}
    )


def test_render_matrix_has_a_header_and_one_line_per_row():
    text = render.render_matrix(rows())
    lines = text.splitlines()
    assert lines[0].split() == [
        "SERVER",
        "STATE",
        "TRANSPORT",
        "TOOLS",
        "SCOPES",
        "BASIS",
    ]
    # Body = everything between the rule and the blank line that precedes the legend.
    body = lines[2 : lines.index("", 2)]
    assert len(body) == 3
    assert body[0].startswith("alpha")
    assert body[1].startswith("beta")
    assert body[2].startswith("gamma")
    assert lines[-1].startswith("~ = inferred")


def test_render_matrix_shows_a_dash_for_an_unmeasured_tool_count():
    text = render.render_matrix(rows())
    beta = next(ln for ln in text.splitlines() if ln.startswith("beta"))
    assert " - " in f" {beta.split()[3]} "


def test_render_matrix_never_prints_a_credential_value():
    text = render.render_matrix(rows())
    assert FAKE_TOKEN not in text


def test_render_matrix_marks_an_inferred_state():
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {"x": {"command": "c"}},
                "disabledMcpServers": ["x"],
                "projects": {"P": {"disabledMcpServers": ["x"]}},
            }
        ),
        project_key="P",
    )
    text = render.render_matrix(matrix.build_rows(top, liveness={}))
    assert "~" in text.splitlines()[2], "an inferred state must be visually marked"


def test_render_matrix_of_no_rows_says_so_rather_than_printing_a_bare_header():
    assert "no MCP servers found" in render.render_matrix(())


def test_render_credentials_lists_names_and_kinds_only():
    text = render.render_credentials(rows())
    assert "alpha" in text
    assert "ALPHA_TOKEN" in text
    assert "present" in text
    assert FAKE_TOKEN not in text


def test_render_credentials_says_so_when_no_row_declares_an_env_block():
    top = topology.build_topology(
        topology.SourceDocs(claude_json={"mcpServers": {"a": {"command": "c"}}}),
        project_key=None,
    )
    text = render.render_credentials(matrix.build_rows(top, liveness={}))
    assert "no env-bearing" in text


def test_render_conflicts_lists_each_note_under_its_server():
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
    text = render.render_conflicts(matrix.build_rows(top, liveness={}))
    assert text.splitlines()[0].startswith("g")
    assert "MEASURED" in text


def test_render_conflicts_is_explicit_when_there_are_none():
    assert "no scope conflicts" in render.render_conflicts(rows())


def test_render_topology_reports_every_scope_and_the_project_row_status():
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {"a": {"command": "c"}},
                "disabledMcpServers": ["b"],
            },
            settings={"deniedMcpServers": [{"serverName": "d"}]},
            settings_local={
                "enabledMcpjsonServers": ["e"],
                "enableAllProjectMcpServers": False,
            },
        ),
        project_key="C:/nope",
    )
    text = render.render_topology(top)
    assert "claude-user" in text
    assert "settings-denied" in text
    assert "project row: NOT FOUND" in text
    assert "C:/nope" in text
    assert "enableAllProjectMcpServers: False" in text


def test_render_topology_reports_a_found_project_row():
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={"projects": {"P": {"disabledMcpServers": ["z"]}}}
        ),
        project_key="P",
    )
    assert "project row: FOUND" in render.render_topology(top)


def test_render_topology_states_the_precedence_order():
    text = render.render_topology(
        topology.build_topology(topology.SourceDocs(), project_key=None)
    )
    assert "settings-denied > claude-project-disabled > claude-user-disabled" in text


def test_render_matrix_truncates_an_absurdly_long_server_name_without_breaking_columns():
    top = topology.build_topology(
        topology.SourceDocs(claude_json={"mcpServers": {"n" * 200: {"command": "c"}}}),
        project_key=None,
    )
    line = render.render_matrix(matrix.build_rows(top, liveness={})).splitlines()[2]
    assert len(line) < 200
    assert line.startswith("n" * 10)
