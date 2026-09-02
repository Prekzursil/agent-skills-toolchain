#!/usr/bin/env python3
"""Write remaining G-1 probe-missing production files (real implementations)."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def w(rel: str, text: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> None:
    w(
        "tools/marketplace/fixtures/planted_collisions.json",
        r'''{
  "existing": ["agent-skills-toolchain", "demo-kit"],
  "valid": ["demo-kit", "json-lint", "alpha-helper"],
  "reserved": ["com", "org", "www", "marketplace"],
  "casefold": [
    {"name": "Agent-Skills-Toolchain", "collides_with": "agent-skills-toolchain"}
  ],
  "confusable": [
    {"name": "\u0430gent-skills-toolchain", "collides_with": "agent-skills-toolchain"}
  ],
  "punctuation": ["-leading", "trailing-", "bad_name!", "has space"]
}
''',
    )
    w(
        "tools/marketplace/name_grammar.py",
        r'''"""Package identity grammar with reserved, casefold, and confusable guards."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

RESERVED = frozenset({"com", "org", "net", "www", "marketplace", "plugin", "admin"})
GRAMMAR = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Cyrillic a and Greek omicron map onto Latin lookalikes.
_CONFUSABLES = str.maketrans({"\u0430": "a", "\u03bf": "o", "\u03a9": "w"})


@dataclass
class NameVerdict:
    name: str
    accepted: bool
    code: str
    collides_with: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _fold(name: str) -> str:
    nfkc = unicodedata.normalize("NFKC", name)
    mapped = nfkc.translate(_CONFUSABLES)
    return mapped.casefold()


def validate_name(name: str, existing: Iterable[str] | None = None) -> NameVerdict:
    existing = list(existing or [])
    folded_existing = {_fold(x): x for x in existing}
    if name.casefold() in RESERVED or name.lower() in RESERVED:
        return NameVerdict(name, False, "reserved")
    if not GRAMMAR.match(name):
        return NameVerdict(name, False, "grammar")
    folded = _fold(name)
    hit = folded_existing.get(folded)
    if hit is not None and hit != name:
        # Distinguish Latin casefold vs confusable (non-ascii in input).
        if any(ord(ch) > 127 for ch in name):
            return NameVerdict(name, False, "confusable_collision", hit)
        return NameVerdict(name, False, "casefold_collision", hit)
    return NameVerdict(name, True, "ok")


def load_index_names() -> list[str]:
    path = Path(__file__).resolve().parents[2] / ".claude-plugin" / "marketplace.json"
    if not path.is_file():
        return ["agent-skills-toolchain"]
    import json

    doc = json.loads(path.read_text(encoding="utf-8"))
    names = [doc.get("name")] if isinstance(doc.get("name"), str) else []
    for plug in doc.get("plugins") or []:
        if isinstance(plug, dict) and isinstance(plug.get("name"), str):
            names.append(plug["name"])
    return [n for n in names if n]


def sweep_index() -> dict:
    names = load_index_names()
    rows = [validate_name(n, names).to_dict() for n in names]
    return {"names": names, "rows": rows, "accepted": all(r["accepted"] for r in rows)}
''',
    )
    print("batch1 done")


if __name__ == "__main__":
    main()
