"""The INJECTED implementation bundle every eval row runs against.

Rows never import the production functions directly — they call them through this bundle. That
is what makes the mutation guard possible: ``dataclasses.replace(DEFAULT_IMPL, judge=<broken>)``
swaps one seam and the owning row must go RED. A row that stays green under its own mutant is
protecting nothing, which is the failure mode 100% coverage cannot see.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agentspec import argv as argv_mod
from agentspec import determinism, dispatchpolicy, oracle, progress, retry, terminal
from agentspec.envelope import Observation


def canonical_json(observation: Observation) -> str:
    """Serialise an observation deterministically: sorted keys, no insignificant whitespace.

    Scoped to PYTHON-side determinism (R8). Cross-runtime byte parity is explicitly OUT of
    scope for this package and is documented as an UNVERIFIED follow-up in the README, because
    Python and JS canonical JSON provably diverge in 6 of 7 measured cases.
    """
    return json.dumps(observation.as_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class Impl:
    """One swappable seam per protected rule."""

    build_argv: Callable[..., Any]
    build_for_rail: Callable[..., Any]
    check_dispatch: Callable[..., Any]
    classify: Callable[..., Any]
    judge: Callable[..., Any]
    plan_retry: Callable[..., Any]
    scan_source: Callable[..., Any]
    serialise: Callable[[Observation], str]
    terminal_line: Callable[..., Any]


DEFAULT_IMPL = Impl(
    build_argv=argv_mod.build_argv,
    build_for_rail=argv_mod.build_for_rail,
    check_dispatch=dispatchpolicy.check_dispatch,
    classify=progress.classify,
    judge=oracle.judge,
    plan_retry=retry.plan_retry,
    scan_source=determinism.scan_source,
    serialise=canonical_json,
    terminal_line=terminal.terminal_line,
)
