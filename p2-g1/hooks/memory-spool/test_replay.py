#!/usr/bin/env python3
"""Unit tests for memory-spool/replay.py -- argv construction + replay/clear/skip logic.

No basic-memory install required: the CLI shell-out (replay._run) is mocked.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent


def _load_isolated():
    """Load THIS dir's `_common` + `replay`, immune to a sibling hook's `_common`.

    Six hook dirs each ship a DIFFERENT `_common.py` and import it by the bare name
    `_common` -- a single flat key in `sys.modules`. Whichever suite pytest collects
    first therefore binds `_common` for the whole process, so a plain `import _common`
    here silently returned another hook's module. Measured on Linux with the full
    `hooks/` tree: `AttributeError: module '_common' has no attribute 'payload_key'`
    (and `bg-registry`'s module even acquires a stray `SPOOL_DIR`, because
    `test_memory_spool.py` assigns onto whatever `_common` it was handed).

    Production is already immune: `_dispatch/dispatch.py` pops these shared names
    before each in-process hook import (`_SHARED_NAMES`). This mirrors that isolation
    rather than depending on collection order.

    `replay.py` runs its own top-level `import _common as C`, so `_common` must resolve
    to OUR instance while replay executes; the previous binding is restored afterwards
    so this suite never poisons a sibling in turn.
    """
    prev = sys.modules.get("_common")
    had_prev = "_common" in sys.modules
    try:
        cspec = importlib.util.spec_from_file_location("_common", THIS / "_common.py")
        common = importlib.util.module_from_spec(cspec)
        sys.modules["_common"] = common
        cspec.loader.exec_module(common)

        rspec = importlib.util.spec_from_file_location(
            "memory_spool_replay_under_test", THIS / "replay.py"
        )
        replay_mod = importlib.util.module_from_spec(rspec)
        sys.modules[rspec.name] = replay_mod
        rspec.loader.exec_module(replay_mod)
    finally:
        if had_prev:
            sys.modules["_common"] = prev
        else:
            sys.modules.pop("_common", None)
    return common, replay_mod


C, replay = _load_isolated()

# The suite is only meaningful if `replay` and this module share ONE `_common`. This
# guard fails the module if `_load_isolated` ever stops binding our `_common` into
# `sys.modules` before `replay.py` executes. It does NOT catch a full revert to the
# flat-namespace import: that regression leaves the test AND `replay.py` bound to the
# SAME foreign module, so `replay.C is C` is True and the guard passes -- the failure
# surfaces instead as loud AttributeErrors naming the foreign `_common` (measured: 8,
# with bg-registry collected first).
assert replay.C is C, "replay.py bound a different _common than the test"


def _spool(tmp: Path, tool: str, payload: dict) -> Path:
    p = tmp / f"1000-{C.payload_key(tool, payload)}.json"
    p.write_text(
        json.dumps(
            {
                "ts": 1000.0,
                "key": "k",
                "tool": tool,
                "title": payload.get("title", "t"),
                "payload": payload,
                "status": "pending",
            }
        ),
        encoding="utf-8",
    )
    return p


def test_build_write_argv_basic():
    argv = replay.build_write_argv(
        {
            "title": "My Note",
            "directory": "reference",
            "tags": "a,b",
            "content": "hello",
        }
    )
    assert argv is not None
    assert "write-note" in argv
    assert argv[argv.index("--title") + 1] == "My Note"
    assert argv[argv.index("--folder") + 1] == "reference"
    assert "--overwrite" in argv and "--local" in argv
    assert argv[argv.index("--tags") + 1] == "a,b"


def test_build_write_argv_tags_list_joined():
    argv = replay.build_write_argv(
        {"title": "T", "directory": "d", "tags": ["x", "y"], "content": "c"}
    )
    assert argv[argv.index("--tags") + 1] == "x,y"


def test_build_write_argv_default_folder_when_missing():
    argv = replay.build_write_argv({"title": "T", "content": "c"})
    assert argv[argv.index("--folder") + 1] == "/"


def test_build_write_argv_garbage_is_none():
    assert replay.build_write_argv({"title": "", "content": "x"}) is None
    assert replay.build_write_argv({"title": "t", "content": ""}) is None
    assert replay.build_write_argv({"title": "t", "content": "   "}) is None


def test_replay_write_success_unlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    p = _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "N", "directory": "reference", "content": "body"},
    )
    monkeypatch.setattr(replay, "_run", lambda argv, stdin: True)
    assert replay.replay_one(p, dry=False) == "replayed"
    assert not p.exists()


def test_replay_write_failure_keeps(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    p = _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "N", "directory": "reference", "content": "body"},
    )
    monkeypatch.setattr(replay, "_run", lambda argv, stdin: False)
    assert replay.replay_one(p, dry=False) == "keep"
    assert p.exists()


def test_replay_garbage_gc(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    p = _spool(tmp_path, "mcp__basic-memory__write_note", {"title": "t", "content": ""})
    assert replay.replay_one(p, dry=False) == "garbage"
    assert not p.exists()


def test_edit_note_is_skipped_never_shells(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    p = _spool(
        tmp_path,
        "mcp__basic-memory__edit_note",
        {"identifier": "x", "operation": "append", "content": "c"},
    )
    called: list[int] = []
    monkeypatch.setattr(replay, "_run", lambda argv, stdin: called.append(1) or True)
    assert replay.replay_one(p, dry=False) == "skip"
    assert p.exists()  # left for flush_check to report
    assert not called  # never auto-applied (append is non-idempotent)


def test_dry_run_does_not_unlink(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    p = _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "N", "directory": "d", "content": "body"},
    )
    assert replay.replay_one(p, dry=True) == "replayed"
    assert p.exists()


def test_main_replays_all_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "A", "directory": "d", "content": "x"},
    )
    _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "B", "directory": "d", "content": "y"},
    )
    monkeypatch.setattr(replay, "_run", lambda argv, stdin: True)
    assert replay.main(["--quiet"]) == 0
    assert not C.list_spools()  # both cleared


def test_spawn_launches_only_when_spooled(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(replay, "_spawn_detached", lambda: calls.append(1))
    assert replay.main(["--spawn"]) == 0
    assert calls == []  # empty spool -> no process spawned
    _spool(
        tmp_path,
        "mcp__basic-memory__write_note",
        {"title": "N", "directory": "d", "content": "x"},
    )
    assert replay.main(["--spawn"]) == 0
    assert calls == [1]  # work present -> spawned once


def test_main_fail_open_on_bad_dir(monkeypatch):
    monkeypatch.setattr(C, "SPOOL_DIR", Path("Z:/nonexistent-spool-dir-xyz"))
    assert replay.main([]) == 0
