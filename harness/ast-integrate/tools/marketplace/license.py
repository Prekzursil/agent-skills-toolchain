"""SPDX validation and declared-versus-actual pairing for marketplace packages."""
from __future__ import annotations

from typing import Any

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
        "code": SPDX_VALID if chosen in _KNOWN else SPDX_INVALID,
        "left": a,
        "right": b,
    }


def check_closure(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "args": list(args), "kwargs": kwargs}


def publication_gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}


def resolve_with_license_gate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}
