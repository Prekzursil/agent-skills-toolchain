#!/usr/bin/env python3
"""Extract the canonical H6 helper source from the skill template.

The template ``skills/workflow-authoring/templates/h6-timeout-heartbeat.md`` is the
SINGLE source of truth for the H6 helper: there is deliberately no second ``.js``
copy to drift from it. This module pulls the marker-delimited fenced block out so
``test_h6_timeout.py`` can EXECUTE the exact bytes an author would paste.

Fails closed on every ambiguity (missing marker, missing fence, empty body, more
than one block) -- a linter that silently extracts nothing is a no-op gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

BEGIN = "<!-- H6-BEGIN -->"
END = "<!-- H6-END -->"
FENCE_OPEN = "```js"
FENCE_CLOSE = "```"

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (
    REPO_ROOT
    / "skills"
    / "workflow-authoring"
    / "templates"
    / "h6-timeout-heartbeat.md"
)


class ExtractError(RuntimeError):
    """The template does not contain exactly one well-formed H6 block."""


def extract_block(markdown: str) -> str:
    """Return the JS source between the H6 markers, fence lines stripped."""
    if markdown.count(BEGIN) != 1 or markdown.count(END) != 1:
        raise ExtractError(
            f"expected exactly one {BEGIN}/{END} pair, found "
            f"{markdown.count(BEGIN)}/{markdown.count(END)}"
        )
    start = markdown.index(BEGIN) + len(BEGIN)
    stop = markdown.index(END)
    if stop < start:
        raise ExtractError(f"{END} appears before {BEGIN}")
    inner = markdown[start:stop]
    lines = [ln for ln in inner.splitlines() if ln.strip()]
    if not lines or lines[0].strip() != FENCE_OPEN:
        raise ExtractError(f"H6 block does not open with a {FENCE_OPEN} fence")
    if lines[-1].strip() != FENCE_CLOSE:
        raise ExtractError(f"H6 block does not close with a {FENCE_CLOSE} fence")
    raw = inner.splitlines()
    open_at = raw.index(FENCE_OPEN)
    close_at = len(raw) - 1 - raw[::-1].index(FENCE_CLOSE)
    body = "\n".join(raw[open_at + 1 : close_at]).strip("\n")
    if not body.strip():
        raise ExtractError("H6 block is empty")
    return body + "\n"


def extract_file(path: Path = TEMPLATE) -> str:
    """Read ``path`` and extract its H6 block."""
    return extract_block(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="h6_extract",
        description="Extract the canonical H6 helper JS from the skill template.",
    )
    parser.add_argument("--template", default=str(TEMPLATE))
    parser.add_argument("--out", default=None, help="write here instead of stdout")
    ns = parser.parse_args(argv)
    try:
        body = extract_file(Path(ns.template))
    except (OSError, ExtractError) as exc:
        print(f"FAILED:h6-extract {exc}", file=sys.stderr)
        return 1
    if ns.out is None:
        sys.stdout.write(body)
    else:
        Path(ns.out).write_text(body, encoding="utf-8", newline="\n")
    print(f"SUCCESS:h6-extract {len(body)} bytes", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
