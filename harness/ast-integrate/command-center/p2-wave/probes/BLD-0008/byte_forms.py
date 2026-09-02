"""Byte-form transformers: LF, CRLF, UTF-8 BOM, CRLF+BOM, UTF-16LE, mixed."""

from __future__ import annotations

UTF8_BOM = b"\xef\xbb\xbf"
UTF16LE_BOM = b"\xff\xfe"

BYTE_FORMS = (
    "lf",
    "crlf",
    "utf8-bom",
    "crlf+bom",
    "utf16le",
    "mixed",
)


def to_crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def to_mixed(text: str) -> str:
    """Alternate LF and CRLF lines so mixed-within-one-file is real, not a label."""
    lf = text.replace("\r\n", "\n")
    lines = lf.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        if i == len(lines) - 1 and line == "":
            continue
        nl = "\r\n" if i % 2 else "\n"
        out.append(line + nl)
    return "".join(out)


def encode_form(text: str, form: str) -> bytes:
    lf = text.replace("\r\n", "\n")
    if form == "lf":
        return lf.encode("utf-8")
    if form == "crlf":
        return to_crlf(lf).encode("utf-8")
    if form == "utf8-bom":
        return UTF8_BOM + lf.encode("utf-8")
    if form == "crlf+bom":
        return UTF8_BOM + to_crlf(lf).encode("utf-8")
    if form == "utf16le":
        return UTF16LE_BOM + lf.encode("utf-16-le")
    if form == "mixed":
        return to_mixed(lf).encode("utf-8")
    raise ValueError(f"unknown byte form {form}")
