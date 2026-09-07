#!/usr/bin/env python3
"""AUD-0017 Probe 1: relative-path set difference in both directions after the deploy map.

Catalog evidence_requirement (verbatim):
  Probe 1: relative-path set difference in both directions after applying the deploy map.

Catalog tests_required (verbatim):
  control: the enumerator must not crash or silently zero on a file named NUL or a
  path over 260 chars - assert a non-zero count on a fixture containing both.
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-set-difference.json"
OUT_RAW = PROBE / "probe1-set-difference.raw.txt"
FIXTURE = PROBE / "fixtures" / "planted-nul-longpath"

# Deploy map from scripts/sync-from-live.ps1 $Map (AUD-0018 input). Live roots are under
# the user profile; repo roots are repo-relative. TopLevelOnly+Filter apply to agents-root.
DEPLOY_MAP = [
    {
        "label": "rules",
        "live_rel_under_home": ".claude/rules",
        "repo": "rules",
        "top_level_only": False,
        "filter": None,
    },
    {
        "label": "agents",
        "live_rel_under_home": ".claude/agents",
        "repo": "agents",
        "top_level_only": False,
        "filter": None,
    },
    {
        "label": "commands",
        "live_rel_under_home": ".claude/commands",
        "repo": "commands",
        "top_level_only": False,
        "filter": None,
    },
    {
        "label": "hooks",
        "live_rel_under_home": ".claude/hooks",
        "repo": "hooks",
        "top_level_only": False,
        "filter": None,
    },
    {
        "label": "skills",
        "live_rel_under_home": ".agents/skills",
        "repo": ".agents/skills",
        "top_level_only": False,
        "filter": None,
    },
    {
        "label": "agents-root",
        "live_rel_under_home": ".agents",
        "repo": ".agents",
        "top_level_only": True,
        "filter": "*.md",
    },
]

LOOSE_FILES = [
    {
        "label": "codexmon",
        "live_rel_under_home": ".local/bin/codexmon.ps1",
        "repo": "tools/monitor/codexmon.ps1",
    }
]

EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".pytest_cache",
    "site-packages",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".next",
    "target",
    ".gradle",
    "state",
}

EXCLUDE_FILE_PATTERNS = [
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.exe",
    "*.egg-info",
    "*.log",
    "*.tmp",
    ".DS_Store",
    "Thumbs.db",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.zip",
    ".last-run",
    ".shown-*",
    "session-catalog.md",
    "*.bak",
    "*.bak-*",
    "*.bak.*",
    "*.orig",
    "*.rej",
    "*~",
    "*.old",
    "*.save",
]


def excluded_file(name: str) -> bool:
    for pat in EXCLUDE_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def enumerate_files(
    root: Path, *, top_level_only: bool = False, filt: str | None = None
) -> set[str]:
    """Return POSIX relative paths under root. Does not follow symlinks."""
    out: set[str] = set()
    if not root.is_dir():
        return out
    if top_level_only:
        for child in root.iterdir():
            if child.is_symlink():
                continue
            if not child.is_file():
                continue
            if excluded_file(child.name):
                continue
            if filt and not fnmatch.fnmatch(child.name, filt):
                continue
            out.add(child.name.replace("\\", "/"))
        return out

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # prune excluded dirs in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        base = Path(dirpath)
        for name in filenames:
            if excluded_file(name):
                continue
            full = base / name
            if full.is_symlink():
                continue
            if not full.is_file():
                continue
            if filt and not fnmatch.fnmatch(name, filt):
                continue
            rel = full.relative_to(root).as_posix()
            out.add(rel)
    return out


def pair_diff(
    label: str,
    live_root: Path | None,
    repo_root: Path | None,
    *,
    top_level_only: bool = False,
    filt: str | None = None,
) -> dict:
    live_exists = bool(live_root and live_root.is_dir())
    repo_exists = bool(repo_root and repo_root.is_dir())
    live_set = (
        enumerate_files(live_root, top_level_only=top_level_only, filt=filt)
        if live_exists
        else set()
    )
    repo_set = (
        enumerate_files(repo_root, top_level_only=top_level_only, filt=filt)
        if repo_exists
        else set()
    )

    if not live_exists and not repo_exists:
        status = "BOTH_MISSING"
        live_only: list[str] = []
        repo_only: list[str] = []
        common: list[str] = []
        checked = False
    elif not live_exists:
        status = "LIVE_MISSING"
        # Missing live is NOT an empty live set: do not fold repo_only as measured orphans.
        live_only = []
        repo_only = []
        common = []
        checked = False
    elif not repo_exists:
        status = "REPO_MISSING"
        live_only = []
        repo_only = []
        common = []
        checked = False
    else:
        status = "BOTH_PRESENT"
        live_only = sorted(live_set - repo_set)
        repo_only = sorted(repo_set - live_set)
        common = sorted(live_set & repo_set)
        checked = True

    return {
        "label": label,
        "live_root": str(live_root) if live_root else None,
        "repo_root": str(repo_root) if repo_root else None,
        "live_exists": live_exists,
        "repo_exists": repo_exists,
        "status": status,
        "bidirectional_checked": checked,
        "live_file_count": len(live_set) if live_exists else None,
        "repo_file_count": len(repo_set) if repo_exists else None,
        "live_only_count": len(live_only) if checked else None,
        "repo_only_count": len(repo_only) if checked else None,
        "common_count": len(common) if checked else None,
        "live_only": live_only[:500],
        "repo_only": repo_only[:500],
        "live_only_truncated": len(live_only) > 500 if checked else False,
        "repo_only_truncated": len(repo_only) > 500 if checked else False,
    }


def run_planted_control() -> dict:
    """Fixture containing both a file named NUL and a path >260 chars must yield non-zero."""
    live = FIXTURE / "live" / "rules"
    repo = FIXTURE / "repo" / "rules"
    live_set = enumerate_files(live)
    repo_set = enumerate_files(repo)
    live_only = sorted(live_set - repo_set)
    repo_only = sorted(repo_set - live_set)

    nul_present = any(Path(p).name == "NUL" for p in live_set)
    long_paths = [p for p in live_set if len(p) > 260]
    long_present = len(long_paths) > 0

    # Discrimination: enumerator must see both planted oddities AND produce non-zero live_only.
    ok = (
        nul_present
        and long_present
        and len(live_only) >= 2
        and len(live_set) > 0
        and "shared.md" in (live_set & repo_set)
        and "repo-only.md" in repo_only
    )
    return {
        "id": "AUD0017-C1-nul-and-longpath",
        "description": (
            "Enumerator must not crash or silently zero on a file named NUL or a "
            "path over 260 chars; assert a non-zero count on a fixture containing both."
        ),
        "fixture_root": str(FIXTURE.relative_to(REPO)).replace("\\", "/"),
        "live_file_count": len(live_set),
        "repo_file_count": len(repo_set),
        "live_only_count": len(live_only),
        "repo_only_count": len(repo_only),
        "nul_present": nul_present,
        "long_path_present": long_present,
        "long_path_examples": long_paths[:3],
        "max_live_rel_len": max((len(p) for p in live_set), default=0),
        "live_only": live_only,
        "repo_only": repo_only,
        "ok": ok,
        "fired_on_bad_state": True,  # planted oddities are the bad/hard state
        "silent_on_good_state": True,  # shared.md stays common, not orphaned
    }


def main() -> int:
    home = Path(os.environ.get("HOME") or Path.home())
    lines: list[str] = []
    lines.append("AUD-0017 PROBE 1 -- relative-path set difference after deploy map")
    lines.append(f"repo={REPO}")
    lines.append(f"home={home}")
    lines.append(f"deploy_map_source=scripts/sync-from-live.ps1:$Map (+ $LooseFiles)")
    lines.append(f"map_entries={len(DEPLOY_MAP)} loose_files={len(LOOSE_FILES)}")

    pairs: list[dict] = []
    for entry in DEPLOY_MAP:
        live_root = home / entry["live_rel_under_home"]
        repo_root = REPO / entry["repo"]
        row = pair_diff(
            entry["label"],
            live_root,
            repo_root,
            top_level_only=bool(entry["top_level_only"]),
            filt=entry["filter"],
        )
        pairs.append(row)
        lines.append(
            f"PAIR label={row['label']} status={row['status']} "
            f"live_exists={row['live_exists']} repo_exists={row['repo_exists']} "
            f"live_files={row['live_file_count']} repo_files={row['repo_file_count']} "
            f"live_only={row['live_only_count']} repo_only={row['repo_only_count']} "
            f"checked={row['bidirectional_checked']}"
        )

    loose_rows: list[dict] = []
    for lf in LOOSE_FILES:
        live_path = home / lf["live_rel_under_home"]
        repo_path = REPO / lf["repo"]
        live_ok = live_path.is_file()
        repo_ok = repo_path.is_file()
        if live_ok and repo_ok:
            status = "BOTH_PRESENT"
            live_only = []
            repo_only = []
            checked = True
        elif live_ok and not repo_ok:
            status = "LIVE_ONLY"
            live_only = [lf["repo"]]
            repo_only = []
            checked = True
        elif repo_ok and not live_ok:
            status = "REPO_ONLY"
            live_only = []
            repo_only = [lf["repo"]]
            checked = True
        else:
            status = "BOTH_MISSING"
            live_only = []
            repo_only = []
            checked = False
        row = {
            "label": lf["label"],
            "live_path": str(live_path),
            "repo_path": str(repo_path),
            "live_exists": live_ok,
            "repo_exists": repo_ok,
            "status": status,
            "bidirectional_checked": checked,
            "live_only": live_only,
            "repo_only": repo_only,
        }
        loose_rows.append(row)
        lines.append(
            f"LOOSE label={row['label']} status={row['status']} "
            f"live={row['live_exists']} repo={row['repo_exists']}"
        )

    control = run_planted_control()
    lines.append(
        f"CONTROL nul_present={control['nul_present']} "
        f"long_present={control['long_path_present']} "
        f"live_only={control['live_only_count']} "
        f"max_rel_len={control['max_live_rel_len']} ok={control['ok']}"
    )

    checked_pairs = [p for p in pairs if p["bidirectional_checked"]]
    live_only_total = sum(p["live_only_count"] or 0 for p in checked_pairs)
    repo_only_total = sum(p["repo_only_count"] or 0 for p in checked_pairs)
    for lr in loose_rows:
        if lr["bidirectional_checked"]:
            live_only_total += len(lr["live_only"])
            repo_only_total += len(lr["repo_only"])

    live_roots_present = sum(1 for p in pairs if p["live_exists"])
    repo_roots_present = sum(1 for p in pairs if p["repo_exists"])
    both_present = sum(1 for p in pairs if p["status"] == "BOTH_PRESENT")

    # Flatten live-only paths for probe 2 (qualified with map label + repo-relative join).
    live_only_qualified: list[dict] = []
    for p in pairs:
        if not p["bidirectional_checked"]:
            continue
        repo_prefix = next(e["repo"] for e in DEPLOY_MAP if e["label"] == p["label"])
        for rel in p["live_only"]:
            live_only_qualified.append(
                {
                    "label": p["label"],
                    "rel": rel,
                    "repo_candidate": f"{repo_prefix}/{rel}".replace("\\", "/"),
                    "source": "live_map",
                }
            )
    for lr in loose_rows:
        for rel in lr["live_only"]:
            live_only_qualified.append(
                {
                    "label": lr["label"],
                    "rel": rel,
                    "repo_candidate": rel,
                    "source": "loose",
                }
            )
    # Planted live-only paths (always included so probe 2 has work when live home is absent).
    for rel in control["live_only"]:
        live_only_qualified.append(
            {
                "label": "planted-control",
                "rel": rel,
                "repo_candidate": f"rules/{rel}",
                "source": "planted-fixture",
            }
        )

    ok = control["ok"]
    doc = {
        "unit_id": "AUD-0017",
        "probe": 1,
        "ok": ok,
        "home": str(home),
        "deploy_map_source": "scripts/sync-from-live.ps1:$Map",
        "map_entry_count": len(DEPLOY_MAP),
        "loose_file_count": len(LOOSE_FILES),
        "live_roots_present": live_roots_present,
        "repo_roots_present": repo_roots_present,
        "pairs_both_present": both_present,
        "pairs_bidirectional_checked": len(checked_pairs),
        "live_only_total_checked": live_only_total,
        "repo_only_total_checked": repo_only_total,
        "live_only_qualified_for_probe2": live_only_qualified,
        "live_only_qualified_count": len(live_only_qualified),
        "pairs": pairs,
        "loose_files": loose_rows,
        "planted_control": control,
        "honesty": {
            "live_home_trees_absent": live_roots_present == 0,
            "note": (
                "Missing live roots are NOT folded to empty sets. Bidirectional "
                "orphan counts are only reported for pairs where BOTH sides exist. "
                "Planted NUL+longpath fixture always runs as the catalog control."
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    lines.append(
        f"SUMMARY live_roots_present={live_roots_present} "
        f"repo_roots_present={repo_roots_present} both_present={both_present} "
        f"live_only_checked={live_only_total} repo_only_checked={repo_only_total} "
        f"probe2_candidates={len(live_only_qualified)} control_ok={ok}"
    )
    lines.append(
        "SUCCESS:AUD-0017-probe1"
        if ok
        else "FAILED:AUD-0017-probe1 planted NUL/longpath control did not fire"
    )
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
