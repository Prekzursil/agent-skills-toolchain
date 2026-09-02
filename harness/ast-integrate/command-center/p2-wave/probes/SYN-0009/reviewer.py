"""Independent reviewer for SYN-0009.

Served only raw admitted inputs. Re-derives the known-present verdict
BEFORE the caller may show this unit's conclusion. Does not import the
synthesizer extractor and refuses to open SYN-0008/SYN-0009 outputs.
"""
from __future__ import annotations

import re
from pathlib import Path

from denylist import posix
from inventory import control_inventory

# Independent copy of the fact contract — not imported from synthesizer.
FACT_RE = re.compile(
    r"SYN-0009-FACT\s+id=(?P<id>[A-Z0-9-]+)\s+span=(?P<span>[A-Za-z0-9-]+)"
)
RAW_ONLY_FACT_ID = "RAW-ONLY-001"
RAW_ONLY_SPAN = "detector-control-fires-on-unsummarized-transcript-span"

FORBIDDEN_SUFFIXES = (
    "SYN-0009.raw-source-control.json",
    "SYN-0008.candidate-syntheses.json",
    "candidate-syntheses.json",
)


def _forbidden(rel: str) -> bool:
    path = posix(rel)
    name = Path(path).name
    return any(path.endswith(s) or name == s for s in FORBIDDEN_SUFFIXES)


def rederive(repo: Path) -> dict:
    """Read admitted raw files only. Must not open the unit conclusion."""
    inv = control_inventory(repo)
    facts: list[dict] = []
    opened: list[str] = []
    for row in inv["admitted"]:
        rel = row["path"]
        if _forbidden(rel):
            raise RuntimeError(f"reviewer refused synthesis conclusion path {rel}")
        fp = repo / rel
        text = fp.read_text(encoding="utf-8", errors="replace")
        opened.append(rel)
        for match in FACT_RE.finditer(text):
            facts.append(
                {
                    "id": match.group("id"),
                    "span": match.group("span"),
                    "source_path": rel,
                }
            )
    raw_only = [f for f in facts if f["id"] == RAW_ONLY_FACT_ID]
    in_excluded = False
    for row in inv["excluded"]:
        fp = repo / row["path"]
        if not fp.is_file():
            continue
        if RAW_ONLY_SPAN in fp.read_text(encoding="utf-8", errors="replace"):
            in_excluded = True
            break
    return {
        "opened_output": False,
        "opened_paths": opened,
        "facts": facts,
        "known_present": bool(raw_only),
        "fact_id": RAW_ONLY_FACT_ID,
        "span": RAW_ONLY_SPAN,
        "source_path": raw_only[0]["source_path"] if raw_only else "",
        "exists_only_in_raw": bool(raw_only) and not in_excluded,
        "admitted_count": inv["admitted_count"],
        "digest_class_admitted": inv["digest_class_admitted"],
        "method": "independent FACT_RE over admitted raw files; conclusion withheld",
    }
