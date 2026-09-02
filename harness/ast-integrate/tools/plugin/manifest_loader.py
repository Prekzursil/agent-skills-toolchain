"""Encoding-aware manifest loader with ONE declared policy (TST-0183).

Policy ``accept-and-normalize``: a manifest may arrive as UTF-8, UTF-8 with a
BOM, UTF-16 (LE/BE, with or without BOM) or UTF-32.  The loader detects the
encoding from the BOM or from the RFC 4627 section 3 NUL-byte pattern, decodes
*strictly* (no replacement characters), and hands the resulting text to the
strict RFC 8259 parser.  Every accepted input therefore yields the same
document and byte-identical UTF-8 for every field value; a decode failure or
a JSON5-ism is rejected with a precise ``reject:<stage>`` message.

Normalisation happens at the *byte->text* stage only.  No "repair" ever runs
on decoded text: rewriting U+00D7 U+00A5 as a mis-decoded UTF-8 pair (the
AUD-0085 mistake) would corrupt correctly encoded text, which is exactly what
:data:`CANONICAL_DESCRIPTION` is built to detect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plugin.strict_json import StrictJSONError, parse_strict

__all__ = [
    "CANONICAL_DESCRIPTION",
    "LoadedManifest",
    "ManifestLoadError",
    "POLICY",
    "SUPPORTED_ENCODINGS",
    "detect_encoding",
    "encode_manifest",
    "load_manifest_bytes",
    "load_manifest_path",
    "sample_manifest",
]

POLICY = "accept-and-normalize"

# Deliberately carries U+00D7 U+00A5 ("×¥"): as UTF-8 these are C3 97 C2 A5,
# which a wrong-stage latin-1 pair "repair" would collapse into U+05E5.
CANONICAL_DESCRIPTION = "Demo plugin — price ×¥1200, naïve café, 日本語 OK"

SUPPORTED_ENCODINGS = (
    "utf-8",
    "utf-8-sig",
    "utf-16-le",
    "utf-16-be",
    "utf-16",
    "utf-32-le",
    "utf-32-be",
    "utf-32",
)

_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


class ManifestLoadError(ValueError):
    """Rejection with a precise stage: ``encoding``, ``json`` or ``shape``."""

    def __init__(self, stage: str, detail: str, *, encoding: str = "") -> None:
        super().__init__(f"reject:{stage} {detail}")
        self.stage = stage
        self.detail = detail
        self.encoding = encoding


@dataclass(frozen=True)
class LoadedManifest:
    """Result of :func:`load_manifest_bytes`."""

    document: dict[str, Any]
    encoding: str
    bom: bool
    source_bytes: int
    text: str
    policy: str = POLICY

    @property
    def normalized_utf8(self) -> bytes:
        """The decoded text re-encoded as BOM-less UTF-8."""
        return self.text.encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "encoding": self.encoding,
            "bom": self.bom,
            "source_bytes": self.source_bytes,
            "policy": self.policy,
            "name": self.document.get("name"),
        }


def sample_manifest() -> dict[str, Any]:
    """The fixture document used by the TST-0183 probes."""
    return {
        "name": "encoding-demo",
        "version": "1.0.0",
        "description": CANONICAL_DESCRIPTION,
        "author": {"name": "Zoë Müller-Ångström"},
        "license": "MIT",
        "keywords": ["encoding", "utf-8", "utf-16", "manifest"],
    }


def _normalize_codec(encoding: str) -> str:
    codec = encoding.strip().lower().replace("_", "-")
    aliases = {
        "utf8": "utf-8",
        "utf8-sig": "utf-8-sig",
        "utf16": "utf-16",
        "utf16le": "utf-16-le",
        "utf16be": "utf-16-be",
        "utf32": "utf-32",
        "utf32le": "utf-32-le",
        "utf32be": "utf-32-be",
    }
    codec = aliases.get(codec, codec)
    if codec not in SUPPORTED_ENCODINGS:
        raise ValueError(f"unsupported manifest encoding {encoding!r}")
    return codec


def encode_manifest(document: dict[str, Any], encoding: str = "utf-8") -> bytes:
    """Serialise ``document`` deterministically and encode it as ``encoding``.

    ``utf-8-sig``, ``utf-16`` and ``utf-32`` write a BOM (Python codec
    behaviour); the ``-le``/``-be`` variants do not.
    """
    codec = _normalize_codec(encoding)
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return text.encode(codec)


def detect_encoding(raw: bytes) -> tuple[str, bool]:
    """Return ``(codec, has_bom)`` from the BOM or the RFC 4627 NUL pattern."""
    for bom, codec in _BOMS:
        if raw.startswith(bom):
            return codec, True
    head = raw[:4]
    if len(head) >= 4:
        if head[0] == 0 and head[1] == 0 and head[2] == 0 and head[3] != 0:
            return "utf-32-be", False
        if head[0] == 0 and head[1] != 0 and head[2] == 0 and head[3] != 0:
            return "utf-16-be", False
        if head[0] != 0 and head[1] == 0 and head[2] == 0 and head[3] == 0:
            return "utf-32-le", False
        if head[0] != 0 and head[1] == 0 and head[2] != 0 and head[3] == 0:
            return "utf-16-le", False
    elif len(head) >= 2:
        if head[0] == 0 and head[1] != 0:
            return "utf-16-be", False
        if head[0] != 0 and head[1] == 0:
            return "utf-16-le", False
    return "utf-8", False


def _decode(raw: bytes, codec: str, bom: bool) -> str:
    if codec == "utf-8-sig":
        return raw.decode("utf-8-sig", errors="strict")
    if bom:
        for marker, marker_codec in _BOMS:
            if marker_codec == codec:
                raw = raw[len(marker) :]
                break
    return raw.decode(codec, errors="strict")


def load_manifest_bytes(raw: bytes) -> LoadedManifest:
    """Decode + strictly parse manifest bytes under :data:`POLICY`.

    Raises :class:`ManifestLoadError` with ``reject:encoding`` when the bytes
    are not valid in the detected encoding, ``reject:json`` when the text is
    not RFC 8259 JSON, and ``reject:shape`` when the root is not an object.
    """
    data = bytes(raw)
    codec, bom = detect_encoding(data)
    try:
        text = _decode(data, codec, bom)
    except UnicodeDecodeError as exc:
        raise ManifestLoadError(
            "encoding",
            f"{codec} decode failed at byte {exc.start}: {exc.reason}",
            encoding=codec,
        ) from exc
    if text.startswith("\ufeff"):
        # BOM survived an unusual codec combination; it is not part of the text.
        text = text[1:]
        bom = True
    try:
        document = parse_strict(text)
    except StrictJSONError as exc:
        raise ManifestLoadError(
            "json",
            f"{exc.kind} at {exc.line}:{exc.column}: {exc}",
            encoding=codec,
        ) from exc
    if not isinstance(document, dict):
        raise ManifestLoadError(
            "shape",
            f"manifest root must be an object, got {type(document).__name__}",
            encoding=codec,
        )
    return LoadedManifest(
        document=document,
        encoding=codec,
        bom=bom,
        source_bytes=len(data),
        text=text,
    )


def load_manifest_path(path: str | Path) -> LoadedManifest:
    """Load the manifest file at ``path`` under :data:`POLICY`."""
    return load_manifest_bytes(Path(path).read_bytes())
