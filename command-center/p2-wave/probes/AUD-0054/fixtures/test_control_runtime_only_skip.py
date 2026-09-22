"""AUD-0054 control fixture: a platform skip declared ONLY at runtime.

This is the tests_required control from the catalog: "a runtime-only skip (raised
inside the test body) must be found by probe 2 and missed by probe 1; if both find
it, the pair is not independent."

Deliberately NO ``@pytest.mark.skipif`` / ``@pytest.mark.skip`` / ``unittest.skipIf``
decorator anywhere in this file -- probe1_ast_platform_skips.py only walks decorator
lists, so it structurally cannot see a ``pytest.skip()`` call that lives inside a
function body. The skip fires on THIS host (Linux, ``sys.platform == "linux"``) so
probe 2's real collected-vs-executed diff observes it as SKIPPED, not merely
collected -- the only way to know a runtime gate fired is to run it.

A sibling always-passing test proves the file collects and runs cleanly outside the
gated case, so the skip is attributable to the platform check and not to a collection
error swallowing the whole module.
"""

from __future__ import annotations

import sys

import pytest


def test_control_sibling_runs_on_every_platform() -> None:
    """Positive control: this file collects and executes normally."""
    assert 1 + 1 == 2


def test_control_windows_only_runtime_skip_no_decorator() -> None:
    """AUD-0054-CONTROL: windows-only, but the gate is a body-level pytest.skip().

    No decorator declares this. On this Linux host `sys.platform != "win32"`, so the
    skip call fires and pytest reports SKIPPED for a node id that WAS collected.
    """
    if sys.platform != "win32":
        pytest.skip(
            "AUD-0054-CONTROL: windows-only runtime gate, no decorator declares it"
        )
    assert False, "unreachable on win32 in this fixture; body intentionally minimal"
