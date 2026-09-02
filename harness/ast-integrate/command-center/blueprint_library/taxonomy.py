"""Category counts are re-derived from the spec text, never a magic integer."""
from __future__ import annotations

from pathlib import Path

SPEC_REL = "blueprint_library/fixtures/required-library-taxonomy.md"


def load_spec_text(root: Path) -> str:
    return (Path(root) / "command-center" / SPEC_REL).read_text(encoding="utf-8")


def parse_category_counts(spec_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in spec_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, rest = stripped.partition(":")
        rest = rest.strip()
        if not rest or not rest[0].isdigit():
            continue
        counts[key.strip()] = int(rest.split()[0])
    return counts


def derived_library_total(spec_text: str) -> int:
    return sum(parse_category_counts(spec_text).values())
