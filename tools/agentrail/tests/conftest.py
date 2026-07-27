"""Thin pytest shim. The DECISION lives in agentspec.evals.pytest_live, which is coverage-gated.

Reused, not reimplemented: agentrail's live lane is the same mechanism agentspec already built
and unit-tests in both directions. This file is not measured by ``--cov=agentrail``, so it
deliberately holds no logic worth testing.
"""

from __future__ import annotations

import pytest
from agentspec.evals.pytest_live import (
    LIVE_MARKER,
    MARKER_SPEC,
    RUN_LIVE_FLAG,
    deselect_reason,
    should_deselect,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        RUN_LIVE_FLAG,
        action="store_true",
        default=False,
        help="run the opt-in live-rail probes (they spawn a real agent CLI)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", MARKER_SPEC)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    run_live = bool(config.getoption(RUN_LIVE_FLAG))
    skip = pytest.mark.skip(reason=deselect_reason())
    for item in items:
        has_marker = item.get_closest_marker(LIVE_MARKER) is not None
        if should_deselect(has_live_marker=has_marker, run_live=run_live):
            item.add_marker(skip)
