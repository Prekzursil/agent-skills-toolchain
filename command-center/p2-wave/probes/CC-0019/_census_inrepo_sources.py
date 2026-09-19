#!/usr/bin/env python3
"""CC-0019 impl: mechanical census of the in-repo source families.

Population substitution disclosure: the catalog-contracted corpus
(~/.claude/harness-restore-20260806/) is ABSENT (measured by probe1 and by the
independent reviewer, 3 signals). This census enumerates the in-repo families
that exist on disk, per the wave lead's re-scope instruction.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
OUT = PROBE_DIR / "source-census.json"

GLOBS = ("*.md", "*.json", "*.jsonl", "*.txt")

FAMILY_ROOTS: dict[str, list[str]] = {
    "findings": ["command-center/adversarial"],
    "option-cards": ["command-center/p2-next", "command-center/option-id"],
    "claims": ["command-center/slop-report"],
    "incidents": ["command-center/casualty", "command-center/events"],
    "sources": ["command-center/sources"],
}
EXTRA_FILES: dict[str, list[str]] = {
    "option-cards": ["command-center/OWNER-DECISIONS.md"],
}


def keep(family: str, rel: str) -> bool:
    """Family scoping rules, explicit so the census is reproducible."""
    name = rel.rsplit("/", 1)[-1].upper()
    if family == "option-cards":
        return (
            "OWNER-DECISION" in name
            or rel.startswith("command-center/option-id/")
            or rel == "COMMAND-CENTER/OWNER-DECISIONS.MD"
            or rel == "command-center/OWNER-DECISIONS.md"
        )
    return True


def enumerate_family(family: str) -> list[str]:
    files: list[Path] = []
    for root in FAMILY_ROOTS[family]:
        p = REPO / root
        if not p.is_dir():
            continue
        for g in GLOBS:
            files += [x for x in p.rglob(g) if x.is_file()]
    for rel in EXTRA_FILES.get(family, []):
        q = REPO / rel
        if q.is_file():
            files.append(q)
    rels = sorted(
        {
            f.relative_to(REPO).as_posix()
            for f in files
            if keep(family, f.relative_to(REPO).as_posix())
        }
    )
    return rels


def main() -> int:
    census: dict = {
        "probe": "CC-0019-inrepo-source-census",
        "repo_root": str(REPO),
        "population_note": (
            "in-repo families; catalog-contracted harness-restore corpus "
            "~/.claude/harness-restore-20260806/ remains ABSENT (probe1 + "
            "independent reviewer 2026-09-19)"
        ),
        "families": {},
        "totals": {},
        "missing_roots": [],
    }
    total_files = 0
    total_bytes = 0
    for family in FAMILY_ROOTS:
        rels = enumerate_family(family)
        rows = []
        fam_bytes = 0
        for rel in rels:
            sz = (REPO / rel).stat().st_size
            fam_bytes += sz
            rows.append({"path": rel, "bytes": sz})
        census["families"][family] = {
            "n_files": len(rels),
            "bytes": fam_bytes,
            "files": rows,
        }
        total_files += len(rels)
        total_bytes += fam_bytes
        big = sorted(rows, key=lambda r: -r["bytes"])[:5]
        print(
            f"{family:13s} files={len(rels):4d} bytes={fam_bytes:9d} "
            f"biggest={[(r['path'].rsplit('/', 1)[-1], r['bytes']) for r in big]}"
        )
    for root in sorted({r for rs in FAMILY_ROOTS.values() for r in rs}):
        if not (REPO / root).is_dir():
            census["missing_roots"].append(root)
    census["totals"] = {"files": total_files, "bytes": total_bytes}
    OUT.write_text(
        json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"TOTAL files={total_files} bytes={total_bytes}")
    print(f"census written: {OUT.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
