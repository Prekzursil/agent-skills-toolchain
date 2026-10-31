"""The SHIPPED rails.toml. Config is the product here, so it is gated like code.

These assertions encode what was MEASURED about each rail. When a live probe settles agy or
gemini, the row changes and so does the expectation here -- which is the point: the verified /
UNVERIFIED split is data under test, not a claim in a README.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentspec.argv import PROMPT_TRANSPORTS

import agentrail
from agentrail.plan import spill_transport
from agentrail.rails import (
    NATIVE_TRANSPORTS,
    RailRow,
    expand_rows,
    load_rows,
    row_by_name,
    verified_names,
)
from agentrail.resolve import resolve
from fakes import FakeFileSystem

HOME = "/home/u"
CONFIG_PATH = Path(agentrail.__file__).with_name("rails.toml")
ROWS: tuple[RailRow, ...] = expand_rows(
    load_rows(CONFIG_PATH.read_text(encoding="utf-8")), {"HOME": HOME}
)


def test_the_shipped_config_is_loadable_and_complete() -> None:
    assert {row.name for row in ROWS} == {
        "codex",
        "grok",
        "opencode",
        "agy",
        "gemini",
    }


def test_only_the_executably_proven_rails_are_marked_verified() -> None:
    """`verified` claims BOTH halves: the binary answers headlessly AND its transport is proven.

    agy answers ``--version`` in 20s (measured 2026-07-27, so the earlier 15s timeout really was
    a detector failure) and is STILL false, because only the binary half is settled. Every
    unverified row must say what would settle it -- a flag with no exit route is a dead end.
    """
    assert verified_names(ROWS) == ("codex", "grok", "opencode")
    for name in ("agy", "gemini"):
        row = row_by_name(ROWS, name)
        assert row.verified is False
        assert "settling experiment" in row.notes.lower()
        assert "UNMEASURED" in row.notes or "UNVERIFIED" in row.notes


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.name)
def test_every_row_lands_on_an_agentspec_legal_transport(row: RailRow) -> None:
    transport, _ = spill_transport(row)
    assert transport in PROMPT_TRANSPORTS
    assert row.native_transport in NATIVE_TRANSPORTS


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.name)
def test_no_row_declares_a_vacuous_receipt_spec(row: RailRow) -> None:
    assert not row.receipt_spec().is_vacuous()


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.name)
def test_every_row_expands_to_a_concrete_path(row: RailRow) -> None:
    for value in (*row.exe_globs, *row.exe_fallbacks):
        assert "${" not in value
        assert value.startswith(HOME)


def test_the_codex_row_carries_the_load_bearing_hardening_flag() -> None:
    """Without --ignore-user-config the whole MCP inventory lands on the command line."""
    codex = row_by_name(ROWS, "codex")
    assert codex.hardening == ("--ignore-user-config",)
    assert codex.native_transport == "stdin"
    assert codex.prompt_flag is None
    assert codex.receipt_flag == "--output-last-message"
    assert "--json" in codex.base_flags
    assert "-a" not in codex.base_flags, (
        "-a/--ask-for-approval is TOP-LEVEL only and errors with exit 2 on `codex exec`"
    )


def test_the_codex_glob_is_wildcarded_on_both_volatile_segments() -> None:
    (pattern,) = row_by_name(ROWS, "codex").exe_globs
    assert "codex-win32-*" in pattern, "the npm per-platform sub-package name moves"
    assert "/vendor/*/bin/" in pattern, "the vendor directory is keyed by target triple"
    assert pattern.count("*") == 2


def test_the_codex_glob_matches_a_future_build_the_fallback_would_miss() -> None:
    future = (
        f"{HOME}/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/"
        "@openai/codex-win32-arm64/vendor/aarch64-pc-windows-msvc/bin/codex.exe"
    )
    resolution = resolve(row_by_name(ROWS, "codex"), FakeFileSystem({future: b""}))
    assert resolution.exe == future
    assert resolution.source == "glob"


def test_the_codex_shim_fallback_is_declared_and_degrades_loudly() -> None:
    codex = row_by_name(ROWS, "codex")
    assert codex.exe_fallbacks == (f"{HOME}/AppData/Roaming/npm/codex.cmd",)
    resolution = resolve(codex, FakeFileSystem({codex.exe_fallbacks[0]: b""}))
    assert resolution.degraded is True
    assert resolution.warnings != ()


def test_the_grok_row_uses_its_real_prompt_file_flag_not_an_argv_form() -> None:
    """-p/--single, --prompt-json and the bare positional all exist and are all refused."""
    grok = row_by_name(ROWS, "grok")
    assert grok.native_transport == "file"
    assert grok.prompt_flag == "--prompt-file"
    assert spill_transport(grok) == ("file", False)
    assert "-p" not in grok.base_flags
    assert "--single" not in grok.base_flags
    assert "--output-format" in grok.base_flags


def test_the_opencode_row_resolves_only_through_shims() -> None:
    opencode = row_by_name(ROWS, "opencode")
    assert opencode.exe_globs == ()
    assert len(opencode.exe_fallbacks) == 2
    assert opencode.native_transport == "stdin"
    assert opencode.base_flags[0] == "run"


@pytest.mark.parametrize("name", ["agy", "gemini"])
def test_an_unverified_rail_declares_argv_and_is_therefore_spilled(name: str) -> None:
    """`argv` is the WORST case a CLI can want, so an UNMEASURED rail is assumed to want it."""
    row = row_by_name(ROWS, name)
    assert row.native_transport == "argv"
    transport, spilled = spill_transport(row)
    assert spilled is True
    assert transport == "stdin"


def test_the_gemini_row_records_its_unsolved_powershell_problem() -> None:
    """A .ps1 is not directly spawnable by CreateProcess. Recorded, not papered over."""
    gemini = row_by_name(ROWS, "gemini")
    assert gemini.exe_globs == (f"{HOME}/.local/bin/gemini.ps1",)
    assert ".ps1" in gemini.notes
