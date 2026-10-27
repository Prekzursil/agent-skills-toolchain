"""Licence compatibility lattice over a closed SPDX axis (IMP-0157)."""
from __future__ import annotations

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


@dataclass
class PairVerdict:
    allowed: bool
    result_licence: str
    left: str
    right: str

    def as_dict(self) -> dict:
        return asdict(self)


def matrix_axes() -> list[str]:
    return list(AXES)


def iter_cells():
    for left in AXES:
        for right in AXES:
            yield (left, right, solve_pair(left, right))


def canonical_licence(value: str | None) -> str:
    if value is None:
        return UNKNOWN
    raw = str(value).strip()
    if raw.lower() in {"unlicensed", "none", "unknown", ""}:
        return UNKNOWN
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
        return PairVerdict(False, UNKNOWN, a, b)
    if a == b and a in AXES:
        return PairVerdict(True, a, a, b)
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
    return PairVerdict(False, UNKNOWN, a, b)


__all__ = [
    "AXES",
    "PairVerdict",
    "canonical_licence",
    "coverage_gap",
    "iter_cells",
    "matrix_axes",
    "solve_pair",
]
