"""Independent byte-linter for unportable names (TST-0199 probe 2)."""
from __future__ import annotations

from typing import Iterable

ILLEGAL = set('<>:"/\\|?*')
RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def lint_names(names: Iterable[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for name in names:
        rule = _rule(str(name))
        if rule:
            hits.append({"name": str(name), "rule": rule})
    return hits


def reserved_device_stub(names: Iterable[str]) -> list[dict[str, str]]:
    """Negative control: only CLOCK$/ $IDLE$ — silent on the TST-0199 corpus."""
    hits = []
    for name in names:
        if str(name).upper() in {"CLOCK$", "$IDLE$"}:
            hits.append({"name": str(name), "rule": "windows-reserved-device"})
    return hits


def _rule(name: str) -> str | None:
    base = name.replace("\\", "/").split("/")[-1]
    stem = base.split(".")[0].upper()
    if stem in RESERVED:
        return "windows-reserved-device"
    if any(ch in ILLEGAL for ch in name) or "/" in name or "\\" in name:
        return "illegal-char"
    if name.endswith(" ") or name.endswith(".") or name.startswith(" "):
        return "trailing-or-leading-ws"
    if "\x00" in name:
        return "nul-byte"
    if name in {".", ".."}:
        return "dot"
    if len(name) > 255:
        return "name-too-long"
    return None
