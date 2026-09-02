"""Licence compatibility lattice over a closed SPDX axis (IMP-0157).

Two layers:

* the square MATRIX over ``AXES`` (:func:`solve_pair`, :func:`iter_cells`) — the
  closed set of licences the registry has been observed to carry, and
* the FUSION solver (:func:`solve_licences`) that folds an inbound licence list
  through the matrix and returns a verdict with a NAMED reason when fusion is
  forbidden outright, so the fusion entry point can refuse before any body is
  merged.  Copyleft + proprietary is refused with
  :data:`REASON_COPYLEFT_PROPRIETARY` and the suggested alternative
  :data:`SUGGESTED_ALTERNATIVE_CLEAN_ROOM`.

Fail-closed: an unlicensed / unknown inbound licence never defaults to MIT.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from workflow_foundry.license_extract import UNKNOWN, normalize_to_spdx

AXES = (
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MPL-2.0",
    "Unlicense",
    "UNKNOWN",
)

PERMISSIVE = frozenset(
    {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense"}
)

# Strong / reciprocal copyleft families. MPL-2.0 is file-level copyleft and is kept
# on the permissive-compatible path the matrix already defines.
COPYLEFT = frozenset(
    {
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
    }
)

# SPDX user-defined licence references (``LicenseRef-<idstring>``) denote licences
# outside the SPDX list; every one is treated as proprietary for fusion purposes.
PROPRIETARY_PREFIX = "LicenseRef-"
_LICENSE_REF = re.compile(r"^LicenseRef-[A-Za-z0-9.\-]+$")

REASON_COPYLEFT_PROPRIETARY = "COPYLEFT_PROPRIETARY"
REASON_COPYLEFT_CONFLICT = "COPYLEFT_CONFLICT"
REASON_UNKNOWN_INBOUND = "UNKNOWN_INBOUND"
REASON_UNSOLVED_PAIR = "UNSOLVED_PAIR"
REASON_EMPTY_INBOUND = "EMPTY_INBOUND"

SUGGESTED_ALTERNATIVE_CLEAN_ROOM = "CLEAN-ROOM-REIMPLEMENT"
SUGGESTED_ALTERNATIVE_DECLARE_LICENCE = "DECLARE-LICENCE"
SUGGESTED_ALTERNATIVE_SINGLE_FAMILY = "PICK-ONE-COPYLEFT-FAMILY"


@dataclass
class PairVerdict:
    allowed: bool
    result_licence: str
    left: str
    right: str
    reason: str | None = None
    suggested_alternative: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class LicenceVerdict:
    """Outcome of folding an inbound licence list through the matrix."""

    allowed: bool
    result_licence: str
    inbound: list[str]
    canonical: list[str]
    reason: str | None = None
    suggested_alternative: str | None = None
    failing_pair: list[str] | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def matrix_axes() -> list[str]:
    return list(AXES)


def iter_cells():
    for left in AXES:
        for right in AXES:
            yield (left, right, solve_pair(left, right))


def is_proprietary(licence: str) -> bool:
    """True for an SPDX ``LicenseRef-*`` identifier (non-list, treated as proprietary)."""
    return str(licence).startswith(PROPRIETARY_PREFIX)


def is_copyleft(licence: str) -> bool:
    """True for a strong / reciprocal copyleft SPDX id (GPL, AGPL, LGPL families)."""
    return str(licence) in COPYLEFT


def canonical_licence(value: str | None) -> str:
    if value is None:
        return UNKNOWN
    raw = str(value).strip()
    if raw.lower() in {"unlicensed", "none", "unknown", ""}:
        return UNKNOWN
    if _LICENSE_REF.match(raw):
        # An SPDX LicenseRef is already canonical; the prose normaliser would
        # collapse it to UNKNOWN and lose the proprietary signal.
        return raw
    spdx = normalize_to_spdx(raw)
    if spdx in AXES:
        return spdx
    if spdx == UNKNOWN:
        return UNKNOWN
    return spdx


def coverage_gap(raw) -> dict:
    unidentified: list[str] = []
    missing: list[str] = []
    observed: list[str] = []
    for item in raw or []:
        token = str(item)
        canon = canonical_licence(token)
        if canon == UNKNOWN and token.lower() not in {"unlicensed", "none", "unknown", ""}:
            if token not in AXES:
                unidentified.append(token)
                continue
        if canon not in AXES:
            missing.append(canon)
            continue
        observed.append(canon)
    return {
        "exhaustive": not unidentified and not missing,
        "observed_count": len(observed),
        "axis_count": len(AXES),
        "observed_canonical": sorted(set(observed)),
        "missing_from_matrix": missing,
        "unidentified_spellings": unidentified,
    }


def solve_pair(left: str, right: str) -> PairVerdict:
    a = canonical_licence(left)
    b = canonical_licence(right)
    if a == UNKNOWN or b == UNKNOWN:
        return PairVerdict(
            False, UNKNOWN, a, b,
            REASON_UNKNOWN_INBOUND, SUGGESTED_ALTERNATIVE_DECLARE_LICENCE,
        )
    if a == b:
        # A licence is always compatible with itself (matrix diagonal and beyond).
        return PairVerdict(True, a, a, b)
    a_prop, b_prop = is_proprietary(a), is_proprietary(b)
    a_cl, b_cl = is_copyleft(a), is_copyleft(b)
    if (a_cl and b_prop) or (b_cl and a_prop):
        # Reciprocal copyleft cannot be combined with a licence that forbids
        # redistribution of source: forbidden outright, no outbound licence exists.
        return PairVerdict(
            False, UNKNOWN, a, b,
            REASON_COPYLEFT_PROPRIETARY, SUGGESTED_ALTERNATIVE_CLEAN_ROOM,
        )
    if a_cl and b_cl:
        # Two different reciprocal families (e.g. GPL-2.0-only vs GPL-3.0-only).
        return PairVerdict(
            False, UNKNOWN, a, b,
            REASON_COPYLEFT_CONFLICT, SUGGESTED_ALTERNATIVE_SINGLE_FAMILY,
        )
    if a_prop or b_prop:
        # Most-restrictive-wins: permissive / MPL material may be folded into a
        # proprietary product, and the product stays proprietary.
        return PairVerdict(True, a if a_prop else b, a, b)
    if a_cl or b_cl:
        # Copyleft absorbs permissive / MPL material; the result is the copyleft licence.
        return PairVerdict(True, a if a_cl else b, a, b)
    if a in PERMISSIVE and b in PERMISSIVE:
        # fail-closed: mixed permissives stay the more specific of the two only
        # when identical families; otherwise the pair is allowed as Apache-2.0
        # if either is Apache, else MIT if either is MIT, else left.
        if "Apache-2.0" in {a, b}:
            return PairVerdict(True, "Apache-2.0", a, b)
        if "MIT" in {a, b}:
            return PairVerdict(True, "MIT", a, b)
        return PairVerdict(True, a, a, b)
    if a == "MPL-2.0" and b in PERMISSIVE:
        return PairVerdict(True, "MPL-2.0", a, b)
    if b == "MPL-2.0" and a in PERMISSIVE:
        return PairVerdict(True, "MPL-2.0", a, b)
    return PairVerdict(
        False, UNKNOWN, a, b, REASON_UNSOLVED_PAIR, SUGGESTED_ALTERNATIVE_CLEAN_ROOM
    )


def solve_licences(inbound: Iterable[str]) -> LicenceVerdict:
    """Fold an inbound licence list through :func:`solve_pair`, left to right.

    The running result licence of each allowed pair becomes the left operand of the
    next pair, so the outbound licence is the most restrictive compatible licence
    of the whole set.  The first forbidden pair stops the fold and its named reason
    and suggested alternative are carried on the verdict.  An empty list, or any
    UNKNOWN inbound licence, is refused (never a silent permissive default).
    """
    raw = [str(item) for item in inbound]
    canon = [canonical_licence(item) for item in raw]
    if not canon:
        return LicenceVerdict(
            False, UNKNOWN, raw, canon,
            REASON_EMPTY_INBOUND, SUGGESTED_ALTERNATIVE_DECLARE_LICENCE, None,
        )
    if len(canon) == 1:
        single = solve_pair(canon[0], canon[0])
        if not single.allowed:
            return LicenceVerdict(
                False, UNKNOWN, raw, canon,
                single.reason, single.suggested_alternative, [single.left, single.right],
            )
        return LicenceVerdict(True, single.result_licence, raw, canon)
    acc = canon[0]
    for nxt in canon[1:]:
        verdict = solve_pair(acc, nxt)
        if not verdict.allowed:
            return LicenceVerdict(
                False, UNKNOWN, raw, canon,
                verdict.reason, verdict.suggested_alternative,
                [verdict.left, verdict.right],
            )
        acc = verdict.result_licence
    return LicenceVerdict(True, acc, raw, canon)


__all__ = [
    "AXES",
    "COPYLEFT",
    "PERMISSIVE",
    "PROPRIETARY_PREFIX",
    "LicenceVerdict",
    "PairVerdict",
    "REASON_COPYLEFT_CONFLICT",
    "REASON_COPYLEFT_PROPRIETARY",
    "REASON_EMPTY_INBOUND",
    "REASON_UNKNOWN_INBOUND",
    "REASON_UNSOLVED_PAIR",
    "SUGGESTED_ALTERNATIVE_CLEAN_ROOM",
    "SUGGESTED_ALTERNATIVE_DECLARE_LICENCE",
    "SUGGESTED_ALTERNATIVE_SINGLE_FAMILY",
    "canonical_licence",
    "coverage_gap",
    "is_copyleft",
    "is_proprietary",
    "iter_cells",
    "matrix_axes",
    "solve_licences",
    "solve_pair",
]
