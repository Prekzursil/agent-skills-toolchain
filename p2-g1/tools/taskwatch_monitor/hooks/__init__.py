"""Auto-attach hook: watch any background op that crosses the 60s threshold.

The day-1 auto-attach deliverable (grill G-4), split so the risky harness
coupling is isolated from the testable logic:

* :mod:`hooks.attach` — the *pure* decision layer: :func:`~hooks.attach.should_attach`
  (kill-switch / 60s threshold / whitelist) plus :func:`~hooks.attach.decide`
  (adds dedup) over an :class:`~hooks.attach.AttachOp`. No I/O, 100 % branch-covered.
* :mod:`hooks.posttool` — the thin PostToolUse / longrun shell: parses the hook
  event, calls :mod:`hooks.attach`, and auto-registers a taskwatch task via
  :mod:`mcp_server.logic`. Fail-open (any error → exit 0) and deduped via a small
  persisted JSON set.
"""

from __future__ import annotations

from .attach import (
    ATTACH_THRESHOLD_S,
    DEFAULT_WHITELIST,
    AttachDecision,
    AttachOp,
    decide,
    dedup_key,
    should_attach,
)
from .posttool import (
    DEFAULT_TEMPLATE,
    classify_kind,
    extract_op,
    load_seen,
    main,
    run_hook,
    save_seen,
)

__all__ = [
    "ATTACH_THRESHOLD_S",
    "DEFAULT_TEMPLATE",
    "DEFAULT_WHITELIST",
    "AttachDecision",
    "AttachOp",
    "classify_kind",
    "decide",
    "dedup_key",
    "extract_op",
    "load_seen",
    "main",
    "run_hook",
    "save_seen",
    "should_attach",
]
