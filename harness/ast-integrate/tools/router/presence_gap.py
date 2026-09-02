"""Repo-versus-live capability presence-gap detector (IMP-0401).

Failure class FC-11329, "skill exists in repo but not in live skill
directory", made router-visible: the capability index is annotated so any id
the router could *select* but cannot *load* carries ``router_defect =
DEFECT_UNLOADABLE``.

The comparison is bidirectional.  ``repo_only`` and ``live_only`` are both
computed (``set(repo) - set(live)`` and the reverse) because a one-directional
check silently misses everything installed live that the repo no longer
ships.  ``one_directional_repo_minus_live`` is kept as the named mutant so a
probe can show it misses a planted live-only capability.

Capability ids are ``skill:<name>`` where ``<name>`` is the SKILL.md
frontmatter ``name`` (falling back to the parent directory name).  The
fixtures keep frontmatter name == directory name so an independent
directory-name enumerator must agree with ``detect``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "DEFECT_UNLOADABLE",
    "METHOD",
    "annotate_index",
    "capability_ids",
    "default_live_skill_roots",
    "default_repo_skill_root",
    "detect",
    "enumerate_root",
    "load_index_ids",
    "one_directional_repo_minus_live",
    "skill_id",
]

DEFECT_UNLOADABLE = "selectable-but-unloadable"
METHOD = (
    "bidirectional set difference of skill:<name> ids enumerated from SKILL.md "
    "frontmatter (repo roots vs live roots); index annotated with presence, "
    "loadable and router_defect"
)

PRESENCE_BOTH = "both"
PRESENCE_REPO_ONLY = "repo-only"
PRESENCE_LIVE_ONLY = "live-only"
PRESENCE_INDEX_ONLY = "index-only"

_FRONTMATTER_NAME = re.compile(r"^name:\s*['\"]?([^'\"\r\n#]+?)['\"]?\s*$", re.MULTILINE)


# -- enumeration -------------------------------------------------------------
def default_repo_skill_root(repo_root: Path | str) -> Path:
    """The repo's published skill root: ``.agents/skills`` when present, else ``skills``."""
    root = Path(repo_root)
    canonical = root / ".agents" / "skills"
    if canonical.is_dir():
        return canonical
    return root / "skills"


def default_live_skill_roots(home: Path | str | None = None) -> list[Path]:
    """Where a live agent loads skills from on this host."""
    base = Path(home) if home is not None else Path.home()
    return [base / ".claude" / "skills", base / ".agents" / "skills"]


