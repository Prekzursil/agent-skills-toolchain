"""Spec 3 — user-authored skill consolidation ANALYSIS (no deletions).

Distinguishes three kinds of multiplicity so a human can decide safely:
  - exact_duplicates : same SKILL.md content under >1 path (true redundancy)
  - name_collisions  : same skill name, DIFFERENT content (version drift / conflict)
  - description_issues: SKILL.md descriptions that won't auto-trigger well
                        (multi-line -> silently truncates to line 1; or missing).

Marketplace skills (plugin caches) are intentionally EXCLUDED — only user-authored
roots are analysed. Output is a proposal report; the caller never deletes anything.
"""

from __future__ import annotations
from typing import Any
import hashlib
import re
from pathlib import Path

_PLUGIN_MARKERS = ("plugins", "plugins-cache", "marketplace", ".plugin")
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+:")
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
# Detects a multi-line YAML value: a description line whose NEXT non-blank line
# begins with whitespace (YAML block scalar / folded continuation).
_MULTILINE_DESC_RE = re.compile(r"^(description:\s*.+)\n[ \t]+\S", re.MULTILINE)


def _is_marketplace(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(m in parts for m in _PLUGIN_MARKERS)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return ""


def _frontmatter_description(text: str) -> str | None:
    """Return the description value from YAML frontmatter, or None if absent.

    Returns a string with embedded '\\n' if the value is a multi-line YAML block
    scalar (indented continuation on next line), so callers can detect the issue.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    fm = text[: end if end != -1 else len(text)]
    # Detect multi-line first (indented continuation)
    ml = _MULTILINE_DESC_RE.search(fm)
    if ml:
        # Return first line + sentinel newline to signal multi-line
        m2 = _DESC_RE.search(fm)
        base = m2.group(1).strip() if m2 else ""
        return base + "\n<continuation>"
    m = _DESC_RE.search(fm)
    return m.group(1).strip() if m else None


def analyze_skills(roots: list[Path]) -> dict[str, Any]:
    skills: list[tuple[str, Path, str]] = []  # (name, path, content)
    for root in roots:
        if not root.is_dir():
            continue
        for sk in root.rglob("SKILL.md"):
            if _is_marketplace(sk):
                continue
            content = _read(sk)
            skills.append((sk.parent.name, sk, content))

    by_hash: dict[str, list[str]] = {}
    by_name: dict[str, list[tuple[str, str]]] = {}
    desc_issues: list[dict[str, Any]] = []
    for name, path, content in skills:
        h = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()
        by_hash.setdefault(h, []).append(str(path))
        by_name.setdefault(name, []).append((str(path), h))
        desc = _frontmatter_description(content)
        if desc is None:
            desc_issues.append(
                {"skill": name, "path": str(path), "issue": "no description"}
            )
        elif "\n" in desc or len(desc) > 1024:
            desc_issues.append(
                {
                    "skill": name,
                    "path": str(path),
                    "issue": "multi-line/over-long description (won't trigger reliably)",
                }
            )

    exact_dupes = [sorted(paths) for paths in by_hash.values() if len(paths) > 1]
    name_collisions = [
        {"name": n, "paths": [p for p, _ in entries]}
        for n, entries in by_name.items()
        if len({h for _, h in entries}) > 1  # same name, >1 distinct content
    ]
    return {
        "skills_scanned": len(skills),
        "unique_names": len(by_name),
        "exact_duplicate_groups": exact_dupes,
        "name_collisions": name_collisions,
        "description_issues": desc_issues,
    }


def render_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Skill Consolidation Analysis (Spec 3 — analysis only, no deletions)",
        "",
    ]
    lines.append(
        f"- Skills scanned (user-authored only): **{analysis['skills_scanned']}**"
    )
    lines.append(f"- Unique skill names: **{analysis['unique_names']}**")
    lines.append(
        f"- Exact-duplicate content groups: **{len(analysis['exact_duplicate_groups'])}**"
    )
    lines.append(
        f"- Name collisions (same name, different content): **{len(analysis['name_collisions'])}**"
    )
    lines.append(
        f"- Description-trigger issues: **{len(analysis['description_issues'])}**"
    )
    lines.append("")
    if analysis["name_collisions"]:
        lines.append(
            "## ⚠ Name collisions (resolve before merging — these are NOT safe to auto-dedupe)"
        )
        for c in analysis["name_collisions"][:50]:
            lines.append(f"- `{c['name']}`: " + " | ".join(c["paths"]))
        lines.append("")
    if analysis["description_issues"]:
        lines.append(
            "## Description fixes (Layer-1 win: 1-line trigger+exclusion+output)"
        )
        for d in analysis["description_issues"][:80]:
            lines.append(f"- `{d['skill']}` — {d['issue']}")
        lines.append("")
    lines.append(
        "> Exact-duplicate groups are listed in the JSON report. Many are the *intentional* "
        "cross-AI mirror (canonical repo ↔ ~/.agents/skills ↔ ~/.claude/skills) — verify before "
        "removing any. No file is deleted by this tool."
    )
    return "\n".join(lines)
