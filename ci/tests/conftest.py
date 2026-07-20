"""pytest wiring for the ci/ check suites.

The helpers live in ``dual_write_fixtures`` (a uniquely named module) so that a
session collecting both this directory and ``tools/d001-dual-write/tests``
cannot import the wrong sibling off ``sys.path``.
"""

from __future__ import annotations

from dual_write_fixtures import repo

__all__ = ["repo"]
