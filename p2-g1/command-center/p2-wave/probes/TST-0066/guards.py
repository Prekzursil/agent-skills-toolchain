#!/usr/bin/env python3
"""TST-0066 guards: string-comparing control vs canonical deny-guard.

string_deny_exact mirrors the estate guards' shape (raw-string compare,
fnmatch allowlist, startswith deny, parents-membership containment);
canonical_deny_exact resolves to a canonical identity FIRST and then
compares, per the receipt's fix shape."""
from __future__ import annotations

import fnmatch

from winpath import canonical, same_identity


def string_deny_exact(candidate: str, denied: str) -> str:
    return "REJECT" if (candidate == denied or candidate.startswith(denied)) else "ACCEPT"


def canonical_deny_exact(candidate: str, denied: str) -> str:
    return "REJECT" if same_identity(candidate, denied) else "ACCEPT"


def string_allow_fnmatch(candidate: str, glob: str) -> str:
    return "ACCEPT" if fnmatch.fnmatch(candidate, glob) else "REJECT"


def canonical_allow_fnmatch(candidate: str, glob: str) -> str:
    from winpath import canonical as _c
    return "ACCEPT" if fnmatch.fnmatch(_c(candidate), _c(glob)) else "REJECT"
