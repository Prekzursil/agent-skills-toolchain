"""Tests for the one thin filesystem shim.

The reader is injected, so the parsing/collection logic is exercised without touching
disk. One test at the bottom deliberately binds the REAL default reader against
``tmp_path`` -- a seam-only suite would leave the production default unproven, which is
a measured failure mode in this repo.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcpctl import sources


def fake_reader(files: dict[str, str]):
    def _read(path: Path) -> str:
        try:
            return files[str(path).replace("\\", "/")]
        except KeyError as exc:
            raise FileNotFoundError(str(path)) from exc

    return _read


def test_source_paths_names_all_five_scopes_under_the_given_home():
    paths = sources.source_paths(Path("H:/home"))
    assert paths.claude_json == Path("H:/home/.claude.json")
    assert paths.mcp_json == Path("H:/home/.mcp.json")
    assert paths.settings == Path("H:/home/.claude/settings.json")
    assert paths.settings_local == Path("H:/home/.claude/settings.local.json")
    assert paths.disabled_defaults == Path(
        "H:/home/.claude/.mcp-disabled-defaults.json"
    )


def test_as_tuple_exposes_label_path_pairs_for_every_scope():
    labels = [label for label, _ in sources.source_paths(Path("H:/home")).as_tuple()]
    assert labels == [
        "claude_json",
        "mcp_json",
        "settings",
        "settings_local",
        "disabled_defaults",
    ]


def test_load_sources_parses_every_present_file():
    paths = sources.source_paths(Path("H:/home"))
    files = {
        "H:/home/.claude.json": json.dumps({"mcpServers": {"a": {"command": "c"}}}),
        "H:/home/.mcp.json": json.dumps({"mcpServers": {"b": {"command": "c"}}}),
        "H:/home/.claude/settings.json": json.dumps({"deniedMcpServers": []}),
        "H:/home/.claude/settings.local.json": json.dumps(
            {"enabledMcpjsonServers": []}
        ),
        "H:/home/.claude/.mcp-disabled-defaults.json": json.dumps(
            {"disabledMcpServers": ["z"]}
        ),
    }
    docs, problems = sources.load_sources(paths, read_text=fake_reader(files))
    assert problems == ()
    assert isinstance(docs.claude_json, dict)
    assert docs.disabled_defaults == {"disabledMcpServers": ["z"]}


def test_an_absent_file_is_not_a_problem_it_is_just_absent():
    paths = sources.source_paths(Path("H:/home"))
    docs, problems = sources.load_sources(paths, read_text=fake_reader({}))
    assert problems == ()
    assert docs.claude_json is None
    assert docs.settings is None


def test_an_unparseable_file_is_reported_as_a_problem_and_left_none():
    paths = sources.source_paths(Path("H:/home"))
    files = {"H:/home/.claude.json": "{ not json"}
    docs, problems = sources.load_sources(paths, read_text=fake_reader(files))
    assert docs.claude_json is None
    assert len(problems) == 1
    assert problems[0].label == "claude_json"
    assert "JSONDecodeError" in problems[0].reason


def test_a_json_document_that_is_not_an_object_is_a_problem():
    paths = sources.source_paths(Path("H:/home"))
    files = {"H:/home/.mcp.json": "[1, 2, 3]"}
    docs, problems = sources.load_sources(paths, read_text=fake_reader(files))
    assert docs.mcp_json is None
    assert problems[0].label == "mcp_json"
    assert "top level" in problems[0].reason


def test_an_unreadable_file_is_reported_rather_than_raised():
    def denying_reader(path: Path) -> str:
        raise PermissionError(str(path))

    paths = sources.source_paths(Path("H:/home"))
    docs, problems = sources.load_sources(paths, read_text=denying_reader)
    assert docs.claude_json is None
    assert len(problems) == 5
    assert all("PermissionError" in p.reason for p in problems)


def test_a_problem_reason_is_control_stripped_and_home_collapsed():
    def hostile_reader(path: Path) -> str:
        raise OSError("bad \x1b]0;pwn\x07 at C:/Users/bob/f")

    paths = sources.source_paths(Path("H:/home"))
    _docs, problems = sources.load_sources(paths, read_text=hostile_reader)
    assert "\x1b" not in problems[0].reason
    assert "bob" not in problems[0].reason


def test_load_sources_binds_the_real_reader_by_default(tmp_path: Path):
    """Real default binding: no injected reader, real files, real Path.read_text."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"mcpServers": {"real": {"command": "c"}}, "disabledMcpServers": []}
        ),
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"deniedMcpServers": [{"serverName": "nope"}]}), encoding="utf-8"
    )
    docs, problems = sources.load_sources(sources.source_paths(tmp_path))
    assert problems == ()
    assert isinstance(docs.claude_json, dict)
    assert docs.claude_json["mcpServers"] == {"real": {"command": "c"}}
    assert docs.mcp_json is None


def test_default_home_and_project_key_come_from_the_environment_shim():
    home = sources.default_home()
    assert home.is_absolute()
    key = sources.project_key_for(Path("C:/a/b"))
    assert key == "C:/a/b"
