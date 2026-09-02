"""Declared vs LICENSE-file SPDX classification for AUD-0024.

A declared MIT with an AGPL LICENSE file is a conflict. The resolver never
picks either identifier as the winner. This module reports; it is not legal
advice.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"

CONFLICT = "DECLARED-VERSUS-ACTUAL-CONFLICT"
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"
ABSENT = "LICENSE-FILE-ABSENT"
LICENSE_ABSENT = "LICENSE-ABSENT"
UNKNOWN = "UNKNOWN"
LEGAL_DISCLAIMER = (
    "This inventory reports SPDX identifier membership, LICENSE-file fingerprints, "
    "and published-matrix lookup results. It is not legal advice, does not "
    "authorize combination or distribution, and does not replace owner review."
)

_COPYLEFT_STRONG = frozenset(
    {
        "GPL-1.0-only",
        "GPL-1.0-or-later",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-1.0-only",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "SSPL-1.0",
    }
)
_COPYLEFT_WEAK = frozenset(
    {
        "LGPL-2.0-only",
        "LGPL-2.0-or-later",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "MPL-1.1",
        "MPL-2.0",
        "EPL-1.0",
        "EPL-2.0",
        "CDDL-1.0",
        "CDDL-1.1",
    }
)

_DECLARED_ALIASES = {
    "mit license": "MIT",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache license version 2.0": "Apache-2.0",
    "bsd license": AMBIGUOUS,
    "lgpl": AMBIGUOUS,
    "lgplv2+": "LGPL-2.1-or-later",
    "lgplv2.1+": "LGPL-2.1-or-later",
    "lgplv3+": "LGPL-3.0-or-later",
    "gplv3": "GPL-3.0-only",
    "gplv2": "GPL-2.0-only",
    "zpl 2.1": "ZPL-2.1",
    "python software foundation license": "PSF-2.0",
}

_CLASSIFIER_MAP = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": AMBIGUOUS,
    "License :: OSI Approved :: BSD License": AMBIGUOUS,
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1-or-later",
    "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0-only",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: Zope Public License": "ZPL-2.1",
}

_LICENSE_NAMES = frozenset(
    {
        "license",
        "license.txt",
        "license.md",
        "license.rst",
        "licence",
        "licence.txt",
        "licence.md",
        "copying",
        "copying.txt",
        "copying.md",
        "copying.lesser",
        "unlicense",
        "unlicence",
    }
)

_EXPR_SPLIT = re.compile(r"\s+(?:OR|AND|WITH)\s+", re.IGNORECASE)

_normalize = None
_validate_spdx = None
_pair_verdict = None


def _load_prod() -> None:
    global _normalize, _validate_spdx, _pair_verdict
    if _normalize is not None:
        return
    wf = TOOLS / "workflow_foundry" / "license_extract.py"
    spec = importlib.util.spec_from_file_location("aud0024_license_extract", wf)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {wf}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _normalize = mod.normalize_to_spdx
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from marketplace.license import pair_verdict, validate_spdx  # noqa: WPS433

    _validate_spdx = validate_spdx
    _pair_verdict = pair_verdict


def normalize_to_spdx(value: str | None) -> str:
    _load_prod()
    return str(_normalize(value))


def validate_spdx(identifier: Any) -> dict:
    _load_prod()
    return dict(_validate_spdx(identifier))


def pair_verdict(left: Any, right: Any) -> dict:
    _load_prod()
    return dict(_pair_verdict(left, right))


def is_license_filename(name: str) -> bool:
    n = name.lower()
    if n in _LICENSE_NAMES:
        return True
    return n.startswith("license") or n.startswith("licence")


def looks_like_expression(raw: str) -> bool:
    return bool(_EXPR_SPLIT.search(raw or ""))


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower().strip(".,;()")


def declared_to_spdx(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {
            "raw": None,
            "spdx": LICENSE_ABSENT,
            "code": LICENSE_ABSENT,
            "ambiguous": False,
        }
    text = str(raw).strip()
    if not text:
        return {
            "raw": raw,
            "spdx": LICENSE_ABSENT,
            "code": LICENSE_ABSENT,
            "ambiguous": False,
        }
    if looks_like_expression(text):
        return {
            "raw": text,
            "spdx": AMBIGUOUS,
            "code": AMBIGUOUS,
            "ambiguous": True,
        }
    alias = _DECLARED_ALIASES.get(_squash(text))
    if alias == AMBIGUOUS:
        return {
            "raw": text,
            "spdx": AMBIGUOUS,
            "code": AMBIGUOUS,
            "ambiguous": True,
        }
    spdx = alias if isinstance(alias, str) else normalize_to_spdx(text)
    if spdx == UNKNOWN and text in _CLASSIFIER_MAP:
        spdx = _CLASSIFIER_MAP[text]
    gate = validate_spdx(spdx if spdx not in {UNKNOWN, AMBIGUOUS, LICENSE_ABSENT} else text)
    if spdx == AMBIGUOUS:
        return {
            "raw": text,
            "spdx": AMBIGUOUS,
            "code": AMBIGUOUS,
            "ambiguous": True,
            "spdx_gate": gate,
        }
    if gate.get("valid"):
        return {
            "raw": text,
            "spdx": gate.get("identifier") or spdx,
            "code": gate.get("code"),
            "ambiguous": False,
            "spdx_gate": gate,
        }
    if spdx not in {UNKNOWN, LICENSE_ABSENT, AMBIGUOUS}:
        # Fingerprinted but not on the SPDX list still names a family; keep it.
        return {
            "raw": text,
            "spdx": spdx,
            "code": gate.get("code") or "SPDX-INVALID",
            "ambiguous": False,
            "spdx_gate": gate,
        }
    return {
        "raw": text,
        "spdx": UNKNOWN,
        "code": gate.get("code") or "SPDX-INVALID",
        "ambiguous": False,
        "spdx_gate": gate,
    }


def classifier_to_spdx(classifiers: list[str]) -> dict[str, Any] | None:
    hits = [c for c in classifiers if isinstance(c, str) and "License ::" in c]
    mapped = []
    for c in hits:
        if c in _CLASSIFIER_MAP:
            mapped.append((_CLASSIFIER_MAP[c], c))
        else:
            mapped.append((UNKNOWN, c))
    if not mapped:
        return None
    ids = {m[0] for m in mapped}
    if AMBIGUOUS in ids and len(ids) == 1:
        return {
            "raw": mapped[0][1],
            "spdx": AMBIGUOUS,
            "code": AMBIGUOUS,
            "ambiguous": True,
            "source": "classifier",
        }
    concrete = {x for x in ids if x not in {UNKNOWN, AMBIGUOUS}}
    if len(concrete) == 1:
        only = next(iter(concrete))
        return declared_to_spdx(only) | {"source": "classifier", "raw": mapped[0][1]}
    if len(concrete) > 1:
        return {
            "raw": "; ".join(m[1] for m in mapped),
            "spdx": AMBIGUOUS,
            "code": AMBIGUOUS,
            "ambiguous": True,
            "source": "classifier",
        }
    return {
        "raw": mapped[0][1],
        "spdx": UNKNOWN,
        "code": "SPDX-INVALID",
        "ambiguous": False,
        "source": "classifier",
    }


def classify_license_blob(text: str | None) -> dict[str, Any]:
    if text is None or not str(text).strip():
        return {
            "spdx": UNKNOWN,
            "code": "EMPTY-LICENSE-FILE",
            "method": "license-file",
        }
    spdx = normalize_to_spdx(text)
    gate = validate_spdx(spdx if spdx != UNKNOWN else None)
    return {
        "spdx": spdx if spdx != UNKNOWN else UNKNOWN,
        "code": gate.get("code") if spdx != UNKNOWN else "UNRECOGNIZED-LICENSE-TEXT",
        "method": "license-file",
        "spdx_gate": gate if spdx != UNKNOWN else None,
    }


def resolve_declared_versus_actual(
    declared_spdx: str | None,
    actual_spdx: str | None,
    *,
    license_file_present: bool,
) -> dict[str, Any]:
    """Never silently resolve a metadata/file divergence to either side."""
    d = declared_spdx if declared_spdx not in {None, "", LICENSE_ABSENT} else None
    a = actual_spdx if actual_spdx not in {None, "", ABSENT} else None
    if license_file_present:
        if d and a and d != a:
            return {
                "resolved_spdx": CONFLICT,
                "conflict": True,
                "unresolved": True,
                "ambiguous": d == AMBIGUOUS or a == AMBIGUOUS,
                "reason": "declared-versus-actual-divergence",
            }
        if a and a not in {UNKNOWN, AMBIGUOUS}:
            if d in {None, UNKNOWN, AMBIGUOUS}:
                return {
                    "resolved_spdx": a,
                    "conflict": False,
                    "unresolved": False,
                    "ambiguous": False,
                    "reason": "license-file-only",
                }
            return {
                "resolved_spdx": a,
                "conflict": False,
                "unresolved": False,
                "ambiguous": False,
                "reason": "declared-matches-actual",
            }
        if license_file_present and a in {UNKNOWN, AMBIGUOUS} and d and d not in {UNKNOWN, AMBIGUOUS}:
            return {
                "resolved_spdx": CONFLICT,
                "conflict": True,
                "unresolved": True,
                "ambiguous": a == AMBIGUOUS,
                "reason": "license-file-present-but-unclassified-versus-declared",
            }
        if a in {UNKNOWN, AMBIGUOUS}:
            return {
                "resolved_spdx": AMBIGUOUS if a == AMBIGUOUS else UNRESOLVED,
                "conflict": False,
                "unresolved": True,
                "ambiguous": a == AMBIGUOUS,
                "reason": "license-file-unclassified",
            }
    if d in {AMBIGUOUS}:
        return {
            "resolved_spdx": AMBIGUOUS,
            "conflict": False,
            "unresolved": True,
            "ambiguous": True,
            "reason": "declared-expression-or-family-only",
        }
    if d and d not in {UNKNOWN}:
        return {
            "resolved_spdx": d,
            "conflict": False,
            "unresolved": False,
            "ambiguous": False,
            "reason": "declared-metadata-only-file-absent",
        }
    if d == UNKNOWN:
        return {
            "resolved_spdx": UNRESOLVED,
            "conflict": False,
            "unresolved": True,
            "ambiguous": False,
            "reason": "declared-unknown-file-absent",
        }
    return {
        "resolved_spdx": UNRESOLVED,
        "conflict": False,
        "unresolved": True,
        "ambiguous": False,
        "reason": "no-declared-no-file",
    }


def copyleft_class(spdx: str | None) -> str:
    if not spdx or spdx in {CONFLICT, UNRESOLVED, AMBIGUOUS, ABSENT, LICENSE_ABSENT, UNKNOWN}:
        return "none"
    if spdx in _COPYLEFT_STRONG:
        return "strong"
    if spdx in _COPYLEFT_WEAK:
        return "weak"
    if spdx.startswith("GPL-") or spdx.startswith("AGPL-"):
        return "strong"
    if spdx.startswith("LGPL-") or spdx.startswith("MPL-"):
        return "weak"
    return "none"


def marketplace_flag(
    *,
    intended_spdx: str,
    resolved_spdx: str,
    conflict: bool,
) -> dict[str, Any]:
    """Public-marketplace distribution gate. Not legal advice.

    pair_verdict(MIT, GPL-3.0-only) is COMPATIBLE in the combined-work matrix
    because GPL can take MIT inbound. That is the wrong question for shipping
    an undeclared/permissive marketplace plugin that contains copyleft code.
    """
    intended = intended_spdx if intended_spdx not in {None, ""} else LICENSE_ABSENT
    copyleft = copyleft_class(resolved_spdx)
    if conflict or resolved_spdx == CONFLICT:
        return {
            "incompatible_with_public_marketplace": True,
            "verdict": "INCOMPATIBLE",
            "reason": "declared-versus-actual-conflict-blocks-publication",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    if resolved_spdx in {UNRESOLVED, UNKNOWN, LICENSE_ABSENT}:
        return {
            "incompatible_with_public_marketplace": True,
            "verdict": "UNKNOWN-NEEDS-REVIEW",
            "reason": "unresolved-license-never-treated-as-compatible",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    if resolved_spdx == AMBIGUOUS:
        return {
            "incompatible_with_public_marketplace": True,
            "verdict": "UNKNOWN-NEEDS-REVIEW",
            "reason": "ambiguous-spdx-expression",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    if copyleft == "strong":
        return {
            "incompatible_with_public_marketplace": True,
            "verdict": "INCOMPATIBLE",
            "reason": "strong-copyleft-inbound-forces-stricter-outbound-than-undeclared-or-permissive-marketplace-plugin",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    if copyleft == "weak":
        return {
            "incompatible_with_public_marketplace": True,
            "verdict": "UNKNOWN-NEEDS-REVIEW",
            "reason": "weak-copyleft-inbound-owner-review-required",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    if intended in {LICENSE_ABSENT, UNRESOLVED, UNKNOWN, AMBIGUOUS, CONFLICT}:
        # Permissive dep under an undeclared plugin license: plugin itself is
        # still LICENSE-ABSENT. The *package* is not copyleft-incompatible.
        return {
            "incompatible_with_public_marketplace": False,
            "verdict": "COMPATIBLE-FAMILY-PLUGIN-LICENSE-UNDECLARED",
            "reason": "permissive-or-known-noncopyleft; plugin outbound remains LICENSE-ABSENT",
            "copyleft": copyleft,
            "legal_advice": False,
        }
    pv = pair_verdict(intended, resolved_spdx)
    return {
        "incompatible_with_public_marketplace": pv.get("verdict") != "COMPATIBLE",
        "verdict": pv.get("verdict"),
        "reason": "published-matrix-lookup-versus-intended-outbound",
        "copyleft": copyleft,
        "pair": pv,
        "legal_advice": False,
    }


def find_license_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(p in {".git", "node_modules", "__pycache__", ".venv"} for p in path.parts):
                continue
            if is_license_filename(path.name):
                found.append(path)
    except OSError:
        return []
    found.sort(key=lambda p: (len(p.parts), p.as_posix().lower()))
    return found


def read_text(path: Path, limit: int = 256_000) -> str:
    data = path.read_bytes()[:limit]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data.decode("utf-8", errors="replace")


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=1, sort_keys=True)
