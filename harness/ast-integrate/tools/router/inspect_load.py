"""Independent instrument for load_mode. IMP-0387.

Deliberately NOT the YAML resolver: it measures the load mode from the raw
text of a rule file (frontmatter fence + a ``paths:`` key carrying a globstar)
so that the resolver's prediction can be checked against an instrument that
shares none of its parsing code.  Usable in-process (``inspect_load_mode``) or
as a subprocess (``python3 inspect_load.py --json <rule.md>``), which is how
the probes obtain the *measured* column.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALWAYS_ON = "ALWAYS-ON"
LAZY = "LAZY"

# A TOP-LEVEL ``paths`` key: column 0, no indentation.  A ``paths:`` nested
# under another key (indented) or mentioned in the body is not the load switch.
_TOP_LEVEL_PATHS = re.compile(r"^paths\s*:", re.MULTILINE)


def _frontmatter_block(text: str) -> str:
    """Raw text between the opening ``---`` fence and the closing one ('' if none)."""
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def inspect_load_mode(text: str) -> str:
    block = _frontmatter_block(text)
    if block and _TOP_LEVEL_PATHS.search(block):
        return LAZY
    return ALWAYS_ON


def inspect_text(text: str) -> dict[str, Any]:
    """Structured measurement of one rule text (the evidence behind the verdict)."""
    block = _frontmatter_block(text)
    return {
        "load_mode": inspect_load_mode(text),
        "has_frontmatter": bool(block),
        "has_paths_key": bool(block and _TOP_LEVEL_PATHS.search(block)),
        "has_globstar": "**/*" in block,
        "frontmatter_bytes": len(block.encode("utf-8")),
        "body_bytes": len(text.encode("utf-8")) - len(block.encode("utf-8")),
    }


def inspect_file(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    doc = inspect_text(text)
    doc["path"] = str(p)
    doc["name"] = p.name
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_load.py",
        description="Measure the load mode (ALWAYS-ON / LAZY) of rule files from raw text.",
    )
    parser.add_argument("paths", nargs="+", help="rule file(s) to inspect")
    parser.add_argument("--json", action="store_true", help="emit a JSON document instead of text")
    args = parser.parse_args(argv)

    results: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw in args.paths:
        p = Path(raw)
        if not p.is_file():
            missing.append(raw)
            continue
        results.append(inspect_file(p))
    if missing:
        print(f"inspect_load: no such file: {', '.join(missing)}", file=sys.stderr)
        return 2

    if args.json:
        payload: Any = results[0] if len(results) == 1 else {"files": results}
        print(json.dumps(payload, sort_keys=True))
    else:
        for doc in results:
            print(f"{doc['load_mode']}\t{doc['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
