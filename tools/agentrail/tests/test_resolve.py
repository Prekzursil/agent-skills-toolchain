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


def test_two_coexisting_builds_pin_the_tie_break_and_warn_about_it() -> None:
    """MEASURED: with both vendor builds present, resolve() silently took ``arm64`` on an x64
    box and reported nothing -- ``degraded=False``, ``warnings=()``.

    Two properties are pinned here, and the pin is what makes them checkable:

    * WHICH build wins. ``matches[0]`` over a SORTED list is deterministic, but until this
      assertion existed a ``matches[0] -> matches[-1]`` mutation survived the whole suite.
    * That the operator is TOLD. A choice made between two builds with no warning is how a
      stale target triple survives an interrupted ``npm -g update`` unnoticed.

    Not a failure and not ``degraded``: the resolution works, and turning a working rail into
    an error over a diagnostic would be its own defect.
    """
    fs = FakeFileSystem({CODEX_TODAY: b"", CODEX_TOMORROW: b""})
    sink = CollectingWarnings()
    resolution = resolve(codex_row(), fs, sink=sink)

    assert resolution.exe == min(CODEX_TODAY, CODEX_TOMORROW), (
        "the tie-break is the FIRST of the sorted matches"
    )
    assert resolution.exe == CODEX_TOMORROW, "sorted-first here is the arm64 build"
    assert resolution.source == "glob"
    assert resolution.degraded is False, "an ambiguous glob is not a degradation"
    assert len(resolution.warnings) == 1
    assert "matched 2 builds" in resolution.warnings[0]
    assert "took the first" in resolution.warnings[0]
    assert sink.drain() == resolution.warnings


def test_an_unambiguous_glob_stays_silent() -> None:
    """The detector control: a warning that always fires would be noise, not a signal."""
    sink = CollectingWarnings()
    resolution = resolve(codex_row(), FakeFileSystem({CODEX_TODAY: b""}), sink=sink)
    assert resolution.warnings == ()
    assert sink.messages == []


def test_an_ambiguous_glob_resolves_without_a_sink() -> None:
    """The warning still reaches the envelope through ``Resolution.warnings``."""
    fs = FakeFileSystem({CODEX_TODAY: b"", CODEX_TOMORROW: b""})
    resolution = resolve(codex_row(), fs, sink=None)
    assert len(resolution.warnings) == 1


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
