"""Reject unportable filenames at publish time (TST-0199)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REJECTED_UNPORTABLE = "REJECTED_UNPORTABLE"
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
ILLEGAL = set('<>:"/\\|?*')

CORPUS: dict[str, Any] = {
    "portable": ["readme.txt", "src/main.py", "docs/guide.md", "pkg-1.2.3.tgz"],
    "unportable": [
        {"name": "CON", "rule": "windows-reserved-device"},
        {"name": "PRN.txt", "rule": "windows-reserved-device"},
        {"name": "AUX", "rule": "windows-reserved-device"},
        {"name": "NUL", "rule": "windows-reserved-device"},
        {"name": "COM1", "rule": "windows-reserved-device"},
        {"name": "COM9.log", "rule": "windows-reserved-device"},
        {"name": "LPT1", "rule": "windows-reserved-device"},
        {"name": "LPT9.out", "rule": "windows-reserved-device"},
        {"name": "bad:name.txt", "rule": "illegal-char-colon"},
        {"name": "star*.txt", "rule": "illegal-char-asterisk"},
        {"name": "q?.txt", "rule": "illegal-char-question"},
        {"name": "a<b.txt", "rule": "illegal-char-lessthan"},
        {"name": "a>b.txt", "rule": "illegal-char-greaterthan"},
        {"name": "pipe|.txt", "rule": "illegal-char-pipe"},
        {"name": "quote\".txt", "rule": "illegal-char-quote"},
        {"name": "slash/name.txt", "rule": "path-separator"},
        {"name": "back\\slash.txt", "rule": "path-separator"},
        {"name": "trailing. ", "rule": "trailing-space"},
        {"name": "trailingdot.", "rule": "trailing-dot"},
        {"name": " spacelead.txt", "rule": "leading-space"},
        {"name": "nul\x00byte.txt", "rule": "nul-byte"},
        {"name": "a" * 256 + ".txt", "rule": "name-too-long"},
        {"name": "..", "rule": "dot-dot"},
        {"name": ".", "rule": "dot"},
        {"name": "foo ", "rule": "trailing-space"},
        {"name": "foo.", "rule": "trailing-dot"},
        {"name": "COM5", "rule": "windows-reserved-device"},
        {"name": "LPT3.TXT", "rule": "windows-reserved-device"},
        {"name": "CON.txt", "rule": "windows-reserved-device"},
        {"name": "bad<name", "rule": "illegal-char-lessthan"},
        {"name": "bad>name", "rule": "illegal-char-greaterthan"},
        {"name": "bad|name", "rule": "illegal-char-pipe"},
        {"name": "bad\"name", "rule": "illegal-char-quote"},
        {"name": "bad:name", "rule": "illegal-char-colon"},
        {"name": "bad*name", "rule": "illegal-char-asterisk"},
        {"name": "bad?name", "rule": "illegal-char-question"},
        {"name": "dir/../x.txt", "rule": "path-separator"},
        {"name": "C:\\abs.txt", "rule": "path-separator"},
        {"name": "aux.txt", "rule": "windows-reserved-device"},
        {"name": "nul.txt", "rule": "windows-reserved-device"},
    ],
}


def load_corpus() -> dict[str, Any]:
    return CORPUS


def classify(name: str) -> str | None:
    base = name.replace("\\", "/").split("/")[-1]
    stem = base.split(".")[0].upper()
    if stem in RESERVED:
        return "windows-reserved-device"
    if any(ch in ILLEGAL for ch in name):
        if ":" in name:
            return "illegal-char-colon"
        if "*" in name:
            return "illegal-char-asterisk"
        if "?" in name:
            return "illegal-char-question"
        if "<" in name:
            return "illegal-char-lessthan"
        if ">" in name:
            return "illegal-char-greaterthan"
        if "|" in name:
            return "illegal-char-pipe"
        if '"' in name:
            return "illegal-char-quote"
        if "/" in name or "\\" in name:
            return "path-separator"
    if "\x00" in name:
        return "nul-byte"
    if name.endswith(" "):
        return "trailing-space"
    if name.endswith("."):
        return "trailing-dot"
    if name.startswith(" "):
        return "leading-space"
    if name in {".", ".."}:
        return "dot-dot" if name == ".." else "dot"
    if len(name) > 255:
        return "name-too-long"
    return None
