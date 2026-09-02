"""Strip architecture names and author ids from a dossier copy."""
from __future__ import annotations

import copy
import re
from typing import Any

# Opaque labels only. Do not leak A1–A9 or the nine class names into judge text.
_CLASS = [
    (re.compile(r"config-first-minimal", re.I), "CLASS"),
    (re.compile(r"config-first minimal", re.I), "CLASS"),
    (re.compile(r"generated-ssot", re.I), "CLASS"),
    (re.compile(r"generated SSOT", re.I), "CLASS"),
    (re.compile(r"marketplace-first", re.I), "CLASS"),
    (re.compile(r"gateway/lazy-activation", re.I), "CLASS"),
    (re.compile(r"lazy-activation", re.I), "CLASS"),
    (re.compile(r"distributed workflow-runtime", re.I), "CLASS"),
    (re.compile(r"workflow-runtime", re.I), "CLASS"),
    (re.compile(r"cross-vendor adapter", re.I), "CLASS"),
    (re.compile(r"security-first", re.I), "CLASS"),
    (re.compile(r"UX/product-first", re.I), "CLASS"),
    (re.compile(r"product-first", re.I), "CLASS"),
    (re.compile(r"maximal hybrid", re.I), "CLASS"),
    (re.compile(r"maximal-hybrid", re.I), "CLASS"),
]
_ARCH = re.compile(r"\bA([1-9]|1[01])\b")
_DROP_KEYS = {
    "architecture_id",
    "architecture_class",
    "architecture_name",
    "produced_by",
    "author",
    "author_id",
    "vendor",
    "model",
}


def _scrub_text(text: str) -> str:
    out = text
    for pat, repl in _CLASS:
        out = pat.sub(repl, out)
    out = _ARCH.sub("ENTRY", out)
    out = out.replace("phase3/A1/", "phase3/ENTRY/")
    out = out.replace("phase3/A2/", "phase3/ENTRY/")
    return out


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key, val in obj.items():
            if key in _DROP_KEYS:
                continue
            out[key] = scrub(val)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, str):
        return _scrub_text(obj)
    return copy.deepcopy(obj)


def leak_hits(obj: Any) -> list[str]:
    """Return leak strings found in a judge-visible object (for the leakage probe)."""
    found: list[str] = []
    names = [
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
        "A7",
        "A8",
        "A9",
        "config-first-minimal",
        "generated-ssot",
        "marketplace-first",
        "maximal hybrid",
    ]

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _DROP_KEYS:
                    found.append(k)
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, str):
            for n in names:
                if n in node:
                    found.append(n)

    walk(obj)
    return sorted(set(found))


leak_hits = leak_hits
