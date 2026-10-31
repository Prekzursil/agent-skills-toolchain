"""OPT-IN LIVE probes. Deselected by default and never run in CI.

These are the only tests that touch a real machine: a real filesystem outside ``tmp_path``, a
real executable, a real :func:`subprocess.run`. CI passes ``-m "not live"`` and
``tests/conftest.py`` deselects them anyway, so both belts are on.

Run them deliberately::

    pytest --run-live -m live

They are also the SETTLING EXPERIMENTS for the two UNVERIFIED rows: if
``test_an_unverified_rail_can_be_probed`` ever passes for agy or gemini, that row's
``verified`` flag should be flipped in rails.toml and ``test_config_rows.py`` updated with it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import agentrail
from agentrail.rails import RailRow, expand_rows, load_rows, row_by_name
from agentrail.resolve import ExecutableNotFound, resolve
from agentrail.runner import LocalFileSystem, SubprocessSpawn

CONFIG = Path(agentrail.__file__).with_name("rails.toml")
VERIFIED = ("codex", "grok", "opencode")
UNVERIFIED = ("agy", "gemini")


def live_rows() -> tuple[RailRow, ...]:
    return expand_rows(
        load_rows(CONFIG.read_text(encoding="utf-8")), {"HOME": str(Path.home())}
    )


@pytest.mark.live
@pytest.mark.parametrize("name", VERIFIED)
def test_a_verified_rail_resolves_on_this_machine(name: str) -> None:
    resolution = resolve(row_by_name(live_rows(), name), LocalFileSystem())
    assert Path(resolution.exe).is_file()


@pytest.mark.live
def test_the_codex_vendor_glob_resolves_to_exactly_one_build() -> None:
    """Two matches would mean a stale build survived an interrupted npm update."""
    from agentrail.resolve import glob_ambiguity

    matches = glob_ambiguity(row_by_name(live_rows(), "codex"), LocalFileSystem())
    assert len(matches) == 1, (
        f"expected 1 vendor build, found {len(matches)}: {matches}"
    )


@pytest.mark.live
@pytest.mark.parametrize("name", VERIFIED)
def test_a_verified_rail_answers_version_headlessly(name: str) -> None:
    """The probe behind `verified = true`. Spawns a REAL process -- hence the live marker."""
    resolution = resolve(row_by_name(live_rows(), name), LocalFileSystem())
    outcome = SubprocessSpawn()(
        argv=(resolution.exe, "--version"),
        stdin_payload=None,
        timeout_s=30,
        cwd=None,
    )
    assert outcome.error_reason is None, outcome.detail
    assert outcome.exit_code == 0


@pytest.mark.live
@pytest.mark.parametrize("name", UNVERIFIED)
def test_an_unverified_rail_can_be_probed(name: str) -> None:
    """THE SETTLING EXPERIMENT for the two opt-in rows. Ran 2026-07-27; results below.

    * ``agy``    -- PASSES. ``--version`` exits 0 within 20s, so the earlier 15s timeout was a
      DETECTOR failure and not a verdict. That settles the BINARY half only; the row stays
      ``verified = false`` because its prompt transport is still unmeasured.
    * ``gemini`` -- FAILS, and the failure is the FINDING: ``WinError 193, %1 is not a valid
      Win32 application``. The resolved entry point is a ``.ps1``, which ``CreateProcess``
      cannot launch. A red here is the correct, informative state until a native entry point
      or a powershell wrapper row exists.

    Answering ``--version`` is NECESSARY but NOT SUFFICIENT for ``verified = true``: that flag
    also claims the prompt transport was proven by an executable probe with a control.
    """
    try:
        resolution = resolve(row_by_name(live_rows(), name), LocalFileSystem())
    except ExecutableNotFound as exc:
        pytest.fail(f"{name} is not installed here: {exc}")
    outcome = SubprocessSpawn()(
        argv=(resolution.exe, "--version"),
        stdin_payload=None,
        timeout_s=20,
        cwd=None,
    )
    assert outcome.error_reason is None, (
        f"{name} does not answer --version headlessly: {outcome.detail}. Keep verified = false "
        f"and record WHY in the row's notes -- a timeout is a detector failure, but WinError 193 "
        f"is a real incompatibility."
    )
