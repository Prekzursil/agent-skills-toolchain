"""Normalize license strings and LICENSE-file text to SPDX identifiers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"
AMBIGUOUS = "AMBIGUOUS"

_SPDX = {
    "MIT": "MIT",
    "MIT LICENSE": "MIT",
    "APACHE-2.0": "Apache-2.0",
    "APACHE LICENSE 2.0": "Apache-2.0",
    "APACHE LICENSE, VERSION 2.0": "Apache-2.0",
    "APACHE LICENSE VERSION 2.0": "Apache-2.0",
    "BSD-2-CLAUSE": "BSD-2-Clause",
    "BSD-3-CLAUSE": "BSD-3-Clause",
    "ISC": "ISC",
    "MPL-2.0": "MPL-2.0",
    "GPL-2.0-ONLY": "GPL-2.0-only",
    "GPL-3.0-ONLY": "GPL-3.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "AGPL-3.0-ONLY": "AGPL-3.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
    "LGPL-2.1-OR-LATER": "LGPL-2.1-or-later",
    "LGPL-3.0-OR-LATER": "LGPL-3.0-or-later",
    "UNLICENSE": "Unlicense",
    "PSF-2.0": "PSF-2.0",
    "ZPL-2.1": "ZPL-2.1",
    "SSPL-1.0": "SSPL-1.0",
}

_TEXT_FINGERPRINTS: tuple[tuple[str, str], ...] = (
    ("zero-clause bsd", "0BSD"),
    ("cc0 1.0 universal", "CC0-1.0"),
    ("eclipse public license", "EPL-2.0"),
    ("boost software license", "BSL-1.0"),
    ("this software is provided 'as-is'", "Zlib"),
    ("neither the name of the copyright holder", "BSD-3-Clause"),
    ("redistribution and use in source and binary forms", "BSD-2-Clause"),
    ("permission to use, copy, modify, and/or distribute this software for any", "ISC"),
    ("permission is hereby granted, free of charge", "MIT"),
    ("gnu affero general public license", "AGPL-3.0-only"),
    ("gnu general public license", "GPL-3.0-only"),
    ("gnu lesser general public license", "LGPL-2.1-or-later"),
    ("apache license", "Apache-2.0"),
    ("mozilla public license", "MPL-2.0"),
    ("this is free and unencumbered software", "Unlicense"),
)
_SPDX_HEADER = re.compile(
    r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", re.I
)

_WS = re.compile(r"\s+")


def _squash(value: str) -> str:
    return _WS.sub(" ", (value or "").strip()).upper().strip(".,;()")


def normalize_to_spdx(value: str | None) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).strip()
    if not text:
        return UNKNOWN
    key = _squash(text)
    if key in _SPDX:
        return _SPDX[key]
    low = text.lower()
    hits = [spdx for needle, spdx in _TEXT_FINGERPRINTS if needle in low]
    if len(set(hits)) == 1:
        return hits[0]
    if len(set(hits)) > 1:
        return AMBIGUOUS
    # SPDX combinators, not English LICENSE prose ("EXPRESS OR IMPLIED").
    if len(key) < 80 and (" OR " in key or " AND " in key or " WITH " in key):
        return AMBIGUOUS
    if key in {"BSD LICENSE", "BSD", "LGPL", "GPL"}:
        return AMBIGUOUS
    return UNKNOWN


def extract_from_blob(text: str | None) -> dict[str, Any]:
    spdx = normalize_to_spdx(text)
    return {"spdx": spdx, "raw_bytes": len(text or "")}


def _record(spdx: str, method: str, source_path: str) -> dict[str, Any]:
    blocked = spdx in {UNKNOWN, AMBIGUOUS}
    return {
        "spdx_id": spdx,
        "spdx": spdx,
        "method": method,
        "source_path": source_path,
        "blocked_from_redistribution": blocked,
    }


def extract_licence(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    # SPDX headers first (method=spdx-header).
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".c", ".h", ".py", ".java", ".js"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        m = _SPDX_HEADER.search(text)
        if m:
            return _record(m.group(1).strip(), "spdx-header", str(path.relative_to(root)).replace("\\", "/"))
    # package.json license field.
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            doc = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
        lic = doc.get("license") if isinstance(doc, dict) else None
        if isinstance(lic, str) and lic.strip():
            return _record(lic.strip(), "package-metadata", "package.json")
    # License files.
    for name in ("LICENSE", "COPYING", "UNLICENSE", "LICENCE"):
        path = root / name
        if path.is_file():
            blob = path.read_text(encoding="utf-8", errors="replace")
            header = _SPDX_HEADER.search(blob)
            if header:
                return _record(header.group(1).strip(), "spdx-header", name)
            spdx = normalize_to_spdx(blob)
            if spdx == UNKNOWN:
                low = blob.lower()
                for needle, ident in _TEXT_FINGERPRINTS:
                    if needle in low:
                        spdx = ident
                        break
            method = "license-file"
            return _record(spdx, method, name)
    return _record(UNKNOWN, "none", "")


def redistribution_gate(rec: Any) -> dict[str, Any]:
    if isinstance(rec, dict):
        spdx = rec.get("spdx_id") or rec.get("spdx") or UNKNOWN
    else:
        spdx = str(rec or UNKNOWN)
    if spdx in {UNKNOWN, AMBIGUOUS, "", "None"}:
        return {
            "allowed": False,
            "reason": "UNKNOWN-LICENCE-BLOCKS-REDISTRIBUTION",
            "spdx": spdx,
        }
    return {"allowed": True, "reason": "LICENCE-TERMS-KNOWN", "spdx": spdx}
