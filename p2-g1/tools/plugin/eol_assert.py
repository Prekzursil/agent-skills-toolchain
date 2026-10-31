"""EOL assertions for shipped shell scripts (blob vs worktree)."""
from __future__ import annotations

from pathlib import Path

REQUIRED_EOL_LF = ("*.sh",)


def missing_eol_lf_patterns(gitattributes: str) -> list[str]:
    present: set[str] = set()
    for raw in gitattributes.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pat, *attrs = parts
        joined = " ".join(attrs)
        if "eol=lf" in joined:
            present.add(pat)
    return [p for p in REQUIRED_EOL_LF if p not in present]
