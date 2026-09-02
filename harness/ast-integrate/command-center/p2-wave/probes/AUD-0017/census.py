"""Bidirectional relative-path set difference after the deploy map."""
from __future__ import annotations

from pathlib import Path

from deploy_map import ENTRIES, LOOSE_FILES, UNMAPPED_REPO_RELS, kind_roots
from enumerator import iter_files


def _union_live(live_dirs: list[Path]) -> dict[str, list[str]]:
    """rel -> list of absolute locations (same rel may exist in two live trees)."""
    found: dict[str, list[str]] = {}
    for d in live_dirs:
        for rel, path in iter_files(d).items():
            found.setdefault(rel, []).append(str(path))
    return found


def census_one_kind(kind: str, repo_dir: Path, live_dirs: list[Path]) -> dict:
    repo_files = iter_files(repo_dir)
    live_files = _union_live(live_dirs)
    repo_keys = set(repo_files)
    live_keys = set(live_files)
    live_only = sorted(live_keys - repo_keys)
    repo_only = sorted(repo_keys - live_keys)
    both = sorted(repo_keys & live_keys)
    return {
        "kind": kind,
        "mode": "tree",
        "repo_dir": str(repo_dir),
        "repo_exists": repo_dir.is_dir(),
        "live_dirs": [str(p) for p in live_dirs],
        "live_dir_exists": [p.is_dir() for p in live_dirs],
        "repo_count": len(repo_keys),
        "live_count": len(live_keys),
        "live_only": [
            {"rel": rel, "locations": live_files[rel], "map_key": f"{kind}/{rel}"}
            for rel in live_only
        ],
        "repo_only": [
            {
                "rel": rel,
                "location": str(repo_files[rel]),
                "map_key": f"{kind}/{rel}",
            }
            for rel in repo_only
        ],
        "both_count": len(both),
    }


def census_one_file(kind: str, repo_file: Path, live_file: Path, map_rel: str) -> dict:
    repo_ok = repo_file.is_file()
    live_ok = live_file.is_file()
    live_only = []
    repo_only = []
    if live_ok and not repo_ok:
        live_only.append(
            {
                "rel": map_rel,
                "locations": [str(live_file)],
                "map_key": f"{kind}/{map_rel}",
            }
        )
    if repo_ok and not live_ok:
        repo_only.append(
            {
                "rel": map_rel,
                "location": str(repo_file),
                "map_key": f"{kind}/{map_rel}",
            }
        )
    return {
        "kind": kind,
        "mode": "file",
        "repo_dir": str(repo_file),
        "repo_exists": repo_ok,
        "live_dirs": [str(live_file)],
        "live_dir_exists": [live_ok],
        "repo_count": int(repo_ok),
        "live_count": int(live_ok),
        "live_only": live_only,
        "repo_only": repo_only,
        "both_count": int(repo_ok and live_ok),
    }


def census(repo: Path, live_home: Path, fixture: dict | None = None) -> dict:
    r = Path(fixture["repo"]) if fixture else repo
    h = Path(fixture["live_home"]) if fixture else live_home
    kinds = []
    live_only: list[dict] = []
    repo_only: list[dict] = []
    for ent in ENTRIES:
        row = census_one_kind(
            ent["kind"],
            r / ent["repo_rel"],
            [h / rel for rel in ent["live_rels"]],
        )
        kinds.append(row)
        live_only.extend(row["live_only"])
        repo_only.extend(row["repo_only"])
    if fixture is None:
        for ent in LOOSE_FILES:
            row = census_one_file(
                ent["kind"],
                r / ent["repo_rel"],
                h / ent["live_rel"],
                ent["repo_rel"],
            )
            kinds.append(row)
            live_only.extend(row["live_only"])
            repo_only.extend(row["repo_only"])
    unmapped = []
    for rel in UNMAPPED_REPO_RELS:
        p = r / rel
        unmapped.append(
            {
                "repo_rel": rel,
                "exists": p.is_dir(),
                "file_count": len(iter_files(p)) if p.is_dir() else 0,
                "note": "present on disk; not in AUD-0018 $Map; not folded into the orphan sets",
            }
        )
    return {
        "scope": "fixture" if fixture else "host",
        "repo_root": str(r),
        "live_home": str(h),
        "kinds": kinds,
        "live_only": live_only,
        "repo_only": repo_only,
        "unmapped_repo_trees": unmapped if fixture is None else [],
        "counts": {
            "live_only": len(live_only),
            "repo_only": len(repo_only),
            "kinds": len(kinds),
        },
        "map_rows": kind_roots(repo, live_home, fixture=fixture),
    }
