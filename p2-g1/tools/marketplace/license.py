"""SPDX validation and declared-versus-actual pairing for marketplace packages.

IMP-0093: identifier validity is checked against the pinned official SPDX
list (tools/marketplace/spdx.py) in addition to the embedded fast set;
closure compatibility is delegated to marketplace.compatibility, whose
verdicts come only from published pairs and never assume an uncovered
pair is compatible.
"""
from __future__ import annotations

from typing import Any

from marketplace import compatibility as _compat
from marketplace import spdx as _spdx

LICENSE_ABSENT = "LICENSE-ABSENT"
SPDX_INVALID = "SPDX-INVALID"
SPDX_VALID = "SPDX-VALID"
LICENSE_UNSATISFIABLE = "LICENSE-UNSATISFIABLE"
LEGAL_DISCLAIMER = (
    "This inventory reports SPDX identifier membership. It is not legal advice."
)

_KNOWN = frozenset(
    {
        "0BSD",
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "MPL-2.0",
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
        "Unlicense",
        "PSF-2.0",
        "ZPL-2.1",
        "SSPL-1.0",
        "EPL-1.0",
        "EPL-2.0",
        "CDDL-1.0",
        "CDDL-1.1",
    }
)


def validate_spdx(identifier: Any) -> dict[str, Any]:
    if identifier is None or str(identifier).strip() == "":
        return {
            "valid": False,
            "identifier": None,
            "code": LICENSE_ABSENT,
        }
    ident = str(identifier).strip()
    if ident in _KNOWN:
        return {"valid": True, "identifier": ident, "code": SPDX_VALID}
    # official pinned SPDX list is the second, authoritative tier
    if ident in _spdx.official_ids():
        return {"valid": True, "identifier": ident, "code": SPDX_VALID}
    return {"valid": False, "identifier": ident, "code": SPDX_INVALID}


def pair_verdict(left: Any, right: Any) -> dict[str, Any]:
    a = None if left in (None, "", "LICENSE-ABSENT") else str(left)
    b = None if right in (None, "", "LICENSE-ABSENT") else str(right)
    if a and b and a != b:
        return {
            "conflict": True,
            "resolved": None,
            "code": "DECLARED-VERSUS-ACTUAL-CONFLICT",
            "left": a,
            "right": b,
        }
    chosen = a or b
    return {
        "conflict": False,
        "resolved": chosen,
        "code": SPDX_VALID if (chosen and validate_spdx(chosen)["valid"]) else SPDX_INVALID,
        "left": a,
        "right": b,
    }


def check_closure(license_ids: list[str | None]) -> dict[str, Any]:
    """Compatibility verdicts across a resolved dependency closure.

    ok = no INCOMPATIBLE pair. needs_review = pairs the published matrix
    does not cover, routed to the owner (never assumed compatible).
    """
    return _compat.check_closure(license_ids)


def publication_gate(packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Publication gate: a package with a missing or invalid license is
    LICENSE-ABSENT/SPDX-INVALID and MUST block publication; an
    incompatible closure also blocks. Unknown pairs do not block but are
    routed to the owner.
    """
    failures: list[dict[str, Any]] = []
    ids: list[str | None] = []
    for pkg in packages or []:
        name = str(pkg.get("name") or "<unnamed>")
        verdict = validate_spdx(pkg.get("license"))
        ids.append(pkg.get("license") if verdict["valid"] else None)
        if not verdict["valid"]:
            failures.append(
                {
                    "package": name,
                    "code": verdict["code"],
                    "identifier": verdict["identifier"],
                }
            )
    closure = check_closure(ids)
    return {
        "ok": not failures and closure["ok"],
        "legal_disclaimer": LEGAL_DISCLAIMER,
        "failures": failures,
        "closure": closure,
        "owner_action": closure["owner_action"],
    }


def resolve_with_license_gate(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve-time gate over a resolved dependency closure: an
    incompatible combination is reported here with the exact offending
    pair instead of silently installing.
    """
    ids = [pkg.get("license") for pkg in resolved or []]
    closure = check_closure(ids)
    return {
        "ok": closure["ok"],
        "packages": [str(pkg.get("name") or "<unnamed>") for pkg in resolved or []],
        "offending": closure["offending"],
        "unknown": closure["unknown"],
        "needs_review": closure["needs_review"],
        "owner_action": closure["owner_action"],
        "legal_disclaimer": LEGAL_DISCLAIMER,
    }
