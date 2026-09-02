#!/usr/bin/env python3
"""Parse the required library taxonomy from spec text. No total constant."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FAMILY_LINE = re.compile(r"^([a-z0-9-]+/[a-z0-9-]+)\s+(\d+)\s*$")
HEADING = re.compile(r"^###\s+([a-z0-9-]+/[a-z0-9-]+)\s*$")
LEAF = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)\s*$")

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "fixtures" / "spec_taxonomy.md"


@dataclass(frozen=True)
class Family:
    id: str
    declared_count: int
    leaves: tuple[str, ...]

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)


@dataclass
class Taxonomy:
    families: tuple[Family, ...]
    source_path: str
    inconsistencies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ids(self) -> tuple[str, ...]:
        out: list[str] = []
        for fam in self.families:
            out.extend(fam.leaves)
        return tuple(out)

    @property
    def leaf_total(self) -> int:
        return sum(fam.leaf_count for fam in self.families)

    @property
    def declared_total(self) -> int:
        return sum(fam.declared_count for fam in self.families)

    def as_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "leaf_total": self.leaf_total,
            "declared_total": self.declared_total,
            "consistent": not self.inconsistencies,
            "inconsistencies": list(self.inconsistencies),
            "families": [
                {
                    "id": f.id,
                    "declared_count": f.declared_count,
                    "leaf_count": f.leaf_count,
                    "leaves": list(f.leaves),
                }
                for f in self.families
            ],
            "ids": list(self.ids),
        }


def parse_spec(text: str, *, source_path: str = "<string>") -> Taxonomy:
    """Recount families and leaves from spec text. Totals are derived, never a constant."""
    declared: dict[str, int] = {}
    order: list[str] = []
    leaves_by: dict[str, list[str]] = {}
    current: str | None = None
    seen_leaf: set[str] = set()
    problems: list[str] = []

    for raw in text.splitlines():
        line = raw.rstrip()
        hm = HEADING.match(line)
        if hm:
            current = hm.group(1)
            leaves_by.setdefault(current, [])
            if current not in order and current not in declared:
                order.append(current)
            continue
        fm = FAMILY_LINE.match(line)
        if fm:
            fam, n = fm.group(1), int(fm.group(2))
            if fam in declared:
                problems.append(f"duplicate-family-header:{fam}")
            declared[fam] = n
            if fam not in order:
                order.append(fam)
            leaves_by.setdefault(fam, [])
            continue
        lm = LEAF.match(line)
        if lm:
            slug = lm.group(1)
            if current is None:
                problems.append(f"leaf-before-heading:{slug}")
                continue
            if slug in seen_leaf:
                problems.append(f"duplicate-leaf:{slug}")
                continue
            seen_leaf.add(slug)
            leaves_by.setdefault(current, []).append(slug)

    families: list[Family] = []
    for fam_id in order:
        leaves = tuple(leaves_by.get(fam_id, []))
        declared_n = declared.get(fam_id)
        if declared_n is None:
            problems.append(f"heading-without-declared-count:{fam_id}")
            declared_n = 0
        if declared_n != len(leaves):
            problems.append(
                f"count-mismatch:{fam_id}:declared={declared_n}:leaves={len(leaves)}"
            )
        families.append(Family(id=fam_id, declared_count=declared_n, leaves=leaves))

    for fam_id in declared:
        if fam_id not in leaves_by or (
            not leaves_by[fam_id] and fam_id not in {f.id for f in families}
        ):
            if fam_id not in order:
                problems.append(f"declared-family-without-heading:{fam_id}")

    return Taxonomy(
        families=tuple(families),
        source_path=source_path,
        inconsistencies=tuple(problems),
    )


def load_spec(path: Path | None = None) -> Taxonomy:
    p = path or DEFAULT_SPEC
    return parse_spec(p.read_text(encoding="utf-8"), source_path=str(p))


if __name__ == "__main__":
    tax = load_spec()
    print(
        f"families={len(tax.families)} leaf_total={tax.leaf_total} "
        f"declared_total={tax.declared_total} consistent={not tax.inconsistencies}"
    )
    for fam in tax.families:
        print(f"  {fam.id} declared={fam.declared_count} leaves={fam.leaf_count}")
    if tax.inconsistencies:
        raise SystemExit(1)
    raise SystemExit(0)
