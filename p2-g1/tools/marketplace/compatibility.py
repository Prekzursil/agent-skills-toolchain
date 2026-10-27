"""License compatibility over the resolved dependency closure (IMP-0093).

Verdicts come from data/compatibility-matrix.json, which encodes only
PUBLISHED pair verdicts (FSF license-list compatibility notes, MPL-2.0
3.3 secondary-license clause, EPL-2.0 secondary-license provision).
Any pair the matrix does not cover is UNKNOWN-NEEDS-REVIEW - never
assumed compatible - and is reported for owner review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MATRIX_PATH = HERE / "data" / "compatibility-matrix.json"

COMPATIBLE = "COMPATIBLE"
INCOMPATIBLE = "INCOMPATIBLE"
UNKNOWN_NEEDS_REVIEW = "UNKNOWN-NEEDS-REVIEW"
OWNER_ACTION = "route to owner for human review; never auto-assume compatible"

__surface__ = "marketplace.compatibility"


def pair_key(left: str, right: str) -> str:
    """Stable unordered pair key."""
    return "|".join(sorted((str(left).strip(), str(right).strip())))


def load_matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def pair_compatibility(
    left: str | None, right: str | None, matrix: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Verdict for one license pair straight from the published matrix."""
    doc = matrix if matrix is not None else load_matrix()
    left_s = None if left in (None, "") else str(left).strip()
    right_s = None if right in (None, "") else str(right).strip()
    if (
        left_s is None
        or right_s is None
        or left_s == "LICENSE-ABSENT"
        or right_s == "LICENSE-ABSENT"
    ):
        return {
            "pair": pair_key(str(left), str(right)),
            "verdict": UNKNOWN_NEEDS_REVIEW,
            "source": None,
            "reason": "one side of the pair has no license; closure cannot be licensed",
        }
    key = pair_key(left_s, right_s)
    row = (doc.get("pairs") or {}).get(key)
    if row is None:
        return {
            "pair": key,
            "verdict": UNKNOWN_NEEDS_REVIEW,
            "source": None,
            "reason": "pair not covered by the published matrix",
        }
    return {
        "pair": key,
        "verdict": str(row.get("verdict") or "").upper(),
        "source": row.get("source"),
        "reason": row.get("reason"),
    }


