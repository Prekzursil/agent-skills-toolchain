#!/usr/bin/env python3
"""Licence classification and compatibility gate for REL-0013.

Riders are a first-class blocking class. UNKNOWN never defaults to permissive.
Copyleft carried into a permissive release blocks. Clean-room reimplementation
does not import the source copyleft into the outbound artefact.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

PERMISSIVE = frozenset(
    {
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "ISC",
        "0BSD",
        "CC0-1.0",
        "Unlicense",
        "Python-2.0",
        "Zlib",
    }
)
WEAK_COPYLEFT = frozenset(
    {
        "MPL-2.0",
        "LGPL-2.1",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "EPL-2.0",
        "CDDL-1.0",
    }
)
STRONG_COPYLEFT = frozenset(
    {
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "Sleepycat",
    }
)
UNKNOWN_LABELS = frozenset(
    {"", "UNKNOWN", "NOASSERTION", "NONE", "UNLICENSED", "UNLICENSED-UNKNOWN"}
)
CARRIED = frozenset(
    {
        "ADOPT-AS-IS",
        "TRANSLATE",
        "DISTILL",
        "ADOPT-WITH-WRAPPER",
        "EXTEND",
        "MERGE",
        "SPECIALIZE",
        "REPAIR",
        None,
        "",
    }
)
NOT_CARRIED = frozenset(
    {"CLEAN-ROOM-REIMPLEMENT", "REBUILD-FROM-SPEC", "REJECT", "RETIRE"}
)

CLASS_PERMISSIVE = "permissive"
CLASS_WEAK = "weak-copyleft"
CLASS_STRONG = "strong-copyleft"
CLASS_UNKNOWN = "unknown-terms"
CLASS_RIDER = "restrictive-rider"

RIDER_PATTERNS = (
    re.compile(
        r"may not be used to train or\s+evaluate machine learning models",
        re.I,
    ),
    re.compile(r"no-ml-training", re.I),
    re.compile(r"not be used to train.{0,80}(machine learning|\bml\b)", re.I),
    re.compile(r"field[- ]of[- ]use", re.I),
    re.compile(r"non-commercial", re.I),
    re.compile(r"not for commercial", re.I),
)
COPYLEFT_TEXT = re.compile(
    r"gnu (affero )?general public license|licensed as a whole at no charge",
    re.I,
)


def lf_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return lf_sha256(raw), len(raw.replace(b"\r\n", b"\n"))


def _norm_spdx(value: str | None) -> str:
    return (value or "").strip()


def carried_into_release(disposition: str | None) -> bool:
    disp = disposition if disposition is not None else ""
    if disp in NOT_CARRIED:
        return False
    return disp in CARRIED or disp == ""


def detect_rider(text: str) -> str | None:
    if not text:
        return None
    for pat in RIDER_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def spdx_family(spdx: str) -> str:
    if not spdx or spdx.upper() in UNKNOWN_LABELS:
        return CLASS_UNKNOWN
    if spdx in STRONG_COPYLEFT:
        return CLASS_STRONG
    if spdx in WEAK_COPYLEFT:
        return CLASS_WEAK
    if spdx in PERMISSIVE:
        return CLASS_PERMISSIVE
    return CLASS_UNKNOWN


@dataclass
class Classified:
    spdx: str
    base_spdx: str | None
    licence_class: str
    rider_quote: str | None
    unknown_reason: str | None
    text_path: str | None
    text_sha256: str | None
    text_bytes: int = 0
    notes: list[str] = field(default_factory=list)


def classify_licence(
    *,
    declared_spdx: str | None,
    text: str | None,
    text_path: str | None,
    text_sha256: str | None,
    text_bytes: int = 0,
) -> Classified:
    """Classify from the licence *text* plus declared SPDX.

    Declared SPDX without readable text is UNKNOWN, never MIT.
    A rider on a permissive SPDX is class restrictive-rider, never the base name.
    """
    declared = _norm_spdx(declared_spdx)
    body = text if isinstance(text, str) else ""
    rider = detect_rider(body)
    family = spdx_family(declared)

    if not body.strip() or not text_path:
        reason = "no licence text was read; declared SPDX is not a substitute"
        if not text_path:
            reason = "no licence_text_path; terms could not be established"
        return Classified(
            spdx="UNKNOWN",
            base_spdx=declared or None,
            licence_class=CLASS_UNKNOWN,
            rider_quote=None,
            unknown_reason=reason,
            text_path=text_path,
            text_sha256=text_sha256,
            text_bytes=text_bytes,
        )

    if rider:
        return Classified(
            spdx=f"{declared or 'UNKNOWN'}-WITH-RIDER"
            if declared and declared.upper() not in UNKNOWN_LABELS
            else "UNKNOWN-WITH-RIDER",
            base_spdx=declared or None,
            licence_class=CLASS_RIDER,
            rider_quote=rider,
            unknown_reason=None,
            text_path=text_path,
            text_sha256=text_sha256,
            text_bytes=text_bytes,
            notes=["rider not folded into base SPDX name"],
        )

    text_copyleft = bool(COPYLEFT_TEXT.search(body))
    if text_copyleft and family == CLASS_PERMISSIVE:
        return Classified(
            spdx="UNKNOWN",
            base_spdx=declared or None,
            licence_class=CLASS_UNKNOWN,
            rider_quote=None,
            unknown_reason=(
                "licence text contains copyleft phrasing that disagrees with "
                f"declared SPDX {declared!r}"
            ),
            text_path=text_path,
            text_sha256=text_sha256,
            text_bytes=text_bytes,
        )

    if family == CLASS_UNKNOWN:
        return Classified(
            spdx="UNKNOWN",
            base_spdx=declared or None,
            licence_class=CLASS_UNKNOWN,
            rider_quote=None,
            unknown_reason=f"SPDX {declared!r} is not a known identifier",
            text_path=text_path,
            text_sha256=text_sha256,
            text_bytes=text_bytes,
        )

    return Classified(
        spdx=declared,
        base_spdx=declared,
        licence_class=family,
        rider_quote=None,
        unknown_reason=None,
        text_path=text_path,
        text_sha256=text_sha256,
        text_bytes=text_bytes,
    )


def read_licence(repo: Path, rel: str | None) -> tuple[str | None, str | None, str | None, int]:
    if not rel:
        return None, None, None, 0
    path = repo / rel
    if not path.is_file():
        return None, rel, None, 0
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    return text, rel, lf_sha256(raw), len(raw.replace(b"\r\n", b"\n"))


def block_reason(
    classified: Classified,
    *,
    outbound_class: str,
    carried: bool,
) -> str | None:
    if not carried:
        return None
    if classified.licence_class == CLASS_UNKNOWN:
        return "unknown-terms"
    if classified.licence_class == CLASS_RIDER:
        return "restrictive-rider"
    if outbound_class == CLASS_PERMISSIVE and classified.licence_class in {
        CLASS_STRONG,
        CLASS_WEAK,
    }:
        return "licence-incompatible"
    if outbound_class == CLASS_WEAK and classified.licence_class == CLASS_STRONG:
        return "licence-incompatible"
    return None


def evaluate_entry(
    classified: Classified,
    *,
    outbound_class: str,
    disposition: str | None,
) -> dict:
    carried = carried_into_release(disposition)
    reason = block_reason(
        classified, outbound_class=outbound_class, carried=carried
    )
    return {
        "spdx": classified.spdx,
        "base_spdx": classified.base_spdx,
        "licence_class": classified.licence_class,
        "rider_quote": classified.rider_quote,
        "unknown_reason": classified.unknown_reason,
        "licence_text_path": classified.text_path,
        "licence_text_sha256": classified.text_sha256,
        "licence_text_bytes": classified.text_bytes,
        "disposition": disposition or None,
        "carried_into_release": carried,
        "block_reason": reason,
        "gate": "BLOCK" if reason else "ALLOW",
        "notes": list(classified.notes),
    }
