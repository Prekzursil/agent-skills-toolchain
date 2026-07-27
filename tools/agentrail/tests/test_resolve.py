"""Executable resolution: the glob survives a version/target bump, a hardcoded path does not."""

from __future__ import annotations

import pytest

from agentrail.ports import CollectingWarnings
from agentrail.rails import RailRow
from agentrail.resolve import (
    ExecutableNotFound,
    glob_ambiguity,
    resolve,
)
from fakes import FakeFileSystem

CODEX_GLOB = (
    "/home/u/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
    "@openai/codex-win32-*/vendor/*/bin/codex.exe"
)
CODEX_TODAY = (
    "/home/u/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
    "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
)
CODEX_TOMORROW = (
    "/home/u/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
    "@openai/codex-win32-arm64/vendor/aarch64-pc-windows-msvc/bin/codex.exe"
)
SHIM = "/home/u/AppData/Roaming/npm/codex.cmd"


def codex_row() -> RailRow:
    return RailRow(name="codex", exe_globs=(CODEX_GLOB,), exe_fallbacks=(SHIM,))


@pytest.mark.parametrize("present", [CODEX_TODAY, CODEX_TOMORROW])
def test_the_glob_resolves_across_a_version_and_target_bump(present: str) -> None:
    """THE point of globbing: neither of these paths is written down anywhere."""
    fs = FakeFileSystem({present: b""})
    resolution = resolve(codex_row(), fs)
    assert resolution.exe == present
    assert resolution.source == "glob"
    assert resolution.degraded is False
    assert resolution.warnings == ()


def test_a_glob_hit_that_is_not_a_file_is_skipped() -> None:
    fs = FakeFileSystem({CODEX_TODAY: b""})
    fs.files[CODEX_TOMORROW] = b""

    class DirectoryLike(FakeFileSystem):
        def is_file(self, path: str) -> bool:
            return path != CODEX_TOMORROW and super().is_file(path)

    filtered = DirectoryLike(dict(fs.files))
    assert resolve(codex_row(), filtered).exe == CODEX_TODAY


def test_the_second_glob_pattern_is_tried_when_the_first_misses() -> None:
    row = RailRow(name="two", exe_globs=("/nope/*", "/yes/*"))
    fs = FakeFileSystem({"/yes/tool": b""})
    resolution = resolve(row, fs)
    assert resolution.exe == "/yes/tool"
    assert resolution.tried == ("/nope/*", "/yes/*")


def test_the_shim_fallback_warns_because_it_is_a_real_degradation() -> None:
    fs = FakeFileSystem({SHIM: b""})
    sink = CollectingWarnings()
    resolution = resolve(codex_row(), fs, sink=sink)
    assert resolution.exe == SHIM
    assert resolution.source == "fallback"
    assert resolution.degraded is True
    assert len(resolution.warnings) == 1
    assert "npm shim" in resolution.warnings[0]
    assert sink.drain() == resolution.warnings
    assert sink.messages == []


def test_the_fallback_still_resolves_without_a_sink() -> None:
    resolution = resolve(codex_row(), FakeFileSystem({SHIM: b""}), sink=None)
    assert resolution.source == "fallback"
    assert resolution.warnings != ()


def test_nothing_resolving_raises_a_closed_taxonomy_reason() -> None:
    with pytest.raises(ExecutableNotFound) as caught:
        resolve(codex_row(), FakeFileSystem())
    assert caught.value.reason == "env-missing-codex"
    assert caught.value.rail_name == "codex"
    assert caught.value.tried == (CODEX_GLOB, SHIM)


def test_glob_ambiguity_reports_every_match_deduplicated_and_sorted() -> None:
    fs = FakeFileSystem({CODEX_TODAY: b"", CODEX_TOMORROW: b""})
    row = RailRow(name="codex", exe_globs=(CODEX_GLOB, CODEX_GLOB))
    assert glob_ambiguity(row, fs) == tuple(sorted((CODEX_TODAY, CODEX_TOMORROW)))


def test_glob_ambiguity_skips_non_files() -> None:
    class NoFiles(FakeFileSystem):
        def is_file(self, path: str) -> bool:
            return False

    assert glob_ambiguity(codex_row(), NoFiles({CODEX_TODAY: b""})) == ()


def test_the_fake_glob_matches_segment_by_segment_like_the_real_one() -> None:
    """A whole-string fnmatch would let ``vendor/*/bin`` cross a separator."""
    fs = FakeFileSystem({"/a/b/c/d": b"", "/a/b/d": b""})
    assert fs.glob("/a/*/d") == ("/a/b/d",)
