"""The opt-in LIVE lane, as pure functions so the mechanism is itself coverage-gated.

MEASURED HOLE: the repo's blocking coverage steps run a bare ``pytest`` with no ``-m`` filter,
and no existing package registers a marker or a default deselect — so a ``pytest.mark.live``
test would be COLLECTED AND RUN in CI. Asserting "not run by CI" without building the mechanism
is a claim, not a gate.

``tests/conftest.py`` is a thin shim that calls these functions, so the DECISION lives inside
the coverage-gated package and is unit-tested in both directions, rather than sitting in a
conftest that ``--cov=agentspec`` never measures.
"""

from __future__ import annotations

LIVE_MARKER = "live"
RUN_LIVE_FLAG = "--run-live"
LIVE_CALLS: list[dict] = []


def reset() -> None:
    LIVE_CALLS.clear()

MARKER_SPEC = (
    f"{LIVE_MARKER}: opt-in, needs a real agent rail; "
    f"deselected unless {RUN_LIVE_FLAG} is passed"
)
"""Registered via ``pytest_configure`` so ``--strict-markers`` cannot trip over it."""


def should_deselect(*, has_live_marker: bool, run_live: bool) -> bool:
    """True when a collected item must be dropped from this run."""
    return has_live_marker and not run_live


def deselect_reason() -> str:
    """Why an item was dropped, and how to run it — a skip with no remedy is a dead end."""
    return (
        f"deselected: {LIVE_MARKER}-marked tests need a real agent rail; "
        f"pass {RUN_LIVE_FLAG} to run them"
    )