def frontmatter_name(skill_md: Path) -> str | None:
    """``name`` from the YAML frontmatter of a SKILL.md, or None."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    block = text[3:end]
    match = _FRONTMATTER_NAME.search(block)
    if not match:
        return None
    name = match.group(1).strip()
    return name or None


def skill_id(skill_md: Path) -> str:
    """Capability id for one SKILL.md: ``skill:<frontmatter name | dir name>``."""
    name = frontmatter_name(skill_md) or skill_md.parent.name
    return f"skill:{name}"


def enumerate_root(root: Path | str) -> dict[str, Any]:
    """Enumerate one skill root: ids plus the stat facts a reader needs."""
    path = Path(root)
    row: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "skill_md_count": 0,
        "ids": [],
    }
    if not path.is_dir():
        return row
    ids: set[str] = set()
    count = 0
    for skill_md in sorted(path.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        if "__pycache__" in skill_md.parts or "node_modules" in skill_md.parts:
            continue
        count += 1
        ids.add(skill_id(skill_md))
    row["skill_md_count"] = count
    row["ids"] = sorted(ids)
    return row


def capability_ids(roots: Iterable[Path | str]) -> tuple[set[str], list[dict[str, Any]]]:
    """Union of ids over ``roots`` plus the per-root stat rows (ids omitted)."""
    ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for root in roots:
        row = enumerate_root(root)
        ids.update(row.pop("ids"))
        rows.append(row)
    return ids, rows


def load_index_ids(index: Path | str | dict[str, Any] | None) -> tuple[list[str], list[dict[str, Any]]]:
    """Indexed capability ids (ordered) and the raw capability rows."""
    if index is None:
        return [], []
    if isinstance(index, dict):
        doc = index
    else:
        path = Path(index)
        if not path.is_file():
            return [], []
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return [], []
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for cap in doc.get("capabilities") or []:
        if isinstance(cap, dict) and cap.get("capability_id"):
            cid = str(cap["capability_id"])
            rows.append(dict(cap))
        elif isinstance(cap, str) and cap:
            cid = cap
            rows.append({"capability_id": cid})
        else:
            continue
        if cid not in ids:
            ids.append(cid)
    return ids, rows


# -- comparison --------------------------------------------------------------
def one_directional_repo_minus_live(repo_ids: Iterable[str], live_ids: Iterable[str]) -> list[str]:
    """The mutant: repo minus live only.  Misses every live-only capability."""
    return sorted(set(repo_ids) - set(live_ids))


def annotate_index(
    index_rows: list[dict[str, Any]],
    repo_ids: set[str],
    live_ids: set[str],
) -> dict[str, Any]:
    """Annotate each indexed capability with presence / loadable / router_defect.

    A capability is loadable iff it is present in a live root.  Anything the
    index offers that is not loadable is a router-visible defect.
    """
    capabilities: list[dict[str, Any]] = []
    repo_only: list[str] = []
    live_only: list[str] = []
    both: list[str] = []
    index_only: list[str] = []
    unloadable: list[str] = []
    for raw in index_rows:
        cid = str(raw.get("capability_id") or "")
        if not cid:
            continue
        in_repo = cid in repo_ids
        in_live = cid in live_ids
        if in_repo and in_live:
            presence = PRESENCE_BOTH
            both.append(cid)
        elif in_repo:
            presence = PRESENCE_REPO_ONLY
            repo_only.append(cid)
        elif in_live:
            presence = PRESENCE_LIVE_ONLY
            live_only.append(cid)
        else:
            presence = PRESENCE_INDEX_ONLY
            index_only.append(cid)
        loadable = in_live
        row = dict(raw)
        row["capability_id"] = cid
        row["presence"] = presence
        row["in_repo"] = in_repo
        row["in_live"] = in_live
        row["loadable"] = loadable
        row["router_defect"] = None if loadable else DEFECT_UNLOADABLE
        if not loadable:
            unloadable.append(cid)
        capabilities.append(row)
    return {
        "capabilities": capabilities,
        "presence_gap": {
            "defect": DEFECT_UNLOADABLE,
            "repo_only": sorted(repo_only),
            "live_only": sorted(live_only),
            "both": sorted(both),
            "index_only": sorted(index_only),
            "selectable_but_unloadable": sorted(unloadable),
            "repo_only_count": len(repo_only),
            "live_only_count": len(live_only),
            "both_count": len(both),
            "index_only_count": len(index_only),
            "selectable_but_unloadable_count": len(unloadable),
        },
    }


def detect(
    repo_roots: Iterable[Path | str],
    live_roots: Iterable[Path | str],
    index: Path | str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bidirectional presence gap between repo and live skill roots.

    ``index`` is the capability index to annotate.  When it is None the
    detector annotates the enumerated union (every id the router could see
    from either side) so the host answer is still well-formed.
    """
    repo_ids, repo_rows = capability_ids(repo_roots)
    live_ids, live_rows = capability_ids(live_roots)

    repo_only = sorted(repo_ids - live_ids)
    live_only = sorted(live_ids - repo_ids)
    both = sorted(repo_ids & live_ids)
    overlap_illegal = sorted(set(repo_only) & set(live_only))

    index_ids, index_rows = load_index_ids(index)
    index_source = "capability-index"
    if not index_rows:
        index_source = "enumerated-union (no index supplied)"
        index_ids = sorted(repo_ids | live_ids)
        index_rows = [{"capability_id": cid, "kind": "skill"} for cid in index_ids]
    annotated = annotate_index(index_rows, repo_ids, live_ids)
    gap = annotated["presence_gap"]

    return {
        "method": METHOD,
        "defect": DEFECT_UNLOADABLE,
        "repo_only": repo_only,
        "live_only": live_only,
        "both": both,
        "repo_only_count": len(repo_only),
        "live_only_count": len(live_only),
        "both_count": len(both),
        "disjoint": not overlap_illegal,
        "overlap_illegal": overlap_illegal,
        "repo_roots": repo_rows,
        "live_roots": live_rows,
        "repo_count": len(repo_ids),
        "live_count": len(live_ids),
        "indexed": {
            "source": index_source,
            "count": len(index_ids),
            "ids": list(index_ids),
            "repo_only": gap["repo_only"],
            "live_only": gap["live_only"],
            "both": gap["both"],
            "index_only": gap["index_only"],
            "repo_only_count": gap["repo_only_count"],
            "live_only_count": gap["live_only_count"],
            "both_count": gap["both_count"],
            "index_only_count": gap["index_only_count"],
            "selectable_but_unloadable": gap["selectable_but_unloadable"],
            "selectable_but_unloadable_count": gap["selectable_but_unloadable_count"],
        },
        "annotated_index": annotated,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="repo-vs-live skill presence gap")
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--live", action="append", default=None, help="live skill root (repeatable)")
    parser.add_argument("--index", default=None, help="capability-index.json to annotate")
    args = parser.parse_args(argv)
    live = [Path(p) for p in args.live] if args.live else default_live_skill_roots()
    report = detect([default_repo_skill_root(args.repo_root)], live, index=args.index)
    report.pop("annotated_index", None)
    json.dump(report, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
