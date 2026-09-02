"""Gap-class and scanner-exit classification for BLD-0053.

Gap classes (catalog): no provenance, no pin, no lockfile hash, no SBOM
entry, no license record, no advisory query. Floating ranges are NO-PIN.

Exit 127 is TOOL-MISSING, never CLEAN. A naive classifier that maps any
non-1 exit to CLEAN is the planted control the probes must catch.
"""
from __future__ import annotations

import re
from typing import Any

GAP_ORDER = (
    "NO-PIN",
    "NO-LOCKFILE-HASH",
    "NO-PROVENANCE",
    "NO-LICENSE-RECORD",
    "NO-SBOM-ENTRY",
    "NO-ADVISORY-QUERY",
)

EXACT_NPM = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
EXACT_PY = re.compile(
    r"^==\s*\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.]+)?$"
)
EXACT_BARE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def classify_scanner_exit(code: int) -> str:
    """Map a scanner process exit to a verdict class.

    0 = CLEAN, 1 = FINDINGS, 127 = TOOL-MISSING. Any other code is also
    TOOL-MISSING: it is not a scanner verdict and must never be CLEAN.
    """
    if code == 0:
        return "CLEAN"
    if code == 1:
        return "FINDINGS"
    return "TOOL-MISSING"


def naive_scanner_exit(code: int) -> str:
    """Planted-wrong classifier: treats 127 as CLEAN."""
    if code == 1:
        return "FINDINGS"
    return "CLEAN"


def is_exact_pin(spec: str | None, ecosystem: str = "npm") -> bool:
    text = (spec or "").strip()
    if not text or text in {"*", "latest", "x", "X"}:
        return False
    eco = (ecosystem or "npm").lower()
    if eco in {"pypi", "python"}:
        if EXACT_PY.match(text):
            return True
        if text.startswith("=="):
            return bool(EXACT_BARE.match(text[2:].strip()))
        return False
    if eco in {"crates.io", "cargo", "rust"}:
        return bool(EXACT_BARE.match(text.lstrip("=")))
    if text.startswith(("^", "~", ">", "<", "*", "workspace:")):
        return False
    if any(tok in text for tok in ("||", " - ", ".x", ".*")):
        return False
    return bool(EXACT_NPM.match(text.lstrip("=v")))


def ordered_gaps(flags: dict[str, bool]) -> list[str]:
    return [g for g in GAP_ORDER if flags.get(g)]


def classify_dep(
    *,
    spec: str | None,
    ecosystem: str,
    integrity: str | None,
    resolved: str | None,
    license_record: str | None,
    in_sbom: bool,
    advisory_queried: bool,
    locked: bool,
) -> list[str]:
    flags = {
        "NO-PIN": not is_exact_pin(spec, ecosystem),
        "NO-LOCKFILE-HASH": not (locked and bool(integrity)),
        "NO-PROVENANCE": not bool(resolved),
        "NO-LICENSE-RECORD": not bool(license_record),
        "NO-SBOM-ENTRY": not in_sbom,
        "NO-ADVISORY-QUERY": not advisory_queried,
    }
    return ordered_gaps(flags)


def row_key(ecosystem: str, name: str, version: str | None) -> str:
    return f"{ecosystem}:{name}@{version or '?'}"


def compact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: compact(v) for k, v in obj.items() if v is not None}
    return obj
