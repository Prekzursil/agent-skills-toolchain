"""Compatibility-resolver re-export.

The implementation lives in ``tools/marketplace/compat.py``.  This module makes
``import compat`` resolve to the same functions when ``tools/`` (rather than
``tools/marketplace/``) is the ``sys.path`` entry, as the IMP-0085 test runner
does; nothing is implemented here.
"""
from __future__ import annotations

try:
    from marketplace import compat as _impl
except ImportError:  # imported as ``tools.compat`` with the repo root on sys.path
    from tools.marketplace import compat as _impl

MATRIX_PLATFORMS = _impl.MATRIX_PLATFORMS
MATRIX_CLIENTS = _impl.MATRIX_CLIENTS
DEFAULT_INDEX = _impl.DEFAULT_INDEX
FilterResult = _impl.FilterResult
strip_bom = _impl.strip_bom
decode_text = _impl.decode_text
load_candidates = _impl.load_candidates
candidate_key = _impl.candidate_key
filter_candidates = _impl.filter_candidates
assert_nonempty_reason_on_empty = _impl.assert_nonempty_reason_on_empty
resolution_matrix = _impl.resolution_matrix

__all__ = [
    "DEFAULT_INDEX",
    "FilterResult",
    "MATRIX_CLIENTS",
    "MATRIX_PLATFORMS",
    "assert_nonempty_reason_on_empty",
    "candidate_key",
    "decode_text",
    "filter_candidates",
    "load_candidates",
    "resolution_matrix",
    "strip_bom",
]
