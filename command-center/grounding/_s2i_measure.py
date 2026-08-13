"""Measure the repo-side skill description surface BEFORE proposing any gate.

Load-bearing question: would a description-health gate be RED at HEAD?  If it
would, adding it as a blocking CI step red-blocks main and every sibling PR --
the exact failure the ground floor names.  So measure first, design second.

Reads the two repo skill roots ONLY (no live trees, no ~).  Parses frontmatter
the same way ci/check_skill_context_budget.py does, so the numbers are
comparable to the gate that already exists for the DAILY tier.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = {
    "canonical(.agents/skills)": REPO / ".agents" / "skills",
    "projection(skills)": REPO / "skills",
}
SPEC_MAX = 1024
FOLD_TOKENS = {"|", ">", "|-", ">-", "|+", ">+"}


def parse(path: Path) -> dict:
    """Return name/description/shape for one SKILL.md, or a reason it failed."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {"error": "no-frontmatter"}
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {"error": "unclosed-frontmatter"}

    fm = lines[1:end]
    name = ""
    desc = ""
    folded = False
    for idx, line in enumerate(fm):
        key, sep, value = line.partition(":")
        if not sep or key not in {"name", "description"}:
            continue
        value = value.strip()
        if key == "name":
            name = value.strip("\"'")
            continue
        # Folded/literal block scalar, or a continuation line -> multi-line.
        if value in FOLD_TOKENS:
            folded = True
            desc = ""
            j = idx + 1
            while j < len(fm) and (fm[j][:1].isspace() or not fm[j].strip()):
                desc += fm[j].strip() + " "
                j += 1
            desc = desc.strip()
            continue
        if idx + 1 < len(fm) and fm[idx + 1][:1].isspace():
            folded = True
            desc = value.strip("\"'")
            j = idx + 1
            while j < len(fm) and fm[j][:1].isspace():
                desc += " " + fm[j].strip()
                j += 1
            continue
        desc = value.strip("\"'")

    if not name or not desc:
        return {"error": "missing-name-or-description"}
    return {"name": name, "desc": desc, "folded": folded, "len": len(desc)}


def main() -> int:
    out: dict[str, object] = {}
    for label, root in ROOTS.items():
        if not root.is_dir():
            out[label] = {"error": "root missing"}
            continue
        skills = sorted(p for p in root.glob("*/SKILL.md") if p.is_file())
        rows = []
        errors = []
        for p in skills:
            r = parse(p)
            r["path"] = p.relative_to(REPO).as_posix()
            if "error" in r:
                errors.append(r)
            else:
                rows.append(r)
        over = sorted(
            (r for r in rows if r["len"] > SPEC_MAX),
            key=lambda r: -r["len"],
        )
        folded = sorted(r["name"] for r in rows if r["folded"])
        total = sum(r["len"] for r in rows)
        out[label] = {
            "skill_dirs": len(skills),
            "parsed": len(rows),
            "parse_errors": errors,
            "description_chars_total": total,
            "over_1024_count": len(over),
            "over_1024": [(r["name"], r["len"]) for r in over],
            "folded_count": len(folded),
            "folded": folded,
            "max_len": max((r["len"] for r in rows), default=0),
        }

    print(json.dumps(out, indent=2, sort_keys=True))
    for label, data in out.items():
        if not isinstance(data, dict) or "skill_dirs" not in data:
            continue
        print(
            f"\n{label}: dirs={data['skill_dirs']} parsed={data['parsed']} "
            f"errors={len(data['parse_errors'])} "
            f"total={data['description_chars_total']} "
            f"over1024={data['over_1024_count']} folded={data['folded_count']} "
            f"max={data['max_len']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
