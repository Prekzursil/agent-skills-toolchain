"""Canonical SPDX body diff and extra-LICENSE restriction search.

Probe 1 diffs a component LICENSE against the canonical text of its declared
SPDX id after stripping copyright lines and collapsing whitespace. A raw
byte-diff is recorded only as a diagnostic: non-zero raw diff on a known
canonical file must NOT be treated as a rider (catalog control).

Probe 2 searches README, NOTICE, usage docs, package metadata and source
headers — files a LICENSE-only diff cannot see.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

# SPDX license-list MIT body (copyright line is a placeholder; stripped).
CANONICAL: dict[str, str] = {
    "MIT": (
        "MIT License\n"
        "\n"
        "Copyright (c) <year> <copyright holders>\n"
        "\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        'of this software and associated documentation files (the "Software"), to deal\n'
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n"
        "\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n"
        "\n"
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n"
    ),
    "ISC": (
        "ISC License\n"
        "\n"
        "Copyright (c) <year> <copyright holders>\n"
        "\n"
        "Permission to use, copy, modify, and/or distribute this software for any\n"
        "purpose with or without fee is hereby granted, provided that the above\n"
        "copyright notice and this permission notice appear in all copies.\n"
        "\n"
        'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES\n'
        "WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF\n"
        "MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR\n"
        "ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES\n"
        "WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN\n"
        "ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF\n"
        "OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.\n"
    ),
    "BSD-2-Clause": (
        "Copyright (c) <year> <owner>\n"
        "\n"
        "Redistribution and use in source and binary forms, with or without\n"
        "modification, are permitted provided that the following conditions are met:\n"
        "\n"
        "1. Redistributions of source code must retain the above copyright notice, this\n"
        "   list of conditions and the following disclaimer.\n"
        "\n"
        "2. Redistributions in binary form must reproduce the above copyright notice,\n"
        "   this list of conditions and the following disclaimer in the documentation\n"
        "   and/or other materials provided with the distribution.\n"
        "\n"
        'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"\n'
        "AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n"
        "IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE\n"
        "DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE\n"
        "FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL\n"
        "DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR\n"
        "SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER\n"
        "CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,\n"
        "OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE\n"
        "OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.\n"
    ),
}

_TITLE_LINES = frozenset(
    {
        "mit license",
        "mit licence",
        "mit license (with openai/anthropic rider)",
        "isc license",
        "bsd 2-clause license",
        "bsd 3-clause license",
        "apache license",
        "apache license version 2.0, january 2004",
    }
)

_RIDER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "no-ml-training",
        re.compile(
            r"train(?:ing|ed)?|fine[- ]?tune|machine learning|"
            r"eval(?:uation)?(?:\s+harness|\s+fold)|training corpus|"
            r"dataset.{0,40}(ml|model)|pipeline for machine learning",
            re.I,
        ),
    ),
    (
        "field-of-use",
        re.compile(
            r"restricted part(?:y|ies)|field[- ]of[- ]use|"
            r"no rights are granted to|additional rider",
            re.I,
        ),
    ),
    (
        "non-commercial",
        re.compile(r"non[- ]?commercial|not for commercial", re.I),
    ),
    (
        "attribution-in-ui",
        re.compile(
            r"attribution[- ]in[- ]ui|display (?:the )?copyright|"
            r"product ui must display",
            re.I,
        ),
    ),
    (
        "ethical-use",
        re.compile(r"ethical[- ]use|do not use.{0,40}surveillance", re.I),
    ),
)

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
    }
)

_LICENSE_NAMES = frozenset(
    {
        "license",
        "license.md",
        "license.txt",
        "licence",
        "licence.md",
        "licence.txt",
        "copying",
        "copying.md",
        "unlicense",
        "notice",
        "notice.md",
        "notice.txt",
    }
)

_EXTRA_NAMES = (
    "readme",
    "readme.md",
    "readme.txt",
    "notice",
    "notice.md",
    "notice.txt",
    "usage.md",
    "contributing.md",
    "package.json",
    "pyproject.toml",
    "cargo.toml",
)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")


def normalize_license_body(text: str) -> str:
    """Copyright- and whitespace-insensitive license body."""
    lines: list[str] = []
    for raw in normalize_newlines(text).split("\n"):
        s = re.sub(r"\s+", " ", raw).strip()
        if not s:
            continue
        low = s.lower()
        if low in _TITLE_LINES:
            continue
        if low.startswith("copyright"):
            continue
        lines.append(low)
    return " ".join(lines)


def extra_clauses(component_text: str, canonical_text: str) -> str:
    canon_n = normalize_license_body(canonical_text)
    extras: list[str] = []
    buf: list[str] = []
    for raw in normalize_newlines(component_text).split("\n"):
        s = raw.strip()
        if not s:
            if buf:
                para = " ".join(buf)
                buf = []
                n = normalize_license_body(para)
                if n and n not in canon_n:
                    extras.append(para)
            continue
        buf.append(s)
    if buf:
        para = " ".join(buf)
        n = normalize_license_body(para)
        if n and n not in canon_n:
            extras.append(para)
    return "\n\n".join(extras)


def classify_riders(text: str) -> list[str]:
    if not (text or "").strip():
        return []
    found: list[str] = []
    for name, pat in _RIDER_RULES:
        if pat.search(text):
            found.append(name)
    return found


def diff_against_canonical(license_text: str, declared_spdx: str) -> dict[str, Any]:
    spdx = (declared_spdx or "").strip() or "UNKNOWN"
    canonical = CANONICAL.get(spdx)
    raw_a = normalize_newlines(license_text)
    raw_b = normalize_newlines(canonical) if canonical else ""
    raw_zero = bool(canonical) and raw_a == raw_b
    body_a = normalize_license_body(license_text)
    body_b = normalize_license_body(canonical) if canonical else ""
    zero = bool(canonical) and body_a == body_b
    extra = extra_clauses(license_text, canonical) if canonical else license_text
    riders = classify_riders(extra) if not zero else []
    return {
        "declared_spdx": spdx,
        "canonical_known": canonical is not None,
        "raw_byte_zero_diff": raw_zero,
        "zero_diff": zero,
        "normalized_component_sha16": _sha16(body_a),
        "normalized_canonical_sha16": _sha16(body_b) if canonical else "",
        "extra_clauses": extra[:8000],
        "rider_classes": riders,
        "has_rider": bool(riders) or (canonical is not None and not zero and bool(extra.strip())),
    }


def _sha16(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extra_license_hits(root: Path, *, skip_license_blobs: bool = True) -> list[dict[str, Any]]:
    """Search restriction language outside LICENSE/COPYING blobs."""
    hits: list[dict[str, Any]] = []
    if not root.is_dir():
        return hits
    for path in _iter_files(root):
        name = path.name.lower()
        if skip_license_blobs and name in _LICENSE_NAMES and not name.startswith("notice"):
            continue
        if name.startswith("notice") or name in {n.lower() for n in _EXTRA_NAMES} or _is_header_candidate(path):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if name.endswith((".py", ".js", ".ts", ".c", ".h")):
                text = "\n".join(text.splitlines()[:40])
            classes = classify_riders(text)
            if classes:
                hits.append(
                    {
                        "path": path.as_posix(),
                        "rel": path.name,
                        "rider_classes": classes,
                        "excerpt": _excerpt(text, classes),
                    }
                )
    return hits


def _is_header_candidate(path: Path) -> bool:
    return path.suffix.lower() in {".py", ".js", ".ts", ".c", ".h", ".go", ".rs"}


def _excerpt(text: str, classes: Iterable[str]) -> str:
    low = text.lower()
    for name, pat in _RIDER_RULES:
        if name not in classes:
            continue
        m = pat.search(text)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 80)
            return text[start:end].replace("\n", " ")[:240]
    return low[:160]


def _iter_files(root: Path):
    for dirpath, dirnames, filenames in __import__("os").walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
        for name in filenames:
            yield Path(dirpath) / name
