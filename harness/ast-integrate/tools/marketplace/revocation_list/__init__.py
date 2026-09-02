"""Marketplace revocation list (IMP-0079): signed-list client and degrade-loudly sink.

Re-exports the public surface of the two core submodules:

* :mod:`.degrade` - :class:`DegradeSink`, the durable bounded warning sink, and
  the ``STALE`` / ``REJECTED`` warning codes;
* :mod:`.revocation` - :class:`HttpTransport` / :class:`FetchError`, the
  verify-only :class:`RevocationClient`, its :class:`RevocationDecision`, and
  the :class:`RevocationList` model.

``install_gate`` (the install-time gate) and ``fixtures`` (test doubles and the
owner signing helpers) are imported explicitly by their consumers and are not
loaded at package import time.
"""
from __future__ import annotations

from .degrade import REJECTED, STALE, DegradeSink, DegradeSinkCorrupt
from .revocation import (
    ALLOW,
    FRESH,
    REFUSE,
    UNREACHABLE,
    FetchError,
    HttpTransport,
    ListSchemaError,
    ListSequenceError,
    ListSignatureError,
    RefreshResult,
    RevocationClient,
    RevocationDecision,
    RevocationList,
    RevocationListError,
    sign_envelope,
)

__all__ = [
    "ALLOW",
    "DegradeSink",
    "DegradeSinkCorrupt",
    "FRESH",
    "FetchError",
    "HttpTransport",
    "ListSchemaError",
    "ListSequenceError",
    "ListSignatureError",
    "REFUSE",
    "REJECTED",
    "RefreshResult",
    "RevocationClient",
    "RevocationDecision",
    "RevocationList",
    "RevocationListError",
    "STALE",
    "UNREACHABLE",
    "sign_envelope",
]
