"""The cleaned module: it logs instead of printing to stdout."""

from __future__ import annotations

import logging
from collections.abc import Iterable

_log = logging.getLogger(__name__)


def summarize(values: Iterable[float]) -> float:
    total = sum(values)
    _log.debug("total: %s", total)
    return total