def check_closure(
    license_ids: list[str | None], matrix: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Per-pair verdicts across a resolved closure.

    ok = no INCOMPATIBLE pair. needs_review = at least one pair the
    matrix does not cover (routed to the owner, never auto-assumed).
    Offending pairs are named exactly, never averaged into a pass rate.
    """
    doc = matrix if matrix is not None else load_matrix()
    seen: list[str | None] = []
    for x in license_ids:
        val = None if x in (None, "") else str(x).strip()
        if val not in seen:
            seen.append(val)
    verdicts: list[dict[str, Any]] = []
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            verdicts.append(pair_compatibility(seen[i], seen[j], doc))
    offending = [v for v in verdicts if v["verdict"] == INCOMPATIBLE]
    unknown = [v for v in verdicts if v["verdict"] == UNKNOWN_NEEDS_REVIEW]
    return {
        "ok": not offending,
        "needs_review": bool(unknown),
        "pairs": verdicts,
        "offending": offending,
        "unknown": unknown,
        "owner_action": OWNER_ACTION if unknown else None,
    }


def _row(left: str, right: str, verdict: str, source: str, reason: str) -> dict[str, Any]:
    return {
        "pair": pair_key(left, right),
        "verdict": verdict,
        "source": source,
        "reason": reason,
    }


def build_matrix_rows() -> dict[str, dict[str, Any]]:
    """The published-matrix rows; the single place they are defined.

    Every verdict cites its published source. Pairs NOT listed here are
    UNKNOWN-NEEDS-REVIEW by policy (enforced in pair_compatibility).
    """
    permissive = [
        "0BSD", "MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense",
        "PSF-2.0", "ZPL-2.1", "Apache-2.0",
    ]
    gpl2 = ["GPL-2.0-only", "GPL-2.0-or-later"]
    gpl3 = ["GPL-3.0-only", "GPL-3.0-or-later"]
    lgpl2 = ["LGPL-2.1-only", "LGPL-2.1-or-later"]
    lgpl3 = ["LGPL-3.0-only", "LGPL-3.0-or-later"]
    agpl3 = ["AGPL-3.0-only", "AGPL-3.0-or-later"]

    rows: dict[str, dict[str, Any]] = {}
    all_ids = sorted(
        set(
            permissive
            + gpl2 + gpl3 + lgpl2 + lgpl3 + agpl3
            + ["MPL-2.0", "CDDL-1.0", "CDDL-1.1", "EPL-1.0", "EPL-2.0", "SSPL-1.0"]
        )
    )
    for ident in all_ids:
        rows[pair_key(ident, ident)] = _row(
            ident, ident, COMPATIBLE, "identical license",
            "the same license terms coincide by definition",
        )

    S_PERMISSIVE = (
        "FSF/SPDX license-list compatibility notes: permissive licenses "
        "impose no reciprocal-obligation conflict on each other"
    )
    for i, a in enumerate(permissive):
        for b in permissive[i + 1:]:
            rows[pair_key(a, b)] = _row(
                a, b, COMPATIBLE, S_PERMISSIVE, "permissive x permissive")

    S_PERM_COPYLEFT = (
        "FSF license-list compatibility notes: permissive licenses are "
        "compatible with GPL/LGPL/AGPL as the incorporated part"
    )
    copyleft = gpl2 + gpl3 + lgpl2 + lgpl3 + agpl3
    for a in permissive:
        if a == "Apache-2.0":
            continue
        for b in copyleft:
            rows.setdefault(
                pair_key(a, b),
                _row(a, b, COMPATIBLE, S_PERM_COPYLEFT,
                     "permissive incorporated into the copyleft work"),
            )

    S_APACHE = (
        "FSF license list: Apache-2.0 is incompatible with GPL-2.0-only "
        "and LGPL-2.1-only (GPLv2 terms); compatible with the "
        "GPLv3-or-later family including AGPL-3.0"
    )
    for b in gpl2 + lgpl2:
        if b.endswith("or-later"):
            rows[pair_key("Apache-2.0", b)] = _row(
                "Apache-2.0", b, COMPATIBLE, S_APACHE,
                "the or-later choice resolves to GPLv3-compatible terms")
        else:
            rows[pair_key("Apache-2.0", b)] = _row(
                "Apache-2.0", b, INCOMPATIBLE, S_APACHE,
                "Apache-2.0 patent/termination clauses are GPLv2-incompatible")
    rows[pair_key("Apache-2.0", "AGPL-3.0-only")] = _row(
        "Apache-2.0", "AGPL-3.0-only", COMPATIBLE, S_APACHE,
        "AGPL-3.0 is GPLv3-family: Apache-2.0-compatible")
    for b in lgpl3 + gpl3:
        rows.setdefault(
            pair_key("Apache-2.0", b),
            _row("Apache-2.0", b, COMPATIBLE, S_APACHE,
                 "GPLv3-family is Apache-2.0-compatible"),
        )

    S_GPL2V3 = (
        "FSF license list: GPL-2.0-only and GPL-3.0-only are mutually "
        "incompatible; an or-later grant resolves the conflict"
    )
    for b in gpl3:
        rows[pair_key("GPL-2.0-only", b)] = _row(
            "GPL-2.0-only", b, INCOMPATIBLE, S_GPL2V3,
            "GPLv2-only text cannot adopt v3 terms")
        rows[pair_key("GPL-2.0-or-later", b)] = _row(
            "GPL-2.0-or-later", b, COMPATIBLE, S_GPL2V3,
            "or-later choice resolves to v3 terms")

    S_LGPL = (
        "LGPL-2.1 section 3 permits conversion to GPL-2.0-or-later; "
        "LGPL-3.0 is GPLv3 with additional permissions"
    )
    for a in lgpl2 + lgpl3:
        for b in gpl2 + gpl3:
            key = pair_key(a, b)
            if key in rows:
                continue
            if a in lgpl3 and b == "GPL-2.0-only":
                continue  # deliberately left UNKNOWN
            if a == "LGPL-2.1-only" and b == "GPL-3.0-only":
                continue  # deliberately left UNKNOWN
            rows[key] = _row(
                a, b, COMPATIBLE, S_LGPL, "weak-copyleft link/conversion clause")
    rows[pair_key("LGPL-3.0-only", "GPL-2.0-only")] = _row(
        "LGPL-3.0-only", "GPL-2.0-only", UNKNOWN_NEEDS_REVIEW,
        "conservative (no published verdict for this strict pair)",
        "LGPL-3.0 has no GPLv2-only link clause; never assumed compatible")
    rows[pair_key("LGPL-2.1-only", "GPL-3.0-only")] = _row(
        "LGPL-2.1-only", "GPL-3.0-only", UNKNOWN_NEEDS_REVIEW,
        "conservative (no published verdict for this strict pair)",
        "strict v2.1-only text without an or-later choice; never assumed compatible")

    S_AGPL2 = "FSF license list: AGPL-3.0 is incompatible with GPL-2.0-only"
    for a in agpl3:
        rows[pair_key(a, "GPL-2.0-only")] = _row(
            a, "GPL-2.0-only", INCOMPATIBLE, S_AGPL2,
            "AGPL-3 terms require the GPLv3 family")
        rows[pair_key(a, "GPL-2.0-or-later")] = _row(
            a, "GPL-2.0-or-later", COMPATIBLE, S_AGPL2,
            "the or-later choice resolves to v3 terms")
        for b in agpl3:
            if a != b:
                rows.setdefault(
                    pair_key(a, b),
                    _row(a, b, COMPATIBLE, "AGPL-3.0 section 13",
                         "same license family"),
                )

    S_MPL = (
        "MPL-2.0 section 3.3 secondary-license clause; Mozilla FAQ: "
        "MPL-2.0 is GPL-compatible when the secondary license election "
        "covers GPLv2-or-later/LGPL/AGPL"
    )
    for b in [
        "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
        "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
        "AGPL-3.0-only", "AGPL-3.0-or-later",
    ]:
        rows[pair_key("MPL-2.0", b)] = _row(
            "MPL-2.0", b, COMPATIBLE, S_MPL,
            "section 3.3 secondary-license election")
    rows[pair_key("MPL-2.0", "GPL-2.0-only")] = _row(
        "MPL-2.0", "GPL-2.0-only", UNKNOWN_NEEDS_REVIEW, S_MPL,
        "compatible only via an or-later election; strict v2-only never assumed")

    S_CDDL = (
        "FSF license list: CDDL-1.0/1.1 are incompatible with the GPL "
        "(the chosen CDDL of ZFS-on-Linux remains unresolved)"
    )
    for a in ["CDDL-1.0", "CDDL-1.1"]:
        for b in gpl2 + gpl3:
            rows[pair_key(a, b)] = _row(
                a, b, INCOMPATIBLE, S_CDDL, "CDDL vs GPL")

    S_EPL1 = "Eclipse Legal FAQ: EPL-1.0 is incompatible with GPLv2 (indemnity clause)"
    for b in gpl2:
        rows[pair_key("EPL-1.0", b)] = _row(
            "EPL-1.0", b, INCOMPATIBLE, S_EPL1, "EPL-1.0 indemnity vs GPLv2")
    rows[pair_key("EPL-1.0", "GPL-3.0-only")] = _row(
        "EPL-1.0", "GPL-3.0-only", UNKNOWN_NEEDS_REVIEW,
        "conservative (no published verdict for this strict pair)",
        "EPL-1.0/GPLv3 status is disputed without an explicit election; never assumed")
    S_EPL2 = (
        "EPL-2.0 secondary-license provision: compatible with "
        "GPLv2-or-later/LGPL/AGPL when the election is made"
    )
    for b in [
        "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
        "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
        "AGPL-3.0-only", "AGPL-3.0-or-later",
    ]:
        rows[pair_key("EPL-2.0", b)] = _row(
            "EPL-2.0", b, COMPATIBLE, S_EPL2,
            "EPL-2.0 secondary-license election")

    # SSPL-1.0: no published pair verdicts - every SSPL pair stays UNKNOWN
    # by design (negative control: an unknown pair must NOT be compatible).
    return rows


if __name__ == "__main__":
    print(json.dumps({"rows": len(build_matrix_rows())}, sort_keys=True))
