"""The three non-negotiables: dry-run default, round-trip preservation, backup first."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcpctl.scopes import ScopeId
from mcpctl.sources import SourcePaths, load_sources, source_paths
from mcpctl.topology import Topology, build_topology

from mcpapply import plan as P
from mcpapply.apply import (
    ApplyResult,
    MemoryFileStore,
    RealFileStore,
    _serialise,
    apply_edits_to_doc,
    apply_plan,
    line_ending,
    render_result,
)
from conftest import FIXED_NOW, PROJECT_KEY, STAMP, write_home


def _plan(top: Topology, *changes: P.Change) -> P.Plan:
    return P.build_plan(list(changes), project_key=PROJECT_KEY)


def _reload(paths: SourcePaths) -> Topology:
    docs, _ = load_sources(paths)
    return build_topology(docs, project_key=PROJECT_KEY)


# --------------------------------------------------------------------------
# 1. DRY RUN IS THE DEFAULT
# --------------------------------------------------------------------------


def test_the_default_is_dry_run_and_nothing_reaches_disk(
    home: Path, paths: SourcePaths
):
    """The DEFAULT PARAMETER VALUE is the safety contract; assert it directly."""
    before = {label: p.read_text(encoding="utf-8") for label, p in paths.as_tuple()}
    top = _reload(paths)
    store = MemoryFileStore()
    result = apply_plan(
        _plan(top, P.plan_disable(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        # NOTE: `apply` is deliberately NOT passed.
    )
    assert result.dry_run is True
    assert result.written == ()
    assert result.backups == ()
    assert store.writes == []
    after = {label: p.read_text(encoding="utf-8") for label, p in paths.as_tuple()}
    assert after == before
    assert list(home.glob("**/*.bak")) == []


def test_the_dry_run_still_shows_the_exact_diff(paths: SourcePaths):
    top = _reload(paths)
    result = apply_plan(
        _plan(top, P.plan_disable(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
    )
    (change,) = result.file_changes
    assert change.changed is True
    assert change.label == "claude_json"
    assert '+        "cloud-hub"' in change.diff
    assert "DRY RUN" in render_result(result)


# --------------------------------------------------------------------------
# 2. ROUND-TRIP PRESERVATION
# --------------------------------------------------------------------------


def test_every_unknown_key_survives_an_apply_byte_for_byte(paths: SourcePaths):
    """Load a config full of keys this tool has never heard of, change one thing,
    and assert everything else is identical -- including nesting and ordering."""
    original = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    top = _reload(paths)
    apply_plan(
        _plan(top, P.plan_disable(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    updated = json.loads(paths.claude_json.read_text(encoding="utf-8"))

    # Revert ONLY the intended mutation, then demand exact equality.
    updated["projects"][PROJECT_KEY]["disabledMcpServers"].remove("cloud-hub")
    assert updated == original
    assert list(updated) == list(original)
    assert list(updated["projects"]) == list(original["projects"])
    assert updated["oauthAccount"] == {
        "emailAddress": "owner@example.invalid",
        "keep": "me",
    }
    assert updated["projects"][PROJECT_KEY]["history"] == [{"display": "keep this too"}]


def test_a_key_the_tool_has_never_heard_of_survives_in_every_touched_file(
    tmp_path: Path,
):
    paths = write_home(
        tmp_path,
        claude_json={
            "mcpServers": {"a": {"command": "x"}},
            "éxotic☃": {"deep": {"deeper": [None, True, 1.5]}},
        },
    )
    top = _reload(paths)
    apply_plan(
        _plan(top, P.plan_disable(top, "a")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    updated = json.loads(paths.claude_json.read_text(encoding="utf-8"))
    assert updated["éxotic☃"] == {"deep": {"deeper": [None, True, 1.5]}}


def test_apply_edits_to_doc_never_mutates_its_input():
    doc = {"disabledMcpServers": ["keep"], "other": {"nested": 1}}
    edit = P.Edit(
        scope=ScopeId.CLAUDE_USER_DISABLED,
        label="claude_json",
        key_path=("disabledMcpServers",),
        op=P.Op.LIST_ADD,
        server="added",
    )
    updated, problems = apply_edits_to_doc(doc, [edit])
    assert problems == ()
    assert updated["disabledMcpServers"] == ["keep", "added"]
    assert doc["disabledMcpServers"] == ["keep"]


def test_adding_a_name_already_present_is_a_no_op():
    doc = {"disabledMcpServers": ["dup"]}
    edit = P.Edit(
        scope=ScopeId.CLAUDE_USER_DISABLED,
        label="claude_json",
        key_path=("disabledMcpServers",),
        op=P.Op.LIST_ADD,
        server="dup",
    )
    updated, _ = apply_edits_to_doc(doc, [edit])
    assert updated["disabledMcpServers"] == ["dup"]


def test_a_missing_intermediate_row_is_created_not_clobbered():
    doc: dict[str, object] = {"projects": {"other": {"keep": 1}}}
    edit = P.Edit(
        scope=ScopeId.CLAUDE_PROJECT_DISABLED,
        label="claude_json",
        key_path=("projects", "fresh", "disabledMcpServers"),
        op=P.Op.LIST_ADD,
        server="s",
    )
    updated, problems = apply_edits_to_doc(doc, [edit])
    assert problems == ()
    assert updated["projects"] == {
        "other": {"keep": 1},
        "fresh": {"disabledMcpServers": ["s"]},
    }


# --------------------------------------------------------------------------
# `deniedMcpServers` holds OBJECTS
# --------------------------------------------------------------------------


def test_removing_a_denial_matches_the_object_shape_not_a_bare_string():
    doc = {
        "deniedMcpServers": [
            {"serverName": "target"},
            {"serverName": "other"},
            "target",
            42,
        ]
    }
    edit = P.Edit(
        scope=ScopeId.SETTINGS_DENIED,
        label="settings",
        key_path=("deniedMcpServers",),
        op=P.Op.LIST_REMOVE,
        server="target",
    )
    updated, problems = apply_edits_to_doc(doc, [edit])
    assert problems == ()
    assert updated["deniedMcpServers"] == [{"serverName": "other"}, 42]


# --------------------------------------------------------------------------
# Malformed documents degrade; they are never clobbered
# --------------------------------------------------------------------------


def test_a_wrong_typed_container_is_reported_and_skipped_never_overwritten():
    doc = {"disabledMcpServers": "not-a-list", "mcpServers": "also-not-a-map"}
    edits = [
        P.Edit(
            scope=ScopeId.CLAUDE_USER_DISABLED,
            label="claude_json",
            key_path=("disabledMcpServers",),
            op=P.Op.LIST_ADD,
            server="s",
        ),
        P.Edit(
            scope=ScopeId.CLAUDE_USER_DISABLED,
            label="claude_json",
            key_path=("disabledMcpServers",),
            op=P.Op.LIST_REMOVE,
            server="s",
        ),
        P.Edit(
            scope=ScopeId.CLAUDE_USER,
            label="claude_json",
            key_path=("mcpServers",),
            op=P.Op.MAP_SET,
            server="s",
            spec={"command": "x"},
        ),
        P.Edit(
            scope=ScopeId.CLAUDE_USER,
            label="claude_json",
            key_path=("mcpServers",),
            op=P.Op.MAP_DELETE,
            server="s",
        ),
    ]
    updated, problems = apply_edits_to_doc(doc, edits)
    assert len(problems) == 4
    assert updated == doc


def test_a_non_mapping_on_the_walk_is_reported_and_skipped():
    doc = {"projects": "a string where the map should be"}
    edit = P.Edit(
        scope=ScopeId.CLAUDE_PROJECT_DISABLED,
        label="claude_json",
        key_path=("projects", "k", "disabledMcpServers"),
        op=P.Op.LIST_ADD,
        server="s",
    )
    updated, problems = apply_edits_to_doc(doc, [edit])
    assert "projects is a str, not an object" in problems[0]
    assert updated == doc


def test_absent_containers_make_remove_and_delete_no_ops():
    updated, problems = apply_edits_to_doc(
        {},
        [
            P.Edit(
                scope=ScopeId.CLAUDE_USER_DISABLED,
                label="l",
                key_path=("disabledMcpServers",),
                op=P.Op.LIST_REMOVE,
                server="s",
            ),
            P.Edit(
                scope=ScopeId.CLAUDE_USER,
                label="l",
                key_path=("mcpServers",),
                op=P.Op.MAP_DELETE,
                server="s",
            ),
        ],
    )
    assert problems == ()
    assert updated == {}


def test_map_set_creates_the_container_when_absent():
    updated, problems = apply_edits_to_doc(
        {},
        [
            P.Edit(
                scope=ScopeId.CLAUDE_USER,
                label="l",
                key_path=("mcpServers",),
                op=P.Op.MAP_SET,
                server="s",
                spec={"command": "x"},
            )
        ],
    )
    assert problems == ()
    assert updated == {"mcpServers": {"s": {"command": "x"}}}


def test_map_set_with_no_spec_writes_an_empty_object():
    updated, _ = apply_edits_to_doc(
        {"mcpServers": {}},
        [
            P.Edit(
                scope=ScopeId.CLAUDE_USER,
                label="l",
                key_path=("mcpServers",),
                op=P.Op.MAP_SET,
                server="s",
            )
        ],
    )
    assert updated == {"mcpServers": {"s": {}}}


def test_an_unparseable_target_is_refused_not_rewritten(tmp_path: Path):
    paths = write_home(tmp_path)
    paths.claude_json.write_text("{ this is not json", encoding="utf-8")
    top = build_topology(load_sources(paths)[0], project_key=PROJECT_KEY)
    result = apply_plan(
        P.build_plan(
            [P.plan_add(top, "n", {"command": "x"}, scope=ScopeId.CLAUDE_USER)],
            project_key=PROJECT_KEY,
        ),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert any("unparseable JSON" in p for p in result.problems)
    assert paths.claude_json.read_text(encoding="utf-8") == "{ this is not json"


def test_a_non_object_top_level_is_refused(tmp_path: Path):
    paths = write_home(tmp_path)
    paths.mcp_json.write_text("[1, 2, 3]", encoding="utf-8")
    top = build_topology(load_sources(paths)[0], project_key=PROJECT_KEY)
    result = apply_plan(
        P.build_plan(
            [P.plan_add(top, "n", {"command": "x"}, scope=ScopeId.MCP_JSON)],
            project_key=PROJECT_KEY,
        ),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert any("top level is not an object" in p for p in result.problems)
    assert paths.mcp_json.read_text(encoding="utf-8") == "[1, 2, 3]"


# --------------------------------------------------------------------------
# 3. BACKUP BEFORE WRITE
# --------------------------------------------------------------------------


def test_a_backup_is_taken_first_and_restores_the_original_exactly(paths: SourcePaths):
    original = paths.claude_json.read_bytes()
    top = _reload(paths)
    result = apply_plan(
        _plan(top, P.plan_disable(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.dry_run is False
    (record,) = result.backups
    backup = Path(record.backup)
    assert backup.name == f".claude.json.mcpapply-{STAMP}.bak"
    assert backup.read_bytes() == original
    assert record.size_bytes == len(original)
    assert paths.claude_json.read_bytes() != original

    # The printed restore command is REAL: run its effect and get the original back.
    assert "Copy-Item" in result.restore
    assert "cp --" in result.restore
    paths.claude_json.write_bytes(backup.read_bytes())
    assert paths.claude_json.read_bytes() == original


def test_a_newly_created_file_gets_no_backup_but_is_still_written(tmp_path: Path):
    paths = write_home(tmp_path, mcp_json=None)
    assert not paths.mcp_json.exists()
    top = build_topology(load_sources(paths)[0], project_key=PROJECT_KEY)
    result = apply_plan(
        P.build_plan(
            [P.plan_add(top, "fresh", {"command": "x"}, scope=ScopeId.MCP_JSON)],
            project_key=PROJECT_KEY,
        ),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.backups == ()
    assert result.file_changes[0].created is True
    assert json.loads(paths.mcp_json.read_text(encoding="utf-8"))["mcpServers"] == {
        "fresh": {"command": "x"}
    }
    assert "no backup was taken" in result.restore


def test_the_write_is_refused_when_the_file_moved_since_the_preview():
    """A running host rewrites ~/.claude.json constantly; writing stale bytes would
    silently revert whatever it just did."""
    paths = source_paths(Path("/h"))
    quiet = json.dumps({"mcpServers": {}})
    store = MemoryFileStore({str(paths.claude_json): quiet})
    top = build_topology(
        load_sources(paths, read_text=store.read_text)[0], project_key=None
    )
    change = P.plan_add(top, "n", {"command": "x"}, scope=ScopeId.CLAUDE_USER)

    class Racing(MemoryFileStore):
        """Another writer lands between the preview read and the pre-write re-read."""

        def read_text(self, path: Path) -> str:
            text = super().read_text(path)
            self.files[str(path)] = json.dumps({"mcpServers": {}, "raced": True})
            return text

    racing = Racing({str(paths.claude_json): quiet})
    result = apply_plan(
        P.build_plan([change], project_key=None),
        paths=paths,
        store=racing,
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert any("changed on disk" in p and "REFUSED" in p for p in result.problems)
    assert result.written == ()
    assert racing.writes == []


def test_a_refusing_guard_blocks_the_write_and_keeps_the_preview(paths: SourcePaths):
    top = _reload(paths)
    before = paths.claude_json.read_bytes()
    result = apply_plan(
        _plan(top, P.plan_disable(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "a host session is running\x1b[31m",
    )
    assert result.dry_run is True
    # strip_controls removed the ESC byte; the residual literal text is harmless.
    assert result.blocked == "a host session is running[31m"
    assert "" not in result.blocked
    assert result.written == ()
    assert paths.claude_json.read_bytes() == before
    assert "BLOCKED:" in render_result(result)


def test_a_plan_that_changes_nothing_writes_nothing(paths: SourcePaths):
    top = _reload(paths)
    result = apply_plan(
        _plan(top, P.plan_disable(top, "chrome-devtools")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.written == ()
    assert result.file_changes == ()


def test_a_live_only_plan_produces_no_file_changes_at_all(paths: SourcePaths):
    top = _reload(paths)
    result = apply_plan(
        _plan(top, P.plan_reconnect(top, "cloud-hub")),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.file_changes == ()
    assert result.written == ()


def test_a_no_op_edit_is_reported_as_unchanged(paths: SourcePaths):
    """Disabling a name already in the ROOT list still resolves as a change request,
    but the serialised document is identical, so nothing is written."""
    top = _reload(paths)
    change = P.Change(
        intent=P.Intent.DISABLE,
        server="ghidra-mcp",
        edits=(
            P.Edit(
                scope=ScopeId.CLAUDE_USER_DISABLED,
                label="claude_json",
                key_path=("disabledMcpServers",),
                op=P.Op.LIST_ADD,
                server="ghidra-mcp",
            ),
        ),
    )
    result = apply_plan(
        _plan(top, change),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert result.file_changes[0].changed is False
    assert result.written == ()
    assert "unchanged" in render_result(result)


# --------------------------------------------------------------------------
# The production store, exercised for real against tmp_path
# --------------------------------------------------------------------------


def test_the_real_store_lands_content_atomically_and_leaves_no_temp(tmp_path: Path):
    store = RealFileStore()
    target = tmp_path / "t.json"
    assert store.exists(target) is False
    target.write_text('{"a": 1}', encoding="utf-8")
    assert store.exists(target) is True
    assert store.read_text(target) == '{"a": 1}'
    store.write_text(target, '{"a": 2}')
    assert target.read_text(encoding="utf-8") == '{"a": 2}'
    assert list(tmp_path.glob("*.tmp")) == []
    size = store.copy_file(target, tmp_path / "t.bak")
    assert (tmp_path / "t.bak").read_text(encoding="utf-8") == '{"a": 2}'
    assert size == len('{"a": 2}')


def test_the_memory_store_mirrors_the_real_one():
    one, two = Path("/a"), Path("/b")
    store = MemoryFileStore({str(one): "one"})
    assert store.exists(one) is True
    assert store.exists(two) is False
    assert store.read_text(one) == "one"
    store.write_text(two, "two")
    assert store.writes == [str(two)]
    assert store.copy_file(two, Path("/b.bak")) == 3
    missing = Path("/missing")
    with pytest.raises(FileNotFoundError, match="missing"):
        store.read_text(missing)


def test_a_file_without_a_trailing_newline_keeps_that_convention(tmp_path: Path):
    paths = write_home(tmp_path)
    paths.claude_json.write_text(
        json.dumps({"mcpServers": {"a": {"command": "x"}}}, indent=2), encoding="utf-8"
    )
    top = build_topology(load_sources(paths)[0], project_key=None)
    apply_plan(
        P.build_plan([P.plan_disable(top, "a")], project_key=None),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    assert not paths.claude_json.read_text(encoding="utf-8").endswith("\n")


def test_the_diff_masks_a_credential_that_rides_along_in_context(tmp_path: Path):
    """A diff window can catch a neighbouring env value; it must not print it."""
    # PLACEHOLDER, assembled at runtime so no credential-shaped literal is committed.
    fake_pat = "gh" + "p_" + ("0123456789" * 4)[:36]
    paths = write_home(
        tmp_path,
        claude_json={"mcpServers": {"a": {"command": "x", "env": {"T": fake_pat}}}},
    )
    top = build_topology(load_sources(paths)[0], project_key=None)
    result = apply_plan(
        # An EDIT rewrites the spec object, so the env line lands inside the diff hunk.
        P.build_plan([P.plan_edit(top, "a", {"command": "y"})], project_key=None),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
    )
    blob = json.dumps(result.to_dict())
    assert fake_pat not in blob
    assert "[REDACTED:gh-pat]" in blob


def test_result_to_dict_carries_every_field():
    payload = ApplyResult(dry_run=True, problems=("p",)).to_dict()
    assert payload["dry_run"] is True
    assert payload["problems"] == ["p"]
    assert payload["restore"].startswith("no backup")


def test_the_files_own_line_endings_survive_a_write(tmp_path: Path):
    """MEASURED on this box: ~/.claude.json and settings.json are LF but ~/.mcp.json is
    CRLF. Writing LF unconditionally would rewrite that whole file to change nothing but
    its line endings."""
    paths = write_home(tmp_path)
    crlf = json.dumps({"mcpServers": {}}, indent=2).replace("\n", "\r\n") + "\r\n"
    paths.mcp_json.write_text(crlf, encoding="utf-8", newline="")
    top = build_topology(load_sources(paths)[0], project_key=None)
    apply_plan(
        P.build_plan(
            [P.plan_add(top, "n", {"command": "x"}, scope=ScopeId.MCP_JSON)],
            project_key=None,
        ),
        paths=paths,
        store=RealFileStore(),
        now=FIXED_NOW,
        apply=True,
        guard=lambda: "",
    )
    written = paths.mcp_json.read_text(encoding="utf-8", newline="")
    assert "\r\n" in written
    assert "\n" not in written.replace("\r\n", "")


def test_line_ending_detects_both_conventions():
    assert line_ending('{\r\n  "a": 1\r\n}') == "\r\n"
    assert line_ending('{\n  "a": 1\n}') == "\n"
    assert line_ending("") == "\n"


def test_the_writer_round_trips_a_real_shaped_config_byte_for_byte(tmp_path: Path):
    """The identity property the diff quality rests on: serialising an UNCHANGED
    document must reproduce the original bytes, so an apply's diff shows only the edit.
    Verified read-only against the live ~/.claude.json (236,130 B) and settings.json
    (23,242 B) on 2026-07-27: both IDENTICAL."""
    original = (
        json.dumps(
            {
                "numStartups": 374,
                "oauthAccount": {"emailAddress": "o@example.invalid"},
                "mcpServers": {"a": {"command": "x", "args": ["-m", "a"]}},
                "unicode": "café ☃",
                "projects": {"C:/w": {"disabledMcpServers": ["a"], "history": []}},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    target = tmp_path / ".claude.json"
    target.write_text(original, encoding="utf-8", newline="")
    doc = json.loads(original)
    rebuilt = _serialise(doc, trailing_newline=True, newline=line_ending(original))
    assert rebuilt == original
